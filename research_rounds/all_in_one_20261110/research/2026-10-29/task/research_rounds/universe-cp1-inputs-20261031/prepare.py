"""One bounded reusable market cache, no account/trade engine execution."""
from pathlib import Path
import sys,json,time,hashlib,importlib.util,collections,traceback,os
import numpy as np,pandas as pd
O=Path(__file__).resolve().parent;W=O.parent;RR=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds');BEGIN='2025-07-01';END='2026-06-30';REQUIRED_END='2026-03-31';CUT='2025-12-31';BUDGET=900
def load(n,p):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);sys.modules[n]=m;s.loader.exec_module(m);return m
G=load('universe_existing_case_generator',W/'case-stock-cp1-warmup-20261031/generate.py');N,M,C=G.N,G.M,G.C;T=load('universe_original_CP1_trace',W/'cp1-evidence-trace-20261031/trace.py');S=load('universe_frozen_industry_stage',W/'industry-mobile-stage-20261031/stage.py');T.BEGIN=BEGIN;T.END=END
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):
 p=Path(p);p.parent.mkdir(exist_ok=True,parents=True);temp=p.with_name(p.name+'.tmp');temp.write_text(json.dumps(T.norm(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n');temp.replace(p)
def source_paths(sid):
 r=N.RECORDS[sid];return {k:N.OLD/r['files'][k]['path'] for k in ['signal','events','states']}|{'IX_G1':N.IX/'signals'/f'{sid}.parquet'}
def compact(rows):
 keys=['canonical_series','scale_id','source_segment','original_E0_episode_id','confirmed_day','receipt_id','decision_evidence_key','formation_start_exclusive','formation_end_inclusive','anchor_observation_id','confirmation_observation_id','previous_market_receipt_id','original_candidate','original_scale','scale_frozen_at','new_advance_price_event_ids','new_log_price_displacement','original_credit','evidence_signature','trace_unknown']
 return [{k:r[k] for k in keys} for r in rows]
def outputs_valid(r):
 return r.get('contract_signature')==SIGNATURE and all(Path(p).exists() and sha(p)==h for p,h in r.get('output_sha256',{}).items())
def emit_stock(sid,case,prefix_sample):
 start=time.monotonic();refs={};checks={};old_source_status=None;CP_reuse=False;facts_reuse=False
 if case is not None:
  assert all(sha(p)==h for p,h in case['source_sha256'].items())
  assert all(sha(W/'case-stock-cp1-warmup-20261031'/p)==h for p,h in case['output_sha256'].items())
  root=W/'case-stock-cp1-warmup-20261031';refs=dict(facts=str(root/'full-facts'/f'{sid}.parquet'),CP1_input=str(root/'CP1-input'/f'{sid}.parquet'),CP1=str(root/'CP1'/f'{sid}.parquet'));f=pd.read_parquet(refs['facts']).loc[:END];q=pd.read_parquet(refs['CP1_input']).loc[:END];z=pd.read_parquet(refs['CP1']).loc[:END];source_hash=case['source_sha256'];CP_reuse=facts_reuse=True;checks['previous_case_full_chain_verified']=True;mode='verified_case_reuse'
 else:
  f,receipt=N.derive(sid,END);paths=source_paths(sid);source_hash={str(p):sha(p) for p in paths.values()};native=pd.read_parquet(W/'native-I-cache-interface-20261031/facts'/f'{sid}.parquet').loc[BEGIN:END];G.exact(f.loc[BEGIN:END],native);checks['native_I_export_all_fields_exact']=True;q=G.frame(sid,f,END);z=M.calculate(q);old=C.O/'signals'/f'{sid}.parquet';mode='new_fixed_chain'
  if old.exists():
   try:
    G.exact(q,C.frame(sid,END));G.exact(z,pd.read_parquet(old).loc[:END]);refs['CP1']=str(old);CP_reuse=True;old_source_status='full_input_and_CP1_exact';checks['old_CP1_current_source_exact']=True
    oldfacts=C.PREP/'facts'/f'{sid}.parquet';ff=pd.read_parquet(oldfacts)
    if set(N.COLS)<=set(ff):G.exact(f,ff.loc[:END,N.COLS]);refs['facts']=str(oldfacts);facts_reuse=True
   except (AssertionError,ValueError,FileNotFoundError) as e:old_source_status='incompatible_or_unavailable:'+str(e)[:350]
  if 'facts' not in refs:
   path=O/'facts'/f'{sid}.parquet';f.to_parquet(path);refs['facts']=str(path)
  path=O/'CP1-input'/f'{sid}.parquet';q.to_parquet(path);refs['CP1_input']=str(path)
  if 'CP1' not in refs:
   path=O/'CP1'/f'{sid}.parquet';z.to_parquet(path);refs['CP1']=str(path)
  if sid in prefix_sample and not f.empty:
   short,_=N.derive(sid,CUT);G.exact(short,f.loc[:CUT]);G.exact(M.calculate(G.frame(sid,short,CUT)),z.loc[:CUT]);checks['physical_I_CP1_prefix_exact']=True
 if f.empty:rs=[];status='not_applicable_no_local_observation_by_end'
 else:
  events_path=next(p for p in source_hash if p.endswith('/events.parquet'));ev=pd.read_parquet(events_path).reindex(q.index);rs,_,_=T.trace(sid,q,z,ev,f.e0_target.reindex(q.index).astype(bool));status='complete';checks['trace_unknown_receipts']=sum(bool(r['trace_unknown']) for r in rs)
 rpath=O/'receipts'/f'{sid}.json';save(rpath,compact(rs));refs['receipts']=str(rpath);checks['old_cache_source_compatibility']=old_source_status
 audit=f.loc[BEGIN:END];zz=z.loc[BEGIN:END];required=f.loc[BEGIN:REQUIRED_END];r=dict(symbol=sid,status=status,mode=mode,CP1_reused=CP_reuse,facts_reused=facts_reuse,contract_signature=SIGNATURE,refs=refs,source_sha256=source_hash,output_sha256={p:sha(p) for p in refs.values()},warm_from=str(f.index.min().date()) if len(f) else None,cache_through=END,required_account_end=REQUIRED_END,full_warm_observations=len(f),audit_observations=len(audit),audit_CP1_ready=int(zz.ready.sum()),audit_CP1_unready=int(len(zz)-zz.ready.sum()),audit_CP1_receipts=int(zz.receipt.sum()),required_account_observations=len(required),required_account_CP1_receipts=int(z.loc[BEGIN:REQUIRED_END,'receipt'].sum()),checks=checks,seconds=time.monotonic()-start)
 save(O/'items'/f'{sid}.json',r);return r
def emit_industry(sid):
 start=time.monotonic();T.BEGIN='1900-01-01';f,ev,ep,reference=T.source_frame(sid,N.RECORDS);z=M.calculate(f);old=W/'cp1-evidence-trace-20261031'/f'{sid}.original-CP1.parquet';checks={}
 if old.exists():G.exact(z.loc[:REQUIRED_END],pd.read_parquet(old).loc[:REQUIRED_END]);checks['previous5_CP1_prefix_exact']=True
 rr,_,_=T.trace(sid,f,z,ev,ep);state=S.run(sid,f,z,{r['confirmed_day']:r['receipt_id'] for r in rr});audit=[dict(series=sid,**r) for r in state if BEGIN<=r['day']<=END];previous=pd.read_parquet(W/'industry-mobile-stage-20261031/coverage90'/f'{sid}.parquet').to_dict('records');assert T.norm(audit)==T.norm(previous),(sid,'old90 state audit mismatch');checks['previous90_full_audit_exact']=True
 previous5=W/'industry-mobile-stage-20261031'/f'{sid}_STATE.json'
 if previous5.exists():assert read(previous5)==[r for r in state if r['day']<=REQUIRED_END];checks['previous5_full_state_prefix_exact']=True
 root=O/'industry';paths={'CP1_input':root/'CP1-input'/f'{sid}.parquet','CP1':root/'CP1'/f'{sid}.parquet','state':root/'state'/f'{sid}.parquet','receipts':root/'receipts'/f'{sid}.json'};f.to_parquet(paths['CP1_input']);z.to_parquet(paths['CP1']);pd.DataFrame(state).to_parquet(paths['state'],index=False);save(paths['receipts'],compact([r for r in rr if BEGIN<=r['confirmed_day']<=END]));sources=[N.OLD/N.RECORDS[sid]['files'][k]['path'] for k in ['signal','events','states']]+[W/'mainline-absolute-Q4-20261031/industry-facts'/f'{sid}.parquet'];r=dict(series=sid,status='complete',contract_signature=SIGNATURE,refs={k:str(p) for k,p in paths.items()},source_sha256={str(p):sha(p) for p in sources},output_sha256={str(p):sha(p) for p in paths.values()},warm_from=str(f.index.min().date()),full_warm_observations=len(f),audit_observations=len(f.loc[BEGIN:END]),audit_CP1_ready=int(z.loc[BEGIN:END].ready.sum()),audit_CP1_receipts=int(z.loc[BEGIN:END].receipt.sum()),checks=checks,seconds=time.monotonic()-start);save(O/'industry/items'/f'{sid}.json',r);T.BEGIN=BEGIN;return r
SOURCES=[Path(__file__),O/'PROTOCOL.txt',W/'native-I-cache-interface-20261031/cache.py',RR/'pv-strength-b5-20261025/code/policy.py',RR/'b5-g1-20261025/code/policies_g1.py',RR/'continuous-protection-lines-20261028/code/model.py',RR/'continuous-protection-lines-20261028/code/common.py',W/'cp1-evidence-trace-20261031/trace.py',W/'industry-mobile-stage-20261031/stage.py',N.OLD/'manifest.json',N.IX/'signals/manifest.json']
SIGNATURE=T.ident('fixed-original-market-cache',BEGIN,END,REQUIRED_END,{str(p):sha(p) for p in SOURCES if p!=Path(__file__) and p!=O/'PROTOCOL.txt'})
def main():
 started=time.monotonic();ids=read(W/'native-I-cache-interface-20261031/FREEZE.json')['stocks'];assert len(ids)==1709 and len(set(ids))==1709;industries=sorted(k for k in N.RECORDS if k.startswith('URFI'));assert len(industries)==90;case={r['sid']:r for r in read(W/'case-stock-cp1-warmup-20261031/MANIFEST.json')};prefix_sample=sorted(set(ids)-set(case))[:3]
 for d in ['facts','CP1-input','CP1','items','receipts','industry/CP1-input','industry/CP1','industry/state','industry/receipts','industry/items']:(O/d).mkdir(parents=True,exist_ok=True)
 freeze=O/'FREEZE.json'
 if not freeze.exists():save(freeze,dict(before_run=True,stocks=ids,industries=industries,case_verified_candidates=len(case),old_CP1_candidates=sum((C.O/'signals'/f'{s}.parquet').exists() for s in ids),prefix_sample=prefix_sample,contract_signature=SIGNATURE,cache_window=[BEGIN,END],next_account_window=[BEGIN,REQUIRED_END],source_sha256={str(p):sha(p) for p in SOURCES},estimated_seconds=705,workers=1,budget_seconds=BUDGET,new_account_paths=0,not_PIT=True))
 else:assert read(freeze)['contract_signature']==SIGNATURE
 allr=[];ir=[];resumed=0
 def progress(phase):
  elapsed=time.monotonic()-started;save(O/'PROGRESS.json',dict(phase=phase,stocks_done=len(allr),industries_done=len(ir),resumed_valid=resumed,seconds=elapsed,remaining_stocks=1709-len(allr),remaining_industries=90-len(ir),status_counts=dict(collections.Counter(r['status'] for r in allr))));print('PROGRESS',phase,len(allr),len(ir),round(elapsed,2),flush=True)
 for sid in ids:
  path=O/'items'/f'{sid}.json'
  if path.exists() and outputs_valid(read(path)):allr.append(read(path));resumed+=1;continue
  if time.monotonic()-started>BUDGET-5:progress('budget_stop_stocks');return
  try:allr.append(emit_stock(sid,case.get(sid),prefix_sample))
  except BaseException as e:
   r=dict(symbol=sid,status='blocked_original_input_or_identity',error=repr(e),traceback=traceback.format_exc(),contract_signature=SIGNATURE,refs={},output_sha256={});save(path,r);allr.append(r)
  if len(allr)%50==0:progress('stocks')
 for sid in industries:
  path=O/'industry/items'/f'{sid}.json'
  if path.exists() and outputs_valid(read(path)):ir.append(read(path));resumed+=1;continue
  if time.monotonic()-started>BUDGET-5:progress('budget_stop_industries');return
  try:ir.append(emit_industry(sid))
  except BaseException as e:
   r=dict(series=sid,status='blocked_industry_input_or_identity',error=repr(e),traceback=traceback.format_exc(),contract_signature=SIGNATURE,refs={},output_sha256={});save(path,r);ir.append(r)
  if len(ir)%15==0:progress('industry')
 save(O/'STOCK_MANIFEST.json',allr);save(O/'INDUSTRY_MANIFEST.json',ir);progress('done');save(O/'COMPLETION.json',dict(completed=True,stocks=1709,industries=90,seconds=time.monotonic()-started,resumed=resumed,stock_status=dict(collections.Counter(r['status'] for r in allr)),industry_status=dict(collections.Counter(r['status'] for r in ir)),CP1_reused=sum(r.get('CP1_reused',False) for r in allr),facts_reused=sum(r.get('facts_reused',False) for r in allr),original407_exact=sum(bool(r.get('checks',{}).get('old_CP1_current_source_exact')) for r in allr),new_account_paths=0,budget_independent=True));print('DONE',round(time.monotonic()-started,2),flush=True)
if __name__=='__main__':main()
