from __future__ import annotations

from collections import OrderedDict
import json
import os
from pathlib import Path
import re
import sqlite3
import threading
import time

import numpy as np

from .embedding import EmbeddingConfig, create_encoder
from .normalization import clean_text


def prepare_lexical_index(metadata_path, output_path) -> dict:
    metadata_path, output_path = Path(metadata_path).resolve(), Path(output_path).resolve()
    manifest_path = output_path.with_suffix(".json")
    stat = metadata_path.stat()
    signature = {"metadata_size": stat.st_size, "metadata_mtime_ns": stat.st_mtime_ns, "format": 1}
    if output_path.is_file() and manifest_path.is_file():
        report = json.loads(manifest_path.read_text())
        if report.get("signature") == signature:
            return report
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_suffix(".building.sqlite3")
    temporary.unlink(missing_ok=True)
    start = time.monotonic()
    with sqlite3.connect(metadata_path.as_uri() + "?mode=ro&immutable=1", uri=True) as source, sqlite3.connect(temporary) as target:
        target.execute("CREATE VIRTUAL TABLE passages USING fts5(text,title,content='',tokenize='unicode61 remove_diacritics 2')")
        cursor = source.execute("SELECT vector_id,text,title FROM chunks ORDER BY vector_id")
        count = 0
        while rows := cursor.fetchmany(4096):
            target.executemany("INSERT INTO passages(rowid,text,title) VALUES(?,?,?)", rows)
            count += len(rows)
        target.commit()
        target.execute("INSERT INTO passages(passages) VALUES('optimize')")
        target.commit()
    os.replace(temporary, output_path)
    report = {"signature": signature, "passages": count, "elapsed_seconds": round(time.monotonic() - start, 3)}
    manifest_path.write_text(json.dumps(report, indent=2))
    return report


class MetadataFaissRetriever:
    def __init__(self, metadata_path, embedding_config: EmbeddingConfig, candidate_count=48, backend="transformer"):
        self.metadata_path = Path(metadata_path).resolve()
        self.lexical_path = self.metadata_path.parent / "lexical.sqlite3"
        self.candidate_count = candidate_count
        self._lock = threading.RLock()
        self._encoder = None
        self.embedding_config = embedding_config
        self.backend = backend
        self.mode = "lexical_candidates_faiss"
        self._prepared = False
        self._vectors = OrderedDict()

    @property
    def encoder(self):
        with self._lock:
            if self._encoder is None:
                self._encoder = create_encoder(self.embedding_config, backend=self.backend)
            return self._encoder

    def warmup(self):
        with self._lock:
            report = prepare_lexical_index(self.metadata_path, self.lexical_path)
            self._prepared = True
            _ = self.encoder
            return report

    def search(self, query, top_k=5, domain=None, *, doc_ids=None, entity_terms=None):
        if type(top_k) is not int or not 1 <= top_k <= 100:
            raise ValueError("top_k phải nằm trong [1, 100]")
        if doc_ids is not None and not doc_ids and not entity_terms or entity_terms is not None and not entity_terms and not doc_ids:
            return []
        tokens = list(dict.fromkeys(re.findall(r"\w+", clean_text(query).casefold())))[:24]
        stop = {"là", "gì", "nào", "của", "và", "có", "cho", "biết", "hãy", "thì", "những", "các", "như", "thế", "mình", "tôi"}
        tokens = [word for word in tokens if word not in stop and len(word) > 1]
        if not tokens:
            return []
        conditions = ["passages MATCH ?"]
        values = [" OR ".join('"' + word.replace('"', '""') + '"' for word in tokens)]
        if domain:
            conditions.append("c.domain = ?")
            values.append(domain)
        scope = []
        if doc_ids:
            if len(doc_ids) > 1000:
                raise ValueError("Bộ lọc tài liệu vượt giới hạn")
            scope.append("c.doc_id IN (" + ",".join("?" for _ in doc_ids) + ")")
            values.extend(doc_ids)
        if entity_terms:
            if len(entity_terms) > 100:
                raise ValueError("Bộ lọc thực thể vượt giới hạn")
            for term in entity_terms:
                scope.append("(instr(unicode_fold(c.title),?)>0 OR instr(unicode_fold(c.text),?)>0)")
                values.extend([str(term).casefold()] * 2)
            if not doc_ids:
                phrases = ' OR '.join('"' + clean_text(term).replace('"', '""') + '"' for term in entity_terms if clean_text(term))
                if phrases:
                    values[0] = "(" + values[0] + ") AND (" + phrases + ")"
        if scope:
            conditions.append("(" + " OR ".join(scope) + ")")
        with self._lock:
            if not self._prepared:
                prepare_lexical_index(self.metadata_path, self.lexical_path)
                self._prepared = True
            with sqlite3.connect(self.lexical_path.resolve().as_uri() + "?mode=ro&immutable=1", uri=True) as connection:
                connection.create_function("unicode_fold", 1, lambda value: (value or "").casefold(), deterministic=True)
                connection.execute("ATTACH DATABASE ? AS corpus", (self.metadata_path.as_uri() + "?mode=ro&immutable=1",))
                connection.row_factory = sqlite3.Row
                sql = "SELECT c.* FROM passages JOIN corpus.chunks c ON c.vector_id=passages.rowid WHERE " + " AND ".join(conditions)
                sql += " ORDER BY bm25(passages,1.0,3.0) LIMIT ?"
                rows = [dict(row) for row in connection.execute(sql, [*values, max(self.candidate_count, top_k)])]
            if not rows:
                return []
            import faiss

            missing = [row for row in rows if row["vector_id"] not in self._vectors]
            if missing:
                encoded = self.encoder.encode_passages([row["text"] for row in missing])
                for row, vector in zip(missing, encoded):
                    self._vectors[row["vector_id"]] = np.asarray(vector, dtype="float32")
            vectors = np.asarray([self._vectors[row["vector_id"]] for row in rows], dtype="float32")
            while len(self._vectors) > 4096:
                self._vectors.popitem(last=False)
            faiss.normalize_L2(vectors)
            question = np.asarray(self.encoder.encode_queries([query]), dtype="float32")
            faiss.normalize_L2(question)
            index = faiss.IndexFlatIP(vectors.shape[1])
            index.add(vectors)
            scores, indices = index.search(question, min(top_k, len(rows)))
            return [{**rows[int(position)], "score": float(score), "retrieval_mode": self.mode,
                     "candidate_count": len(rows)} for score, position in zip(scores[0], indices[0]) if position >= 0]
