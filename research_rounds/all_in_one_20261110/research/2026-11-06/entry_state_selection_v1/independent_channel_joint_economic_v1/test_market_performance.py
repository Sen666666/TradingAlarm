"""Small non-economic loading benchmark; no strategy/holdings consumer is imported."""
import gc
import hashlib
import json
import os
import resource
import subprocess
import time
import pandas as pd
from market_adapter import MarketAdapter, END


def rss_mb():
    return int(subprocess.check_output(['ps', '-o', 'rss=', '-p', str(os.getpid())])) / 1024


def run():
    a = MarketAdapter(native_cache_limit=8)
    start = time.perf_counter()
    a._setup()
    setup_s = time.perf_counter() - start
    baseline_rss = rss_mb()
    chosen = ['300666.SZ', '002583.SZ', '300085.SZ']
    chosen += [s for s in sorted(a._engine.manifest) if s not in chosen][:7]
    rows = []
    original_context = a._native_context
    builds = [0]
    def counted_context(sid, cut):
        if (sid, cut) not in a._native:
            builds[0] += 1
        return original_context(sid, cut)
    a._native_context = counted_context
    for sid in chosen:
        start = time.perf_counter()
        frame = a.load_sid(sid)
        market_s = time.perf_counter() - start
        frame_mb = frame.memory_usage(deep=True).sum() / 2**20
        del frame
        start = time.perf_counter()
        a.close(sid, '2025-12-17')
        native_first_close_s = time.perf_counter() - start
        gc.collect()
        rows.append(dict(sid=sid, market_load_s=market_s, first_native_close_s=native_first_close_s,
                         compact_frame_deep_mb=frame_mb, rss_mb=rss_mb(), native_contexts=len(a._native)))
    assert builds[0] == len(chosen), (builds[0], chosen)
    assert len(a._native) == 0
    days = a._engine.cal[a._engine.cal.year == 2023][:100]
    passes = []
    timings = []
    for repeat in range(2):
        start = time.perf_counter()
        observations = []
        for day in days:
            for sid in chosen:
                facts = a.qualification(sid, day)
                observations.append(dict(sid=sid, day=day, **facts))
        timings.append(time.perf_counter() - start)
        passes.append(pd.DataFrame(observations))
    pd.testing.assert_frame_equal(passes[0], passes[1], check_exact=True)
    assert builds[0] == len(chosen), ('NATIVE_CONTEXT_CHURN', builds[0])
    assert len(a._native) == 0
    continuous_mb = sum(f.memory_usage(deep=True).sum() for f in a._continuous_qual.values()) / 2**20
    source_hashes = a.verify_sources()
    source_digest = hashlib.sha256(json.dumps(source_hashes, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    sid = chosen[-1]
    n = 200
    start = time.perf_counter()
    for _ in range(n):
        a.close(sid, '2025-12-17')
    close_us = (time.perf_counter() - start) * 1e6 / n
    start = time.perf_counter()
    for _ in range(n):
        # Reconstruct the old copying access overhead, without any economic action.
        a.load_sid(sid).loc[pd.Timestamp('2025-12-17')].to_dict()
        a.qualification(sid, '2025-12-17')
    previous_access_us = (time.perf_counter() - start) * 1e6 / n
    gc.collect()
    result = dict(scope='TEN_SID_INPUT_ONLY_NO_ECONOMICS', setup_seconds=setup_s,
                  baseline_rss_mb=baseline_rss, final_rss_mb=rss_mb(),
                  peak_rss_mb=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 2**20,
                  samples=rows, repeated_close_us=close_us, old_copying_access_us=previous_access_us,
                  speedup=previous_access_us / close_us,
                  native_lru_limit=a.native_cache_limit,
                  native_context_build_count=builds[0],
                  ten_sid_100day_two_pass_seconds=timings,
                  two_pass_exact=True,
                  compact_continuous_industry_mb=continuous_mb,
                  loaded_source_files=len(source_hashes), loaded_source_mapping_sha256=source_digest,
                  extrapolation_warning='Not a full run estimate. Disk caches, source history lengths, native LRU churn, concurrent workload and allocator reuse change costs. No strategy loops measured.')
    loads = [r['market_load_s'] for r in rows]
    sizes = [r['compact_frame_deep_mb'] for r in rows]
    result['linear_market_only_ranges'] = [dict(loaded_sids=n,
        seconds_range=[n*min(loads), n*max(loads)],
        pandas_deep_mb_range=[n*min(sizes), n*max(sizes)]) for n in (100, 500, 1000, 1709)]
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    run()
