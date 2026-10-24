from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from huggingface_hub import snapshot_download

from vn_assistant.config import WORKSPACE_ROOT


MODELS = {
    "qwen": ("Qwen/Qwen3-0.6B", "c1899de289a04d12100db370d81485cdf75e47ca"),
    "e5": ("intfloat/multilingual-e5-base", "d128750597153bb5987e10b1c3493a34e5a4502a"),
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", choices=["qwen", "e5", "all"], default="all")
    args = parser.parse_args()
    names = list(MODELS) if args.models == "all" else [args.models]
    for name in names:
        model, revision = MODELS[name]
        folder = WORKSPACE_ROOT / "models/Qwen3-0.6B" if name == "qwen" else None
        snapshot = snapshot_download(model, revision=revision, local_dir=folder,
                                     allow_patterns=["*.safetensors", "*.json", "*.txt", "*.model", "*.jinja"],
                                     ignore_patterns=["onnx/*", "openvino/*"], max_workers=2)
        manifest = {"model_id": model, "revision": revision, "snapshot": str(Path(snapshot).resolve()),
                    "downloaded_at": datetime.now(timezone.utc).isoformat()}
        report_dir = WORKSPACE_ROOT / "artifacts/backend"
        report_dir.mkdir(parents=True, exist_ok=True)
        (report_dir / f"{name}_model_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        print(json.dumps(manifest, ensure_ascii=False))


if __name__ == "__main__":
    main()
