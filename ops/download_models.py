"""Download SVR production MARBERTv2 (seed_99) from Google Drive and prepare ONNX/CT2 artifacts."""

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

# Verified Google Drive handoff folders (Sira / Aya single-task MARBERTv2 release)
SEED99_DRIVE_FOLDER_ID = "1wZPNugbk9Mxkl-zG1pLnP_nac9QWY_tG"
SEED99_DRIVE_URL = f"https://drive.google.com/drive/folders/{SEED99_DRIVE_FOLDER_ID}"
MANIFEST_DRIVE_FOLDER_ID = "1HarYxoqG-YWW-IR5n-PkEWBV-gV4I6Rv"
MANIFEST_DRIVE_URL = f"https://drive.google.com/drive/folders/{MANIFEST_DRIVE_FOLDER_ID}"
HANDOFF_DRIVE_FOLDER_ID = "1UbB6vuA4u1IEiWQFwb3ySynAE0kEwEWw"
HANDOFF_DRIVE_URL = f"https://drive.google.com/drive/folders/{HANDOFF_DRIVE_FOLDER_ID}"


def download_seed99_from_drive(target_dir: Path) -> None:
    try:
        import gdown
    except ImportError as exc:
        raise RuntimeError(
            "gdown is required to download checkpoints from Google Drive. "
            "Install it with: pip install gdown"
        ) from exc

    target_dir.mkdir(parents=True, exist_ok=True)
    print(f"Downloading MARBERTv2 seed_99 from Google Drive ({SEED99_DRIVE_URL}) into {target_dir}...")
    gdown.download_folder(
        id=SEED99_DRIVE_FOLDER_ID,
        output=str(target_dir),
        quiet=False,
        use_cookies=False,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare SVR production models from Google Drive.")
    parser.add_argument("--seed", type=int, default=99, help="Checkpoint seed (default: 99).")
    parser.add_argument(
        "--models-dir",
        type=Path,
        default=REPO_ROOT / "models" / "marbertv2-single-task",
        help="Root directory for MARBERTv2 checkpoints.",
    )
    parser.add_argument("--check-only", action="store_true", help="Verify local artifacts without downloading.")
    parser.add_argument("--skip-onnx", action="store_true", help="Skip ONNX INT8 export step.")
    parser.add_argument(
        "--with-egyptian-whisper",
        action="store_true",
        help="Also build models/whisper-large-v3-egyptian-ct2 for 6 GB GPU hosts.",
    )
    args = parser.parse_args()

    ckpts = discover_single_task_checkpoints(args.models_dir, seed=args.seed)
    if ckpts is None:
        if args.check_only:
            print(f"MISSING: MARBERTv2 seed_{args.seed} checkpoints not found under {args.models_dir}")
            print(f"Download from: {SEED99_DRIVE_URL}")
            sys.exit(1)
        if args.seed != 99:
            raise RuntimeError(
                f"Automated Drive download targets seed_99 ({SEED99_DRIVE_URL}). "
                f"For seed_{args.seed}, download manually from {MANIFEST_DRIVE_URL}."
            )
        download_seed99_from_drive(args.models_dir / "seed_99")
        ckpts = discover_single_task_checkpoints(args.models_dir, seed=args.seed)
        if ckpts is None:
            raise RuntimeError(f"Download completed but 4 checkpoints were not found under {args.models_dir / 'seed_99'}")

    onnx_ready = all((ckpts[f] / "model_int8.onnx").is_file() for f in CLASSIFICATION_FIELDS)
    print(f"MARBERTv2 seed_{args.seed} checkpoints ready (4/4 heads, onnx_int8={onnx_ready}).")

    if args.check_only:
        sys.exit(0)

    if not args.skip_onnx and not onnx_ready:
        print("Exporting MARBERTv2 seed_99 to ONNX INT8...")
        subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "ops" / "export_marbert_onnx.py"),
                "--models-dir",
                str(args.models_dir),
                "--seed",
                str(args.seed),
            ],
            check=True,
        )

    whisper_ct2 = REPO_ROOT / "models" / "whisper-large-v3-egyptian-ct2"
    if args.with_egyptian_whisper and not whisper_ct2.is_dir():
        print("Building Egyptian Arabic Whisper CTranslate2 (int8_float16)...")
        subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "ops" / "build_egyptian_whisper_ct2.py"),
                "--output-dir",
                str(whisper_ct2),
            ],
            check=True,
        )


if __name__ == "__main__":
    main()
