"""Single-task text classification training with EgyBERT (Phase 2).

Trains four independent classifiers (one per field) on train, evaluates on validation,
and outputs prediction files and run records in Aya's infra format.
"""
import json
import logging
from pathlib import Path
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Dataset, WeightedRandomSampler
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    get_linear_schedule_with_warmup,
)

from infra.experiment_config import ExperimentConfig
from infra.harness import evaluate_predictions
from infra.predictions_file import (
    predictions_path,
    read_predictions_file,
    write_predictions_file,
)
from infra.run_record import (
    build_run_record,
    make_seed_result,
    save_run_record,
)
from infra.seeds import set_global_seed
from infra.shared_config import load_shared_config

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

UNCLEAR_REASON = (
    "unclear has 0 rows in train (1 in val, 0 in test), so the model never trains on it; "
    "excluded from customer_state macro-F1 only (Hazem's decision)."
)
EXCLUSIONS = {
    "customer_state": {
        "labels": ["unclear"],
        "reason": UNCLEAR_REASON,
    }
}


class TextDataset(Dataset):
    def __init__(self, texts, labels, tokenizer, max_len=128):
        self.encodings = tokenizer(
            texts,
            padding=True,
            truncation=True,
            max_length=max_len,
            return_tensors="pt",
        )
        self.labels = torch.tensor(labels, dtype=torch.long)

    def __len__(self):
        return len(self.labels)

    def __getitem__(self, idx):
        item = {key: val[idx] for key, val in self.encodings.items()}
        item["labels"] = self.labels[idx]
        return item


def train_single_field(
    field_name,
    classes,
    class_weights,
    train_texts,
    train_labels_str,
    val_texts,
    val_labels_str,
    tokenizer,
    device,
    seed,
    lr=3e-5,
    batch_size=16,
    max_epochs=5,
    patience=2,
):
    set_global_seed(seed)
    class_to_idx = {c: i for i, c in enumerate(classes)}
    train_labels = [class_to_idx[l] for l in train_labels_str]
    train_dataset = TextDataset(train_texts, train_labels, tokenizer)

    # Use WeightedRandomSampler for extreme minority class in churn_risk
    if field_name == "churn_risk":
        class_counts = [len([l for l in train_labels if l == i]) for i in range(len(classes))]
        sample_weights = [1.0 / max(1, class_counts[l]) for l in train_labels]
        sampler = WeightedRandomSampler(
            weights=sample_weights,
            num_samples=len(train_labels),
            replacement=True,
        )
        train_loader = DataLoader(train_dataset, batch_size=batch_size, sampler=sampler)
        loss_fn = nn.CrossEntropyLoss()
    else:
        train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
        w_tensor = torch.tensor(
            [class_weights[c] for c in classes],
            dtype=torch.float,
            device=device,
        )
        loss_fn = nn.CrossEntropyLoss(weight=w_tensor)

    # Prepare validation loader for all val rows
    val_labels_clean = [class_to_idx.get(l, 0) for l in val_labels_str]
    val_dataset = TextDataset(val_texts, val_labels_clean, tokenizer)
    val_loader = DataLoader(val_dataset, batch_size=32, shuffle=False)

    model = AutoModelForSequenceClassification.from_pretrained(
        "faisalq/EgyBERT",
        num_labels=len(classes),
    )
    model.to(device)

    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=0.01)
    total_steps = len(train_loader) * max_epochs
    scheduler = get_linear_schedule_with_warmup(
        optimizer,
        num_warmup_steps=int(total_steps * 0.1),
        num_training_steps=total_steps,
    )
    scaler = torch.amp.GradScaler("cuda")

    best_macro_f1 = -1.0
    best_val_probs = None
    patience_counter = 0

    # Build mask for validation scoring if field has excluded labels
    if field_name == "customer_state":
        eval_mask = [l != "unclear" for l in val_labels_str]
    else:
        eval_mask = [True] * len(val_labels_str)

    eval_true = [val_labels_str[i] for i, m in enumerate(eval_mask) if m]

    for epoch in range(max_epochs):
        model.train()
        for batch in train_loader:
            optimizer.zero_grad()
            input_ids = batch["input_ids"].to(device)
            attention_mask = batch["attention_mask"].to(device)
            labels = batch["labels"].to(device)
            with torch.amp.autocast("cuda"):
                outputs = model(input_ids=input_ids, attention_mask=attention_mask)
                loss = loss_fn(outputs.logits, labels)
            scaler.scale(loss).backward()
            scaler.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            scaler.step(optimizer)
            scaler.update()
            scheduler.step()

        # Evaluate on validation
        model.eval()
        epoch_probs = []
        with torch.no_grad():
            for batch in val_loader:
                input_ids = batch["input_ids"].to(device)
                attention_mask = batch["attention_mask"].to(device)
                with torch.amp.autocast("cuda"):
                    outputs = model(input_ids=input_ids, attention_mask=attention_mask)
                    probs = torch.softmax(outputs.logits, dim=-1)
                epoch_probs.extend(probs.cpu().numpy().tolist())

        epoch_preds = [classes[int(np.argmax(p))] for p in epoch_probs]
        eval_preds = [epoch_preds[i] for i, m in enumerate(eval_mask) if m]

        # Calculate macro-F1 on scored validation rows
        from infra.metrics import evaluate_field
        rep = evaluate_field(eval_true, eval_preds, classes)
        current_macro_f1 = rep["macro"]["f1"]
        logger.info(
            f"[{field_name}] Seed {seed} Epoch {epoch + 1}: validation macro-F1 = {current_macro_f1:.4f}"
        )

        if current_macro_f1 > best_macro_f1:
            best_macro_f1 = current_macro_f1
            best_val_probs = epoch_probs
            patience_counter = 0
        else:
            patience_counter += 1
            if epoch >= 2 and patience_counter >= patience:
                logger.info(
                    f"[{field_name}] Seed {seed}: Early stopping at epoch {epoch + 1}"
                )
                break

    return best_val_probs, best_macro_f1


def run_experiment(
    run_id="001",
    runs_dir="runs",
    data_dir="../svr-data/final",
    shared_config_path="notebooks/training/shared_config.json",
):
    shared = load_shared_config(shared_config_path)
    weights_path = Path(data_dir) / "class_weights.json"
    weights_data = json.loads(weights_path.read_text(encoding="utf-8"))

    classes_by_field = {
        field: list(weights.keys())
        for field, weights in weights_data["weights"].items()
    }

    train_df = pd.read_csv(Path(data_dir) / "clean_training_train.csv")
    val_df = pd.read_csv(Path(data_dir) / "clean_training_val.csv")

    assert len(train_df) == shared["train_rows"], f"Train rows {len(train_df)} != {shared['train_rows']}"
    assert len(val_df) == shared["val_rows"], f"Val rows {len(val_df)} != {shared['val_rows']}"

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    device_name = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu"
    logger.info(f"Training on device: {device_name}")

    tokenizer = AutoTokenizer.from_pretrained("faisalq/EgyBERT")

    train_texts = train_df["text_norm"].astype(str).tolist()
    val_texts = val_df["text_norm"].astype(str).tolist()

    truth_rows = [
        {
            "audio_file": row["audio_file"],
            "complaint_category": row["complaint_category"],
            "complaint_urgency": row["complaint_urgency"],
            "customer_state": row["customer_state"],
            "churn_risk": row["churn_risk"],
        }
        for _, row in val_df.iterrows()
    ]

    seeds = list(shared["experiment_seeds"])
    fields = ["complaint_category", "complaint_urgency", "customer_state", "churn_risk"]

    config = ExperimentConfig(
        model="EgyBERT",
        dataset_version=shared["dataset_version"],
        split="train",
        learning_rate=3e-5,
        batch_size=16,
        epochs=3,
        other_hyperparameters={
            "max_epochs": 5,
            "early_stopping_patience": 2,
            "warmup_ratio": 0.1,
            "weight_decay": 0.01,
            "max_seq_len": 128,
            "optimizer": "AdamW",
            "dropout": 0.1,
            "task_type": "single_task",
            "selection_rule": "highest validation macro-F1 checkpoint",
        },
    )

    per_seed = []
    runs_dir_path = Path(runs_dir)

    for seed in seeds:
        pred_path = predictions_path(runs_dir, run_id, "val", seed)
        if pred_path.exists():
            logger.info(f"=== Seed {seed}: found existing predictions file at {pred_path}, skipping training ===")
            pred_data = read_predictions_file(pred_path, classes_by_field, expected_split="val")
            pred_rows = pred_data["harness_rows"]
        else:
            logger.info(f"=== Starting Seed {seed} ===")
            val_probs_by_field = {}

            for field in fields:
                logger.info(f"--- Training field: {field} (seed {seed}) ---")
                probs, best_f1 = train_single_field(
                    field_name=field,
                    classes=classes_by_field[field],
                    class_weights=weights_data["weights"][field],
                    train_texts=train_texts,
                    train_labels_str=train_df[field].tolist(),
                    val_texts=val_texts,
                    val_labels_str=val_df[field].tolist(),
                    tokenizer=tokenizer,
                    device=device,
                    seed=seed,
                    lr=3e-5,
                    batch_size=16,
                    max_epochs=5,
                    patience=2,
                )
                val_probs_by_field[field] = probs

            # Assemble prediction rows with probabilities for all 4 fields
            rows = []
            for i, audio_file in enumerate(val_df["audio_file"]):
                row_probs = {}
                for field in fields:
                    field_classes = classes_by_field[field]
                    p_list = val_probs_by_field[field][i]
                    # Ensure probabilities sum strictly to 1.0 within tolerance
                    p_sum = sum(p_list)
                    norm_p = [float(p / p_sum) for p in p_list]
                    # Adjust rounding on largest element to ensure exact sum
                    diff = 1.0 - sum(norm_p)
                    max_idx = int(np.argmax(norm_p))
                    norm_p[max_idx] += diff
                    row_probs[field] = {c: norm_p[j] for j, c in enumerate(field_classes)}

                rows.append({
                    "audio_file": audio_file,
                    "probabilities": row_probs,
                })

            # Write predictions file
            pred_path.parent.mkdir(parents=True, exist_ok=True)
            write_predictions_file(
                path=pred_path,
                run_id=run_id,
                model="EgyBERT",
                split="val",
                seed=seed,
                dataset_version=shared["dataset_version"],
                rows=rows,
                classes_by_field=classes_by_field,
            )
            logger.info(f"Saved predictions file: {pred_path}")
            pred_data = read_predictions_file(pred_path, classes_by_field, expected_split="val")
            pred_rows = pred_data["harness_rows"]
        harness_report = evaluate_predictions(
            split="val",
            truth_rows=truth_rows,
            pred_rows=pred_rows,
            classes_by_field=classes_by_field,
            exclusions_by_field=EXCLUSIONS,
        )

        seed_metrics = {
            "complaint_category_macro_f1": harness_report["fields"]["complaint_category"]["macro"]["f1"],
            "complaint_urgency_macro_f1": harness_report["fields"]["complaint_urgency"]["macro"]["f1"],
            "customer_state_macro_f1": harness_report["fields"]["customer_state"]["macro"]["f1"],
            "churn_risk_macro_f1": harness_report["fields"]["churn_risk"]["macro"]["f1"],
        }
        per_seed.append(
            make_seed_result(
                run_id=run_id,
                config=config,
                evaluated_split="val",
                seed=seed,
                metrics=seed_metrics,
            )
        )
        logger.info(f"Seed {seed} metrics: {seed_metrics}")

    # Build and save run record
    artifacts = {
        "predictions": [
            f"runs/exp_{run_id}/predictions_val_seed{s}.json" for s in seeds
        ]
    }
    record = build_run_record(
        run_id=run_id,
        hypothesis=(
            "EgyBERT single-task fine-tuning on train with class weights and 128 max sequence "
            "length beats the TF-IDF baseline on validation macro-F1."
        ),
        config=config,
        shared_config=shared,
        per_seed=per_seed,
        evaluated_split="val",
        artifacts=artifacts,
        device=device_name,
        exceptions=harness_report["exceptions"],
        reference_config=None,
        changed_factor=None,
        reference_run_id=None,
        ddof=1,
    )

    saved_path = save_run_record(record, runs_dir)
    logger.info(f"Saved run record: {saved_path}")
    return record


if __name__ == "__main__":
    run_experiment()
