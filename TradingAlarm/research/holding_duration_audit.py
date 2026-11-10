"""Retrospective duration attribution, never an executable holding-period filter."""
import hashlib
import json
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent
SOURCES = [
    ('strength-pairwise', 'hk7-pairwise_price-daily-base'),
    ('strength-pairwise', 'hk7-pairwise_volume-daily-base'),
    ('strength-symmetric-exit', 'hk7-symmetric_pairwise_volume-daily-base'),
    ('trend-slot-workbench', 'hk7-symmetric_pairwise_volume-rank_slots-base'),
    ('strength-graded-exposure', 'hk7-graded_pairwise_volume-daily-base'),
]

def duration_bucket(n):
    if n <= 10: return '01_up_to_10'
    if n <= 21: return '02_11_to_21'
    if n <= 63: return '03_22_to_63'
    return '04_over_63'

def main():
    out = ROOT / 'results/holding-duration-audit'
    out.mkdir(exist_ok=True)
    rows, checks = [], []
    for directory, case in SOURCES:
        source = ROOT / 'results' / directory / f'{case}-episodes.json'
        episodes = json.loads(source.read_text())
        path = pd.read_parquet(source.with_name(f'{case}-path.parquet'))
        error = abs(sum(e['pnl'] for e in episodes) - (float(path.nav.iloc[-1])-1)*1e6)
        assert error < 1e-6, (case,error)
        checks.append(dict(case=case,source=str(source.relative_to(ROOT)),sha256=hashlib.sha256(source.read_bytes()).hexdigest(),accounting_error=error))
        for ep in episodes:
            fees = ep['trade_fees'] + ep['dividend_fees']
            rows.append(dict(case=case,symbol=ep['symbol'],entry_year=int(ep['entry_date'][:4]),
                status=ep['status'],sessions=ep['observed_holding_sessions'],
                bucket=duration_bucket(ep['observed_holding_sessions']) if ep['status']=='closed' else '05_open_censored',
                net=ep['pnl'],gross=ep['pnl']+fees,fees=fees,
                retained_claim=ep.get('nontradable_claim_value',0),win=int(ep['pnl']>0)))
    frame=pd.DataFrame(rows)
    frame.to_parquet(out/'episodes.parquet',index=False)
    def summarize(keys):
        return frame.groupby(keys,dropna=False).agg(count=('net','size'),net=('net','sum'),gross=('gross','sum'),fees=('fees','sum'),win_rate=('win','mean'),median_sessions=('sessions','median'),retained_claim=('retained_claim','sum')).reset_index()
    buckets=summarize(['case','bucket'])
    buckets.to_csv(out/'duration.csv',index=False)
    summarize(['case','entry_year','bucket']).to_csv(out/'entry-cohorts.csv',index=False)
    (out/'validation.json').write_text(json.dumps(dict(checks=checks,limits=[
        'Inclusive observed asset sessions, not calendar weeks. Open episodes separately right censored.',
        'Final duration known only after exit: not evidence for time stop or minimum holding period.',
        'Closed parent may retain marked in-kind claims; not necessarily fully realized cash.',
        'Gross adds explicit recorded fees back, not a simulated frictionless strategy.',
        'Entry-year cohorts are not calendar-year returns. Selected HK7 development pool only.',
        'Monetary contributions reflect sizing; cannot isolate duration causal effects.'
    ]),indent=2))
    print(buckets.to_string(index=False))

if __name__=='__main__':main()
