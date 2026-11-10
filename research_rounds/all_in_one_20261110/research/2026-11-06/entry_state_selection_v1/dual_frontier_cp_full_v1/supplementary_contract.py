"""Supplementary source-contract and root-birth audit; preserves sealed replay outputs."""
from pathlib import Path
import sys,json,time,hashlib
import pandas as pd,numpy as np
O=Path(__file__).resolve().parent;sys.path.insert(0,str(O));import replay_signals as r
M=json.loads(r.M.read_text());rows=[];roots=[]
start=time.monotonic()
for no,v in enumerate(M):
 sid=v['symbol'];pp=next(p for p in v['source_sha256'] if p.endswith('/signal.parquet'))
 f=pd.read_parquet(v['refs']['CP1_input']).loc[:r.END]
 if f.empty:continue
 pr=pd.read_parquet(pp).reindex(f.index);facts=pd.read_parquet(v['refs']['facts']).reindex(f.index);old=pd.read_parquet(v['refs']['CP1']).reindex(f.index)
 z=r.model.features(f);base=r.calc(f,pr,False,z)
 contract=dict(amount_maxerr=float((pr.amount-f.amount).abs().max()),factor_maxerr=float((pr.adjustment_factor-facts.factor).abs().max()),rawclose_factor_maxerr=float((pr.raw_close*pr.adjustment_factor-f.close).abs().max()),observed_consistent=bool(pr.observed_bar.eq(pr.is_observed_bar).all() and pr.is_observed_bar.notna().all()))
 assert contract['amount_maxerr']==0 and contract['factor_maxerr']==0
 assert contract['rawclose_factor_maxerr']<=1e-10 and contract['observed_consistent'],(sid,contract)
 strict=pd.Series(True,index=f.index)
 for c in ['observed_bar','is_observed_bar','price_eligible','volume_eligible']:strict &= pr[c].notna()&pr[c].eq(True)
 for c in ['source_invalid','synthetic_event_bar']:strict &= pr[c].notna()&pr[c].eq(False)
 strict &= np.isfinite(pr.raw_low)&np.isfinite(pr.raw_high)&pr.raw_low.gt(0)&pr.raw_high.ge(pr.raw_low)&np.isfinite(pr.raw_volume)&pr.raw_volume.gt(0)
 drops=base.qok&~strict
 assert not drops.any(),(sid,'strict_contract_would_drop',f.index[drops].tolist())
 ph=base.phase.map({0:pd.NA,1:'SEEK',2:'UP'}).astype('string')
 re=base.reset.map({0:pd.NA,1:'source_reset',2:'unprepared',3:'E0_invalid',4:'E0_down_reset',5:'start',6:'lower_anchor',7:'receipt_consumed'}).astype('string')
 assert ph.equals(old.phase),(sid,'phase')
 assert re.equals(old.reset_reason),(sid,'reset')
 # Full CP input permits correct historical birth; segment starts already active are explicitly unknown.
 active=f.e0_valid;birth=active&(~active.shift(fill_value=False)|f.segment_id.ne(f.segment_id.shift()))
 bpos=np.flatnonzero(birth)
 for j,k in enumerate(bpos):
  en=int(bpos[j+1]) if j+1<len(bpos) else len(f)
  active_idx=np.arange(k,en)[active.iloc[k:en].to_numpy()]
  if not len(active_idx):continue
  last=int(active_idx[-1]);day=str(f.index[k].date())
  if str(f.index[last].date())<'2022-01-01':continue
  unknown=bool(k==0 or f.segment_id.iloc[k]!=f.segment_id.iloc[k-1])
  roots.append(dict(sid=sid,I_root=day,segment=int(f.segment_id.iloc[k]),last_day=str(f.index[last].date()),unknown_birth=unknown,birth_before_2022=day<'2022-01-01',observations=len(active_idx)))
 rows.append(dict(sid=sid,n=len(f),strict_would_drop=int(drops.sum()),phase_exact=True,reset_exact=True,**contract))
 if(no+1)%300==0:print('AUDIT',no+1,flush=True)
pd.DataFrame(rows).to_csv(O/'SUPPLEMENTARY_SOURCE_CONTRACT.csv',index=False)
pd.DataFrame(roots).to_parquet(O/'I_ROOTS.parquet',index=False)
r.save('SUPPLEMENTARY_SEAL.json',dict(code_hash=r.sha(__file__),stocks=len(rows),checks='Original amount and facts factor exact, raw_close*factor <=1e-10, observed flags identical; no qok row fails strict Boolean or finite-positive ordered raw geometry. Baseline phase and reset equal.',strict_q_differences=0,initial_signals_unchanged=r.sha(O/'EVENTS.parquet')==json.loads((O/'SIGNAL_SEAL.json').read_text())['events_hash'],seconds=time.monotonic()-start))
print('SUPPLEMENTARY_COMPLETE',len(rows),len(roots),time.monotonic()-start,flush=True)
