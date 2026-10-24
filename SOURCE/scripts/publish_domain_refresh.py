"""Publish a tested corpus release, retaining a recoverable previous active version."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import sqlite3

from vn_assistant.dataio import iter_records
from vn_assistant.domain_scope import contains_intangible


def publish(root, release):
    root, release = Path(root).resolve(), Path(release).resolve()
    backend = json.loads((release / "backend_evaluation_final.json").read_text())
    training = json.loads((release / "training_report.json").read_text())
    if not backend["passed"] or training["kg_evaluation"]["accuracy"] != 1:
        raise ValueError("Release has not passed its backend/KG evaluation")
    # The standard local service must be stopped; the staging API uses port 8005.
    with socket.socket() as probe:
        if probe.connect_ex(("127.0.0.1", 8001)) == 0:
            raise ValueError("Stop the local service on port 8001 before publishing")
    rows = list(iter_records(release / "data/structured_records.jsonl"))
    new_ids = {r["record_id"] for r in rows}
    old_destinations = {r["record_id"] for r in iter_records(root / "data/structured_records.jsonl") if r.get("domain") == "tourism"}
    if not old_destinations.issubset(new_ids):
        raise ValueError("Release removed an existing visitor destination")
    if any(contains_intangible(json.dumps(r["data"], ensure_ascii=False)) for r in rows):
        raise ValueError("Excluded subject remains in active corpus")
    with sqlite3.connect(release / "artifacts/faiss/metadata.sqlite3") as connection:
        if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("Invalid metadata")
        if any(contains_intangible(text) for (text,) in connection.execute("SELECT text FROM chunks")):
            raise ValueError("Excluded subject remains in search metadata")
    previous = release.parent / "previous"
    if previous.exists():
        raise ValueError("Previous-version backup already exists; refusing to overwrite it")
    previous.mkdir()
    replacements = []
    pairs = [(Path("data") / name, False) for name in ["structured_records.jsonl", "rag_dataset_final.jsonl", "router_training.csv"]]
    pairs += [(Path("artifacts") / name, True) for name in ["kg", "router", "faiss"]]
    try:
        for relative, directory in pairs:
            source, target, backup = release / relative, root / relative, previous / relative
            temporary = target.with_name("." + target.name + ".refresh")
            if temporary.exists():
                raise ValueError("Stale publication path " + str(temporary))
            if directory:
                shutil.copytree(source, temporary)
            else:
                shutil.copy2(source, temporary)
            backup.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                os.replace(target, backup)
            replacements.append((target, backup))
            os.replace(temporary, target)
    except BaseException:
        for target, backup in reversed(replacements):
            if target.is_dir():
                shutil.rmtree(target)
            elif target.exists():
                target.unlink()
            if backup.exists():
                os.replace(backup, target)
        raise
    result = {"published_at": datetime.now(timezone.utc).isoformat(), "release": str(release),
              "documents": len(rows), "preserved_previous_destinations": len(old_destinations),
              "active_rag_sha256": hashlib.sha256((root / "data/rag_dataset_final.jsonl").read_bytes()).hexdigest(),
              "previous_version": str(previous), "previous_version_policy": "Inactive rollback copy; never training/retrieval input"}
    (release / "publication_report.json").write_text(json.dumps(result, ensure_ascii=False, indent=2))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--release", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(publish(args.root, args.release), ensure_ascii=False, indent=2))
