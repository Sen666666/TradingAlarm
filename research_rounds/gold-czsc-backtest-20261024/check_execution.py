"""Targeted execution checks: timing, gap cancellation, fees and terminal mark."""
from pathlib import Path
import json
import pandas as pd
from engine import run,SCENARIOS
HERE=Path(__file__).resolve().parent
idx=pd.date_range('2025-01-02',periods=5,freq='B')
bars=pd.DataFrame(dict(open=[100.,101.,98.,94.,99.],high=[102.,103.,101.,97.,102.],low=[99.,100.,89.,93.,98.],close=[100.,102.,90.,96.,100.],volume=[100.]*5),index=idx)
s=pd.DataFrame(0,index=idx,columns=['B1','B2','B3','B3A','new_buy','new_sell']);s['bi_low']=95.;s['bi_end']='2024-12-30';s.loc[idx[0],['B1','new_buy']]=1
summary,d,t,f,o=run(bars,s,['B1'],'M',SCENARIOS['base'])
assert f.date.tolist()==[str(idx[1].date()),str(idx[3].date())] and f.side.tolist()==['buy','sell']
assert t.exit_reason.iloc[0]=='support_broken'
gap=bars.copy();gap.loc[idx[1],'open']=94.
ss,dd,tt,ff,oo=run(gap,s,['B1'],'M',SCENARIOS['base']);assert ss['trades']==0 and ss['net_return']==0 and ss['cancelled_orders']==1
summary2,d2,t2,f2,o2=run(bars,s,['B1'],'M',SCENARIOS['delay1']);assert f2.date.tolist()==[str(idx[2].date()),str(idx[4].date())]
ss,dd,tt,ff,oo=run(bars,s,[],'S',SCENARIOS['base'],benchmark=True);assert tt.terminal.iloc[0] and ff.iloc[-1].raw_price==bars.close.iloc[-1]
assert f.iloc[0].price>f.iloc[0].raw_price and f.iloc[1].price<f.iloc[1].raw_price
record=dict(passed=True,checks=['signal_close_to_next_open','no_future_intraday_low_at_entry','known_gap_below_support_cancels','delay1_second_following_open','predeclared_terminal_close','adverse_slippage_and_closed_leg_accounting'])
with (HERE/'execution-checks.json').open('x') as fp:json.dump(record,fp,ensure_ascii=False,indent=2);fp.write('\n')
print(json.dumps(record,ensure_ascii=False))
