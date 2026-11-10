"""Isolated F1/proof replay and process-boundary audit. No financial imports."""
from pathlib import Path
from dataclasses import asdict, dataclass, field
from types import SimpleNamespace
from datetime import datetime, timezone
import ast
import hashlib
import importlib.util
import json
import math
import os
import subprocess
import sys
import time
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import proof_context as PC

O=Path(__file__).resolve().parent
B=O.parent
W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
R=O/'run-v1'
CORE=B/'v2-frozen/signal_core.py'
CONTRACT=B/'v2-frozen/CONTRACT.md'
POLICY=W/'g-broad-s-concentrated-native-r2-20261101/policy.py'
EXPECTED_CORE='962275bd41b5c7bbc062a1191780a6b6a9c616f8d3097ea669b602eabbc9ac59'
EXPECTED_CONTRACT='c3914aed1896563253961ea40d6065614a115cef21e13a93e1e74ad71779c54a'
EXPECTED_POLICY='b27d8fac3e977d30de9153d4a400d62caf9a2c69695692da1a88ecba4e24607e'
ANCHORS={
 '2022':dict(account_first_close='2022-01-04',cutoff='2021-12-31'),
 '2025_26':dict(account_first_close='2025-07-01',cutoff='2025-06-30')}

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def clean(x):
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple,np.ndarray)):return [clean(v) for v in x]
 if isinstance(x,np.generic):return clean(x.item())
 if isinstance(x,float) and not math.isfinite(x):return None
 if isinstance(x,(pd.Timestamp,datetime)):return x.isoformat()
 if isinstance(x,Path):return str(x)
 return x
def canonical(x):return json.dumps(clean(x),sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)
def write(p,x):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 p.write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def number(x):return float(x) if pd.notna(x) and math.isfinite(x) else None

def load_core():
 assert sha(CORE)==EXPECTED_CORE and sha(CONTRACT)==EXPECTED_CONTRACT
 assert sha(POLICY)==EXPECTED_POLICY
 spec=importlib.util.spec_from_file_location('bootstrap_frozen_F1',CORE)
 mod=importlib.util.module_from_spec(spec);sys.modules[spec.name]=mod;spec.loader.exec_module(mod)
 return mod

def isolated_market_reference():
 # Compile ONLY original Scope and evidence; never Policy.__init__ or module imports.
 tree=ast.parse(POLICY.read_text());scope=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='Scope')
 policy=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='Policy')
 evidence=next(n for n in policy.body if isinstance(n,ast.FunctionDef) and n.name=='evidence')
 mod=ast.fix_missing_locations(ast.Module(body=[scope,evidence],type_ignores=[]))
 ns={'dataclass':dataclass,'field':field,'__name__':__name__}
 exec(compile(mod,str(POLICY)+'::market_only_AST','exec'),ns)
 return ns['evidence']

def filtered(path,day,reference=False,only_day=False):
 key='day' if reference else 'date';limit=day if reference else pd.Timestamp(day).to_pydatetime()
 return pq.read_table(path,filters=[(key,'==' if only_day else '<=',limit)]).to_pandas()

def source_for(core,node,row,segment):
 if node['sector'] is not None and pd.notna(row.price_source_segment_id):segment=int(row.price_source_segment_id)
 return core.Source('NATIVE1709-fixed-research-roster',
   'composite-original-as-run' if node['sector'] is None else 'index-'+node['sector'],
   'original-signed-m21/min5/equal-sector-min8' if node['sector'] is None else 'original-signed-m21/research-industry-min5',
   'original-source-segment-'+str(segment)),segment

def observation(core,node,day,row,segment):
 source,segment=source_for(core,node,row,segment)
 close=number(row.price_input);breadth=number(row.breadth)
 if not bool(row.price_observed):assert close is None,'unobservable price must remain unknown'
 return core.Observation(str(pd.Timestamp(day).date()),source,close,breadth),segment

def record(node,row,source_segment,state,dec,previous_permit):
 close=number(row.price_input);breadth=number(row.breadth)
 return dict(day=dec.at,stream=node['original_scope'],close=close,breadth=breadth,
  breadth_margin=breadth-.6 if breadth is not None else None,
  old_line_log_margin=math.log(close/dec.line_used) if close is not None and dec.line_used is not None else None,
  mode=dec.mode,effective_status=dec.effective_status,permit_next_open=dec.permit_next_open,
  permission_change=('permission_granted' if dec.permit_next_open else 'permission_revoked') if dec.permit_next_open!=previous_permit else None,
  original_break=dec.original_break,line_used=dec.line_used,next_line=dec.next_line,prior_scale=dec.scale_before_close,
  anchor=state.anchor,frontier=state.frontier,frozen_segment_scale=state.scale,credit=state.credit,
  starts=state.starts,repairs=state.repairs,failures=state.failures,
  pending_failure_at=state.pending_price_failure.at if state.pending_price_failure else None,
  events=list(dec.events),unknown=list(dec.unknown),source_segment=source_segment,
  ready_m=number(row.get('ready_m',row.get('signed_m_stocks_ready'))),positive_m=number(row.get('positive_m')),
  ready_industries=number(row.get('breadth_industries_ready')),node_id=node['node_id'],sector_name=node['name'])

def same_reference(actual,reference,fields,node,day):
 left={k:clean(actual[k]) for k in fields};right={k:clean(reference[k]) for k in fields}
 if left!=right:
  diff={k:[left[k],right[k]] for k in fields if left[k]!=right[k]}
  raise AssertionError(f'{node} {day} old audited fields differ: {diff}')

def snapshot(core,node,state,dec,proof,consumed_digest,observations,first_day):
 return dict(schema=PC.VERSION,kernel_sha256=EXPECTED_CORE,F1_contract_sha256=EXPECTED_CONTRACT,
  market_reducer_sha256=sha(O/'proof_context.py'),original_policy_market_subset_sha256=EXPECTED_POLICY,
  domain='NATIVE1709',node_id=node['node_id'],original_F1_scope=node['original_scope'],policy_scope=node['policy_scope'],
  asof=state.last_at,original_close_at=state.last_at+'T15:10:00+08:00',
  confirmed_cursor=PC.cursor(state.last_at),scope_observation_sequence=observations,
  input_left_endpoint=first_day,causal_consumed_observation_sha256=consumed_digest,
  f1_checkpoint=json.loads(core.dumps(state)),last_decision=asdict(dec),market_context=asdict(proof),
  market_evidence_does_not_certify_actual_trial=True)

def replay_one(core,node,data,ref=None):
 assert len(data) and data.index.is_unique and data.index.is_monotonic_increasing
 state=core.State(scope=node['original_scope']);proof=PC.MarketProof(scope=node['policy_scope'])
 reference_fn=isolated_market_reference();reference=SimpleNamespace(scopes={},proof_history=[])
 daily=[];proof_daily=[];segment=0;previous_permit=False;consumed=hashlib.sha256();field_points=0
 for seq,(day,row) in enumerate(data.iterrows(),1):
  ob,segment=observation(core,node,day,row,segment)
  consumed.update((canonical(asdict(ob))+'\n').encode())
  state,dec=core.step(state,ob)
  source=PC.source_signature(asdict(ob.source));support=state.mode=='ACTIVE' and state.pending_price_failure is None
  oldlen=len(proof.proof_history)
  proof=PC.reduce_market(proof,source=source,day=ob.at,seq=seq,events=dec.events,permit=dec.permit_next_open,support=support)
  reference_fn(reference,node['policy_scope'],source,dec.events,dec.permit_next_open,support,PC.cursor(ob.at),seq)
  q=reference.scopes[node['policy_scope']]
  for k in ('source','seq','context','permit','support','mature'):assert getattr(proof,k)==getattr(q,k),(node['node_id'],ob.at,k)
  assert list(proof.events)==q.events
  assert list(proof.proof_history[oldlen:])==reference.proof_history[oldlen:]
  assert len(proof.proof_history)==len(reference.proof_history)
  rec=record(node,row,segment,state,dec,previous_permit);daily.append(rec)
  if ref is not None:
   same_reference(rec,ref.loc[ob.at].to_dict(),list(ref.columns),node['node_id'],ob.at);field_points+=len(ref.columns)
  proof_daily.append(dict(day=ob.at,scope=node['policy_scope'],source=source,seq=seq,
    confirmed_cursor=PC.cursor(ob.at),context=proof.context,support=proof.support,mature=proof.mature,permit=proof.permit))
  previous_permit=dec.permit_next_open
 assert list(proof.proof_history)==reference.proof_history
 result=snapshot(core,node,state,dec,proof,consumed.hexdigest(),len(data),str(data.index[0].date()))
 return result,pd.DataFrame(daily).set_index('day'),pd.DataFrame(proof_daily).set_index('day'),field_points

def worker(mode,key):
 core=load_core();specs=read(R/'SOURCE_MANIFEST.json');nodes=specs['nodes'];anchor=ANCHORS[key];window=R/key
 assert read(R/'FREEZE.json')['runner_sha256']==sha(__file__)
 assert read(R/'FREEZE.json')['reducer_sha256']==sha(O/'proof_context.py')
 root=window/({'source':'verification/source-prefix','physical':'states','cold_next':'verification/cold-through-next','resume':'verification/resumed-next'}[mode])
 root.mkdir(parents=True,exist_ok=False);out=[];access=[];started=time.monotonic()
 for node in nodes:
  nid=node['node_id'];cut=anchor['cutoff'];end=anchor['account_first_close'] if mode=='cold_next' else cut
  if mode=='resume':
   path=window/'states'/f'{nid}.json';saved=read(path)
   state=core.loads(canonical(saved['f1_checkpoint']));proof=PC.from_dict(saved['market_context'])
   assert state.last_at==cut and proof.last_day==cut
   npth=window/'verification/next-observation'/f'{nid}.parquet';data=pd.read_parquet(npth)
   access.append(dict(path=str(npth),min=str(data.index.min().date()),max=str(data.index.max().date()),rows=len(data),purpose='one next observation only'))
   assert len(data)==1 and str(data.index[0].date())==anchor['account_first_close']
   ob,segment=observation(core,node,data.index[0],data.iloc[0],int(state.source.revision.split('-')[-1]))
   state,dec=core.step(state,ob)
   proof=PC.reduce_market(proof,source=PC.source_signature(asdict(ob.source)),day=ob.at,seq=proof.seq+1,
      events=dec.events,permit=dec.permit_next_open,support=state.mode=='ACTIVE' and state.pending_price_failure is None)
   payload=dict(f1_checkpoint=json.loads(core.dumps(state)),last_decision=asdict(dec),market_context=asdict(proof))
   expected=read(window/'verification/cold-through-next'/f'{nid}.json')
   assert canonical(payload)==canonical({k:expected[k] for k in payload}),(key,nid,'restored next state differs')
   write(root/f'{nid}.json',payload)
   out.append(dict(node_id=nid,restored_from=str(path),seed_sha256=sha(path),next_observation_sha256=sha(npth),
      full_state_context_history_exact=True,scope_observation_sequence=proof.seq))
  else:
   ip=Path(node['input_file']) if mode in ('source','cold_next') else window/'input-prefix'/f'{nid}.parquet'
   data=filtered(ip,end) if mode in ('source','cold_next') else pd.read_parquet(ip)
   assert str(data.index[-1].date())==end and (data.index<=pd.Timestamp(end)).all()
   access.append(dict(path=str(ip),predicate='date <= '+end if mode in ('source','cold_next') else 'entire physically truncated file',
       min=str(data.index.min().date()),max=str(data.index.max().date()),rows=len(data)))
   if mode=='cold_next':
    refpath=window/'verification/reference-through-next'/f'{nid}.parquet'
   else:refpath=window/'reference-prefix'/f'{nid}.parquet'
   ref=pd.read_parquet(refpath)
   assert list(ref.index)==[str(t.date()) for t in data.index]
   result,daily,proofdaily,fields=replay_one(core,node,data,ref)
   write(root/f'{nid}.json',result)
   daily.to_parquet(root/f'{nid}.daily.parquet');proofdaily.to_parquet(root/f'{nid}.proof.parquet')
   if mode=='physical':
    baseline=window/'verification/source-prefix'
    assert sha(root/f'{nid}.json')==sha(baseline/f'{nid}.json'),(key,nid,'physical checkpoint mismatch')
    assert sha(root/f'{nid}.daily.parquet')==sha(baseline/f'{nid}.daily.parquet')
    assert sha(root/f'{nid}.proof.parquet')==sha(baseline/f'{nid}.proof.parquet')
   out.append(dict(node_id=nid,observations=len(data),old_shadow_fields_exact=fields,
       every_market_context_step_matches_isolated_original_evidence=True,
       mode=result['last_decision']['mode'],effective_status=result['last_decision']['effective_status'],
       permit=proofdaily.iloc[-1].permit,mature=proofdaily.iloc[-1].mature,support=proofdaily.iloc[-1].support,
       unknown=list(result['last_decision']['unknown']),ready_m=number(daily.iloc[-1].ready_m),
       physical_checkpoint_byte_exact=mode=='physical',checkpoint_sha256=sha(root/f'{nid}.json')))
 write(root/'WORKER_RESULT.json',dict(mode=mode,anchor=key,pid=os.getpid(),passed=True,nodes=out,data_access=access,
       loaded_financial_modules=[n for n in sys.modules if n in ('native_capital','imports_native','policy','joint_v3')],
       seconds=time.monotonic()-started))
 print('WORKER_DONE',key,mode,len(out),round(time.monotonic()-started,3),flush=True)

def execute(mode,key):
 subprocess.run([sys.executable,'-B',str(Path(__file__).resolve()),'worker',mode,key],check=True)

def main():
 R.mkdir(exist_ok=False);begun=time.monotonic()
 assert sha(CORE)==EXPECTED_CORE and sha(CONTRACT)==EXPECTED_CONTRACT and sha(POLICY)==EXPECTED_POLICY
 catpath=B/'industry-coverage/run-v1/NODE_CATALOGUE.json';cat=read(catpath)
 nodes=[dict(node_id='NATIVE1709_global',domain='NATIVE1709',sector=None,name='original global composite',
    original_scope='NATIVE1709_global',policy_scope='G',fixed_identities=1709,source_roster=1687,
    input_file=str(B/'input-preparation/prepared-v2/NATIVE1709/market.parquet'),
    reference=str(B/'historical-shadow/run-v1/NATIVE1709_global_daily.parquet'))]
 for n in cat:
  if n['domain']=='NATIVE1709':
   nodes.append(dict(node_id=n['node_id'],domain='NATIVE1709',sector=n['sector'],name=n['name'],
     original_scope=n['scope'],policy_scope=n['sector'],fixed_identities=n['fixed_identities'],source_roster=n['source_roster'],
     input_file=n['input_file'],reference=n['daily_result_path']))
 assert len(nodes)==91 and len({n['policy_scope'] for n in nodes})==91
 inputs=[Path(n[k]) for n in nodes for k in ('input_file','reference')]
 approved_roots=[B/'input-preparation/prepared-v2',B/'historical-shadow/run-v1',B/'industry-coverage/run-v1']
 approved={str(root/rel):digest for root in approved_roots for rel,digest in read(root/'ARTIFACT_SHA256.json').items()}
 assert all(str(p) in approved and sha(p)==approved[str(p)] for p in inputs),'input/reference differs from original frozen artifact manifest'
 sources=[CORE,CONTRACT,POLICY,catpath,B/'g-s-minimal-input-readiness/PREPARATION_MANIFEST.json',
    B/'input-preparation/prepared-v2/INPUT_GATE.json',B/'industry-coverage/run-v1/INPUT_GATE.json',
    B/'historical-shadow/run-v1/SHADOW_FREEZE.json',B/'industry-coverage/run-v1/SHADOW_FREEZE.json',
    B/'historical-shadow/run_shadow.py',B/'industry-coverage/extend_industries.py',
    W/'case-stage-ledger-20261031/v3/joint_v3.py',
    W/'capital-capability-design-only-20261101/G_BROAD_S_CONCENTRATED_CONTRACT_PROPOSAL.txt',
    W/'capital-capability-design-only-20261101/G_BROAD_S_CONCENTRATED_CONTRACT_V2.txt']+inputs+[root/'ARTIFACT_SHA256.json' for root in approved_roots]
 hashes={str(p):sha(p) for p in sources}
 write(R/'SOURCE_MANIFEST.json',dict(created_at=datetime.now(timezone.utc).isoformat(),sources_sha256=hashes,nodes=nodes,
    anchors=ANCHORS,source_full_file_hashes_are_provenance_only_not_state_inputs=True))
 write(R/'FREEZE.json',dict(before_model_execution=True,kernel_sha256=EXPECTED_CORE,F1_contract_sha256=EXPECTED_CONTRACT,
    original_policy_sha256=EXPECTED_POLICY,protocol_sha256=sha(O/'PROTOCOL.txt'),runner_sha256=sha(__file__),
    reducer_sha256=sha(O/'proof_context.py'),source_manifest_sha256=sha(R/'SOURCE_MANIFEST.json'),
    clock='original joint_v3.ordinal(day)=date.toordinal(); original close15:10+08; full scope seq',
    account_first_closes=ANCHORS,all_native_scopes=91,no_OLD407=True))
 # Materialize cutoff files. Do not read next observations at this phase.
 prefixes=[]
 for key,a in ANCHORS.items():
  for n in nodes:
   d=filtered(n['input_file'],a['cutoff']);ref=filtered(n['reference'],a['cutoff'],True)
   assert len(d) and (d.index<=pd.Timestamp(a['cutoff'])).all()
   assert list(ref.index)==[str(t.date()) for t in d.index]
   ip=R/key/'input-prefix'/f"{n['node_id']}.parquet";rp=R/key/'reference-prefix'/f"{n['node_id']}.parquet"
   ip.parent.mkdir(parents=True,exist_ok=True);rp.parent.mkdir(parents=True,exist_ok=True)
   d.to_parquet(ip);ref.to_parquet(rp)
   pd.testing.assert_frame_equal(d,pd.read_parquet(ip),check_exact=True)
   prefixes.append(dict(anchor=key,node_id=n['node_id'],first=str(d.index[0].date()),last=str(d.index[-1].date()),
    observations=len(d),input_path=str(ip),input_sha256=sha(ip),reference_path=str(rp),reference_sha256=sha(rp),
    unknown_price=int(d.price_input.isna().sum()),unknown_breadth=int(d.breadth.isna().sum()),
    fixed_identities=n['fixed_identities'],source_roster=n['source_roster']))
 write(R/'PHYSICAL_PREFIX_MANIFEST.json',prefixes)
 for key in ANCHORS:
  execute('source',key);execute('physical',key)
 states_before={str(p.relative_to(R)):sha(p) for key in ANCHORS for p in (R/key/'states').rglob('*') if p.is_file()}
 write(R/'BEFORE_NEXT_OBSERVATION_SNAPSHOT_SHA256.json',states_before)
 # Only now export the one next observation and reference prefix for restore tests.
 next_records=[]
 for key,a in ANCHORS.items():
  for n in nodes:
   day=a['account_first_close'];q=filtered(n['input_file'],day,only_day=True)
   assert len(q)==1 and str(q.index[0].date())==day
   p=R/key/'verification/next-observation'/f"{n['node_id']}.parquet";p.parent.mkdir(parents=True,exist_ok=True);q.to_parquet(p)
   ref=filtered(n['reference'],day,True);rp=R/key/'verification/reference-through-next'/f"{n['node_id']}.parquet"
   rp.parent.mkdir(parents=True,exist_ok=True);ref.to_parquet(rp)
   next_records.append(dict(anchor=key,node_id=n['node_id'],day=day,rows=1,input_sha256=sha(p),purpose='restore test only; excluded from bootstrapped state'))
 write(R/'NEXT_OBSERVATION_TEST_MANIFEST.json',next_records)
 for key in ANCHORS:execute('cold_next',key);execute('resume',key)
 states_after={str(p.relative_to(R)):sha(p) for key in ANCHORS for p in (R/key/'states').rglob('*') if p.is_file()}
 assert states_before==states_after
 assert hashes=={p:sha(p) for p in hashes}
 workers=[read(R/key/path/'WORKER_RESULT.json') for key in ANCHORS for path in
   ('verification/source-prefix','states','verification/cold-through-next','verification/resumed-next')]
 assert len({x['pid'] for x in workers})==8
 assert all(not x['loaded_financial_modules'] for x in workers)
 summary={}
 for key in ANCHORS:
  rows=read(R/key/'states/WORKER_RESULT.json')['nodes'];industries=rows[1:]
  summary[key]=dict(global_state=rows[0],industry_nodes=90,industry_active=sum(x['mode']=='ACTIVE' for x in industries),
   industry_permit=sum(x['permit'] for x in industries),industry_mature=sum(x['mature'] for x in industries),
   industry_mature_and_permit=sum(x['mature'] and x['permit'] for x in industries),
   unknown_breadth_at_cutoff=sum('breadth' in x['unknown'] for x in industries),
   unknown_nodes=[dict(node_id=x['node_id'],unknown=x['unknown'],mode=x['mode'],ready_m=x['ready_m']) for x in industries if x['unknown']])
 write(R/'COMPLETION.json',dict(passed=True,anchors=2,scopes_per_anchor=91,complete_seed_checkpoints=182,
   prefix_physical_files=182,every_available_old_daily_field_exact=True,
   original_prefix_field_comparisons=sum(x['old_shadow_fields_exact'] for w in workers if w['mode']=='physical' for x in w['nodes']),
   prefix_observations=sum(x['observations'] for x in prefixes),all_original_evidence_context_steps_exact=True,
   physical_source_checkpoint_byte_identity=182,cross_process_restore_next_full_state_exact=182,
   independent_worker_pids=[x['pid'] for x in workers],seed_snapshots_unchanged_after_next_tests=True,
   sources_unchanged=True,kernel_and_contract_unchanged=True,summary=summary,
   financial_accounts_created=0,financial_account_events=0,stock_intents_or_orders=0,downloads=0,
   historical_future_returns_read=0,seconds=time.monotonic()-begun))
 write(R/'ARTIFACT_SHA256.json',{str(p.relative_to(R)):sha(p) for p in sorted(R.rglob('*')) if p.is_file() and p.name!='ARTIFACT_SHA256.json'})
 print('BOOTSTRAP_COMPLETE',canonical(read(R/'COMPLETION.json')),flush=True)

if __name__=='__main__':
 try:
  if len(sys.argv)>1 and sys.argv[1]=='worker':worker(sys.argv[2],sys.argv[3])
  else:main()
 except BaseException as e:
  write(R/('FAILURE-'+('-'.join(sys.argv[1:]) or 'coordinator')+'.json'),dict(type=type(e).__name__,reason=str(e),pid=os.getpid()))
  raise
