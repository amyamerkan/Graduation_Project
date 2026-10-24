from __future__ import annotations

import json
import re
from importlib.resources import files
from typing import Any


def build_messages(question: str, evidence: list[dict[str, Any]]) -> list[dict[str, str]]:
    template_dir = files("vn_assistant").joinpath("prompt_templates")
    system = template_dir.joinpath("system.txt").read_text(encoding="utf-8")
    template = template_dir.joinpath("select_claims.txt").read_text(encoding="utf-8")
    candidates = [{"claim_id": claim["claim_id"], "text": claim["text"], "kind": entry["kind"]}
                  for entry in evidence for claim in entry["allowed_claims"]]
    values = {"question_json": json.dumps(question, ensure_ascii=False),
              "candidates_json": json.dumps(candidates, ensure_ascii=False, separators=(",", ":"))}
    user = re.sub(r"\{\{(question_json|candidates_json)\}\}", lambda match: values[match.group(1)], template)
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]
