"""Merge AbdelrahmanHassan/whisper-large-v3-egyptian-arabic LoRA and convert to CTranslate2 int8_float16."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BASE_MODEL_ID = "openai/whisper-large-v3"
ADAPTER_ID = "AbdelrahmanHassan/whisper-large-v3-egyptian-arabic"


def build_egyptian_whisper_ct2(
    *,
    output_dir: Path,
    quantization: str = "int8_float16",
    keep_merged: bool = False,
) -> Path:
    import torch
    from peft import PeftModel
    from transformers import AutoModelForSpeechSeq2Seq, WhisperProcessor

    merged_dir = output_dir.parent / "_whisper_egyptian_merged_tmp"
    if merged_dir.exists():
        shutil.rmtree(merged_dir)
    merged_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loading base model {BASE_MODEL_ID} and LoRA adapter {ADAPTER_ID}...")
    processor = WhisperProcessor.from_pretrained(ADAPTER_ID)
    base_model = AutoModelForSpeechSeq2Seq.from_pretrained(
        BASE_MODEL_ID,
        torch_dtype=torch.float16,
        low_cpu_mem_usage=True,
    )
    peft_model = PeftModel.from_pretrained(base_model, ADAPTER_ID)
    merged_model = peft_model.merge_and_unload()

    print(f"Saving merged HF checkpoint to {merged_dir}...")
    merged_model.save_pretrained(str(merged_dir), safe_serialization=True)
    processor.save_pretrained(str(merged_dir))

    if output_dir.exists():
        shutil.rmtree(output_dir)

    cmd = [
        "ct2-transformers-converter",
        "--model",
        str(merged_dir),
        "--output_dir",
        str(output_dir),
        "--quantization",
        quantization,
        "--copy_files",
        "tokenizer.json",
        "preprocessor_config.json",
    ]
    print("Running:", " ".join(cmd))
    subprocess.run(cmd, check=True)

    if not keep_merged and merged_dir.exists():
        shutil.rmtree(merged_dir)

    print(f"Egyptian Whisper CT2 ({quantization}) ready at: {output_dir}")
    return output_dir


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build CTranslate2 Egyptian Arabic Whisper large-v3 model for faster-whisper."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=REPO_ROOT / "models" / "whisper-large-v3-egyptian-ct2",
        help="Destination directory for CTranslate2 model.",
    )
    parser.add_argument(
        "--quantization",
        type=str,
        default="int8_float16",
        help="CTranslate2 quantization type (default: int8_float16 for 6 GB GPU).",
    )
    parser.add_argument(
        "--keep-merged",
        action="store_true",
        help="Keep intermediate merged HuggingFace checkpoint.",
    )
    args = parser.parse_args()
    build_egyptian_whisper_ct2(
        output_dir=args.output_dir,
        quantization=args.quantization,
        keep_merged=args.keep_merged,
    )


if __name__ == "__main__":
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8")
    main()
