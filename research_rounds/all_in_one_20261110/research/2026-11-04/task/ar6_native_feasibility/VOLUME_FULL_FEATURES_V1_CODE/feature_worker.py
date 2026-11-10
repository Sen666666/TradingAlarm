"""Guarded one-series worker. Root has NOT authorized the1799 batch.

No import initializes market/account/runner. Only the frozen pure assemble is
loaded after a separate future full-feature grant has been validated.
"""
from pathlib import Path
import hashlib,json,importlib.util,sys
import pandas as pd,numpy as np
W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds');T=Path('/Users/bytedance/Documents/Codex/2026-11-04/task');U=W/'universe-cp1-inputs-20261031';RR=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds');END='2026-06-30';ASSEMBLY=T/'risk_constraints/run_volume_fixture_verification_fix_v2.py';ASSEMBLY_SHA='c3dbee1b5347f02ec8074c5bd47059ccd83bcd5dc6fce9d0edfb77ab6836a087'
_MODULE=None
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def save(p,x):
 p=Path(p);tmp=p.with_name(p.name+'.tmp');tmp.write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str));tmp.replace(p)
def inventory():
 # Metadata only. Empty source domains remain1799 members, never fake false signals.
 jobs=[]
 old_scores={r['symbol']:r for r in read(W/'pvr-slot1-native-readiness-20261101/SCORES_MANIFEST.json')['entries']};new_scores={r['symbol']:r for r in read(T/'ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full/SCORES_MANIFEST.json')['entries']}
 for stock,rs in [(True,read(U/'STOCK_MANIFEST.json')),(False,read(U/'INDUSTRY_MANIFEST.json'))]:
  for r in rs:
   sid=r['symbol'if stock else'series'];signal=next(p for p in r['source_sha256']if p.endswith('/signal.parquet'))
   if stock:facts=r['refs']['facts']
   else:
    fs=[p for p in r['source_sha256']if '/industry-facts/'in p];assert len(fs)==1;facts=fs[0]
   hashes={**r['source_sha256'],**r['output_sha256']}
   if stock:
    hashes[str(W/'pvr-slot1-native-readiness-20261101/scores'/(sid+'.parquet'))]=old_scores[sid]['output_sha256'];hashes[str(T/'ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full/scores'/(sid+'.parquet'))]=new_scores[sid]['output_sha256']
    legacy=W/'pvr-current-v3-information-capital-20261101/pvr-cache'/(sid+'.parquet')
    if old_scores[sid]['legacy_cache_sha256'] is not None:hashes[str(legacy)]=old_scores[sid]['legacy_cache_sha256']
    else:assert not legacy.exists(),'unexpected new legacy cache'
   jobs.append(dict(sid=sid,stock=stock,rows=r.get('full_warm_observations',0),input_status=r['status'],raw_signal=signal,facts=facts,q=r['refs']['CP1_input'],CP1=r['refs']['CP1'],input_sha256=hashes))
 assert len(jobs)==1799 and sum(j['rows']==0 for j in jobs)==22
 assert all(j['stock']and j['input_status']=='not_applicable_no_local_observation_by_end'for j in jobs if j['rows']==0)
 return jobs
def require_full_grant(job,grant_path):
 assert grant_path and Path(grant_path).exists(),'1799 export not authorized; separate root full-feature grant required'
 g=read(grant_path);assert g['root_approved']is True and g['scope']=='FULL_1799_PURE_FEATURE_EXPORT_V1'
 assert 1<=g['workers']<=6 and 0<g['max_wall_seconds']<=3600
 assert g['ACT_shared_gate_passed']is True and sha(__file__)==g['worker_sha256']
 assert sha(ASSEMBLY)==g['assemble_sha256']==ASSEMBLY_SHA
 assert sha(U/'STOCK_MANIFEST.json')==g['stock_manifest_sha256']and sha(U/'INDUSTRY_MANIFEST.json')==g['industry_manifest_sha256']
 outroot=Path(g['output_root']).resolve();expected=T/'ar6_native_feasibility/VOLUME_FULL_FEATURES_V1';assert outroot==expected.resolve()
 assert job['sid']in g['series_ids']and len(g['series_ids'])==1799
 return g,outroot

def initialize_assemble():
 global _MODULE
 if _MODULE is not None:return _MODULE
 assert sha(ASSEMBLY)==ASSEMBLY_SHA
 spec=importlib.util.spec_from_file_location('full_feature_frozen_fixture_assemble',ASSEMBLY);m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m)
 sys.path[:0]=[str(RR/'b5-g1-20261025/code'),str(RR/'pv-strength-b5-20261025/code'),str(RR/'pv-participation-response-20261020/code')]
 import evidence,policy,grade,policies_g1,data_utils,arithmetic
 m.evidence=evidence;m.policy=policy;m.grade=grade;m.policies=policies_g1;m.eligible_prices=data_utils.eligible_prices
 m.NUM=m.module('full_feature_original_numeric',RR/'pv-participation-response-20261020/code/numeric.py');m.B4=evidence._load_frozen_b4();m.CP=m.module('full_feature_original_CP1',RR/'continuous-protection-lines-20261028/code/model.py');m.SCORE=m.score_function()
 expected={'evidence':RR/'pv-strength-b5-20261025/code/evidence.py','policy':RR/'pv-strength-b5-20261025/code/policy.py','arithmetic':RR/'pv-strength-b5-20261025/code/arithmetic.py','grade':RR/'b5-g1-20261025/code/grade.py','policies_g1':RR/'b5-g1-20261025/code/policies_g1.py','data_utils':RR/'pv-participation-response-20261020/code/data_utils.py'}
 for name,p in expected.items():assert Path(sys.modules[name].__file__).resolve()==p.resolve(),('import identity differs',name)
 _MODULE=m;return m
def exact(a,b):
 aa=a.copy(deep=False);bb=b.copy(deep=False);aa.index=a.index.as_unit('ns');bb.index=b.index.as_unit('ns');assert set(aa.columns)==set(bb.columns);pd.testing.assert_frame_equal(aa[bb.columns],bb,check_exact=True,check_dtype=False,check_freq=False,check_names=False)
def run_item(job,grant_path):
 g,outroot=require_full_grant(job,grant_path)
 assert all(sha(p)==h for p,h in job['input_sha256'].items()),('item source changed',job['sid'])
 folder=outroot/'items'/job['sid'];assert not folder.exists(),'existing item needs explicit frozen reuse review; never overwrite'
 folder.mkdir(parents=True)
 if job['rows']==0:
  # Deliberately never call assemble(empty). Observation absence is NA, not false.
  rec=dict(sid=job['sid'],status='NA_NO_OBSERVATION_THROUGH_2026JUN30',stock=True,rows=0,all_stock_day_lookup='UNKNOWN_NO_OBSERVATION',models_called=0,source_sha256=job['input_sha256'],arm='signal_volume_neutral',fullwarm_schema_refs={k:job[k]for k in ['facts','q','CP1']})
  save(folder/'DONE.json',rec);return rec
 m=initialize_assemble();raw=pd.read_parquet(job['raw_signal']).loc[:END];real=m.assemble(raw,job['stock'],False)
 f=pd.read_parquet(job['facts']).loc[:END];assert set(f.columns)<=set(real['facts'].columns);exact(real['facts'][f.columns],f)
 exact(real['q'],pd.read_parquet(job['q']).loc[:END]);exact(real['CP1'],pd.read_parquet(job['CP1']).loc[:END])
 if job['stock']:
  legacy=W/'pvr-current-v3-information-capital-20261101/pvr-cache'/(job['sid']+'.parquet')
  if legacy.exists():old=pd.read_parquet(legacy);assert old.index.max()<=pd.Timestamp(END);exact(real['PVR'].reindex(old.index),old)
  p2024=T/'ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full/scores'/(job['sid']+'.parquet');pnative=W/'pvr-slot1-native-readiness-20261101/scores'/(job['sid']+'.parquet');a=pd.read_parquet(p2024);b=pd.read_parquet(pnative).loc['2025-07-01':END];cal=pd.concat([a,b]);assert len(cal)==968 and cal.index.is_unique;exact(real['PVR'][['score']].reindex(cal.index),cal)
 neutral=m.assemble(raw,job['stock'],True);exact(real['facts'][['close','segment_id','factor','raw_close']],neutral['facts'][['close','segment_id','factor','raw_close']]);assert real['evidence'].ready.equals(neutral['evidence'].ready)
 outputs={}
 for name,frame in neutral.items():
  if name=='PVR'and not job['stock']:continue
  p=folder/(name+'.parquet');tmp=p.with_suffix('.tmp');frame.to_parquet(tmp);tmp.replace(p);outputs[str(p)]=sha(p)
 rec=dict(sid=job['sid'],stock=job['stock'],status='TRUE_PARITY_PASS_NEUTRAL_EXPORTED',rows=len(neutral['facts']),source_sha256=job['input_sha256'],outputs=outputs,real_data_copied=False,models='frozen assemble both arms',financial_stage_or_ACT_on_computed=False)
 save(folder/'DONE.json',rec);return rec
if __name__=='__main__':raise SystemExit('Worker only; root has not authorized1799 export. Use separate explicit future grant.')
