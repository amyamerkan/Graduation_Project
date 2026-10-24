from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

from vn_assistant.config import SETTINGS
from vn_assistant.embedding import EmbeddingConfig
from vn_assistant.index_recovery import recover_index


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", default="mps")
    parser.add_argument("--batch-size", type=int, default=32)
    args = parser.parse_args()
    saved = json.loads((SETTINGS.faiss_index_path.parent / "index_config.json").read_text())
    config = EmbeddingConfig(**{**saved["embedding"], "device": args.device, "batch_size": args.batch_size})
    report = recover_index(SETTINGS.faiss_metadata_path, SETTINGS.faiss_index_path, config)
    (SETTINGS.faiss_index_path.parent / "recovery_report.json").write_text(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
