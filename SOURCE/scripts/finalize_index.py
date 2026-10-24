"""Finish validation as soon as the currently running index build publishes its files."""
import json
from pathlib import Path
import time
from evaluate_retrieval import run
from verify_pipeline import verify

index_dir = Path('artifacts/faiss')
status_path = index_dir / 'validation_status.json'

def save(state, **details):
    temp = status_path.with_suffix('.tmp')
    temp.write_text(json.dumps({'state':state, **details}, ensure_ascii=False, indent=2))
    temp.replace(status_path)

if __name__ == '__main__':
    save('waiting_for_index')
    try:
        while True:
            path = index_dir / 'build_progress.json'
            progress = json.loads(path.read_text()) if path.exists() else {}
            if progress.get('status') == 'complete':
                break
            if progress.get('status') == 'interrupted':
                raise RuntimeError('Index build interrupted; rerun scripts/build_vectors.py and this script.')
            time.sleep(30)
        save('validating')
        integration = verify(index_dir)
        retrieval = run(full_index=index_dir)
        pipeline_path = Path('artifacts/pipeline_report.json')
        pipeline = json.loads(pipeline_path.read_text()) if pipeline_path.exists() else {}
        for key, path in {
            'kg_evaluation': Path('artifacts/kg/evaluation_report.json'),
            'router_evaluation': Path('artifacts/router/evaluation_report.json'),
            'faiss': index_dir / 'index_config.json',
            'sparql_benchmark': Path('artifacts/kg/sparql_benchmark.json'),
            'embedding_ablation': Path('artifacts/evaluation/embedding_ablation.json'),
        }.items():
            if path.exists(): pipeline[key] = json.loads(path.read_text())
        pipeline.update(status='complete', integration=integration, retrieval_evaluation=retrieval)
        pipeline_path.write_text(json.dumps(pipeline, ensure_ascii=False, indent=2))
        save('complete', integration=integration, retrieval_metrics=retrieval['metrics'],
             limitation='Retrieval gold is a small development set with known positives, not an independently labelled benchmark.')
    except BaseException as exc:
        save('failed', error=f'{type(exc).__name__}: {exc}')
        raise
