#!/usr/bin/env python3
"""Fine-tune GPT-2 on the prepared KalamGPT text corpus.

Run from the repository root:
    python3 training/train_gpt2.py --dataset-version v1

The script saves checkpoints during training and writes the final model and
matching tokenizer to models/kalam-gpt2-v1 by default. It is designed to run
in a GPU environment such as Google Colab; a CPU dry run can validate paths
and tokenization without starting training.
"""
from __future__ import annotations

import argparse
import inspect
import json
import os
import random
from datetime import datetime, timezone
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-version", default="v1")
    parser.add_argument("--model-name", default="gpt2")
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--checkpoint-dir", type=Path, default=None)
    parser.add_argument("--block-size", type=int, default=512)
    parser.add_argument("--epochs", type=float, default=3.0)
    parser.add_argument("--train-batch-size", type=int, default=2)
    parser.add_argument("--eval-batch-size", type=int, default=2)
    parser.add_argument("--gradient-accumulation-steps", type=int, default=8)
    parser.add_argument("--learning-rate", type=float, default=5e-5)
    parser.add_argument("--warmup-ratio", type=float, default=0.05)
    parser.add_argument("--weight-decay", type=float, default=0.01)
    parser.add_argument("--logging-steps", type=int, default=25)
    parser.add_argument("--save-total-limit", type=int, default=2)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--resume-from-checkpoint", default=None)
    parser.add_argument("--dry-run", action="store_true", help="Load/tokenize a small sample and exit")
    parser.add_argument("--trust-remote-code", action="store_true")
    return parser.parse_args()


def set_seed(seed: int) -> None:
    random.seed(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)
    try:
        import numpy as np
        np.random.seed(seed)
    except ImportError:
        pass
    try:
        import torch
        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)
    except ImportError:
        pass


def build_training_args(TrainingArguments, args: argparse.Namespace, checkpoint_dir: Path, use_fp16: bool, use_bf16: bool):
    """Support both older and newer Transformers argument names."""
    values = {
        "output_dir": str(checkpoint_dir),
        "num_train_epochs": args.epochs,
        "per_device_train_batch_size": args.train_batch_size,
        "per_device_eval_batch_size": args.eval_batch_size,
        "gradient_accumulation_steps": args.gradient_accumulation_steps,
        "learning_rate": args.learning_rate,
        "warmup_ratio": args.warmup_ratio,
        "weight_decay": args.weight_decay,
        "logging_dir": str(checkpoint_dir / "logs"),
        "logging_steps": args.logging_steps,
        "save_strategy": "steps",
        "save_steps": max(args.logging_steps * 10, 100),
        "save_total_limit": args.save_total_limit,
        "load_best_model_at_end": True,
        "metric_for_best_model": "eval_loss",
        "greater_is_better": False,
        "fp16": use_fp16,
        "bf16": use_bf16,
        "seed": args.seed,
        "report_to": "none",
        "remove_unused_columns": False,
    }
    parameters = inspect.signature(TrainingArguments.__init__).parameters
    if "eval_strategy" in parameters:
        values["eval_strategy"] = "steps"
    else:
        values["evaluation_strategy"] = "steps"
    values["eval_steps"] = values["save_steps"]
    return TrainingArguments(**{k: v for k, v in values.items() if k in parameters})


def main() -> None:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    dataset_root = repo_root / "data" / "kalam" / "datasets" / args.dataset_version
    train_path = dataset_root / "train.txt"
    validation_path = dataset_root / "validation.txt"
    output_dir = (args.output_dir or repo_root / "models" / f"kalam-gpt2-{args.dataset_version}").resolve()
    checkpoint_dir = (args.checkpoint_dir or output_dir / "checkpoints").resolve()
    if not train_path.is_file() or not validation_path.is_file():
        raise SystemExit(f"Missing dataset files under {dataset_root}. Run prepare_dataset.py and split_dataset.py first.")
    if args.block_size < 16:
        raise SystemExit("--block-size must be at least 16")
    set_seed(args.seed)

    try:
        import torch
        from datasets import load_dataset
        from transformers import (
            AutoModelForCausalLM,
            AutoTokenizer,
            DataCollatorForLanguageModeling,
            Trainer,
            TrainingArguments,
        )
    except ImportError as exc:
        raise SystemExit("Training dependencies are missing. Install torch, transformers, datasets, and accelerate before training.") from exc

    has_cuda = torch.cuda.is_available()
    use_bf16 = bool(has_cuda and torch.cuda.is_bf16_supported())
    use_fp16 = bool(has_cuda and not use_bf16)
    print(f"Device: {'cuda' if has_cuda else 'cpu'}")
    print(f"Mixed precision: {'bf16' if use_bf16 else 'fp16' if use_fp16 else 'disabled'}")
    print(f"Model: {args.model_name}")
    print(f"Train file: {train_path}")
    print(f"Validation file: {validation_path}")

    tokenizer = AutoTokenizer.from_pretrained(args.model_name, trust_remote_code=args.trust_remote_code)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    raw = load_dataset("text", data_files={"train": str(train_path), "validation": str(validation_path)})

    def tokenize(batch):
        return tokenizer(batch["text"], add_special_tokens=True, truncation=False)

    tokenized = raw.map(tokenize, batched=True, remove_columns=["text"], desc="Tokenizing corpus")
    block_size = min(args.block_size, tokenizer.model_max_length if tokenizer.model_max_length < 100000 else args.block_size)

    def group_texts(batch):
        concatenated = {key: sum(batch[key], []) for key in batch}
        total_length = (len(concatenated["input_ids"]) // block_size) * block_size
        result = {key: values[:total_length] for key, values in concatenated.items()}
        result["labels"] = list(result["input_ids"])
        return {key: [values[i : i + block_size] for i in range(0, total_length, block_size)] for key, values in result.items()}

    tokenized = tokenized.map(group_texts, batched=True, desc=f"Grouping tokens into blocks of {block_size}")
    print(f"Token blocks: train={len(tokenized['train'])}, validation={len(tokenized['validation'])}")
    if args.dry_run:
        print("Dry run completed; no model weights were downloaded and no training was started.")
        return

    model = AutoModelForCausalLM.from_pretrained(args.model_name, trust_remote_code=args.trust_remote_code)
    model.resize_token_embeddings(len(tokenizer))
    model.config.pad_token_id = tokenizer.pad_token_id
    collator = DataCollatorForLanguageModeling(tokenizer=tokenizer, mlm=False)
    training_args = build_training_args(TrainingArguments, args, checkpoint_dir, use_fp16, use_bf16)
    trainer_kwargs = {
        "model": model,
        "args": training_args,
        "train_dataset": tokenized["train"],
        "eval_dataset": tokenized["validation"],
        "data_collator": collator,
    }
    # Transformers renamed Trainer.tokenizer to Trainer.processing_class in
    # newer releases. Detect the installed API instead of pinning the user to
    # one library version.
    trainer_parameters = inspect.signature(Trainer.__init__).parameters
    if "processing_class" in trainer_parameters:
        trainer_kwargs["processing_class"] = tokenizer
    elif "tokenizer" in trainer_parameters:
        trainer_kwargs["tokenizer"] = tokenizer
    trainer = Trainer(**trainer_kwargs)
    checkpoint = args.resume_from_checkpoint or None
    trainer.train(resume_from_checkpoint=checkpoint)
    output_dir.mkdir(parents=True, exist_ok=True)
    trainer.save_model(str(output_dir))
    tokenizer.save_pretrained(str(output_dir))
    metrics = trainer.evaluate()
    run_manifest = {
        "model_name": args.model_name,
        "dataset_version": args.dataset_version,
        "train_file": str(train_path),
        "validation_file": str(validation_path),
        "block_size": block_size,
        "epochs": args.epochs,
        "train_batch_size": args.train_batch_size,
        "gradient_accumulation_steps": args.gradient_accumulation_steps,
        "learning_rate": args.learning_rate,
        "seed": args.seed,
        "device": "cuda" if has_cuda else "cpu",
        "mixed_precision": "bf16" if use_bf16 else "fp16" if use_fp16 else "disabled",
        "metrics": metrics,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    (output_dir / "training_manifest.json").write_text(json.dumps(run_manifest, indent=2, default=str) + "\n", encoding="utf-8")
    print(f"Saved model and tokenizer to: {output_dir}")
    print(json.dumps(metrics, indent=2, default=str))


if __name__ == "__main__":
    main()
