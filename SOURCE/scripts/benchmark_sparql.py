"""Compare scan/filter and bound code lookup on the same graph and result set."""
import json
from pathlib import Path
import statistics
import sys
import time
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from vn_assistant.sparql_service import SparqlService

service = SparqlService('artifacts/kg/vn_knowledge_graph.ttl', 'queries')
optimized = service.render_query('03_unit_by_code', {'code': '00070'})
baseline = optimized.replace('  VALUES ?code { "00070" }\n  ?unit vn:code ?code ; a ?type ; vn:name ?name .',
                             '  ?unit a ?type ; vn:name ?name ; vn:code ?code .\n  FILTER(STR(?code) = "00070")')
report = {'query': '03_unit_by_code', 'code': '00070', 'runs': 5, 'method': 'same graph, one warmup per variant, then alternating runs; includes parsing'}
results = {}
times = {key: [] for key in ('baseline', 'optimized')}
for key, query in [('baseline', baseline), ('optimized', optimized)]:
    results[key] = sorted(tuple(str(x) if x is not None else '' for x in row) for row in service.graph.query(query))
assert results['baseline'] == results['optimized']
for _ in range(5):
    for key, query in [('baseline', baseline), ('optimized', optimized)]:
        start = time.perf_counter()
        list(service.graph.query(query))
        times[key].append((time.perf_counter() - start) * 1000)
report.update({key + '_median_ms': statistics.median(values) for key, values in times.items()})
report['same_results'] = True
report['speedup'] = report['baseline_median_ms'] / report['optimized_median_ms']
Path('artifacts/kg/sparql_benchmark.json').write_text(json.dumps(report, indent=2))
print(json.dumps(report, indent=2))
