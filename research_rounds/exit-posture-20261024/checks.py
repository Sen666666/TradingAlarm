"""Execution invariants on synthetic data, before seeing real account results."""
import numpy as np,pandas as pd
from engine import backtest,SCENARIOS

def check():
 ix=pd.date_range('2025-01-01',periods=6);d=pd.DataFrame({'open':[100,101,102,103,104,105],'high':110.,'low':1.,'close':[100,101,102,103,104,105],'volume':100.},index=ix)
 s=pd.DataFrame({'target':[1,1,0,1,1,1],'entered':[1,0,0,1,0,0],'floor':90.,'exit_line':90.,'exit_reason':['','','structure','','',''],'entry_kind':'test','event':0},index=ix)
 ini={'active':False,'floor':np.nan,'previous_close':99.}
 _,l,t,f,o=backtest(d,s,ini,'X',SCENARIOS['base'])
 assert f.iloc[0].date=='2025-01-02' and f.iloc[0].raw_price==101 # does not cancel on future intraday low=1
 assert f.iloc[1].date=='2025-01-04' and f.iloc[1].side=='sell' # rebound does not cancel latched sell
 assert t.iloc[-1].terminal and f.iloc[-1].signal_date=='preset_end'
 _,_,_,f2,_=backtest(d,s,ini,'X',SCENARIOS['delay1']);assert not len(f2) or f2.iloc[0].date=='2025-01-03'
 gap=d.copy();gap.loc[ix[1],'open']=80
 _,_,_,fg,og=backtest(gap,s,ini,'X',SCENARIOS['base']);assert (og.action=='cancel_gap').any()
 flat=s.copy();flat.target=0;flat.entered=0
 z,_,tz,_,_=backtest(d,flat,ini,'X',SCENARIOS['base']);assert z['net_return']==0 and len(tz)==0
 features=pd.DataFrame({'atr':.001},index=ix)
 _,_,tm,_,_=backtest(d,s,ini,'X',SCENARIOS['base'],matched_to=t,policy='E2',features=features)
 assert list(tm.entry_date)==list(t.entry_date)
 np.testing.assert_allclose(tm.entry_price,t.entry_price)
 assert (pd.to_datetime(tm.exit_date)<=pd.to_datetime(t.exit_date)).all()
 return {'synthetic_execution':'pass','checks':['next_open','no_future_low','latched_sell','delay','gap_cancel','terminal_close','empty_account','matched_actual_entries']}
if __name__=='__main__':print(check())
