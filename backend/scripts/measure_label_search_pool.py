#!/usr/bin/env python3
"""Measure demo-query recall and warm label-search latency without changing the service.

Run from any directory with backend/.venv/bin/python. Translations are deliberately
excluded, matching the default service setting. Times complete production service
calls with only the raw limit overridden. Warm includes folio-python's built-in
_basic_search memoization; this is not a first-time-query latency benchmark.

Primary comparisons use fixed P=20 as requested; top_k=10 also compares to P=40. Production's current expression
already requests P=40 at top_k=10. folio-python 0.4.0 sets no score_cutoff;
the supplemental pool-cutoff crowding metric is not a configured threshold.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import math
import logging.handlers
import tempfile
from unittest.mock import patch
from pathlib import Path
import statistics
import sys
import time

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
sys.path.insert(0, str(BACKEND))
from rapidfuzz import fuzz, utils
from app.services.folio.folio_service import FolioService, _construct_folio
from app.services.folio.labels import true_alternative_labels
from app.config import settings
from app.services.ontology.spec import FOLIO_SPEC

POOLS = (20, 40, 80, 160)
KS = (3, 5, 10)


def queries_from_demos():
    queries = {}
    files = []
    for path in sorted((ROOT / 'frontend/demos').rglob('*.json')):
        data = json.loads(path.read_text())
        result = data.get('cache', {}).get('job', {}).get('result') or {}
        relative = str(path.relative_to(ROOT))
        files.append({'path': relative, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                      'ontology_id': result.get('ontology_id')})
        def add(text, source):
            if isinstance(text, str) and text.strip():
                text = text.strip()
                entry = queries.setdefault(text.casefold(), {'query': text, 'sources': []})
                provenance = {'file': relative, 'field': source}
                if provenance not in entry['sources']:
                    entry['sources'].append(provenance)
        for chunk in result.get('metadata', {}).get('llm_concepts', {}).values():
            for concept in chunk:
                add(concept.get('concept_text'), 'metadata.llm_concepts[].concept_text')
        for annotation in result.get('annotations', []):
            add(annotation.get('span', {}).get('text'), 'annotations[].span.text')
            for concept in annotation.get('concepts', []):
                add(concept.get('concept_text'), 'annotations[].concepts[].concept_text')
    return [queries[key] for key in sorted(queries)], files


def rescore(folio, query, raw):
    results = []
    for concept, raw_score in raw:
        labels = [getattr(concept, 'label', None), getattr(concept, 'preferred_label', None),
                  *true_alternative_labels(folio, concept)]
        score = max((fuzz.WRatio(query, candidate, processor=utils.default_process)
                     for candidate in labels if candidate), default=0)
        results.append((concept, score, raw_score))
    results.sort(key=lambda hit: hit[1], reverse=True)
    return results


def hit_json(hit):
    concept, score, raw_score = hit
    return {'iri': concept.iri, 'label': concept.label or concept.preferred_label,
            'score': score, 'raw_score': raw_score}


def percentile95(values):
    return sorted(values)[math.ceil(.95 * len(values)) - 1]


def top_k_improvements(queries, pool, k, baseline_pool):
    """Count queries admitting a new concept strictly above the baseline kth score.

    Existing baseline concepts do not count: otherwise identical pools would
    score improvements merely because their first hit exceeds their last hit.
    Ranks are one-based in the larger pool; old is the hit at the same rank.
    """
    count = 0
    examples = []
    for entry in queries:
        old = entry['pools'][str(baseline_pool)]['top_k'][str(k)]
        new = entry['pools'][str(pool)]['top_k'][str(k)]
        if not old:
            continue
        old_iris = {hit['iri'] for hit in old}
        improved = [(rank, hit) for rank, hit in enumerate(new, 1)
                    if hit['iri'] not in old_iris and hit['score'] > old[-1]['score']]
        count += bool(improved)
        if improved and len(examples) < 10:
            rank, hit = improved[0]
            examples.append({'query': entry['query'], 'k': k, 'rank': rank,
                             'old': old[rank - 1] if rank <= len(old) else None,
                             'new': hit, 'baseline_cutoff': old[-1],
                             'baseline_cutoff_score': old[-1]['score']})
    return {'baseline_pool': baseline_pool, 'query_count': count, 'examples': examples}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path,
                        default=BACKEND / 'eval/results/label_search_pool_2026-11-08.json')
    args = parser.parse_args()
    queries, files = queries_from_demos()
    print(f'{len(queries)} case-insensitive unique queries from {len(files)} demos', flush=True)
    # alea-llm-client opens a home-directory log at import time. Redirect only
    # that handler so this offline receipt also works in a read-only home sandbox.
    handler = logging.handlers.RotatingFileHandler
    with tempfile.TemporaryDirectory(prefix='label-pool-') as log_dir:
        def local_handler(filename, *a, **kw):
            if str(filename).endswith('/.alea/logs/alea_llm_client.log'):
                filename = str(Path(log_dir) / 'alea_llm_client.log')
            return handler(filename, *a, **kw)
        with patch('logging.handlers.RotatingFileHandler', local_handler):
            from folio import FOLIO
            # Use production's branch for both cache identity and construction;
            # folio-python's default branch is a different ontology snapshot.
            repo_branch = FOLIO_SPEC.coords.repo_branch
            owl = FOLIO.load_cache(github_repo_branch=repo_branch)
            if not owl:
                raise RuntimeError(f'FOLIO OWL cache for production branch {repo_branch!r} is absent or empty; '
                                   'populate that branch cache first; refusing fallback or network access')
            # load_owl otherwise rewrites even a cache hit in the read-only home.
            with patch.object(FOLIO, 'load_owl', return_value=owl):
                folio = _construct_folio(github_repo_branch=repo_branch)
    service = FolioService()
    service._folio = folio
    # Build the same branch map as production before warming conversion.
    service._build_branch_map()
    settings.translation_matching_enabled = False
    raw_search = folio.search_by_label
    print('Warm-up: all queries and all pools', flush=True)
    for i, entry in enumerate(queries):
        for pool in POOLS:
            ranked = rescore(folio, entry['query'], folio.search_by_label(
                entry['query'], include_alt_labels=True, limit=pool))
            for concept, _, _ in ranked[:10]:
                service._to_folio_concept(concept)
        if (i + 1) % 100 == 0:
            print(f'  warmed {i + 1}/{len(queries)}', flush=True)
    timings = {(p, k): [] for p in POOLS for k in KS}
    crowding = {'raw_hits': 0, 'below_pool_cutoff': 0, 'below_own_raw_score': 0}
    print('Measurement: rotating pool and conversion order per query', flush=True)
    for i, entry in enumerate(queries):
        query = entry['query']
        entry['pools'] = {}
        for pool in POOLS[i % 4:] + POOLS[:i % 4]:
            raw = raw_search(query, include_alt_labels=True, limit=pool)
            ranked = rescore(folio, query, raw)
            elapsed = {}
            # Patch outside the timer; exercise the full production method unchanged.
            def forced_pool(label, include_alt_labels=True, limit=20):
                return raw_search(label, include_alt_labels=include_alt_labels, limit=pool)
            with patch.object(folio, 'search_by_label', forced_pool):
                for k in KS[i % 3:] + KS[:i % 3]:
                    start = time.perf_counter_ns()
                    converted = service.search_by_label(query, top_k=k)
                    elapsed[k] = (time.perf_counter_ns() - start) / 1e6
                    timings[pool, k].append(elapsed[k])
                    assert [(c.iri, s) for c, s in converted] == [(c.iri, s) for c, s, _ in ranked[:k]]
            entry['pools'][str(pool)] = {
                'raw_count': len(raw), 'top_k': {str(k): [hit_json(h) for h in ranked[:k]] for k in KS},
                'elapsed_ms': elapsed,
            }
            if pool == 20 and raw:
                cutoff = min(s for _, s in raw)
                counts = {'raw_hits': len(raw),
                          'below_pool_cutoff': sum(s < cutoff for _, s, _ in ranked),
                          'below_own_raw_score': sum(s < r for _, s, r in ranked)}
                entry['crowding'] = {**counts, 'pool_cutoff': cutoff}
                for key, value in counts.items():
                    crowding[key] += value
        if (i + 1) % 100 == 0:
            print(f'  measured {i + 1}/{len(queries)}', flush=True)
    metrics = []
    examples = []
    for pool in POOLS:
        for k in KS:
            changed1 = changed_set = rescues = 0
            improvements = []
            for entry in queries:
                old = entry['pools']['20']['top_k'][str(k)]
                new = entry['pools'][str(pool)]['top_k'][str(k)]
                changed = (old[0]['iri'] if old else None) != (new[0]['iri'] if new else None)
                changed1 += changed
                changed_set += {h['iri'] for h in old} != {h['iri'] for h in new}
                old_score, new_score = (old[0]['score'] if old else 0), (new[0]['score'] if new else 0)
                improvements.append(new_score - old_score)
                rescues += old_score < 90 <= new_score
                if changed and k == 3:
                    examples.append({'pool': pool, 'query': entry['query'], 'old': old[0] if old else None,
                                     'new': new[0] if new else None,
                                     'rescue': old_score < 90 <= new_score})
            times = timings[pool, k]
            baseline = statistics.median(timings[20, k])
            metrics.append({'pool': pool, 'top_k': k, 'top1_changes': changed1,
                            'top_k_set_changes': changed_set,
                            'mean_top1_improvement': statistics.mean(improvements),
                            'max_top1_improvement': max(improvements), 'rescues': rescues,
                            'rescue_fraction': rescues / len(queries),
                            'median_ms': statistics.median(times), 'p95_ms': percentile95(times),
                            'median_ratio_vs_20': statistics.median(times) / baseline,
                            'below_top1_improvement': top_k_improvements(queries, pool, k, 20)})
            if k == 10:
                metrics[-1]['vs_production_pool'] = {
                    'pool': max(k * 4, 20),
                    'below_top1_improvement': top_k_improvements(queries, pool, k, max(k * 4, 20)),
                }
    for key in ('below_pool_cutoff', 'below_own_raw_score'):
        crowding[key + '_fraction'] = crowding[key] / crowding['raw_hits']
    output = {'repo_branch': repo_branch, 'owl_sha256': hashlib.sha256(owl.encode()).hexdigest(), 'query_count': len(queries), 'demo_files': files, 'folio_python_version':
              importlib.metadata.version('folio-python'), 'translation_matching_enabled': False,
              'threshold_note': 'No configured cutoff: process.extract defaults to score_cutoff=None (effective 0). '
              'below_pool_cutoff uses min returned raw score for each query; below_own_raw_score identifies '
              'hits whose library score cannot be achieved by a true label.',
              'timing_note': 'One warm-up pass across every query/pool, then one measured pass; '
              'perf_counter_ns, rotating pool order; raw search + true-label rescore + production conversion '
              'for each k through the unmodified service, forcing only raw limit; normal warmed branch map; '
              'no network, LLM or ontology load in timing. Library _basic_search memoization is warm.',
              'below_top1_note': 'Queries with a concept newly admitted to top_k whose score strictly exceeds '
              'the baseline top_k minimum; includes admissions at any rank, not just top-1 changes. '
              'Count each query once; up to 10 examples per row, first qualifying rank per query. '
              'P=20 is the primary baseline; top_k=10 also compares to production P=40. '
              'P=20 vs P=40 is a smaller-pool control, not a larger-pool comparison.',
              'metrics': metrics, 'crowding': crowding, 'changed_top1s': examples, 'queries': queries}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2) + '\n')
    print(' P   k  top1  setΔ  meanΔ  maxΔ rescues median_ms p95_ms ratio below_top1 vs_P40')
    for m in metrics:
        print(f"{m['pool']:3} {m['top_k']:3} {m['top1_changes']:5} {m['top_k_set_changes']:5} "
              f"{m['mean_top1_improvement']:6.3f} {m['max_top1_improvement']:5.1f} {m['rescues']:7} "
              f"{m['median_ms']:9.3f} {m['p95_ms']:6.3f} {m['median_ratio_vs_20']:5.2f} "
              f"{m['below_top1_improvement']['query_count']:10} "
              f"{m.get('vs_production_pool', {}).get('below_top1_improvement', {}).get('query_count', '-')}")
    print('Crowding:', json.dumps(crowding))
    # Prefer rescues, then largest score improvements; preserve all changes in JSON.
    sample = sorted(examples, key=lambda e: (not e['rescue'], -(e['new']['score'] - e['old']['score']),
                                            e['pool'], e['query']))
    seen = set()
    for example in sample:
        if example['query'] in seen:
            continue
        seen.add(example['query'])
        print(json.dumps(example))
        if len(seen) == 15:
            break
    print(f'Wrote {args.output}', flush=True)


if __name__ == '__main__':
    main()
