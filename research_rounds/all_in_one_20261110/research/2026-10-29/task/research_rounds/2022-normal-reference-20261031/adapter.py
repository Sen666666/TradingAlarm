"""Date/input-only wrapper around the unchanged original normal reference methods."""
from pathlib import Path
import sys,json,time,shutil
import pandas as pd
O=Path(__file__).resolve().parent;W=O.parent
sys.path.insert(0,str(W/'q2-normal-continuation-20261031'))
import continuation as E
J,L,BASE,IO=E.J,E.L,E.BASE,E.IO
START='2022-01-01';END='2022-12-30'
# Process-local calendar parameters. No original source file is rewritten.
J.START=START;J.END=END
def save(p,x):IO.write_json(p,J.T.norm(J.W.canon(x)))
def inputs():
 started=time.monotonic();complete=L.read(O/'inputs/COMPLETION.json');assert complete['passed'] and complete['stock_receipts']==16932 and complete['industry_receipts']==1313
 manifest=L.read(O/'inputs/MANIFEST.json');new={r['sid']:r for r in manifest};sm=L.read(L.U/'STOCK_MANIFEST.json');im=L.read(L.U/'INDUSTRY_MANIFEST.json');fixed=L.read(L.U/'FREEZE.json')['stocks'];assert len(fixed)==1709
 full={};cp={};receipts={};cache_checks=[]
 for r in sm:
  sid=r['symbol'];record=new[sid];assert record['original_output_sha256']==r['output_sha256']
  for p,h in r['output_sha256'].items():assert L.sha(p)==h,('original numeric/export changed',sid,p)
  assert L.sha(record['output_path'])==record['output_sha256']
  f=pd.read_parquet(r['refs']['facts']).loc[:END];q=pd.read_parquet(r['refs']['CP1_input']).loc[:END];z=pd.read_parquet(r['refs']['CP1']).loc[:END]
  assert f.index.equals(q.index) and q.index.equals(z.index)
  for k in ('close','segment_id','i_target','i_floor'):pd.testing.assert_series_equal(f[k],q[k],check_exact=True,check_dtype=False,check_freq=False)
  assert q.e0_valid.equals(f.i_target.astype(bool))
  rr=L.read(record['output_path']);assert len(rr)==int(z.loc[START:END].receipt.eq(True).sum())
  full[sid]=f;cp[sid]=z;receipts[sid]={x['confirmed_day']:x for x in rr};cache_checks.append((sid,len(f.loc[START:END]),len(rr)))
 shared=J.M.context(END,ids=fixed);bundle,market,facts=shared
 assert set(market.lines)==set(fixed)=={l.security_id for l in bundle.lines}
 for sid,f in full.items():facts.f[sid]=f;bundle.series[sid].states=f[['e0_ready','e0_target','segment_id']].rename(columns={'e0_ready':'ready','e0_target':'target'})
 states={};ir={}
 for r in im:
  sid=r['series'];record=new[sid]
  for p,h in r['output_sha256'].items():assert L.sha(p)==h,('industry cache changed',sid,p)
  assert L.sha(record['output_path'])==record['output_sha256']
  s=pd.read_parquet(r['refs']['state']);states[sid]=J.T.norm(s[s.day<=END].to_dict('records'))
  for x in L.read(record['output_path']):ir[sid+'|'+x['confirmed_day']]=x
  assert facts.f[sid].index.max()<=pd.Timestamp(END)
 recovery=J.M.O/'recovery.csv';assert L.sha(recovery)==L.read(J.BASE/'PAIR_FREEZE.json')['sha256'][str(recovery)]
 identity=dict(fixed_identities=fixed,sectors=[x['series'] for x in im],window=[START,END],cash_each=1000000,ACT_external_file=str(recovery),ACT_external_sha256=L.sha(recovery),source_stock_manifest_SHA=L.sha(L.U/'STOCK_MANIFEST.json'),new_receipt_manifest_SHA=L.sha(O/'inputs/MANIFEST.json'),no_future_IPO_imputation=True,stocks_with_2022_rows=sum(n>0 for _,n,_ in cache_checks),numeric_models_recomputed=0,seconds=time.monotonic()-started)
 save(O/'INPUT_GATE.json',dict(passed=True,identity=identity,stock_cache_counts=cache_checks,new_I_CP1_stage_calculations=0));return shared,receipts,cp,states,ir,identity

class Reference(L.PreparedRunner):
 reference='B3'
 def __init__(self,*args,**kw):
  super().__init__(*args,policies=('B',),**kw)
  if self.reference=='B_diag':BASE.enable(self.accounts['B'])
  a=self.accounts['B'];assert a.available==a.initial_cash==a.current_nav==J.D(1000000)
  assert not a.positions and not a.layers and not a.buys and not a.exits and not a.trades and not a.core_epoch and not a.budget.losses
  assert self.planning.__func__ is J.Runner.planning and self.opening.__func__ is J.Runner.opening
 def checkpoint(self,out,last_event):
  # Reuse the validated checkpoint-only exclusion of derived episode_starts.
  E.env2['checkpoint'](self,out,last_event)
  if str(last_event.date()) in {'2022-03-31','2022-06-30','2022-09-30',END}:
   for suffix in ('pkl','json'):shutil.copyfile(Path(out)/('checkpoint.'+suffix),Path(out)/('checkpoint-'+str(last_event.date())+'.'+suffix))
class B3(Reference):reference='B3';route=J.Runner.route
class Bdiag(Reference):reference='B_diag';route=BASE.Runner.route
