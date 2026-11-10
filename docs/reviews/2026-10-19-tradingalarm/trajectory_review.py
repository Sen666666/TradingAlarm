"""Read-only reconstruction of three previously inspected development cases.

No candidate changes, account reruns or writes to the transferred repository.
The charts show desired close-time state, not actual portfolio positions.
"""
import os
import sys
import json
import hashlib
from pathlib import Path

sys.dont_write_bytecode = True
os.environ.setdefault('MPLCONFIGDIR', '/private/tmp/tradingalarm-audit-mpl')
os.environ.setdefault('XDG_CACHE_HOME', '/private/tmp/tradingalarm-audit-cache')
ROOT = Path('/Users/bytedance/repos/TradingAlarm/TradingAlarm/TradingAlarm/research')
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from trend_equal_weight import equal_scores
from trend_half_slow import quiet_half_slow
from trend_thrust_fail import thrust_state
from trend_background_hold import ENTRY, VIOLENT

cases = [
    ('510300', '2013-07-01', '2016-06-30', 'CSI 300 ETF | 2013-2016'),
    ('512480', '2025-07-01', '2026-10-16', 'Semiconductor ETF | 2025-2026'),
    ('515030', '2026-01-01', '2026-10-16', 'New energy ETF | 2026'),
]
fig, axes = plt.subplots(4, 3, figsize=(18, 12), sharex='col', layout='constrained',
                         gridspec_kw={'height_ratios':[2.1, 1.4, 1, 1]})
summary = {'purpose': 'Subjective review of known development examples; signal state only; Q adjustment semantics remain unverified', 'cases': {}}
for col, (code, begin, end, title) in enumerate(cases):
    source = ROOT / 'data' / f'USHJ{code}.json'
    payload = json.loads(source.read_text())
    frame = pd.DataFrame(payload['bars'])
    frame['date'] = pd.to_datetime(frame.date)
    valid = (frame[['open','high','low','close']] > 0).all(axis=1) & np.isfinite(frame[['open','high','low','close','volume','amount']]).all(axis=1)
    frame = frame[valid].drop_duplicates('date').sort_values('date').set_index('date')
    plain = equal_scores(frame.close, frame.amount)
    opener = quiet_half_slow(frame.close, frame.amount, plain)
    held = pd.Series(thrust_state(opener.to_numpy(), plain.fast.to_numpy(), plain.slow.to_numpy(), frame.close.to_numpy()), index=frame.index)
    full = pd.DataFrame({'close':frame.close, 'fast':plain.fast, 'entry_score':opener, 'slow_bps':plain.slow * 10000, 'desired_state':held,
                         'relative_amount':frame.amount / frame.amount.rolling(63).median().shift(1)})
    part = full.loc[begin:end]
    axes[0,col].plot(part.index, part.close / part.close.iloc[0] * 100, color='#233044', lw=1.5)
    axes[0,col].set_title(title, loc='left', fontweight='bold')
    for ax in axes[:,col]:
        ax.fill_between(part.index, 0, 1, where=part.desired_state > 0, transform=ax.get_xaxis_transform(), color='#37a87b', alpha=.12)
        ax.grid(alpha=.18)
    axes[1,col].plot(part.index, part.entry_score, color='#d87523', lw=1, label='Actual entry score')
    axes[1,col].plot(part.index, part.fast, color='#3266aa', lw=.9, label='Fast / shock score')
    axes[1,col].axhline(ENTRY, color='#48864e', ls='--', lw=.8)
    axes[1,col].axhline(5, color='#888888', ls=':', lw=.6)
    axes[1,col].axhline(VIOLENT, color='#bf3c42', ls='--', lw=.8)
    axes[1,col].set_ylim(-.3,10.3)
    axes[2,col].plot(part.index, part.slow_bps, color='#756096', lw=1.2)
    axes[2,col].axhline(0, color='#444444', lw=.6)
    axes[3,col].bar(part.index, part.relative_amount, color='#6d7b8b', width=2)
    axes[3,col].axhline(1, color='#444444', lw=.7)
    change = held.diff().fillna(0).ne(0) & (held.index >= begin) & (held.index <= end)
    events = full.loc[change].copy()
    events.insert(0, 'action', np.where(events.desired_state > 0, 'enter_signal', 'exit_signal'))
    events.to_csv(OUT / f'{code}-signal-events.csv', index_label='date')
    full.loc[begin:end].to_csv(OUT / f'{code}-trajectory.csv', index_label='date')
    summary['cases'][code] = {'begin':begin,'end':end,'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
                             'events':json.loads(events.reset_index().to_json(orient='records',date_format='iso'))}
    axes[3,col].tick_params(axis='x', rotation=30)
axes[0,0].set_ylabel('Price / first shown close = 100')
axes[1,0].set_ylabel('Score')
axes[2,0].set_ylabel('Slow slope, log bps / bar')
axes[3,0].set_ylabel('Amount / prior 63-bar median')
axes[1,0].legend(fontsize=8,loc='lower left')
fig.suptitle('half-slow review | Green = desired long state, decided at close; actual fills differ\nKnown development cases; no model changes. Amount is displayed but does not drive this model.', fontsize=13)
fig.savefig(OUT / 'trajectory-review.png', dpi=150)
plt.close(fig)
summary['source_hashes'] = {name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in ['trend_half_slow.py','trend_equal_weight.py','trend_thrust_fail.py','trend_quiet_scale.py','trend_shock_scale.py','pairwise_trend_strength.py']}
(OUT / 'trajectory-review.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False)+'\n')
print(json.dumps(summary,ensure_ascii=False))
