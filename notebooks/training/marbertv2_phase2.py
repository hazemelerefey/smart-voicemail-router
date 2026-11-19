"""Colab entry point. Each training invocation works on one field and seed."""
import argparse
from pathlib import Path

from marbertv2_artifacts import FIELDS, configure, experiment_dir, finalize, read_inputs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["check", "smoke", "train", "finalize"])
    for name in ("shared", "train", "validation", "weights", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--run-id", default="marbertv2-lr2e5")
    parser.add_argument("--field", choices=FIELDS, default=FIELDS[0])
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--learning-rate", type=float, default=2e-5)
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--reference-run-id")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    data = read_inputs(args.shared, args.train, args.validation, args.weights)
    config = configure(data, args.learning_rate, args.epochs)
    if args.seed not in data.shared["experiment_seeds"]:
        parser.error("Select one of the five seeds from shared_config.json")
    if args.action == "check":
        print(f"Frozen inputs verified: {len(data.train)} train, {len(data.validation)} validation.")
        print("Class order and committed weights:", data.weights)
        return

    if args.action in ("smoke", "train"):
        from marbertv2_train import smoke, train

        if args.action == "smoke":
            smoke(data, config, args.field, args.seed)
            return

    runs_dir = args.output / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    folder = experiment_dir(runs_dir, args.run_id, config)
    if args.action == "train":
        train(data, config, folder, args.field, args.seed, args.resume)
    else:
        finalize(data, runs_dir, folder, args.run_id, config, args.reference_run_id)


if __name__ == "__main__":
    main()
