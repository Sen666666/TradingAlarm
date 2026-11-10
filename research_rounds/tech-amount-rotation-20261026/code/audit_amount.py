"""Audit existing original daily turnover amounts, without financial replay."""
from pathlib import Path
from datetime import datetime, timezone
import csv
import json
import hashlib
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    roster = ROOT/'research_rounds/tech-compound-design-20261026/proposed-pool.csv'
    manifest = ROOT/'research_rounds/rs-h1-execution-20261025/inputs-v2/input-manifest.json'
    sources = {r['series_id']: r for r in json.loads(manifest.read_text())['series']}
    rows = []; identities = {}
    for r in csv.DictReader(roster.open()):
        s = r['symbol']; ref = sources[s]['raw']; p = Path(ref['path'])
        assert sha(p) == ref['sha256'], s
        identities[str(p.relative_to(ROOT))] = ref['sha256']
        d = pd.read_parquet(p)
        expected = {'trade_date','amount','amount_unit','volume','low','high','observed_bar','source_invalid','synthetic_event_bar'}
        assert expected <= set(d), (s, expected-set(d))
        dates = pd.to_datetime(d.trade_date); d = d.loc[dates.ge('2024-01-01')].copy()
        assert d.trade_date.is_unique
        units = set(d.amount_unit.dropna().astype(str)); assert units <= {'CNY'}, (s, units)
        real = d.observed_bar.astype(bool) & ~d.source_invalid.astype(bool) & ~d.synthetic_event_bar.astype(bool)
        valid = real & np.isfinite(d.amount) & d.amount.gt(0) & d.amount_unit.eq('CNY')
        vwap_ok = valid & d.volume.gt(0) & np.isfinite(d.volume)
        vwap = d.amount/d.volume
        # Diagnostic only: never changes signals, pool membership, or trades.
        outside = vwap_ok & ((vwap < d.low*.995) | (vwap > d.high*1.005))
        rows.append(dict(symbol=s,name=r['name'],industry=r['industry'],source_rows=len(d),
            source_first=str(pd.to_datetime(d.trade_date).min().date()) if len(d) else None,
            source_last=str(pd.to_datetime(d.trade_date).max().date()) if len(d) else None,
            real_rows=int(real.sum()),valid_amount_rows=int(valid.sum()),
            real_rows_with_invalid_amount=int((real & ~valid).sum()),
            vwap_range_checks=int(vwap_ok.sum()),vwap_outside_ohlc_tolerance=int(outside.sum()),
            amount_units=','.join(sorted(units)),source_sha256=ref['sha256']))
    assert len(rows) == 407
    with (HERE/'amount-coverage.csv').open('x') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    receipt=dict(recorded_at=datetime.now(timezone.utc).isoformat(),stocks=len(rows),
        rows=sum(r['source_rows'] for r in rows),real_rows=sum(r['real_rows'] for r in rows),
        valid_amount_rows=sum(r['valid_amount_rows'] for r in rows),
        real_rows_with_invalid_amount=sum(r['real_rows_with_invalid_amount'] for r in rows),
        vwap_outside_ohlc_tolerance=sum(r['vwap_outside_ohlc_tolerance'] for r in rows),
        source_amount_units='CNY', end_dates=dict(pd.Series([r['source_last'] for r in rows]).value_counts()),
        exact_condition='candidate.amount_CNY >= Decimal(1.5) * holding.amount_CNY',
        replaces='not share volume, not volume ratio, not turnover rate',
        vwap_check_is_diagnostic_only=True, source_hash_checks_passed=True,
        input_sha256={str(roster.relative_to(ROOT)):sha(roster),str(manifest.relative_to(ROOT)):sha(manifest)},
        raw_source_sha256=identities,new_economic_accounts=0,downloads=0)
    # Convert count scalars, retaining deterministic valid JSON.
    receipt['end_dates']={k:int(v) for k,v in receipt['end_dates'].items()}
    with (HERE/'amount-audit.json').open('x') as f:json.dump(receipt,f,ensure_ascii=False,indent=2);f.write('\n')
    print(json.dumps({k:v for k,v in receipt.items() if k not in ['raw_source_sha256','input_sha256']},ensure_ascii=False),flush=True)

if __name__ == '__main__':main()
