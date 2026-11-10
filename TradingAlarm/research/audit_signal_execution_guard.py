"""Apply fail-closed dated execution guard to currently covered frozen monthly signals."""
import json
from pathlib import Path
from collections import Counter
import pandas as pd
from stock_state_adapter import provider_open_state
from stock_execution import next_open_guard
ROOT=Path(__file__).resolve().parent;OUT=ROOT/'results/stock-data-audit'
def main():
    audits=json.loads((OUT/'stock-state-window-audit.json').read_text())
    checked={(a['symbol'],a['year']) for a in audits if not a['missing_calendar_dates'] and not a['extra_dates'] and a['ohlc_mismatch_over_cent']==0 and a['suspended_local_positive_volume']==0}
    intervals={(a['symbol'],a['year']):(a.get('verified_interval_start',''),a.get('verified_interval_end','')) for a in audits}
    states={}
    for p in (ROOT/'data/stock-state-windows').glob('*.json'):
        d=json.loads(p.read_text())
        for r in d['rows']:states[(d['symbol'],r['date'])]=r
    coverage=pd.read_csv(OUT/'state-signal-coverage.csv');rows=[]
    for r in coverage.itertuples():
        state=states.get((r.symbol,r.execution_date))
        if state is None:reason='missing_dated_provider_state';allowed=False
        else:
            try:
                opened=provider_open_state(state,r.symbol,r.execution_date,source_crosschecked=(r.symbol,r.year) in checked and intervals[(r.symbol,r.year)][0]<=r.execution_date<=intervals[(r.symbol,r.year)][1])
                decision=next_open_guard(opened,'buy',r.signal_date);reason=decision.reason;allowed=decision.allowed
            except ValueError:reason='invalid_provider_identity';allowed=False
        rows.append(dict(strategy=r.strategy,symbol=r.symbol,signal_date=r.signal_date,execution_date=r.execution_date,allowed=allowed,reason=reason))
    pd.DataFrame(rows).to_csv(OUT/'signal-execution-guard.csv',index=False)
    summary={name:dict(Counter(r['reason'] for r in rows if r['strategy']==name)) for name in sorted({r['strategy'] for r in rows})}
    (OUT/'signal-execution-guard.json').write_text(json.dumps(dict(summary=summary,limitation='Unknown price limits remain blocked. Zero allowed here indicates incomplete verification, not proof all historical orders were impossible.'),indent=2));print(summary)
if __name__=='__main__':main()
