"""Independent cached raw acceleration/share diagnostics; no threshold or signal."""
import json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
p = ROOT.parent / 'industry_selection/channels_v2/INDUSTRY_OPPORTUNITIES_DAILY.parquet'
f = pd.read_parquet(p).sort_values(['sector_id_static', 'date']).copy()
g = f.groupby('sector_id_static', sort=False)
f['B_own_lag10_from_saved_lag5'] = g.B_lag5_ownU.shift(5)
f['a_own'] = f.B_now - 2 * f.B_lag5_ownU + f.B_own_lag10_from_saved_lag5
f['a_pair'] = f.dB5_paired - g.dB5_paired.shift(5)
f['log_share5_over_share20'] = np.log(f.share5 / f.share20)
f['_prior_above_weighted'] = f.B_lag5_ownU * f.N_U_previous5
m = f.groupby('date', sort=True).agg(N_pool=('N_U_t', 'sum'), above=('N_above20_t', 'sum'),
                                   above_paired5=('N_above20_tminus5', 'sum'),
                                   N_pool_prior5=('N_U_previous5', 'sum'), above_own_prior5=('_prior_above_weighted', 'sum'))
m['B_pool'] = m.above / m.N_pool
m['B_pool_own_prior5'] = m.above_own_prior5 / m.N_pool_prior5
m['B_pool_paired_prior5'] = m.above_paired5 / m.N_pool
m['dB5_pool_paired'] = m.B_pool - m.B_pool_paired_prior5
m['a_pool_own'] = m.B_pool - 2 * m.B_pool_own_prior5 + m.B_pool_own_prior5.shift(5)
m['a_pool_pair'] = m.dB5_pool_paired - m.dB5_pool_paired.shift(5)
f = f.merge(m.reset_index(), on='date', validate='many_to_one')
calendar = sorted(f.date.unique())
cases = [('PRIMARY_924_SEMI','2024-09-24','URFI881121'),('PRIMARY_924_SOFTWARE','2024-09-24','URFI881272'),
         ('PRIMARY_924_COMM','2024-09-24','URFI881129'),('PRIMARY_2026_SEMI','2026-01-05','URFI881121'),
         ('AUX_2026_JAN15','2026-01-15','URFI881121'),('COUNTER_2022_PROPERTY','2022-01-24','URFI881153'),
         ('COUNTER_2024_OCT8_SOFTWARE','2024-10-08','URFI881272'),('COUNTER_2024_OCT8_FINANCE','2024-10-08','URFI881283')]
pieces = []
for name, anchor, sid in cases:
    j = calendar.index(anchor)
    ds = calendar[j-5:j+16]
    z = f[f.sector_id_static.eq(sid) & f.date.isin(ds)].copy()
    z['case_id'] = name; z['anchor'] = anchor
    z['relative_session'] = z.date.map({d:k-5 for k,d in enumerate(ds)})
    pieces.append(z)
out = pd.concat(pieces, ignore_index=True).sort_values(['case_id', 'date'])
assert len(out) == 168
cols = ['case_id','anchor','date','relative_session','sector_id_static','industry_static','Nstatic','N_U_t',
        'N_above20_t','N_above20_tminus5','B_now','B_lag5_ownU','dB5_paired','a_own','a_pair',
        'share5','share20','share_change_diagnostic','log_share5_over_share20','rs_ind5',
        'N_pool','B_pool','B_pool_own_prior5','dB5_pool_paired','a_pool_own','a_pool_pair']
out[cols].to_csv(ROOT / 'ROOT_CACHED_BURST_RAW.csv', index=False)
selected = out.loc[out.relative_session.eq(0), cols].to_dict('records')
(ROOT / 'ROOT_CACHED_BURST_ANCHORS.json').write_text(json.dumps(selected, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(selected, ensure_ascii=False, indent=2))
