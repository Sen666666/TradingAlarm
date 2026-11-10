from pathlib import Path
import json,hashlib
import pandas as pd,numpy as np
from model import r1_state
from legacy import context,event_frame_numeric
R=Path(__file__).resolve().parent;P=R.parent/'strategy-switching-20261024';S=R.parent/'market-regimes-exit-20261024/inputs'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 assert not (R/'prepared').exists();(R/'prepared').mkdir();(R/'contexts').mkdir();(R/'mechanism').mkdir()
 oldfreeze=json.loads((P/'freeze.json').read_text())
 for name,h in oldfreeze['sha256'].items():assert sha(P/name)==h,name
 cases=json.loads((P/'cases.json').read_text());registry=json.loads((R.parent/'fixed-scenarios-v1/cases.json').read_text());assert cases[:11]==registry
 (R/'cases.json').write_text(json.dumps(cases,ensure_ascii=False,indent=2));stats=[];ab=[];meta=[]
 for sym in sorted({c['symbol'] for c in cases}):
  path=S/f'{sym}.parquet';d=pd.read_parquet(path);assert d.index.is_unique and d.index.is_monotonic_increasing and np.isfinite(d).all().all() and (d>0).all().all()
  e,b,f=context(d);price_events=event_frame_numeric(d.close,d.volume,joint=False)
  pd.testing.assert_frame_equal(b,pd.read_parquet(P/'contexts'/sym/'shadow-E0.parquet'),check_exact=True)
  folder=R/'contexts'/sym;folder.mkdir();e.to_parquet(folder/'events.parquet');b.to_parquet(folder/'shadow-E0.parquet');f.to_parquet(folder/'features.parquet')
  meta.append(dict(symbol=sym,path=str(path),sha256=sha(path),first=str(d.index[0].date()),last=str(d.index[-1].date()),rows=len(d)))
  for c in [x for x in cases if x['symbol']==sym]:
   out=R/'prepared'/c['id'];out.mkdir();s,ini=r1_state(d,e,b,f,c['start'],c['end']);s.to_parquet(out/'R1.parquet');(out/'initial.json').write_text(json.dumps(ini,indent=2))
   off,offini=r1_state(d,e,b,f,c['start'],c['end'],enable_recovery=False);old=pd.read_parquet(P/'prepared'/c['id']/'R.parquet')
   cols=['target','entered','exited','floor','exit_line','entry_kind','exit_reason','shadow_target'];pd.testing.assert_frame_equal(off[cols],old[cols],check_exact=True)
   np.testing.assert_allclose([ini['active'],ini['floor'],ini['previous_close']],[offini['active'],offini['floor'],offini['previous_close']],equal_nan=True,rtol=0,atol=0)
   alt,_=r1_state(d,price_events,b,f,c['start'],c['end']);alt.to_parquet(R/'mechanism'/f"{c['id']}__price-only-confirmation.parquet")
   ab.append(dict(case=c['id'],role=c['role'],PV_recoveries=int(s.recovery_entry.sum()),price_only_recoveries=int(alt.recovery_entry.sum()),changed_recovery_days=int((s.recovery_entry!=alt.recovery_entry).sum()),changed_state_days=int((s.target!=alt.target).sum()),scope='only reentry confirmation events ablated; shadow E0 and ATR fixed; no account'))
   stats.append(dict(case=c['id'],symbol=sym,role=c['role'],R1_entries=int(s.entered.sum()),R1_exits=int(s.exited.sum()),R1_recovery_entries=int(s.recovery_entry.sum()),R_entries=int(old.entered.sum()),R1_active_fraction=float(s.target.mean()),R_active_fraction=float(old.target.mean())))
  print('prepared',sym,flush=True)
 pd.DataFrame(stats).to_csv(R/'signal-review.csv',index=False);pd.DataFrame(ab).to_csv(R/'mechanism/volume-confirmation-ablation.csv',index=False)
 (R/'inputs.json').write_text(json.dumps(dict(series=meta,source_frozen_files_verified=len(oldfreeze['sha256']),old_R_daily_identity_cases=18,new_signal_accounts_run=0),ensure_ascii=False,indent=2));print('PREPARED 18, accounts0',flush=True)
if __name__=='__main__':main()
