#!/usr/bin/env python3
"""Run KalamGPT evaluation prompts and save outputs for human scoring.

This script deliberately does not claim an automatic accuracy score. It saves
prompt, model output, and rubric fields so responses can be reviewed.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-path", type=Path, required=True)
    parser.add_argument("--prompts", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--max-new-tokens", type=int, default=120)
    parser.add_argument("--temperature", type=float, default=0.7)
    parser.add_argument("--top-p", type=float, default=0.9)
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    prompts_path = (args.prompts or repo_root / "data" / "kalam" / "evals" / "layer_eval_prompts.json").resolve()
    output_path = (args.output or args.model_path / "evaluation_outputs.jsonl").resolve()
    if not args.model_path.is_dir():
        raise SystemExit(f"Model directory not found: {args.model_path}")
    if not prompts_path.is_file():
        raise SystemExit(f"Prompt file not found: {prompts_path}")
    try:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except ImportError as exc:
        raise SystemExit("Install torch and transformers before evaluation.") from exc

    prompts = json.loads(prompts_path.read_text(encoding="utf-8"))
    tokenizer = AutoTokenizer.from_pretrained(args.model_path)
    model = AutoModelForCausalLM.from_pretrained(args.model_path)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model.to(device)
    model.eval()
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    torch.manual_seed(args.seed)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with output_path.open("w", encoding="utf-8") as handle:
        for layer, layer_prompts in prompts.items():
            for prompt in layer_prompts:
                formatted_prompt = f"You are KalamGPT, an AI inspired by Dr. A.P.J. Abdul Kalam. You are not Dr. Kalam.\n\nUser: {prompt}\nAssistant:"
                inputs = tokenizer(formatted_prompt, return_tensors="pt", truncation=True, max_length=900).to(device)
                with torch.no_grad():
                    output_ids = model.generate(
                        **inputs,
                        max_new_tokens=args.max_new_tokens,
                        temperature=args.temperature,
                        top_p=args.top_p,
                        repetition_penalty=1.3,
                        do_sample=True,
                        pad_token_id=tokenizer.eos_token_id,
                        eos_token_id=tokenizer.eos_token_id,
                    )
                generated = tokenizer.decode(output_ids[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True).strip()
                record = {
                    "layer": layer,
                    "prompt": prompt,
                    "response": generated,
                    "model_path": str(args.model_path),
                    "created_at_utc": datetime.now(timezone.utc).isoformat(),
                    "human_review": {
                        "relevance_1_to_5": None,
                        "coherence_1_to_5": None,
                        "factual_grounding_1_to_5": None,
                        "kalam_inspired_tone_1_to_5": None,
                        "repetition_1_to_5": None,
                        "safe_no_fabricated_quote": None,
                        "notes": "",
                    },
                }
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
                print(f"[{layer}] {prompt}\n{generated}\n{'-' * 80}")
                count += 1
    print(f"Wrote {count} evaluation records to: {output_path}")


if __name__ == "__main__":
    main()
