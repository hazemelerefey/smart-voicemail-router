"""Fair-comparison single-task training (Phase 2, AZZAR re-run).

Runs ONE model (EgyBERT or MARBERTv2) under the exact Phase 2 protocol,
so the two models can be compared on equal footing:
  - lr 2e-5, batch 16, epochs 3 (max 5, early stopping patience 2),
    warmup 0.1, weight decay 0.01, max seq len 128, AdamW, dropout 0.1
  - class weights from train ONLY, applied in the loss for ALL 4 fields
    (including churn_risk; no sampler tricks)
  - input text_norm only; frozen split train 3575 / val 1003; never test
  - 5 seeds 42/1337/2023/7/99, mean + sample std ddof=1
  - customer_state scored on 4 classes only (unclear row excluded)
  - run records + prediction files in Aya's infra format

Fixes vs Arafa's script (a52400a): lr 3e-5 -> 2e-5; churn now uses class
weights in the loss instead of WeightedRandomSampler; dropout 0.1 is
actually passed to the model config; model is a CLI argument; AMP is
used only when CUDA is available (CPU fallback works for smoke tests).

Usage (Colab T4):
  python train_fair.py --model faisalq/EgyBERT --model-name EgyBERT \\
      --run-id fair-egybert-lr2e5 --data-dir data/final --runs-dir runs \\
      --shared-config shared_config.json
  python train_fair.py --model UBC-NLP/MARBERTv2 --model-name MARBERTv2 \\
      --run-id fair-marbertv2-lr2e5 --data-dir data/final --runs-dir runs \\
      --shared-config shared_config.json

Smoke test (1 field, 1 seed, 1 epoch, CPU-safe):
  python train_fair.py --model faisalq/EgyBERT --model-name EgyBERT \\
      --run-id smoke --fields complaint_category --seeds 42 --max-epochs 1
"""
import argparse
import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Dataset
from transformers import (
    AutoConfig,
    AutoModelForSequenceClassification,
    AutoTokenizer,
    get_linear_schedule_with_warmup,
)

from infra.experiment_config import ExperimentConfig
from infra.harness import evaluate_predictions
from infra.metrics import evaluate_field
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
FIELDS = ["complaint_category", "complaint_urgency", "customer_state", "churn_risk"]


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
    model_id,
    device,
    seed,
    lr=2e-5,
    batch_size=16,
    max_epochs=5,
    patience=2,
):
    set_global_seed(seed)
    class_to_idx = {c: i for i, c in enumerate(classes)}
    train_labels = [class_to_idx[l] for l in train_labels_str]
    train_dataset = TextDataset(train_texts, train_labels, tokenizer)
    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)

    # Class weights in the loss for ALL fields, including churn_risk.
    w_tensor = torch.tensor(
        [class_weights[c] for c in classes],
        dtype=torch.float,
        device=device,
    )
    loss_fn = nn.CrossEntropyLoss(weight=w_tensor)

    val_labels_clean = [class_to_idx.get(l, 0) for l in val_labels_str]
    val_dataset = TextDataset(val_texts, val_labels_clean, tokenizer)
    val_loader = DataLoader(val_dataset, batch_size=32, shuffle=False)

    # Dropout 0.1 passed explicitly (Arafa's script only recorded it).
    config = AutoConfig.from_pretrained(
        model_id,
        num_labels=len(classes),
        hidden_dropout_prob=0.1,
        attention_probs_dropout_prob=0.1,
    )
    model = AutoModelForSequenceClassification.from_pretrained(model_id, config=config)
    model.to(device)

    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=0.01)
    total_steps = len(train_loader) * max_epochs
    scheduler = get_linear_schedule_with_warmup(
        optimizer,
        num_warmup_steps=int(total_steps * 0.1),
        num_training_steps=total_steps,
    )
    use_cuda = device.type == "cuda"
    scaler = torch.amp.GradScaler("cuda") if use_cuda else None

    if field_name == "customer_state":
        eval_mask = [l != "unclear" for l in val_labels_str]
    else:
        eval_mask = [True] * len(val_labels_str)
    eval_true = [val_labels_str[i] for i, m in enumerate(eval_mask) if m]

    best_macro_f1 = -1.0
    best_val_probs = None
    patience_counter = 0

    for epoch in range(max_epochs):
        model.train()
        for batch in train_loader:
            optimizer.zero_grad()
            input_ids = batch["input_ids"].to(device)
            attention_mask = batch["attention_mask"].to(device)
            labels = batch["labels"].to(device)
            if use_cuda:
                with torch.amp.autocast("cuda"):
                    outputs = model(input_ids=input_ids, attention_mask=attention_mask)
                    loss = loss_fn(outputs.logits, labels)
                scaler.scale(loss).backward()
                scaler.unscale_(optimizer)
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                scaler.step(optimizer)
                scaler.update()
            else:
                outputs = model(input_ids=input_ids, attention_mask=attention_mask)
                loss = loss_fn(outputs.logits, labels)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                optimizer.step()
            scheduler.step()

        model.eval()
        epoch_probs = []
        with torch.no_grad():
            for batch in val_loader:
                input_ids = batch["input_ids"].to(device)
                attention_mask = batch["attention_mask"].to(device)
                if use_cuda:
                    with torch.amp.autocast("cuda"):
                        outputs = model(input_ids=input_ids, attention_mask=attention_mask)
                        probs = torch.softmax(outputs.logits, dim=-1)
                else:
                    outputs = model(input_ids=input_ids, attention_mask=attention_mask)
                    probs = torch.softmax(outputs.logits, dim=-1)
                epoch_probs.extend(probs.cpu().numpy().tolist())

        epoch_preds = [classes[int(np.argmax(p))] for p in epoch_probs]
        eval_preds = [epoch_preds[i] for i, m in enumerate(eval_mask) if m]
        rep = evaluate_field(eval_true, eval_preds, classes)
        current_macro_f1 = rep["macro"]["f1"]
        logger.info(
            f"[{field_name}] Seed {seed} Epoch {epoch + 1}: "
            f"validation macro-F1 = {current_macro_f1:.4f}"
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


def run_experiment(args):
    shared = load_shared_config(args.shared_config)
    data_dir = Path(args.data_dir)
    weights_data = json.loads((data_dir / "class_weights.json").read_text(encoding="utf-8"))

    classes_by_field = {
        field: list(weights.keys())
        for field, weights in weights_data["weights"].items()
    }

    train_df = pd.read_csv(data_dir / "clean_training_train.csv")
    val_df = pd.read_csv(data_dir / "clean_training_val.csv")

    assert len(train_df) == shared["train_rows"], (
        f"Train rows {len(train_df)} != {shared['train_rows']}"
    )
    assert len(val_df) == shared["val_rows"], (
        f"Val rows {len(val_df)} != {shared['val_rows']}"
    )
    logger.info(f"Data OK: train {len(train_df)}, val {len(val_df)} (test never loaded)")

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    device_name = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu"
    logger.info(f"Training on device: {device_name}")

    tokenizer = AutoTokenizer.from_pretrained(args.model)

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

    seeds = [int(s) for s in args.seeds]
    fields = args.fields
    run_id = args.run_id
    runs_dir = args.runs_dir

    config = ExperimentConfig(
        model=args.model_name,
        dataset_version=shared["dataset_version"],
        split="train",
        learning_rate=2e-5,
        batch_size=16,
        epochs=3,
        other_hyperparameters={
            "hf_model_id": args.model,
            "max_epochs": args.max_epochs,
            "early_stopping_patience": 2,
            "warmup_ratio": 0.1,
            "weight_decay": 0.01,
            "max_seq_len": 128,
            "optimizer": "AdamW",
            "dropout": 0.1,
            "task_type": "single_task",
            "selection_rule": "highest validation macro-F1 checkpoint",
            "run_by": "AZZAR fair-comparison re-run",
        },
    )

    per_seed = []
    for seed in seeds:
        pred_path = predictions_path(runs_dir, run_id, "val", seed)
        if pred_path.exists():
            logger.info(f"=== Seed {seed}: existing predictions at {pred_path}, skipping training ===")
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
                    model_id=args.model,
                    device=device,
                    seed=seed,
                    lr=2e-5,
                    batch_size=16,
                    max_epochs=args.max_epochs,
                    patience=2,
                )
                val_probs_by_field[field] = probs

            rows = []
            for i, audio_file in enumerate(val_df["audio_file"]):
                row_probs = {}
                for field in fields:
                    field_classes = classes_by_field[field]
                    p_list = val_probs_by_field[field][i]
                    p_sum = sum(p_list)
                    norm_p = [float(p / p_sum) for p in p_list]
                    diff = 1.0 - sum(norm_p)
                    max_idx = int(np.argmax(norm_p))
                    norm_p[max_idx] += diff
                    row_probs[field] = {c: norm_p[j] for j, c in enumerate(field_classes)}
                rows.append({"audio_file": audio_file, "probabilities": row_probs})

            pred_path.parent.mkdir(parents=True, exist_ok=True)
            write_predictions_file(
                path=pred_path,
                run_id=run_id,
                model=args.model_name,
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

    artifacts = {
        "predictions": [
            f"runs/exp_{run_id}/predictions_val_seed{s}.json" for s in seeds
        ]
    }
    record = build_run_record(
        run_id=run_id,
        hypothesis=(
            f"{args.model_name} single-task fine-tuning at lr 2e-5 with class weights "
            "in the loss for all fields beats the TF-IDF baseline on validation macro-F1."
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


def main():
    p = argparse.ArgumentParser(description="Fair-comparison single-task training")
    p.add_argument("--model", required=True, help="HF model id, e.g. faisalq/EgyBERT")
    p.add_argument("--model-name", required=True, help="Short name, e.g. EgyBERT")
    p.add_argument("--run-id", required=True)
    p.add_argument("--data-dir", default="../svr-data/final")
    p.add_argument("--runs-dir", default="runs")
    p.add_argument("--shared-config", default="notebooks/training/shared_config.json")
    p.add_argument("--fields", nargs="+", default=FIELDS)
    p.add_argument("--seeds", nargs="+", default=["42", "1337", "2023", "7", "99"])
    p.add_argument("--max-epochs", type=int, default=5)
    args = p.parse_args()
    run_experiment(args)


if __name__ == "__main__":
    main()
