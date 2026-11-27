"""Export MARBERTv2 single-task checkpoints to ONNX INT8 for fast CPU inference."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from svr_platform.services.classification import (  # noqa: E402
    CLASSIFICATION_FIELDS,
    discover_single_task_checkpoints,
)


def _export_one_fp32(cdir: Path, fp32_path: Path) -> None:
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(str(cdir))
    model = AutoModelForSequenceClassification.from_pretrained(str(cdir), attn_implementation="eager")
    model.eval()

    sample = tokenizer("الشبكة ضعيفة جدا", return_tensors="pt")
    input_names = ["input_ids", "attention_mask"]
    inputs: tuple[torch.Tensor, ...] = (sample["input_ids"], sample["attention_mask"])
    dynamic_axes: dict[str, dict[int, str]] = {
        "input_ids": {0: "batch", 1: "seq"},
        "attention_mask": {0: "batch", 1: "seq"},
        "logits": {0: "batch"},
    }
    if "token_type_ids" in sample:
        input_names.append("token_type_ids")
        inputs = (*inputs, sample["token_type_ids"])
        dynamic_axes["token_type_ids"] = {0: "batch", 1: "seq"}

    with torch.no_grad():
        torch.onnx.export(
            model,
            inputs,
            str(fp32_path),
            input_names=input_names,
            output_names=["logits"],
            dynamic_axes=dynamic_axes,
            opset_version=17,
            dynamo=False,
        )


def _quantize_one_int8(fp32_path: Path, int8_path: Path, field_name: str, keep_fp32: bool) -> None:
    from onnxruntime.quantization import QuantType, quantize_dynamic

    quantize_dynamic(
        model_input=str(fp32_path),
        model_output=str(int8_path),
        op_types_to_quantize=["MatMul", "Gemm"],
        weight_type=QuantType.QInt8,
    )
    data_path = Path(f"{fp32_path}.data")
    fp32_mb = (fp32_path.stat().st_size + (data_path.stat().st_size if data_path.is_file() else 0)) / (1024 * 1024)
    int8_mb = int8_path.stat().st_size / (1024 * 1024)
    print(f"[{field_name}] {fp32_path.parent}: FP32={fp32_mb:.1f} MB -> INT8={int8_mb:.1f} MB")

    if not keep_fp32:
        if fp32_path.exists():
            fp32_path.unlink()
        if data_path.exists():
            data_path.unlink()


def export_seed_to_onnx(models_dir: Path, *, seed: int = 99, keep_fp32: bool = False) -> dict[str, Path]:
    ckpt_dirs = discover_single_task_checkpoints(models_dir, seed=seed)
    if ckpt_dirs is None:
        raise FileNotFoundError(f"Could not locate 4 single-task checkpoints for seed={seed} under {models_dir}")

    exported: dict[str, Path] = {}
    script = Path(__file__).resolve()
    for field_name in CLASSIFICATION_FIELDS:
        cdir = ckpt_dirs[field_name]
        for phase in ("export", "quantize"):
            cmd = [
                sys.executable,
                str(script),
                "--models-dir",
                str(models_dir),
                "--seed",
                str(seed),
                "--field",
                field_name,
                "--phase",
                phase,
            ]
            if keep_fp32:
                cmd.append("--keep-fp32")
            subprocess.run(cmd, check=True)
        exported[field_name] = cdir / "model_int8.onnx"
    return exported


def main() -> None:
    parser = argparse.ArgumentParser(description="Export MARBERTv2 checkpoints to ONNX INT8.")
    parser.add_argument(
        "--models-dir",
        type=Path,
        default=REPO_ROOT / "models" / "marbertv2-single-task",
        help="Root directory containing single-task MARBERTv2 checkpoints.",
    )
    parser.add_argument("--seed", type=int, default=99, help="Checkpoint seed to export.")
    parser.add_argument("--keep-fp32", action="store_true", help="Keep intermediate model.onnx FP32 files.")
    parser.add_argument("--field", type=str, default="", help=argparse.SUPPRESS)
    parser.add_argument("--phase", type=str, default="all", choices=("all", "export", "quantize"), help=argparse.SUPPRESS)
    args = parser.parse_args()

    if args.phase == "all":
        export_seed_to_onnx(args.models_dir, seed=args.seed, keep_fp32=args.keep_fp32)
        return

    ckpt_dirs = discover_single_task_checkpoints(args.models_dir, seed=args.seed)
    if ckpt_dirs is None or args.field not in ckpt_dirs:
        raise FileNotFoundError(f"Checkpoint not found for seed={args.seed} field={args.field}")
    cdir = ckpt_dirs[args.field]
    fp32_path = cdir / "model.onnx"
    int8_path = cdir / "model_int8.onnx"
    if args.phase == "export":
        _export_one_fp32(cdir, fp32_path)
    elif args.phase == "quantize":
        _quantize_one_int8(fp32_path, int8_path, args.field, args.keep_fp32)


if __name__ == "__main__":
    main()
