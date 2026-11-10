"""Three-date independent Rp endpoints/score arithmetic, without maturity inference."""
import csv
import hashlib
import json
from fractions import Fraction
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parent
H = Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz')
M = Path('/Users/bytedance/repos/TradingAlarm/TradingAlarm/TradingAlarm/research/data/ths-index-history-20261018/canonical/USHI1B0300.csv')
old = ROOT.parent / 'continuous_rank_v3/ranking/DAILY_RANKINGS.csv'
snapdays = ['2022-01-24', '2024-09-24', '2026-01-15']
rows = [r for r in csv.DictReader(old.open()) if r['date'] in snapdays]
mr = list(csv.DictReader(M.open()))
calendar = [r['date'] for r in mr]
market = {r['date']: float(r['close']) for r in mr}
z = np.load(H)
hd = [str(d)[:10] for d in z['dates']]
hm = {d: i for i, d in enumerate(hd)}
sm = {str(s): i for i, s in enumerate(z['symbols'])}
price = z['close']
segment = z['segment']
out = []
for day in snapdays:
    j = calendar.index(day)
    d0, d1 = calendar[j - 60], calendar[j - 5]
    dates = calendar[j - 60:j - 5 + 1]
    assert len(dates) == 56
    ix = [hm[d] for d in dates]
    rs = [r for r in rows if r['date'] == day]
    values = []
    for r in rs:
        col = sm[r['sector_id_static']]
        p = price[ix, col]
        seg = segment[ix, col]
        assert np.isfinite(p).all() and (p > 0).all() and np.isfinite(seg).all() and (seg == seg[0]).all()
        rp = float(np.log(p[-1] / p[0]) - np.log(market[d1] / market[d0]))
        values.append(rp)
    for r, v in zip(rs, values):
        p = Fraction(2 * sum(x < v for x in values) + sum(x == v for x in values), 2 * len(values))
        # Recover exact breadth midpercentile from raw B to avoid inferring it from A.
        b = float(r['B_now'])
        bs = [float(x['B_now']) for x in rs]
        pb = Fraction(2 * sum(x < b for x in bs) + sum(x == b for x in bs), 2 * len(bs))
        r['_P'] = (3 * p + 2 * pb) / 5
        r['_rp'] = v
        r['_pRp'] = p
        r['_pB'] = pb
    order = sorted(rs, key=lambda r: (-r['_P'], r['sector_id_static']))
    for r in rs:
        if r['industry_static'] in ['半导体', '软件开发', '通信设备', '房地产']:
            out.append({'date': day, 'sid': r['sector_id_static'], 'industry': r['industry_static'],
                        'Rp_start': d0, 'Rp_end': d1, 'observations': 56, 'return_intervals': 55,
                        'Rp': r['_rp'], 'pRp': float(r['_pRp']), 'B': float(r['B_now']),
                        'pB': float(r['_pB']), 'P': float(r['_P']), 'P_exact': str(r['_P']),
                        'P_raw_rank1': 1 + order.index(r), 'T_rank1': int(r['native_E_order']),
                        'maturity': 'NOT_INFERRED_WITHOUT_PRIOR_STATE'})
result = {'scope': 'three-date input arithmetic, no state/forward labels/accounts',
          'sources': {str(H): hashlib.sha256(H.read_bytes()).hexdigest(), str(M): hashlib.sha256(M.read_bytes()).hexdigest()},
          'rows': out}
(ROOT / 'ROOT_THREE_DATES_INPUT_ARITHMETIC.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(out, ensure_ascii=False, indent=2))
