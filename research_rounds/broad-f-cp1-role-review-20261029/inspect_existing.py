"""Read existing receipts only; no indicator, execution, or account simulation."""
from pathlib import Path
import hashlib
import json
import pandas as pd

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
FACTS = ROOT / 'TradingAlarm/runtime/market/update-20261027-153013-2ffe04/prepared/facts'
F_DIR = ROOT / 'research_rounds/intent-support-20261027/signals'
CP_DIR = ROOT / 'research_rounds/continuous-protection-lines-20261028/signals'
CASES = [('300308.SZ', '2025-06-27'), ('300502.SZ', '2025-06-27'),
         ('688498.SH', '2025-10-20'), ('688498.SH', '2024-02-08')]

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def save(name, obj):
    with (OUT / name).open('x') as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, allow_nan=False)

sources = {}
rows = []
for sid, day in CASES:
    d = pd.Timestamp(day)
    paths = [FACTS / f'{sid}.parquet', F_DIR / f'{sid}.parquet', CP_DIR / f'{sid}.parquet']
    for p in paths:
        sources[str(p.relative_to(ROOT))] = sha(p)
    facts, fine, cp = [pd.read_parquet(p).loc[:d] for p in paths]
    bar = facts.loc[d]
    factor = float(bar.factor)
    up = fine[fine.event.gt(0)]
    f_day = up.index[-1]
    f = up.iloc[-1]
    path = facts.loc[f_day:d]
    cp_valid = []
    for t, r in cp[cp.receipt.fillna(False)].iterrows():
        track = facts.loc[t:d]
        if (track.i_target.all() and track.segment_id.eq(bar.segment_id).all()
                and track.close.gt(float(r.candidate)).all()):
            cp_valid.append({'created': str(t.date()), 'candidate_case_raw': float(r.candidate) / factor})
    rows.append({
        'symbol': sid, 'date': day, 'close_case_raw': float(bar.close) / factor,
        'i_floor_case_raw': float(bar.i_floor) / factor,
        'f_confirmed': str(f_day.date()), 'f_pivot_date': str(f.pivot_date)[:10],
        'f_candidate_case_raw': float(f.pivot) / factor,
        'f_path_close_unbroken': bool(path.close.gt(float(f.pivot)).all()),
        'f_path_i_valid_same_segment': bool(path.i_target.all() and path.segment_id.eq(bar.segment_id).all()),
        'cp_receipt_today': bool(cp.loc[d].receipt),
        'cp_today_candidate_case_raw': float(cp.loc[d].candidate) / factor if bool(cp.loc[d].receipt) else None,
        'last_three_existing_cp_receipts_still_close_unbroken': cp_valid[-3:],
        'interpretation': 'Existing signal candidates, not actual holding floors, entry inheritance, or fills.'
    })
save('case-observations.json', rows)
save('case-source-sha256.json', sources)
print(json.dumps(rows, ensure_ascii=False, indent=2))
