"""Read-only comprehensive daily availability inventory; no account replay or execution."""
from pathlib import Path
import sys,json,hashlib,time,resource,importlib.util,collections
import pandas as pd
import numpy as np
sys.dont_write_bytecode=True
ROOT=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1')
BASE=ROOT/'m3_ab_shared_probe_v1'
OUT=BASE/'daily_gap_inventory_v1'
START=pd.Timestamp('2022-01-01'); END=pd.Timestamp('2026-06-30')
t0=time.monotonic()
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def date(v): return '' if pd.isna(v) else str(pd.Timestamp(v).date())
def save(name,v):
 with (OUT/name).open('x') as f: json.dump(v,f,ensure_ascii=False,indent=2,default=str);f.write('\n')
def csv(name,rows):
 with (OUT/name).open('x') as f: pd.DataFrame(rows).to_csv(f,index=False)
def boolean(x):return x.isin([True,1])
def finite_positive(x):
 v=pd.to_numeric(x,errors='coerce')
 return np.isfinite(v)&v.gt(0)
assert OUT.is_dir() and not (OUT/'RESULT.json').exists()
save('STARTED.json',{'started_utc':pd.Timestamp.now(tz='UTC').isoformat(),'scope':'STATIC_SOURCE_INVENTORY_ONLY_NO_ECONOMIC_RUN','follow_end':date(END)})
protected={}
for folder in [BASE/'indexed_execution_v1/cohort_2022',BASE/'indexed_execution_v1/cohort_2024_924',BASE/'known_halt_contract_v1/cohort_2022_recovery_v2']:
 for p in folder.iterdir():
  if p.is_file(): protected[str(p)]=sha(p)
spec=importlib.util.spec_from_file_location('inventory_bridge',BASE/'source_bridge_v1/bridge.py');bridge=importlib.util.module_from_spec(spec);spec.loader.exec_module(bridge)
s=bridge.load_original('2022')
assert s._no_budget_runs==0 and not s.actions and not s.rounds
cal=s.cal[(s.cal>=START)&(s.cal<=END)]
ev=s.ev.copy(); assert ev.day.min()>=START and ev.day.max()<=pd.Timestamp('2022-12-31')
records=[]; possible={}
for r in ev.to_dict('records'):
 status='I_INELIGIBLE' if not s.true(r['I_qualified']) else 'PVR_UNKNOWN' if not s.true(r['PVR_known']) or not s.finite(r['PVR_score']) else s.checkclose(r)['close_check']
 nxt=cal[cal>r['day']]
 rr={k:r[k] for k in ['event_id','sid','name','sector','industry','event_type']}
 rr.update(signal_day=date(r['day']),next_common_open=date(nxt[0]) if len(nxt) else '',static_close_check=status)
 records.append(rr)
 if status=='PASS' and len(nxt):possible[r['sid']]=min(possible.get(r['sid'],nxt[0]),nxt[0])
csv('CANDIDATE_EVENT_STATIC_CHECKS.csv',records)
eventdf=pd.DataFrame(records)
print('STATIC_SCOPE',json.dumps({'all_events':len(ev),'all_sids':ev.sid.nunique(),'statically_potential_sids':len(possible),'static_pass_events':int(eventdf.static_close_check.eq('PASS').sum()),'all_event_source_checks':eventdf.static_close_check.value_counts().to_dict()},ensure_ascii=False),flush=True)
actual_path=BASE/'known_halt_contract_v1/cohort_2022_recovery_v2'
actual=pd.DataFrame(json.loads((actual_path/'ACTIONS.json').read_text()))
oldpath=ROOT/'m3_stock_birth_during_sector_v1/relative_priority_equity_run_2022_v1/dynamic/ACTIONS.csv'
old=pd.read_csv(oldpath,low_memory=False);old=old[old.arm.eq('A_UNION_B')]
archives=json.loads((actual_path/'ARCHIVES.json').read_text())
states=json.loads((actual_path/'STATES.json').read_text())
registry_path=BASE/'known_halt_contract_v1/HALT_EVIDENCE_V1.json'
registry=json.loads(registry_path.read_text())
cover={(x['sid'],pd.Timestamp(x['session'])):x for x in registry['sessions']}
def inventory(actions):
 result={}
 for sid,g in actions.groupby('sid'):
  deltas=np.zeros((len(cal),2),dtype='int64')
  core=add=0
  for r in g.to_dict('records'):
   k=cal.get_indexer([pd.Timestamp(r['day'])])[0];assert k>=0
   q=int(r['q']);before=(core,add)
   if r['side']=='buy_core':core+=q
   elif r['side']=='buy_add':add+=q
   elif r['side']=='sell_add':add-=q
   elif r['side']=='sell_all':
    assert q==core+add,(sid,r,core,add)
    core=add=0
   assert core>=0 and add>=0
   deltas[k]+=[core-before[0],add-before[1]]
  after=np.cumsum(deltas,axis=0)
  before=np.vstack([np.zeros((1,2),dtype='int64'),after[:-1]])
  result[sid]=(before,after)
 return result
inv=inventory(actual);oldinv=inventory(old)
zero=np.zeros((len(cal),2),dtype='int64')
pending=collections.defaultdict(set)
for rid,r in archives.items():
 d=pd.Timestamp(r['signal_day']);nxt=cal[cal>d]
 if len(nxt): pending[r['sid']].add(nxt[0])
def resp(sid,d):
 k=cal.get_loc(d);a=inv.get(sid,(zero,zero))[0][k];o=oldinv.get(sid,(zero,zero))[0][k]
 unk=states.get(sid,{})
 return dict(actual_core_preopen=int(a[0]),actual_add_preopen=int(a[1]),actual_recorded_pending_ticket=d in pending[sid],actual_unknown_already=(unk.get('state')=='UNKNOWN' and d>=pd.Timestamp(unk['unknown_day'])),old_noshared_core_preopen=int(o[0]),old_noshared_add_preopen=int(o[1]))
def bar(f,d,prefix):
 if d is None or pd.isna(d):return {prefix+'_day':''}
 r=f.loc[d]
 return {prefix+'_day':date(d),prefix+'_raw_open':r['raw_open'],prefix+'_raw_close':r['raw_close'],prefix+'_factor':r['adjustment_factor'],prefix+'_source_kind':r['source_kind'],prefix+'_source_path':r['source_path'],prefix+'_segment_id':r['segment_id']}
def runs(index,mask):
 positions=np.flatnonzero(np.asarray(mask))
 if not len(positions):return []
 splits=np.split(positions,np.flatnonzero(np.diff(positions)>1)+1)
 return [(index[g[0]],index[g[-1]],g) for g in splits]
universe=[];gaps=[];issues=[];transitions=[];search=[];sourcebytes=0;rawbad=collections.Counter();otherbad=collections.Counter()
all_days=pot_days=all_missing=pot_missing=0
for n,(sid,g) in enumerate(ev.groupby('sid',sort=True),1):
 s.load(sid);f=s.raw[sid].frame;facts=s.facts[sid].frame;cp=s.cp[sid].frame
 assert f.index.is_unique and f.index.is_monotonic_increasing
 start=cal[cal>g.day.min()][0];domain=cal[cal>=start];pstart=possible.get(sid)
 d=f.reindex(domain); present=domain.isin(f.index)
 rawvalid=finite_positive(f.raw_open)&finite_positive(f.raw_close)&finite_positive(f.adjustment_factor)
 rawvalid&=boolean(f.observed_bar)&boolean(f.price_eligible)&boolean(f.volume_eligible)&f.source_invalid.isin([False,0])&f.synthetic_event_bar.isin([False,0])
 valididx=f.index[rawvalid]
 sp=next(p for p in s.manifest[sid]['source_sha256'] if p.endswith('/signal.parquet'))
 sh=s.hashes[sp]; fp=s.manifest[sid]['refs']['facts'];cpath=s.manifest[sid]['refs']['CP1'];sourcebytes+=Path(sp).stat().st_size+Path(fp).stat().st_size+Path(cpath).stat().st_size
 groups=eventdf[eventdf.sid.eq(sid)]
 potmask=domain>=pstart if pstart is not None else np.zeros(len(domain),bool)
 all_days+=len(domain);pot_days+=int(np.sum(potmask));all_missing+=int((~present).sum());pot_missing+=int(np.sum((~present)&potmask))
 universe.append(dict(sid=sid,name=g.iloc[0]['name'],industry=g.iloc[0]['industry'],first_birth=date(g.day.min()),last_birth=date(g.day.max()),first_broad_next_open=date(start),first_static_pass_next_open=date(pstart),broad_stock_days=len(domain),potential_stock_days=int(np.sum(potmask)),candidate_events=len(g),static_pass_events=int(groups.static_close_check.eq('PASS').sum()),source_first_row=date(f.index.min()),source_last_row_within_follow_end=date(f.index.max()),source_first_valid_bar=date(valididx.min()) if len(valididx) else '',source_last_valid_bar=date(valididx.max()) if len(valididx) else '',missing_rows=int((~present).sum()),potential_missing_rows=int(np.sum((~present)&potmask)),signal_path=sp,signal_sha256=sh,facts_path=fp,facts_sha256=s.hashes[fp],cp_path=cpath,cp_sha256=s.hashes[cpath]))
 missingrunlist=runs(domain,~present)
 for j,(a,b,positions) in enumerate(missingrunlist,1):
  before=valididx[valididx<a];after=valididx[valididx>b];prev=before[-1] if len(before) else None;nxt=after[0] if len(after) else None
  typ='INTERNAL_MISSING_ROWS' if a>f.index.min() and b<f.index.max() else 'LEADING_SOURCE_BOUNDARY_OR_PRELISTING_UNRESOLVED' if b<f.index.min() else 'TRAILING_NO_LATER_BAR_WITHIN_FOLLOW_WINDOW_NOT_PROOF_PERMANENT_OR_DELISTED'
  days=domain[positions];rr=[resp(sid,x) for x in days];covered=[x for x in days if (sid,x) in cover];pdys=[x for x in days if pstart is not None and x>=pstart]
  row=dict(gap_id=sid+'|'+date(a)+'|'+date(b),sid=sid,name=g.iloc[0]['name'],industry=g.iloc[0]['industry'],gap_start=date(a),gap_end=date(b),missing_common_sessions=len(days),calendar_days_inclusive=(b-a).days+1,gap_type=typ,in_potential_domain=bool(pdys),potential_missing_sessions=len(pdys),first_static_pass_next_open=date(pstart),registry_covered_sessions=len(covered),registry_evidence_ids=';'.join(sorted({cover[(sid,x)]['evidence_id'] for x in covered})),actual_held_sessions=sum(x['actual_core_preopen']+x['actual_add_preopen']>0 for x in rr),actual_pending_sessions=sum(x['actual_recorded_pending_ticket'] for x in rr),old_noshared_possible_reference_held_sessions=sum(x['old_noshared_core_preopen']+x['old_noshared_add_preopen']>0 for x in rr),actual_core_start=rr[0]['actual_core_preopen'],actual_add_start=rr[0]['actual_add_preopen'],source_kind=';'.join(sorted(f.source_kind.dropna().astype(str).unique())),signal_path=sp,signal_sha256=sh,facts_sha256=s.hashes[fp],cp_sha256=s.hashes[cpath],**bar(f,prev,'previous_valid'),**bar(f,nxt,'next_valid'))
  row['between_valid_bars_calendar_days']=(nxt-prev).days if prev is not None and nxt is not None else None
  row['observed_next_bar_is_not_official_resume_confirmation']=True
  row['priority']='P0_ACTUAL_HELD_UNCOVERED' if row['actual_held_sessions'] and len(covered)<len(days) else 'P1_ACTUAL_PENDING_UNCOVERED' if row['actual_pending_sessions'] and len(covered)<len(days) else 'P2_ORIGINAL_REFERENCE_HELD_UNCOVERED' if row['old_noshared_possible_reference_held_sessions'] and len(covered)<len(days) else 'P3_POTENTIAL_UNCOVERED' if pdys and len(covered)<len(days) else 'P4_BROAD_ONLY_OR_ALREADY_COVERED'
  gaps.append(row)
  search.append({k:v for k,v in row.items() if k in ['gap_id','sid','name','gap_start','gap_end','missing_common_sessions','gap_type','in_potential_domain','registry_covered_sessions','actual_held_sessions','actual_pending_sessions','old_noshared_possible_reference_held_sessions','priority','previous_valid_day','previous_valid_raw_open','previous_valid_raw_close','next_valid_day','next_valid_raw_open','next_valid_raw_close','between_valid_bars_calendar_days']})
 badmasks={'MISSING_ROW':~present,'INVALID_OPEN':present&~finite_positive(d.raw_open),'INVALID_CLOSE':present&~finite_positive(d.raw_close),'INVALID_FACTOR':present&~finite_positive(d.adjustment_factor),'INVALID_FLAGS':present&~(boolean(d.observed_bar)&boolean(d.price_eligible)&boolean(d.volume_eligible)&d.source_invalid.isin([False,0])&d.synthetic_event_bar.isin([False,0]))}
 fr=facts.reindex(domain);cr=cp.reindex(domain)
 extra={'FACTS_ROW_MISSING':present&~domain.isin(facts.index),'I_STATE_UNKNOWN':present&~fr.i_target.isin([True,False,1,0]),'I_TRUE_FLOOR_INVALID':present&boolean(fr.i_target)&~finite_positive(fr.i_floor),'CP_STATE_UNKNOWN':present&~cr.receipt.isin([True,False,1,0]),'CP_TRUE_CANDIDATE_INVALID':present&boolean(cr.receipt)&~finite_positive(cr.candidate)}
 masks={**badmasks,**extra}
 for typ,mask in masks.items():
  counter=rawbad if typ in badmasks else otherbad;counter[typ]+=int(np.sum(mask))
  for pos in np.flatnonzero(np.asarray(mask)):
   dt=domain[pos];cov=cover.get((sid,dt));rr=resp(sid,dt)
   issues.append(dict(sid=sid,day=date(dt),issue=typ,potential_domain=bool(potmask[pos]),registry_covered=bool(cov),registry_evidence_id=cov['evidence_id'] if cov else '',raw_row_present=bool(present[pos]),raw_open=d.iloc[pos].raw_open if present[pos] else None,raw_close=d.iloc[pos].raw_close if present[pos] else None,signal_sha256=sh,**rr))
 # All source lineage and factor transitions, not all presumed invalid.
 earlier=f.shift(1)
 change=f.source_kind.astype(str).ne(earlier.source_kind.astype(str))|f.source_path.astype(str).ne(earlier.source_path.astype(str))|f.segment_id.astype(str).ne(earlier.segment_id.astype(str))
 facchange=finite_positive(f.adjustment_factor)&finite_positive(earlier.adjustment_factor)&~np.isclose(pd.to_numeric(f.adjustment_factor,errors='coerce'),pd.to_numeric(earlier.adjustment_factor,errors='coerce'),rtol=1e-11)
 for dt in f.index[((change|facchange)&(f.index>=start)&(f.index<=END)).to_numpy()]:
  ii=f.index.get_loc(dt);prev=f.index[ii-1] if ii else None
  event=s.EVENT_AT.get((sid,dt))
  kinds=[]
  if change.loc[dt]:kinds.append('SOURCE_LINEAGE_CHANGE')
  if facchange.loc[dt]:kinds.append('FACTOR_TRANSITION_ADMITTED_COORDINATE' if event else 'FACTOR_TRANSITION_NOT_IN_FROZEN_ADMITTED_REGISTRY')
  transitions.append(dict(sid=sid,day=date(dt),kind=';'.join(kinds),potential_domain=pstart is not None and dt>=pstart,admitted_economic_event_id=event['economic_event_id'] if event else '',previous_source_kind=earlier.loc[dt].source_kind,current_source_kind=f.loc[dt].source_kind,previous_source_path=earlier.loc[dt].source_path,current_source_path=f.loc[dt].source_path,previous_segment_id=earlier.loc[dt].segment_id,current_segment_id=f.loc[dt].segment_id,previous_factor=earlier.loc[dt].adjustment_factor,current_factor=f.loc[dt].adjustment_factor,previous_observed_day=date(prev),signal_sha256=sh,**resp(sid,dt)))
 if n%250==0:print('PROGRESS',n,'sids',len(gaps),'missing_runs',len(issues),'issue_rows',round(time.monotonic()-t0,2),'seconds',flush=True)
csv('STOCK_UNIVERSE.csv',universe)
csv('MISSING_ROW_RUNS.csv',gaps)
csv('DAILY_ISSUES.csv',issues)
csv('FACTOR_LINEAGE_TRANSITIONS.csv',transitions)
csv('OFFICIAL_SEARCH_QUEUE.csv',sorted(search,key=lambda x:(x['priority'],x['sid'],x['gap_start'])))
actualissues=[r for r in issues if r['actual_core_preopen']+r['actual_add_preopen']>0 or r['actual_recorded_pending_ticket']]
csv('ACTUAL_RESPONSIBILITY_ISSUES.csv',actualissues)
csv('ACTUAL_RESPONSIBILITY_TRANSITIONS.csv',[r for r in transitions if r['actual_core_preopen']+r['actual_add_preopen']>0])
protected_after={p:sha(p) for p in protected}
assert protected_after==protected
assert s._no_budget_runs==0 and not s.actions and not s.rounds and not s.claims
for p,h in s.hashes.items():assert sha(p)==h,('source_drift',p)
source_hashes={**s.hashes,**{str(p):sha(p) for p in [registry_path,oldpath,actual_path/'ACTIONS.json',actual_path/'ARCHIVES.json',actual_path/'STATES.json',BASE/'indexed_execution_v1/COHORT_EXECUTION_CONTRACT_V3.json',BASE/'known_halt_contract_v1/RECOVERY_COHORT_CONTRACT_V2.json']}}
save('SOURCE_HASHES.json',source_hashes)
save('PROTECTED_LEDGER_HASHES.json',protected)
summary={'scope':'2022_BIRTH_COHORT_STATIC_CONSERVATIVE_POTENTIAL_DOMAIN_NOT_ACTUAL_HOLDINGS','start':date(START),'birth_end':'2022-12-31','follow_end':date(END),'common_sessions':len(cal),'all_candidate_events':len(ev),'all_candidate_sids':len(universe),'static_pass_events':int(eventdf.static_close_check.eq('PASS').sum()),'static_potential_sids':len(possible),'all_candidate_stock_days':all_days,'static_potential_stock_days':pot_days,'broad_missing_stock_days':all_missing,'potential_missing_stock_days':pot_missing,'missing_run_count':len(gaps),'potential_missing_run_count':sum(r['in_potential_domain'] for r in gaps),'missing_sid_count':len({r['sid'] for r in gaps}),'potential_missing_sid_count':len({r['sid'] for r in gaps if r['in_potential_domain']}),'missing_gap_type_runs':dict(collections.Counter(r['gap_type'] for r in gaps)),'missing_priority_runs':dict(collections.Counter(r['priority'] for r in gaps)),'raw_problem_stock_days_by_issue':dict(rawbad),'facts_cp_problem_stock_days_by_issue':dict(otherbad),'transition_count':len(transitions),'transition_kind_count':dict(collections.Counter(r['kind'] for r in transitions)),'registry_covered_missing_stock_days':sum(r['registry_covered_sessions'] for r in gaps),'actual_held_missing_stock_days':sum(r['actual_held_sessions'] for r in gaps),'actual_held_gap_runs':sum(r['actual_held_sessions']>0 for r in gaps),'actual_pending_missing_stock_days':sum(r['actual_pending_sessions'] for r in gaps),'actual_held_sids':actual[actual.side.eq('buy_core')].sid.nunique(),'actual_core_buys':int(actual.side.eq('buy_core').sum()),'raw_facts_cp_source_bytes':sourcebytes,'elapsed_seconds':time.monotonic()-t0,'peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'source_hashes_verified':len(source_hashes),'protected_old_ledger_files_verified':len(protected),'economic_replays':s._no_budget_runs,'source_prices_or_flags_modified':False,'actual_ledger_modified':False,'minute_data_used':False,'limits':['Static PASS is original close check before rank/shared-budget/path eligibility; not proof any path buys every security.','Broad superset includes original I/PVR/close-rejected events for completeness; narrower potential start is first original static PASS next common OPEN.','Observed next valid bar is not official evidence of resumption. Missing bars are not automatically suspensions.','Trailing no-bar intervals are censored at follow-end; permanent cessation, delisting and source outage need separate evidence.','Original independent-round inventory is a possible-responsibility reference only, never this shared account or its PnL.','Historical raw/facts/CP sources are frozen current reconstructions; no PIT availability guarantee. OPEN and flags have distinct source validation clocks.','No quotes, indicators, capacity, inventory values or corporate-action factors are synthesized.','Factor transitions with admitted coordinates are coverage annotations, not automatic proof for any alternative ownership path.']}
save('RESULT.json',summary)
save('OUTPUT_SEAL.json',{p.name:sha(p) for p in OUT.iterdir() if p.is_file()})
print('RESULT',json.dumps(summary,ensure_ascii=False,default=str),flush=True)
