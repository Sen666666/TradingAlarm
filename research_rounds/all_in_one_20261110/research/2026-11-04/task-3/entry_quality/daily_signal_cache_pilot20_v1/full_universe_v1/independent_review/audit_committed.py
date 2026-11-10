"""Independent progressive DONE-only saved-value checks. No model/producer imports."""
from pathlib import Path
import argparse,datetime,json,hashlib,math,os
import numpy as np,pandas as pd,pyarrow as pa,pyarrow.parquet as pq
O=Path(__file__).resolve().parent;R=O.parent;E=R.parent.parent
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();read=lambda p:json.loads(Path(p).read_text())
F=['e0_ready','e0_target','e0_floor','e0_entered','e0_exited','i_target','i_floor','i_entered','i_exited','i_buy','i_exit_reason','g_grade','g_ready','g_fresh_up','g_acute_down','g_up_reasons','numeric_event','numeric_leg_direction','close']
D=['2022-01-24','2024-09-24','2026-01-15']
def exact(a,b,label):
 if pd.isna(a)or pd.isna(b):assert pd.isna(a)and pd.isna(b),(label,a,b)
 elif isinstance(a,(int,float,np.integer,np.floating))and not isinstance(a,(bool,np.bool_)):
  assert np.float64(a).view(np.uint64)==np.float64(b).view(np.uint64),(label,a,b)
 else:assert a==b,(label,a,b)
def series(a,b,label):
 assert a.isna().equals(b.isna()),(label,'null')
 k=a.notna()
 if pd.api.types.is_numeric_dtype(a)and not pd.api.types.is_bool_dtype(a):assert np.array_equal(a[k].to_numpy(float).view(np.uint64),b[k].to_numpy(float).view(np.uint64)),(label,'bits')
 else:assert a[k].astype(str).equals(b[k].astype(str)),(label,'values')
def atomic(p,x):
 t=p.with_suffix('.tmp');t.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n');os.replace(t,p)
args=argparse.ArgumentParser();args.add_argument('--final',action='store_true');z=args.parse_args()
f=read(R/'FREEZE.json');ident=f['cache_identity'];selfsha=sha(__file__)
for p,h in f['code_sha256'].items():assert sha(p)==h
for p,h in f['references_sha256'].items():assert sha(p)==h
schema=pa.ipc.read_schema(pa.BufferReader((R/'DAILY_SCHEMA.arrow').read_bytes()));assert sha(R/'DAILY_SCHEMA.arrow')==f['schema_sha256']
grid=pd.DatetimeIndex(pd.read_parquet(f['grid_path']).day);roster=set(pd.read_csv(R/'UNIVERSE5517.csv').sid);assert len(roster)==5517
statepath=O/'COMMITTED_REVIEW_PROGRESS.json';state=read(statepath)if statepath.exists()else{'cache_identity':ident,'audit_code_sha256':selfsha,'stocks':{}}
assert state['cache_identity']==ident and state['audit_code_sha256']==selfsha
old={d:pd.read_parquet(E/'full_local_signal_20240924_v1/signals/ALL_SIGNALS.parquet'if d==D[1]else E/'full_local_signal_two_dates_v1'/d/'signals/ALL_SIGNALS.parquet').set_index('sid')for d in D}
pvr=pd.read_parquet(E/'local_observable_selection_v1/features/LOCAL_FIXED_DATE_FEATURES.parquet').set_index('sid');pcols=['r','scale','amount_ref','u','b','e','E','score']
receipts=sorted((R/'receipts').glob('*.json'));seen=set();newly=0
for file in receipts:
 r=read(file);sid=r['sid'];assert sid in roster and sid not in seen and file.stem==sid;seen.add(sid)
 assert r['status']=='DONE_VALIDATED'and r['cache_identity']==ident
 path=R/r['file'];assert path.parent==R/'artifacts' and path.name==sid+'.parquet'
 stat=path.stat();assert stat.st_size==r['file_bytes'];rh=sha(file);previous=state['stocks'].get(sid)
 if previous and previous['receipt_sha256']==rh and previous['file_size']==stat.st_size and previous['file_mtime_ns']==stat.st_mtime_ns:
  if z.final:assert sha(path)==r['file_sha256']==previous['file_sha256']
  continue
 assert sha(path)==r['file_sha256'];table=pq.read_table(path);assert table.num_rows==1054 and table.schema.remove_metadata().equals(schema)
 meta=table.schema.metadata or {};assert meta.get(b'local_cache_identity')==ident.encode()and meta.get(b'local_cache_sid')==sid.encode()and meta.get(b'local_cache_complete')==b'true'
 assert json.loads(meta[b'local_cache_details'])==r['details']
 x=table.to_pandas();assert x.sid.eq(sid).all()and pd.DatetimeIndex(x.day).equals(grid)and list(x.columns)==f['schema_columns'];x=x.set_index('day')
 assert x.historical_trading_eligibility.eq('UNKNOWN_NONPIT').all()
 missing=~x.source_row_present;assert x.loc[missing,[c for c in x if c.startswith(('native__','numeric__','cp__','pvr__','stage__'))]].isna().all().all()
 assert x.stock_eligible_price_observation.eq(x.native__close.notna()).all()
 expected=np.where(~x.source_row_present,'MISSING_SOURCE_ROW',np.where(~x.stock_eligible_price_observation,'INVALID_ORIGINAL_PRICE_MASK',np.where(x.native__e0_ready.eq(1)&x.native__g_ready.eq(True),'READY','WARMUP_OR_STRENGTH_UNKNOWN')))
 assert np.array_equal(x.stock_signal_knowledge,expected)
 active=x.native__close.notna();series(x.loc[active,'native__close'],x.loc[active,'price__close'],(sid,'native/source-coordinate'))
 cpvalid=x.cp__input_status.eq('VALID_OR_WARMUP');series(x.loc[cpvalid,'cp__e0_valid'],x.loc[cpvalid,'native__i_target'].astype(bool),(sid,'CP-Ivalid'));series(x.loc[cpvalid,'cp__e0_floor'],x.loc[cpvalid,'native__i_floor'],(sid,'CP-Ifloor'))
 blocked=x.cp__input_status.eq('BLOCKED_BY_PRIOR_INVALID_INPUT');assert x.loc[blocked,[c for c in x if c.startswith('cp__')and c!='cp__input_status']].isna().all().all()
 dates={};ne=nm=npvr=mpvr=0
 for day in D:
  row=x.loc[pd.Timestamp(day)];saved=old[day].loc[sid]
  if pd.isna(row.native__close):
   assert saved.signal_status=='MISSING_TARGET_BAR' and not row.source_row_present,(sid,day,'unexpected-invalid-domain');nm+=1;dates[day]={'exact':False,'hold':False,'buy':False,'known':False}
  else:
   assert saved.signal_status=='EXACT_TARGET_STOCK_SIGNAL'
   for c in F:exact(row['native__'+c],saved[c],(sid,day,c))
   ne+=1;known=bool(row.native__e0_ready==1 and row.native__g_ready==True)
   dates[day]={'exact':True,'known':known,'hold':bool(row.native__e0_ready==1 and row.native__i_target==1),'buy':bool(known and row.native__i_target==1 and row.native__i_buy==True)}
 for _,v in pvr.loc[[sid]].iterrows():
  row=x.loc[pd.Timestamp(v.day)];assert bool(row.source_row_present)==bool(v.target_row_present)
  if not v.target_row_present:mpvr+=1;continue
  for c in pcols:exact(row['pvr__'+c],v[c],(sid,v.day,c))
  npvr+=1
 state['stocks'][sid]={'receipt_sha256':rh,'file_sha256':r['file_sha256'],'file_size':stat.st_size,'file_mtime_ns':stat.st_mtime_ns,'origin':r['origin'],'old19_exact':ne,'old19_missing':nm,'oldPVR_present':npvr,'oldPVR_missing':mpvr,'dates':dates,'input_rows':r['details']['profile']['input_rows'],'CP_blocked_rows':int(blocked.sum())};newly+=1
 if newly%100==0:atomic(statepath,state);print('NEW_DONE_REVIEWED',newly,'TOTAL',len(state['stocks']),flush=True)
assert set(state['stocks'])<=seen,'Previously audited receipt disappeared'
atomic(statepath,state)
counts={d:{'exact':sum(v['dates'][d]['exact']for v in state['stocks'].values()),'missing':sum(not v['dates'][d]['exact']for v in state['stocks'].values()),'ready':sum(v['dates'][d]['known']for v in state['stocks'].values()),'I_hold_true':sum(v['dates'][d]['hold']for v in state['stocks'].values()),'i_buy_true':sum(v['dates'][d]['buy']for v in state['stocks'].values())}for d in D}
result={'status':'PASS_COMMITTED_SUBSET_ONLY_NOT_GLOBAL_COMPLETION','cache_identity':ident,'snapshot_UTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),'committed_receipts_seen':len(seen),'independently_audited_saved_stocks':len(state['stocks']),'new_this_review':newly,'global_expected':5517,'dates':counts,'old19_exact':sum(v['old19_exact']for v in state['stocks'].values()),'old19_missing':sum(v['old19_missing']for v in state['stocks'].values()),'oldPVR_present':sum(v['oldPVR_present']for v in state['stocks'].values()),'oldPVR_missing':sum(v['oldPVR_missing']for v in state['stocks'].values()),'reviewer_models':0,'reviewer_accounts':0,'only_DONE_receipt_paths_read':True,'pending_or_uncommitted_artifacts_read':False,'audit_code_sha256':selfsha,'progress_sha256':sha(statepath)}
if z.final:
 completion=read(R/'GENERATION_COMPLETION.json');assert completion['status']=='COMPLETE_GENERATION_PENDING_INDEPENDENT_AUDIT'and completion['done']==5517 and not completion['unknown']and not completion['errors']
 assert seen==roster==set(state['stocks']) and len(seen)==5517
 assert [counts[d]['exact']for d in D]==[4518,5309,5451]and result['old19_exact']==15278 and result['old19_missing']==1273
 assert [counts[d]['ready']for d in D]==[4393,5286,5412]and [counts[d]['I_hold_true']for d in D]==[2117,3616,4371]and [counts[d]['i_buy_true']for d in D]==[177,2313,779]
 assert sum(v['input_rows']for v in state['stocks'].values())==15739264 and len([v for v in state['stocks'].values()if v['origin']=='REUSED_SEALED_PILOT20_NORMALIZED_SCHEMA_NO_MODEL'])==20
 assert sha(Path(f['source']))==f['source_sha256']
 result.update(status='PASS_FINAL_ALL5517_COMMITTED_CACHE_AND_THREE_ORIGINAL_DATES',remaining_blocks=[],source_final_sha256=f['source_sha256'],generation_completion_sha256=sha(R/'GENERATION_COMPLETION.json'))
 name='FINAL_ALL5517_OUTPUT_AUDIT.json'
else:name='COMMITTED_SNAPSHOT_AUDIT.json'
atomic(O/name,result);print(json.dumps(result,ensure_ascii=False),flush=True)
