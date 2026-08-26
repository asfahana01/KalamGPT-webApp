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