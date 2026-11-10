"""Original CP1 trace on cached numeric output, then ONE frozen descriptive gate.
No economic loop, no numeric CP recomputation, no filtered PnL.
"""
from pathlib import Path
from types import SimpleNamespace
from collections import defaultdict
import ast,collections,json,hashlib,math,time
import numpy as np,pandas as pd
R=Path(__file__).resolve().parent.parent;O=Path(__file__).resolve().parent;W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds');U=W/'universe-cp1-inputs-20261031';RR=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds');H={}
def src(p,expected=None):
 p=Path(p);h=hashlib.sha256(p.read_bytes()).hexdigest();assert expected is None or h==expected,(p,'hash differs');H[str(p)]=h;return p
def clean(x):
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,(tuple,list)):return [clean(v) for v in x]
 if isinstance(x,np.generic):return clean(x.item())
 if x is pd.NA or x is pd.NaT:return None
 if isinstance(x,pd.Timestamp):return x.strftime('%Y-%m-%d')
 if isinstance(x,float) and not math.isfinite(x):return None
 return x
def dump(n,x):
 with (O/n).open('x') as f:json.dump(clean(x),f,ensure_ascii=False,indent=2,allow_nan=False)
def extract(p,names,env):
 p=src(p);s=p.read_text();found=set()
 for node in ast.parse(s).body:
  if isinstance(node,(ast.FunctionDef,ast.ClassDef)) and node.name in names:exec(compile(ast.get_source_segment(s,node),str(p)+':definitions_only','exec'),env);found.add(node.name)
 assert found==names
src(O/'CONTRACT.md');src(__file__)
dump('TRACE_PREFLIGHT_FREEZE.json',dict(contract_sha256=H[str(O/'CONTRACT.md')],code_sha256=H[str(Path(__file__))],formula_count=1,economic_runs=0,numeric_CP_recomputations=0,fixed_before_full_gate_values=True,known_cases_already_observed=True))
model=src(RR/'continuous-protection-lines-20261028/code/model.py');env=dict(np=np,pd=pd,math=math,hashlib=hashlib,json=json,collections=collections,BEGIN='1900-01-01',END='2026-06-30',SCALE='CP1-original:'+H[str(model)][:16]);extract(W/'cp1-evidence-trace-20261031/trace.py',{'ident','norm','trace'},env)
menv=dict(EPS=4*2**-53/(1-4*2**-53));extract(model,{'ge'},menv);T=SimpleNamespace(ident=env['ident'],norm=env['norm'],M=SimpleNamespace(ge=menv['ge']));senv=dict(T=T,pd=pd,math=math);extract(W/'industry-mobile-stage-20261031/stage.py',{'Stage','run'},senv)
manifest=json.loads(src(U/'INDUSTRY_MANIFEST.json').read_text());priority=['URFI881129','URFI881280','URFI881130','URFI881275'];manifest=sorted(manifest,key=lambda x:(priority.index(x['series']) if x['series'] in priority else 100,x['series']))
rows=[];coverage=[];day_source=[];begin=time.monotonic();allstates=[]
for item in manifest:
 sec=item['series'];refs=item['refs']
 f=pd.read_parquet(src(refs['CP1_input'],item['output_sha256'][refs['CP1_input']]));z=pd.read_parquet(src(refs['CP1'],item['output_sha256'][refs['CP1']]));state=pd.read_parquet(src(refs['state'],item['output_sha256'][refs['state']]))
 ep=next(k for k in item['source_sha256'] if k.endswith('/events.parquet'));ev=pd.read_parquet(src(ep,item['source_sha256'][ep])).reindex(f.index)
 sp=next(k for k in item['source_sha256'] if k.endswith('/signal.parquet'));signal=pd.read_parquet(src(sp,item['source_sha256'][sp])).reindex(f.index)
 assert f.index.equals(z.index);assert np.array_equal(f.close.to_numpy(),signal.close.to_numpy())
 ids=signal.source_kind.astype('string')+'|'+signal.source_path.astype('string')+'|'+signal.segment_id.astype('string');assert ids.notna().all()
 receipts,_,checks=env['trace'](sec,f,z,ev,f.e0_valid)
 rid_by_day={v['confirmed_day']:v['receipt_id'] for v in receipts};rebuilt=pd.DataFrame(senv['run'](sec,f,z,rid_by_day));pd.testing.assert_frame_equal(rebuilt,state,check_exact=True,check_dtype=False)
 state['day']=pd.to_datetime(state.day).dt.strftime('%Y-%m-%d');ss=state.set_index('day');state['sector']=sec;allstates.append(state)
 day_source.extend(dict(sector=sec,day=str(d.date()),native_sector_source_identity=i) for d,i in ids.items())
 receipt_min=[]
 for r in receipts:
  d=r['confirmed_day'];t=ss.loc[d];q=z.loc[d];a=r['formation_start_exclusive'];segids=ids.loc[a:d];source_ok=bool(len(segids) and segids.notna().all() and segids.nunique()==1)
  accepted=bool(t.new_receipt and t.authorization_usable and not t.receipt_ignored_same_observation and t.authorization_id==r['receipt_id'])
  positive=bool(q.ready and q.receipt and q.delta_frontier>0 and menv['ge'](q.displacement,math.sqrt(5)*q.scale) and menv['ge'](q.credit,math.sqrt(5)*q.scale))
  row={k:r.get(k) for k in ['canonical_series','receipt_id','scale_id','source_segment','original_E0_episode_id','confirmed_day','formation_start_exclusive','formation_end_inclusive','anchor_observation_id','confirmation_observation_id','previous_market_receipt_id','previous_market_confirmed_day','original_candidate','original_scale','original_credit','new_log_price_displacement','new_advance_observations','evidence_signature','trace_unknown']}
  row.update(native_E0_episode_at_confirmation=t.E0_episode,native_attempt_id_at_confirmation=t.attempt_id,source_identity_at_confirmation=ids.loc[d],source_identity_at_formation_start=ids.loc[a],formation_source_consistent=source_ok,positive_original_CP1_receipt=positive,accepted_by_original_stage=accepted,ignored_at_confirmation=bool(t.receipt_ignored_same_observation),stage_action_at_confirmation=t.action,state_source_path=refs['state'],CP1_input_source_path=refs['CP1_input'],CP1_cached_source_path=refs['CP1'],signal_source_path=sp)
  rows.append(row);receipt_min.append(row)
 coverage.append(dict(sector=sec,rows=len(state),trace_receipts=len(receipts),trace_unknown=sum(bool(v['trace_unknown']) for v in receipts),accepted_receipts=sum(v['accepted_by_original_stage'] for v in receipt_min),formation_source_unknown=sum(not v['formation_source_consistent'] for v in receipt_min),actual_source_transitions=int(ids.ne(ids.shift()).iloc[1:].sum()),numeric_CP_recomputed=False,state_exact=True))
 if sec in priority:
  print('PRIORITY_TRACE_READY',sec,json.dumps(clean([r for r in receipt_min if r['receipt_id'] in set(ss.loc[ss.index.isin(['2024-09-25','2022-01-05','2022-11-08']),'authorization_id'].dropna())]),ensure_ascii=False),flush=True)
 if len(coverage)%15==0:print('TRACE_PROGRESS',len(coverage),len(rows),round(time.monotonic()-begin,1),flush=True)
trace=pd.DataFrame(rows);assert not trace.duplicated(['canonical_series','receipt_id']).any();trace.to_csv(O/'ORIGINAL_SECTOR_CP1_FULL_RECEIPTS.csv',index=False,mode='x');pd.DataFrame(coverage).to_csv(O/'ORIGINAL_TRACE_SOURCE_QA.csv',index=False,mode='x')
# Different hash conventions of trace/Stage are reconciled via exact original day/receipt mapping.
tr={r['receipt_id']:r for r in rows};ds=pd.DataFrame(day_source);states=pd.concat(allstates,ignore_index=True);statekeys=states.set_index(['sector','day'])
def enrich(df):
 df=df.merge(ds,on=['sector','day'],how='left',validate='many_to_one')
 out=[]
 for row in df.to_dict('records'):
  auth=row.get('native_sector_authorization_id');a=tr.get(auth);result=dict(current_authorization_trace_found=a is not None,current_authorization_confirmed_day=None,current_authorization_formation_start=None,current_authorization_formation_end=None,current_authorization_accepted=None,current_authorization_source_consistent=None,current_authorization_same_native_episode=None,current_authorization_same_attempt=None,current_authorization_trace_unknown=None,current_authorization_clock_relation='UNKNOWN',sector_market_condition='UNKNOWN',sector_market_reason='UNKNOWN_MISSING_STATE')
  usable=row.get('native_sector_authorization_usable');stockbirth=row.get('root_day');day=row.get('day');has_state=pd.notna(row.get('native_sector_action'))
  if a:
   source_ok=a['formation_source_consistent'] and a['source_identity_at_confirmation']==row.get('native_sector_source_identity')
   episode_same=a['native_E0_episode_at_confirmation']==row.get('native_sector_E0_episode');attempt_same=a['native_attempt_id_at_confirmation']==row.get('native_sector_attempt_id')
   result.update(current_authorization_confirmed_day=a['confirmed_day'],current_authorization_formation_start=a['formation_start_exclusive'],current_authorization_formation_end=a['formation_end_inclusive'],current_authorization_accepted=a['accepted_by_original_stage'],current_authorization_source_consistent=source_ok,current_authorization_same_native_episode=episode_same,current_authorization_same_attempt=attempt_same,current_authorization_trace_unknown=json.dumps(a['trace_unknown']),current_authorization_receipt_id=a['receipt_id'],current_authorization_original_episode=a['original_E0_episode_id'])
   if pd.notna(stockbirth):result['current_authorization_clock_relation']='AFTER_STOCK_BIRTH' if a['confirmed_day']>stockbirth else 'SAME_DAY_AS_STOCK_BIRTH' if a['confirmed_day']==stockbirth else 'BEFORE_STOCK_BIRTH'
  if has_state and row.get('native_sector_action')=='unknown':result.update(sector_market_condition='UNKNOWN',sector_market_reason='UNKNOWN_CURRENT_STAGE')
  elif has_state and pd.notna(usable) and not bool(usable):result.update(sector_market_condition='DENY',sector_market_reason='NO_CURRENT_USABLE_AUTHORIZATION')
  elif has_state and bool(usable):
   if not a:result.update(sector_market_condition='UNKNOWN',sector_market_reason='CURRENT_AUTH_ID_NOT_TRACED')
   elif a['canonical_series']!=row['sector'] or a['trace_unknown'] or not a['positive_original_CP1_receipt'] or not a['accepted_by_original_stage'] or not result['current_authorization_source_consistent'] or not result['current_authorization_same_native_episode'] or not result['current_authorization_same_attempt'] or a['confirmed_day']>day:result.update(sector_market_condition='UNKNOWN',sector_market_reason='AUTH_ID_SOURCE_EPISODE_OR_ACCEPTANCE_UNPROVEN')
   elif pd.isna(stockbirth):result.update(sector_market_condition='UNKNOWN',sector_market_reason='UNKNOWN_STOCK_ROOT_BIRTH')
   elif a['confirmed_day']>stockbirth:result.update(sector_market_condition='ALLOW',sector_market_reason='CURRENT_ACCEPTED_POST_BIRTH_AUTHORIZATION')
   else:result.update(sector_market_condition='DENY',sector_market_reason='CURRENT_AUTH_NOT_STRICTLY_POST_BIRTH')
  born=row.get('born');parent=row.get('proxy_parent_before_signal');source=row.get('case_source_status')
  if source=='UNKNOWN_MISSING_SOURCE' or pd.isna(born):gate='UNKNOWN_STOCK_SIGNAL'
  elif bool(born):gate='KEEP_ORIGINAL_ROOT_BIRTH'
  elif parent=='EXISTING_PROXY_PROBE_PARENT':gate='BYPASS_EXISTING_PROBE_PARENT'
  elif parent=='NO_PROXY_PROBE_PARENT':gate=result['sector_market_condition']+'_LATE_NO_PARENT'
  else:gate='UNKNOWN_EXECUTION_PARENT'
  result['preflight_gate']=gate;out.append(result)
 return pd.concat([df.reset_index(drop=True),pd.DataFrame(out)],axis=1)
m=pd.read_csv(src(O/'MARKET_RECEIPT_BASE_FACTS.csv'),low_memory=False);m=enrich(m);m.to_csv(O/'MARKET_RECEIPT_PREFLIGHT.csv',index=False,mode='x')
ent=pd.read_csv(src(O/'REGISTERED_ENTRY_BASE_FACTS.csv'),low_memory=False);ent['day']=ent.signal_day
extra=[c for c in m if c.startswith(('current_authorization_','sector_market_'))]+['preflight_gate','native_sector_source_identity'];ent=ent.merge(m[['year','sid','day']+extra],on=['year','sid','day'],how='left',validate='one_to_one');ent.to_csv(O/'REGISTERED_ENTRY_PREFLIGHT.csv',index=False,mode='x')
case=pd.read_csv(src(O/'FIXED_CASE_BASE_FACTS.csv'),low_memory=False);case=enrich(case);case.to_csv(O/'FIXED_CASE_PREFLIGHT.csv',index=False,mode='x')
# No outcome totals, filtered PnL, or new return in gate tables.
summary=[];cross=[]
for y in [2022,2024]:
 for scope in ['ALL','COMMON']:
  for denominator,df in [('MARKET_RECEIPTS',m),('REGISTERED_ENTRIES',ent),('ORIGINAL_PROXY_BUYS',ent[ent.actual_buy])]:
   g=df[df.year.eq(y)&(df.common if scope=='COMMON' else True)]
   counts=g.preflight_gate.value_counts().to_dict();summary.append(dict(year=y,scope=scope,denominator=denominator,n=len(g),gate_counts=counts,deny_fraction=counts.get('DENY_LATE_NO_PARENT',0)/len(g),unknown_fraction=sum(v for k,v in counts.items() if k.startswith('UNKNOWN'))/len(g)))
   for cols in [['preflight_gate','ticket_fact'],['preflight_gate','prewindow_root_fact'],['preflight_gate','window_participation_fact'],['preflight_gate','native_sector_action','native_sector_new_receipt','native_sector_authorization_usable'],['preflight_gate','root_exit_relation_fact']]:
    for key,z in g.groupby(cols,dropna=False):cross.append(dict(year=y,scope=scope,denominator=denominator,grouping='|'.join(cols),**dict(zip(cols,key)),n=len(z)))
dump('PREFLIGHT_COUNTS.json',summary);pd.DataFrame(cross).to_csv(O/'PREFLIGHT_COUNT_CROSSES.csv',index=False,mode='x')
changed=[k for k,v in H.items() if hashlib.sha256(Path(k).read_bytes()).hexdigest()!=v];assert not changed
baseh=json.loads(src(O/'BASE_SOURCE_HASHES.json').read_text());assert all(hashlib.sha256(Path(k).read_bytes()).hexdigest()==v for k,v in baseh.items())
dump('TRACE_PREFLIGHT_SOURCE_HASHES.json',H);dump('TRACE_PREFLIGHT_QA.json',dict(sectors=len(coverage),trace_receipts=len(trace),trace_unknown=sum(bool(r['trace_unknown']) for r in rows),source_changed_during_formation=sum(not r['formation_source_consistent'] for r in rows),all_native_stage_fields_rebuilt_exact=True,source_hashes_unchanged=True,economic_runs=0,numeric_CP_recomputations=0,filtered_PnL_runs=0,parameter_searches=0,formula_count=1,seconds=time.monotonic()-begin))
print('SUMMARY',json.dumps(clean(summary),ensure_ascii=False),flush=True);print('CASES',case[['sid','day','root_day','native_sector_authorization_id','current_authorization_confirmed_day','current_authorization_formation_start','native_sector_authorization_usable','preflight_gate','sector_market_condition','sector_market_reason']].to_string(index=False),flush=True)
