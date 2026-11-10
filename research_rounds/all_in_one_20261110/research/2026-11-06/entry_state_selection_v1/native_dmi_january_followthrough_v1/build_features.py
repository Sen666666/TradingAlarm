"""Causal extension of frozen January DMI features. No account events or labels."""
from pathlib import Path
import sys,ast,time,json
sys.dont_write_bytecode=True
O=Path(__file__).resolve().parent;R=O.parent;OLD=R/'native_dmi_two_month_continuous_v1'
sys.path.insert(0,str(OLD));import run_bounded as B
np,pd=B.np,B.pd

def build():
 B.claim(O/'FEATURE_EXTENSION_ONCE.lock');started=time.monotonic()
 M=B.C.U/'STOCK_MANIFEST.json';H=B.J.M.P/'h1.npz';src=R/'dmi_boundary_migration_v1/experiment.py'
 for p,h in B.read(OLD/'FEATURE_INPUT_SHA256.json').items():
  actual=OLD/'FEATURE_BUILD_SOURCE_SNAPSHOT.py' if p==str(OLD/'run_bounded.py') else Path(p)
  assert B.sha(actual)==h,('OLD_FEATURE_INPUT_DRIFT',p,str(actual))
 cal=pd.DatetimeIndex(np.load(H,allow_pickle=False)['dates']);cal=cal[(cal>='2013-01-01')&(cal<=B.C.END)]
 assert B.C.END=='2026-05-15' and str(cal[-1].date())==B.C.END
 target=cal[cal>='2022-01-04'];prior=pd.read_parquet(OLD/'ALL_WINDOW_DMI_FEATURES.parquet')
 env=dict(np=np,pd=pd,N=14)
 nodes=[n for n in ast.parse(src.read_text()).body if isinstance(n,ast.FunctionDef) and n.name in ('calc','rma')]
 assert len(nodes)==2
 exec(compile(ast.Module(body=nodes,type_ignores=[]),str(src)+':frozen_pure_math','exec'),env);calc=env['calc']
 inp={str(p):B.sha(p) for p in [M,H,src,Path(__file__),O/'PROTOCOL.json',OLD/'ALL_WINDOW_DMI_FEATURES.parquet']}
 rec=[];prefix=0;oldrows=0
 for no,mm in enumerate(B.read(M)):
  sid=mm['symbol'];p=next(p for p in mm['source_sha256'] if p.endswith('/signal.parquet'));assert B.sha(p)==mm['source_sha256'][p];inp[p]=mm['source_sha256'][p]
  raw=pd.read_parquet(p).loc[:B.C.END].reindex(cal)
  cols=['open','high','low','close'];valid=np.isfinite(raw[cols]).all(axis=1)&raw[cols].gt(0).all(axis=1)&raw.high.ge(raw[cols].max(axis=1))&raw.low.le(raw[cols].min(axis=1))&raw.segment_id.notna()
  for c in ['price_eligible','observed_bar','is_observed_bar']:valid &= raw[c].fillna(False).astype(bool)
  for c in ['source_invalid','synthetic_event_bar']:valid &= ~raw[c].fillna(True).astype(bool)
  for _,g in raw[valid].groupby('segment_id'):
   assert g.source_kind.notna().all() and g.source_path.notna().all() and g.source_kind.nunique()==g.source_path.nunique()==1,(sid,'SOURCE_IDENTITY')
  z=calc(raw,cal)
  for cut in ['2022-01-04','2022-01-28','2024-09-24','2026-01-30','2026-03-31']:
   cc=cal[cal<=cut];pd.testing.assert_frame_equal(calc(raw.loc[:cut],cc),z.loc[cc],check_exact=True);prefix+=1
  old=prior[prior.sid.eq(sid)];dd=z.loc[pd.DatetimeIndex(old.day),'d'].to_numpy();np.testing.assert_array_equal(dd,old.d.to_numpy());oldrows+=len(old)
  rec.append(pd.DataFrame(dict(sid=sid,day=target.strftime('%Y-%m-%d'),d=z.loc[target,'d'].to_numpy())))
  if (no+1)%300==0:print('FEATURES',no+1,round(time.monotonic()-started,1),flush=True)
 f=pd.concat(rec,ignore_index=True);assert len(f)==1709*len(target) and not f.duplicated(['sid','day']).any() and oldrows==66651
 f.to_parquet(O/'ALL_CONTINUATION_DMI_FEATURES.parquet',index=False)
 B.save(O/'FEATURE_INPUT_SHA256.json',inp)
 B.save(O/'FEATURE_QA.json',dict(passed=True,rows=len(f),stocks=1709,days=len(target),first_day=str(target[0].date()),last_day=str(target[-1].date()),original_feature_rows_exact=oldrows,physical_prefix_exact=prefix,known=int(f.d.notna().sum()),UNKNOWN=int(f.d.isna().sum()),source_math=str(src),thresholds_added=0,outcomes_read=False,seconds=time.monotonic()-started))
 B.save(O/'FEATURE_SEAL.json',{p.name:B.sha(p) for p in [Path(__file__),O/'PROTOCOL.json',O/'ALL_CONTINUATION_DMI_FEATURES.parquet',O/'FEATURE_INPUT_SHA256.json',O/'FEATURE_QA.json']})
 print('FEATURES_DONE',len(f),round(time.monotonic()-started,1),flush=True)
if __name__=='__main__':build()
