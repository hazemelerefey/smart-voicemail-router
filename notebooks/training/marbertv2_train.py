"""Train or resume one MARBERTv2 classification head on a Colab GPU."""
import math
import random
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import torch
import transformers
from torch.utils.data import DataLoader
from transformers import (
    AutoConfig,
    AutoModelForSequenceClassification,
    AutoTokenizer,
    DataCollatorWithPadding,
    get_linear_schedule_with_warmup,
)

from infra.seeds import set_global_seed
from marbertv2_artifacts import read_json, score, task_dir, write_json


def tokenizer_for(config):
    return AutoTokenizer.from_pretrained(config.model, revision=config.other_hyperparameters["model_revision"])


def tokenize(tokenizer, rows, limit):
    return tokenizer([row["text_norm"] for row in rows], truncation=True, max_length=limit,
                     verbose=False)


def batches(encoded, tokenizer, batch_size, labels=None, generator=None):
    examples = [dict(zip(encoded.keys(), values)) for values in zip(*encoded.values())]
    if labels is not None:
        for example, label in zip(examples, labels, strict=True):
            example["labels"] = label
    return DataLoader(examples, batch_size=batch_size, shuffle=generator is not None, generator=generator,
                      collate_fn=DataCollatorWithPadding(tokenizer, pad_to_multiple_of=8))


def cuda_environment():
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is unavailable. Select a Colab GPU runtime and rerun setup.")
    return {
        "gpu": torch.cuda.get_device_name(),
        "torch": str(torch.__version__),
        "transformers": transformers.__version__,
        "cuda": torch.version.cuda,
    }


def build_model(config, classes, checkpoint):
    if checkpoint:
        return AutoModelForSequenceClassification.from_pretrained(checkpoint, local_files_only=True).cuda()
    params = config.other_hyperparameters
    revision = params["model_revision"]
    head = AutoConfig.from_pretrained(
        config.model, revision=revision, id2label=dict(enumerate(classes)),
        label2id={label: i for i, label in enumerate(classes)}, num_labels=len(classes),
        hidden_dropout_prob=params["dropout"], attention_probs_dropout_prob=params["dropout"],
        classifier_dropout=params["dropout"],
    )
    return AutoModelForSequenceClassification.from_pretrained(config.model, revision=revision, config=head).cuda()


def build_optimizer(model, config):
    decay, no_decay = [], []
    for name, parameter in model.named_parameters():
        group = no_decay if name.endswith(("bias", "LayerNorm.weight")) else decay
        group.append(parameter)
    return torch.optim.AdamW([
        {"params": decay, "weight_decay": config.other_hyperparameters["weight_decay"]},
        {"params": no_decay, "weight_decay": 0.0},
    ], lr=config.learning_rate)


def weighted_loss(data, field, config):
    weights = data.weights[field].copy()
    if field == "churn_risk":
        weights["at_risk"] = min(weights["at_risk"], config.other_hyperparameters["churn_weight_cap"])
    tensor = torch.tensor([weights[label] for label in data.classes[field]], device="cuda")
    return torch.nn.CrossEntropyLoss(weight=tensor)


def update(model, batch, loss_fn, optimizer, scaler, clip):
    optimizer.zero_grad(set_to_none=True)
    batch = {key: value.cuda() for key, value in batch.items()}
    labels = batch.pop("labels")
    with torch.autocast("cuda", dtype=torch.float16):
        loss = loss_fn(model(**batch).logits, labels)
    scaler.scale(loss).backward()
    scaler.unscale_(optimizer)
    torch.nn.utils.clip_grad_norm_(model.parameters(), clip)
    scale = scaler.get_scale()
    scaler.step(optimizer)
    scaler.update()
    return float(loss.detach()), scaler.get_scale() >= scale


def smoke(data, config, field, seed):
    environment = cuda_environment()
    set_global_seed(seed)
    tokenizer = tokenizer_for(config)
    limit = config.other_hyperparameters["max_seq_len"]
    for split, rows in (("train", data.train), ("validation", data.validation)):
        ids = tokenizer([row["text_norm"] for row in rows], truncation=False, verbose=False)["input_ids"]
        lengths = [len(tokens) for tokens in ids]
        over = sum(length > limit for length in lengths)
        print(f"{split}: {len(rows) - over}/{len(rows)} fit {limit} tokens, "
              f"{over} truncated, max={max(lengths)}, including special tokens", flush=True)

    classes = data.classes[field]
    rows = data.train[:config.batch_size]
    loader = batches(tokenize(tokenizer, rows, limit), tokenizer, config.batch_size,
                     [classes.index(row[field]) for row in rows])
    model = build_model(config, classes, None)
    model.train()
    # A conservative initial AMP scale gives the smoke step a real optimizer update.
    loss, stepped = update(model, next(iter(loader)), weighted_loss(data, field, config),
                           build_optimizer(model, config), torch.amp.GradScaler("cuda", init_scale=1024),
                           config.other_hyperparameters["gradient_clip_norm"])
    if not math.isfinite(loss) or not stepped:
        raise RuntimeError(f"Smoke step did not update parameters. Loss={loss}, AMP update={stepped}")
    print(f"Smoke step passed on {environment['gpu']} for {field}/{seed}, loss={loss:.6f}", flush=True)


@torch.inference_mode()
def predict(model, loader, rows, classes):
    model.eval()
    values = []
    for batch in loader:
        with torch.autocast("cuda", dtype=torch.float16):
            logits = model(**{key: value.cuda() for key, value in batch.items()}).logits
        probabilities = logits.float().softmax(dim=-1)
        if not torch.isfinite(probabilities).all():
            raise FloatingPointError("Nonfinite validation probabilities")
        values.extend(probabilities.cpu().tolist())
    return {row["audio_file"]: dict(zip(classes, probs, strict=True))
            for row, probs in zip(rows, values, strict=True)}


def epoch_path(folder, epoch):
    return folder / f"epoch_{epoch:02d}"


def save_epoch(folder, model, tokenizer, optimizer, scheduler, scaler, state, shuffle):
    destination = epoch_path(folder, state["epoch"])
    if destination.exists():
        raise FileExistsError(destination)
    with TemporaryDirectory(dir=folder, prefix=".checkpoint-") as staging:
        path = Path(staging) / "checkpoint"
        model.save_pretrained(path)
        tokenizer.save_pretrained(path)
        torch.save({
            "optimizer": optimizer.state_dict(), "scheduler": scheduler.state_dict(),
            "scaler": scaler.state_dict(), "shuffle_rng": shuffle.get_state(),
            "torch_rng": torch.get_rng_state(), "cuda_rng": torch.cuda.get_rng_state_all(),
            "python_rng": random.getstate(), "numpy_rng": np.random.get_state(),
        }, path / "training.pt")
        write_json(path / "state.json", state)
        path.rename(destination)
    for old in folder.glob("epoch_[0-9][0-9]"):
        if old not in {destination, epoch_path(folder, state["best_epoch"])}:
            shutil.rmtree(old)


def restore(path, optimizer, scheduler, scaler, shuffle):
    # This is a trusted, self-generated checkpoint in the experiment's private Drive folder.
    saved = torch.load(path / "training.pt", weights_only=False, map_location="cpu")
    optimizer.load_state_dict(saved["optimizer"])
    scheduler.load_state_dict(saved["scheduler"])
    scaler.load_state_dict(saved["scaler"])
    shuffle.set_state(saved["shuffle_rng"])
    torch.set_rng_state(saved["torch_rng"])
    torch.cuda.set_rng_state_all(saved["cuda_rng"])
    random.setstate(saved["python_rng"])
    np.random.set_state(saved["numpy_rng"])


def train(data, config, folder, field, seed, resume):
    destination = task_dir(folder, seed, field)
    result_path = destination / "result.json"
    if result_path.exists():
        if resume:
            print(f"Already completed {field}/{seed}.")
            return
        raise FileExistsError(f"{result_path} already exists. Use a new run ID to rerun.")
    checkpoints = sorted(destination.glob("epoch_[0-9][0-9]"))
    latest = checkpoints[-1] if checkpoints else None
    if latest and not resume:
        raise FileExistsError("Checkpoint exists. Set RESUME=True to continue the same task and seed.")
    environment = cuda_environment()
    identity = {"field": field, "config": config.for_seed(seed), "environment": environment}
    state = read_json(latest / "state.json") if latest else {
        **identity, "epoch": 0, "best_epoch": 0, "best_f1": -1, "history": [],
    }
    if any(state[key] != value for key, value in identity.items()):
        raise ValueError("The saved checkpoint requires the same training config and GPU environment")

    set_global_seed(seed)
    shuffle = torch.Generator().manual_seed(seed)
    params = config.other_hyperparameters
    limit = params["max_seq_len"]
    classes = data.classes[field]
    tokenizer = tokenizer_for(config)
    train_loader = batches(tokenize(tokenizer, data.train, limit), tokenizer, config.batch_size,
                           [classes.index(row[field]) for row in data.train], shuffle)
    val_loader = batches(tokenize(tokenizer, data.validation, limit), tokenizer, config.batch_size)
    model = build_model(config, classes, latest)
    optimizer = build_optimizer(model, config)
    steps = len(train_loader) * config.epochs
    scheduler = get_linear_schedule_with_warmup(optimizer, math.ceil(steps * params["warmup_ratio"]), steps)
    scaler = torch.amp.GradScaler("cuda", init_scale=1024)
    loss_fn = weighted_loss(data, field, config)
    if latest:
        restore(latest, optimizer, scheduler, scaler, shuffle)
        print(f"Resuming after epoch {state['epoch']} for {field}/{seed}.", flush=True)
    destination.mkdir(parents=True, exist_ok=True)

    for epoch in range(state["epoch"] + 1, config.epochs + 1):
        if state["epoch"] - state["best_epoch"] >= params["early_stopping_patience"]:
            break
        model.train()
        losses = []
        updates = 0
        for batch in train_loader:
            loss, stepped = update(model, batch, loss_fn, optimizer, scaler, params["gradient_clip_norm"])
            if not math.isfinite(loss):
                raise FloatingPointError(f"Nonfinite training loss in epoch {epoch}")
            losses.append(loss)
            if stepped:
                scheduler.step()
                updates += 1
        if not updates:
            raise RuntimeError(f"AMP skipped every update in epoch {epoch}")

        probabilities = predict(model, val_loader, data.validation, classes)
        predictions = [{"audio_file": key, field: max(classes, key=probs.__getitem__)}
                       for key, probs in probabilities.items()]
        report = score(data, [field], predictions)
        f1 = report["fields"][field]["macro"]["f1"]
        if f1 > state["best_f1"]:
            state.update(best_epoch=epoch, best_f1=f1, best_probabilities=probabilities)
        state["epoch"] = epoch
        state["history"].append({"epoch": epoch, "mean_batch_loss": float(np.mean(losses)),
                                 "optimizer_updates": updates, "macro_f1": f1})
        save_epoch(destination, model, tokenizer, optimizer, scheduler, scaler, state, shuffle)
        print(f"{field}/{seed} epoch {epoch}: validation Macro-F1 {f1:.4f}; "
              f"best epoch {state['best_epoch']}", flush=True)

    best = epoch_path(destination, state["best_epoch"])
    if not (best / "training.pt").is_file():
        raise FileNotFoundError(f"Selected checkpoint is missing: {best}")
    write_json(result_path, {
        "field": field, "config": config.for_seed(seed), "device": environment["gpu"],
        "environment": environment, "best_epoch": state["best_epoch"], "history": state["history"],
        "checkpoint": best.relative_to(folder.parent.parent).as_posix(),
        "probabilities": state["best_probabilities"],
    })
    print(f"Saved {result_path}", flush=True)
