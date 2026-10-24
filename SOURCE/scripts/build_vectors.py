"""Resumable Transformer index build; writes progress every 30 seconds."""
import argparse
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
# Use the already downloaded E5 checkpoint; no model download is necessary.
os.environ.setdefault('HF_HUB_OFFLINE', '1')
os.environ.setdefault('TRANSFORMERS_OFFLINE', '1')

from vn_assistant.embedding import EmbeddingConfig
from vn_assistant.faiss_store import build_faiss_index

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--dataset', default='data/rag_dataset_final.jsonl')
    parser.add_argument('--output', type=Path, default=Path('artifacts/faiss'))
    parser.add_argument('--device', default='mps')
    parser.add_argument('--batch-size', type=int, default=16)
    parser.add_argument('--limit-documents', type=int, default=0)
    args = parser.parse_args()
    report = build_faiss_index(args.dataset, args.output / 'vn.index', args.output / 'metadata.sqlite3',
                               args.output / 'index_config.json',
                               EmbeddingConfig(device=args.device, batch_size=args.batch_size),
                               limit_documents=args.limit_documents)
    print(json.dumps(report, ensure_ascii=False, indent=2))
