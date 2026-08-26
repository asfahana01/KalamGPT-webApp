python training/prepare_dataset.py --version v1 
{
  "corpus_version": "v1",
  "created_at_utc": "2026-08-26T06:34:35.958004+00:00",
  "catalog_path": "C:\\Users\\hanaa\\OneDrive\\Desktop\\GitHub\\KalamGPT\\data\\kalam\\catalog\\dataset_catalog.csv",
  "source_count": 422,
  "accepted_documents": 419,
  "rejected_documents": {
    "text_quality": 3
  },
  "accepted_words": 1377879,
  "accepted_characters": 8580914,
  "source_type_counts": {
    "speech": 410,
    "book_or_document": 8,
    "speech_or_transcript": 1
  }
}
Processed corpus written to: C:\Users\hanaa\OneDrive\Desktop\GitHub\KalamGPT\data\kalam\processed\v1



python training/split_dataset.py --version v1 
{
  "dataset_version": "v1",
  "seed": "kalam-gpt-v1",
  "ratios_requested": {
    "train": 0.85,
    "validation": 0.1,
    "test": 0.05000000000000002
  },
  "document_count": 419,
  "split_counts": {
    "train": 363,
    "validation": 36,
    "test": 20
  },
  "split_word_counts": {
    "train": 1193751,
    "validation": 138397,
    "test": 45731
  },
  "files": {
    "train": {
      "text": "train.txt",
      "metadata": "train.jsonl"
    },
    "validation": {
      "text": "validation.txt",
      "metadata": "validation.jsonl"
    },
    "test": {
      "text": "test.txt",
      "metadata": "test.jsonl"
    }
  }
}
Datasets written to: C:\Users\hanaa\OneDrive\Desktop\GitHub\KalamGPT\data\kalam\datasets\v1


## Instruction-tuning dataset

Pilot candidates are not used automatically. Review each record in `data/kalam/datasets/pilot_candidates.jsonl` and change `review_status` from `pending` to `approved` only after checking relevance, source references, originality, and quotation safety.

Build the approved instruction dataset with:

```bash
python training/prepare_instruction_dataset.py --version v1
```

The script writes `instruction.jsonl`, `instruction.txt`, and a manifest under `data/kalam/datasets/instruction/v1/`. If no candidates are approved, it stops intentionally so pending examples cannot enter training by mistake.

## Evaluation outputs

After a model has been trained, generate reproducible outputs for the layer evaluation prompts:

```bash
python training/evaluate_model.py \\
  --model-path models/kalam-gpt2-v1 \\
  --output models/kalam-gpt2-v1/evaluation_outputs.jsonl
```

The evaluation file includes empty human-review fields for relevance, coherence, factual grounding, Kalam-inspired tone, repetition, quotation safety, and notes. It is an evaluation record, not an automatic accuracy percentage.


The instruction builder also creates disjoint files for training and validation:

```text
data/kalam/datasets/instruction/v1/
├── instruction.jsonl       # complete approved set
├── train.jsonl             # used for training
├── validation.jsonl        # held out for validation
├── instruction.txt
├── train.txt
├── validation.txt
└── manifest.json
```

Run instruction-mode fine-tuning into a separate model directory so the raw-corpus baseline is preserved:

```bash
python training/train_gpt2.py \\
  --training-mode instruction \\
  --dataset-version v1 \\
  --model-name gpt2 \\
  --epochs 1 \\
  --output-dir models/kalam-gpt2-instruction-v1 \\
  --checkpoint-dir models/kalam-gpt2-instruction-v1/checkpoints
```

With only four approved examples, use this only as a pipeline test. Expand the approved dataset substantially before treating the resulting model as an improvement.
