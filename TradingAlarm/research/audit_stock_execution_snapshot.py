"""Single-day integration audit; passing state checks is not proof of a fill."""
import json
from pathlib import Path
import pandas as pd
import pyarrow.parquet as pq
from stock_execution import OpenState,next_open_guard
ROOT=Path(__file__).resolve().parent
BASE=Path('/Users/bytedance/repos/my-quant/data/processed')
DATE=pd.Timestamp('2026-05-15');SIGNAL=pd.Timestamp('2026-05-14')
limits=pd.read_parquet(BASE/'factors/limit_prices/limit_prices.parquet')
limits=limits[limits.trade_date.eq(DATE)].set_index('symbol')
raw=pq.read_table(BASE/'daily_bars_history/daily_bars.parquet',filters=[('trade_date','=',DATE)],columns=['symbol','open','volume']).to_pandas().set_index('symbol')
candidates=pd.read_parquet(ROOT/'results/stock-signal-v1/provisional-candidates.parquet')
candidates=candidates[candidates.date.eq(SIGNAL)]
rows=[]
for row in candidates.to_dict('records'):
 symbol=row['symbol'];present=symbol in raw.index and symbol in limits.index
 if present:
  bar=raw.loc[symbol];limit=limits.loc[symbol]
  state=OpenState(str(DATE.date()),float(bar.open),bool(bar.volume>0),str(DATE.date()),float(limit.up_limit),float(limit.down_limit),state_verified=True)
  decision=next_open_guard(state,'buy',str(SIGNAL.date()),slippage_bps=15)
  rows.append(dict(symbol=symbol,rs_order=row['rs_order'],liquidity_order=row['liquidity_order'],guard_pass=decision.allowed,reason=decision.reason))
 else:rows.append(dict(symbol=symbol,guard_pass=False,reason='missing_dated_state'))
frame=pd.DataFrame(rows)
out=dict(signal_date=str(SIGNAL.date()),execution_date=str(DATE.date()),candidates=len(rows),state_guard_pass=int(frame.guard_pass.sum()),reason_counts=frame.reason.value_counts().to_dict(),
 limitations=['Single historical date only','Positive daily volume establishes traded day, not opening-auction fill or exact suspension time','ST exclusion, market access, lots, liquidity, cash and corporate-action ledger remain separate gates','No order submitted and no account backtest performed'],records=rows)
p=ROOT/'results/stock-data-audit/execution-snapshot.json';p.write_text(json.dumps(out,ensure_ascii=False,indent=2))
print(json.dumps({k:v for k,v in out.items() if k!='records'},ensure_ascii=False,indent=2))
