"""Freeze an exposure-only control using 2021 signals, without fitting returns."""
import json
import pandas as pd
from hk_holding_horizon import ROOT,load,run,capped_breakout,adjusted_signal
OUT=ROOT/'results/hk-exit-exposure-control'

def calibration(base,capped):
 a=base.loc['2021-01-01':'2021-12-31'];b=capped.reindex(a.index)
 if len(a)<200 or a.isna().any() or b.isna().any() or a.mean()<=0:raise ValueError('insufficient calibration exposure')
 return {'base_mean':float(a.mean()),'capped_mean':float(b.mean()),'scale':float(min(1.,b.mean()/a.mean())),'observations':len(a)}

def main():
 OUT.mkdir(exist_ok=True)
 protocol={'calibration':'2021 close signals only, no returns used; capped mean / uncapped mean clipped at 1','evaluation':'2022-01-01 onward; same account engine and 20/40bps costs','comparison':'Full size time-capped vs constant-scaled uncapped breakout','limitations':['Calibration exposure match does not imply evaluation exposure or volatility match','One historical calibration year and three selected surviving internet stocks','Continuous target sizing can create rebalancing trades, unlike binary target','Inherited provisional corporate-action, fill, fee, board-lot and in-kind assumptions','Not pristine holdout: evaluation history already examined in earlier studies']}
 (OUT/'protocol.json').write_text(json.dumps(protocol,indent=2))
 loaded={c:load(c) for c in ['00700','09618','03690']};raw={c:v[0] for c,v in loaded.items()};events={c:v[1] for c,v in loaded.items()}
 f=json.loads((ROOT/'data/hk-stock-pilot/usd-hkd.json').read_text());assert f['base']=='USD'
 src=pd.Series({pd.Timestamp(d)+pd.Timedelta(days=1):v['HKD'] for d,v in f['rates'].items()}).sort_index()
 results=[];pairs=[]
 for code in raw:
  idx=raw[code].index;fx=src.reindex(src.index.union(idx)).ffill().reindex(idx)
  signal=adjusted_signal(code,raw,events,fx);base=capped_breakout(signal)
  for cap in [10,20]:
   capped=capped_breakout(signal,cap);cal=calibration(base,capped)
   for cost in [20,40]:
    rows={}
    for name,target in [('time_cap',capped),('exposure_control',base*cal['scale'])]:
     m,p,o=run(raw,events,fx,target,cost_bps=cost,primary=code)
     evaltarget=target.shift().reindex(p.index)
     exposure=(p.parent_shares*raw[code].close.reindex(p.index)+p.security_claim_value)/(p.nav*1e6)
     m.update(symbol=code,cap=cap,cost_bps=cost,variant=name,calibration=cal,mean_target=float(evaltarget.mean()),mean_actual_exposure=float(exposure.mean()),annual_vol=float(p.return_daily.std()*252**.5))
     results.append(m);rows[name]=m
     p.to_csv(OUT/f'{code}-cap{cap}-cost{cost}-{name}.csv')
    pairs.append(dict(symbol=code,cap=cap,cost_bps=cost,scale=cal['scale'],cagr_advantage=rows['time_cap']['cagr']-rows['exposure_control']['cagr'],dd_difference=rows['time_cap']['max_drawdown']-rows['exposure_control']['max_drawdown'],cap_exposure=rows['time_cap']['mean_actual_exposure'],control_exposure=rows['exposure_control']['mean_actual_exposure']))
 (OUT/'results.json').write_text(json.dumps(results,indent=2));(OUT/'pairs.json').write_text(json.dumps(pairs,indent=2))
 print(pd.DataFrame(pairs).to_string(index=False))
if __name__=='__main__':main()
