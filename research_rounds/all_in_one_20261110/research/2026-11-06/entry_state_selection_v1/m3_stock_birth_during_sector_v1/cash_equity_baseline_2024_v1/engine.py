"""Independent 2024 A+B baseline NET80 conditional scenario. No account or order routing.
Only definitions are AST-extracted from the original consumer; no old script is imported.
Economic event identity is frozen separately from date/amount/evidence fields.
"""
from pathlib import Path
from decimal import Decimal as D
import ast,sys,json,hashlib,time,inspect
import numpy as np
import pandas as pd
O=Path(__file__).resolve().parent;E=O.parent;R=E.parent
U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
B=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025')
AS=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024')
sys.path.insert(0,str(B/'code'))
from market_rules import version_on,market_identity_on,RuleUnavailable
from sector_account import QuantityRule,FeeComponent,FeeSchedule
NAV=D('1200000');INIT=D('24000');SLOT=D('48000');RISK=D('3000');SLIP=D('.0005');NET=D('.8');END=pd.Timestamp('2026-06-30');WINDOW='2024_924';START=pd.Timestamp('2024-09-01');BIRTH_END=pd.Timestamp('2024-12-31')
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2,default=str)+'\n')
SOURCE=E/'relative_priority_v1/simulate.py';text=SOURCE.read_text();tree=ast.parse(text)
names={'finite','true','false','lineage','flags','DayFrame','load','getmeta','fee','size','checkclose','act','record','freeze_unknown','mark','entry_open','held_open','held_close','queue'}
extracted={}
for n in tree.body:
 if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name in names:
  segment=ast.get_source_segment(text,n);extracted[n.name]=hashlib.sha256(segment.encode()).hexdigest()
  if n.name=='entry_open':
   needle=" if not finite(z.get('adjustment_factor')) or not np.isclose(z['adjustment_factor'],prev['adjustment_factor'],rtol=1e-11):return freeze_unknown(states,sid,st,'FACTOR_AT_ENTRY_UNKNOWN',d)"
   assert segment.count(needle)==1
   segment=segment.replace(needle," if unadmitted_action_at(sid,d):return freeze_unknown(states,sid,st,'UNADMITTED_ACTION_AT_ENTRY_UNKNOWN',d)\n if pending_bridge(st,d,z,prev):prev=dict(prev,adjustment_factor=z['adjustment_factor'])\n"+needle)
  exec(compile(segment,str(SOURCE)+':definition_only','exec'),globals())
assert set(extracted)==names
p=E/'relative_priority_v1/priority.py';exec(compile(p.read_text(),str(p),'exec'),globals())
native_record=record;native_mark=mark;native_held_open=held_open;native_held_close=held_close;native_entry_open=entry_open;native_load=load
manifest={x['symbol']:x for x in read(U/'STOCK_MANIFEST.json')}
rules=read(B/'inputs-v2/market-rules.json');proxies=read(B/'inputs-v2/economic-protocol.json')['approved_proxy_ids']
panel_path=R/'momentum_persistence_breadth_v1/canonical_mu3_comparison_v2/COMMON_K_COMPARISON.parquet'
panel=pd.read_parquet(panel_path).sort_values(['sector','day']);cal=pd.DatetimeIndex(sorted(panel.day.unique()));cal=cal[cal<=END]
sector={s:g.set_index('day').M3_candidate.to_dict() for s,g in panel.groupby('sector')}
ev=pd.read_csv(E/'SEALED_ALL_BIRTH_EVENTS.csv',parse_dates=['day','previous_common_day'],low_memory=False)
ev=ev[ev.window.eq(WINDOW)&ev.event_type.isin(['A_SECTOR_BIRTH','B_STOCK_BIRTH_DURING_SECTOR'])].copy()
relative=pd.read_csv(E/'relative_m3_cache_v1/coverage_upper_bound_v1/EVENT_COVERAGE.csv',usecols=CAUSAL_COLUMNS)
ev=ev.merge(relative,on='event_id',validate='one_to_one',how='left');assert not ev.duplicated(['day','sid']).any()
raw={};facts={};cp={};capacity={};meta={};closecache={};load_count=0;hashes={}
for p in [SOURCE,O/'engine.py',E/'relative_priority_v1/priority.py',E/'relative_priority_equity_rebuild_v1/PROTOCOL_DRAFT.md',E/'SEALED_ALL_BIRTH_EVENTS.csv',E/'relative_m3_cache_v1/coverage_upper_bound_v1/EVENT_COVERAGE.csv',panel_path,U/'STOCK_MANIFEST.json',B/'inputs-v2/market-rules.json',B/'inputs-v2/economic-protocol.json',B/'code/sector_account.py',B/'code/market_rules.py']:
 hashes[str(p)]=sha(p)
assert sha(E/'relative_priority_equity_rebuild_v1/PROTOCOL_DRAFT.md')=='bce58ac11122a264efd510e84507a4225b77cb55746d64ddf4b1114e56c75ed1'
for p,h in read(E/'relative_priority_v1/FREEZE.json')['hashes'].items():assert sha(p)==h,(p,'legacy freeze drift')
for p,h in read(E/'EVENT_SEAL.json')['source_hashes'].items():assert sha(p)==h,(p,'signal freeze drift')

def load(sid):
 if sid in raw:return
 native_load(sid)
 m=manifest[sid];expected={**m['source_sha256'],**m['output_sha256']}
 for p in [next(p for p in m['source_sha256'] if p.endswith('/signal.parquet')),m['refs']['facts'],m['refs']['CP1']]:assert hashes[p]==expected[p],(sid,p,'manifest drift')

actions_sources={}
def local_actions(sid):
 if sid in actions_sources:return actions_sources[sid]
 p=AS/'inputs-v1/actions'/(sid+'.json');issues=[];coverage=[]
 empty=dict(series_id=sid,currency='CNY',events=[],coverage_evidence=[],unresolved=[],raw_response_empty=True)
 if not p.exists():a=empty;issues.append('ACTION_FILE_MISSING')
 else:
  hashes[str(p)]=sha(p)
  try:a=read(p)
  except Exception:a=empty;issues.append('ACTION_JSON_INVALID')
  if not isinstance(a,dict):a=empty;issues.append('ACTION_SCHEMA_INVALID')
  if a.get('series_id')!=sid:issues.append('ACTION_SECURITY_IDENTITY_MISMATCH')
  if a.get('currency')!='CNY':issues.append('ACTION_CURRENCY_MISMATCH')
  if not isinstance(a.get('events'),list):issues.append('ACTION_EVENTS_SCHEMA');a=dict(a,events=[])
  seen=set()
  for x in a['events']:
   try:
    date=pd.Timestamp(x['effective_date']);assert str(date.date())==x['effective_date'];assert x['effective_date'] not in seen;seen.add(x['effective_date']);assert D(str(x['split_ratio']))>0 and D(str(x['cash_per_old_share']))>=0
   except Exception:issues.append('ACTION_EVENT_SCHEMA_INVALID')
  evidence=a.get('coverage_evidence')
  if not isinstance(evidence,list):issues.append('COVERAGE_SCHEMA_INVALID');evidence=[];a=dict(a,coverage_evidence=[])
  if not evidence:coverage.append('NO_RIGHTS_SOURCE')
  for e in evidence:
   try:
    ep=Path(e['path']);assert ep.exists();assert sha(ep)==e['sha256'];hashes[str(ep)]=sha(ep);raw=read(ep);assert isinstance(raw.get('records'),list)
    if not raw['records']:coverage.append('RIGHTS_EMPTY')
   except Exception:issues.append('RIGHTS_EVIDENCE_MISSING_INVALID_OR_HASH_MISMATCH')
 if a.get('raw_response_empty'):coverage.append('ACTION_RAW_RESPONSE_EMPTY')
 a=dict(a,_source_integrity_ok=not issues,_source_issues=sorted(set(issues)),_source_coverage_status='COVERAGE_UNKNOWN' if issues or coverage else 'LOCAL_SOURCE_PRESENT_NOT_PIT',_source_coverage_issues=sorted(set(coverage)))
 actions_sources[sid]=a;return a

def verify_admitted_evidence():
 root=E/'cash_dividend_2024_coverage_v1';sp=root/'FINAL_OUTPUT_HASHES.json';seal=read(sp)
 assert read(root/'FINAL_INDEPENDENT_AUDIT.json')['result']=='PASS_COMPANY_FACT_EVIDENCE_ONLY'
 for name,h in seal['file_sha256'].items():
  p=root/name;assert sha(p)==h,(p,'2024 evidence seal mismatch');hashes[str(p)]=h
 for p,h in read(root/'SOURCE_SEAL.json')['sources'].items():assert sha(p)==h,(p,'original source drift');hashes[p]=h
 for p,h in read(root/'ADJUDICATION_SUMMARY.json')['original_source_action_hashes'].items():assert sha(p)==h;hashes[p]=h
 hashes[str(sp)]=sha(sp)
 assert read(root/'ADJUDICATION_SUMMARY.json')['production_admitted']==0
 # Source candidates remain blocked. This separate runtime is a bounded NET80 scenario.
verify_admitted_evidence()

def build_events():
 p=E/'cash_dividend_2024_coverage_v1/EVENT_ADAPTER_CANDIDATES.json';t=read(p);assert len(t)==165
 rows=[]
 for r in t:
  sid=r['sid'];d=pd.Timestamp(r['ex_date']);a=local_actions(sid);ordinal=r['local_action_ordinal'];assert a['_source_integrity_ok'];term=a['events'][ordinal-1]
  assert term['effective_date']==r['ex_date'] and D(term['split_ratio'])==1 and D(term['cash_per_old_share'])==D(r['d_source'])
  assert not r['coordinate_verified_for_production'] and not r['entitlement_verified_for_production']
  load(sid);f=raw[sid].frame;prev=f[f.index<d].iloc[-1];cur=f.loc[d]
  ds=D(r['d_source']);dc=D(r['d_cash']);fn=D(str(cur.adjustment_factor));fo=D(str(prev.adjustment_factor));pc=D(str(prev.raw_close))
  assert dc>0 and ds>0 and lineage(prev)==lineage(cur)
  assert abs(fo/D(r['factor_old'])-1)<=D('1e-11') and abs(fn/D(r['factor_new'])-1)<=D('1e-11')
  assert abs(fo*pc/(pc-ds)/fn-1)<=D('1e-11') and str(prev.name.date())==r['previous_day']
  rec=pd.Timestamp(r['record_date']);pay=pd.Timestamp(r['pay_date']);assert rec==prev.name and rec<d<=pay and all(x in cal for x in [rec,d,pay])
  assert START<=rec and d<=END
  notice=r['notice'];components=notice['components'] if notice else []
  fields=dict(sid=sid,economic_event_id=r['economic_event_id_candidate'],event_type='PURE_CASH',record_date=rec,coordinate_snapshot_day=rec,ex_date=d,pay_date=pay,d_source=ds,d_cash=dc,d_ref=r['d_ref'],factor_old=fo,factor_new=fn,previous_close=pc,previous_day=prev.name,coordinate_verified=True,entitlement_verified=True,coordinate_scope='FROZEN_SOURCE_TRANSLATION_ONLY',entitlement_scope='OWN_REGISTER_Q_NET80_NOT_ACTUAL_TAX',origin='2024_REVIEWED_165_SCENARIO',local_action_ordinal=ordinal,source_path=str(p),aliases=['2024_FACT:'+sid+'|'+r['ex_date']],components=components,unresolved_reason=None,evidence_version=r['evidence_version'],scenario_not_PIT=True)
  rows.append(fields)
 assert len({r['economic_event_id'] for r in rows})==165
 regmap={}
 m=pd.read_csv(E/'relative_priority_equity_rebuild_v1/FIRST_ACTION_ROUND_MAP_2024.csv',dtype=str)
 by={(r['sid'],str(r['ex_date'].date())):r['economic_event_id'] for r in rows}
 for r in m.to_dict('records'):
  key=(r['sid'],r['status_day'])
  if key in by:regmap[r['round_id']]=by[key]
 return rows,regmap
EVENTS,REGRESSION_EVENT_MAP=build_events();EVENT_BY_ID={r['economic_event_id']:r for r in EVENTS}
EVENT_AT={(r['sid'],r['ex_date']):r for r in EVENTS};assert len(EVENT_AT)==len(EVENTS)
BY_RECORD={};BY_EX={};BY_PAY={}
for x in EVENTS:
 BY_RECORD.setdefault(x['coordinate_snapshot_day'],[]).append(x);BY_EX.setdefault(x['ex_date'],[]).append(x)
 if x['pay_date'] is not None:BY_PAY.setdefault(x['pay_date'],[]).append(x)
rounds=[];actions=[];decisions=[];blocks=[];ranking_audit=[];bridges=[];registrations=[];claim_ledger=[];marks=[];archives={};claims={};snapshots={}
BRIDGE=True;MODE='FULL';CURRENT_PHASE='UNSET';ALLOWED_EVENT_IDS=None

def enabled(e):return BRIDGE and (ALLOWED_EVENT_IDS is None or e['economic_event_id'] in ALLOWED_EVENT_IDS)
def reset(bridge=True,mode='FULL'):
 global rounds,actions,decisions,blocks,ranking_audit,bridges,registrations,claim_ledger,marks,archives,claims,snapshots,BRIDGE,MODE,ALLOWED_EVENT_IDS
 rounds=[];actions=[];decisions=[];blocks=[];ranking_audit=[];bridges=[];registrations=[];claim_ledger=[];marks=[];archives={};claims={};snapshots={};BRIDGE=bridge;MODE=mode;ALLOWED_EVENT_IDS=None

def claim_key(arm,e):return (WINDOW,arm,e['sid'],e['economic_event_id'])
def register(states,arm,d):
 for e in BY_RECORD.get(d,[]):
  if not enabled(e):continue
  key=claim_key(arm,e)
  if key in snapshots:continue
  st=states.get(e['sid']);state=st['state'] if st else 'FLAT';known=state!='UNKNOWN';q=st['core']+st['add'] if state=='HELD' else 0 if known else None;cq=st['core'] if state=='HELD' else 0 if known else None
  ss=dict(key=key,arm=arm,sid=e['sid'],economic_event_id=e['economic_event_id'],evidence_version=e['evidence_version'],record_date=e.get('record_date'),inventory_snapshot_day=d,snapshot_kind='RECORD_CLOSE' if e.get('record_date') is not None else 'COORDINATE_PREVIOUS_OBSERVATION_ONLY',state=state,record_q=q,core_record_q=cq,owner_round_id=st['round_id'] if state=='HELD' else None,exitpending=st.get('exitpending') if st else None)
  snapshots[key]=ss;registrations.append(ss.copy())
  if q is not None and q>0 and e['entitlement_verified']:
   assert st['sid']==e['sid'] and st['arm']==arm and st['round_id'] in archives
   claims[key]=dict(ss,amount=D(q)*e['d_cash']*NET,core_amount=D(cq)*e['d_cash']*NET,recognized=False,settled=False,ex_date=e['ex_date'],pay_date=e['pay_date'],d_cash=e['d_cash'])

def accrue_day(arm,d):
 for e in BY_EX.get(d,[]):
  key=claim_key(arm,e);c=claims.get(key)
  if c is None or c['recognized']:continue
  st=archives[c['owner_round_id']];amount=c['amount'];st['receivable']+=amount;st['dividend_total']+=amount;c['recognized']=True
  claim_ledger.append(dict(arm=arm,round_id=st['round_id'],economic_event_id=e['economic_event_id'],evidence_version=e['evidence_version'],day=d,event='ACCRUE_NET80',cash_delta=0,receivable_delta=amount,amount=amount,record_q=c['record_q'],core_record_q=c['core_record_q']))

def pay_day(arm,d):
 for e in BY_PAY.get(d,[]):
  key=claim_key(arm,e);c=claims.get(key)
  if c is None or not c['recognized'] or c['settled']:continue
  st=archives[c['owner_round_id']];before=st['cash']+st['receivable'];st['cash']+=c['amount'];st['receivable']-=c['amount'];st['dividend_paid']+=c['amount'];c['settled']=True
  assert before==st['cash']+st['receivable']
  nxt=cal[cal>d];avail=nxt[0] if len(nxt) else None
  claim_ledger.append(dict(arm=arm,round_id=st['round_id'],economic_event_id=e['economic_event_id'],evidence_version=e['evidence_version'],day=d,event='PAY_CLOSE_TRANSFER',cash_delta=c['amount'],receivable_delta=-c['amount'],amount=c['amount'],record_q=c['record_q'],core_record_q=c['core_record_q'],available_from=avail))

def coordinate_matches(e,z,prev):
 if not finite(z.get('adjustment_factor')) or not finite(prev.get('adjustment_factor')) or not finite(prev.get('raw_close')):return False
 fn=D(str(z['adjustment_factor']));fo=D(str(prev['adjustment_factor']));pc=D(str(prev['raw_close']))
 return fn>0 and pc>e['d_source'] and abs(fn/e['factor_new']-1)<=D('1e-11') and abs(fo/e['factor_old']-1)<=D('1e-11') and abs((fo*pc/(pc-e['d_source']))/fn-1)<=D('1e-11')

def pending_bridge(st,d,z,prev):
 e=EVENT_AT.get((st['sid'],d))
 if not e or not enabled(e):return False
 snap=snapshots.get(claim_key(st['arm'],e))
 if not snap or snap['record_q']!=0 or not coordinate_matches(e,z,prev):return False
 bridges.append(dict(arm=st['arm'],round_id=st['round_id'],day=d,economic_event_id=e['economic_event_id'],kind='PENDING_COORDINATE_Q0',record_q=0,dividend=0,old_factor=prev['adjustment_factor'],new_factor=z['adjustment_factor'],floor_signal=st['i_floor'],floor_raw=D(str(st['i_floor']))/D(str(z['adjustment_factor']))))
 return True

def unadmitted_action_at(sid,d):
 if not BRIDGE:return False
 a=local_actions(sid)
 if not a.get('_source_integrity_ok',True):return True
 e=EVENT_AT.get((sid,d))
 return (e is None or not enabled(e)) and any(pd.Timestamp(x['effective_date'])==d for x in a['events'])

def before_held(states,sid,st,d):
 e=EVENT_AT.get((sid,d))
 if unadmitted_action_at(sid,d):
  z=raw[sid].get(d,{})
  if not finite(z.get('raw_open')) or z['raw_open']<=0:freeze_unknown(states,sid,st,'MISSING_OPEN_PATH_UNKNOWN',d);return False
  if lineage(z)!=st['origin']:freeze_unknown(states,sid,st,'SOURCE_CHANGE_PATH_UNKNOWN',d);return False
  freeze_unknown(states,sid,st,'UNADMITTED_ACTION_PATH_UNKNOWN',d);return False
 if not e or not enabled(e):return True
 z=raw[sid].get(d,{})
 # Match native OPEN validation order before bridge or entitlement checks. No current CLOSE data.
 if not finite(z.get('raw_open')) or z['raw_open']<=0:freeze_unknown(states,sid,st,'MISSING_OPEN_PATH_UNKNOWN',d);return False
 if lineage(z)!=st['origin']:freeze_unknown(states,sid,st,'SOURCE_CHANGE_PATH_UNKNOWN',d);return False
 snap=snapshots.get(claim_key(st['arm'],e))
 if snap is None or snap['record_q'] is None or (snap['record_q']>0 and not e['entitlement_verified']):freeze_unknown(states,sid,st,'REGISTER_OR_ENTITLEMENT_UNKNOWN',d);return False
 prev=raw[sid].get(e['previous_day'],{})
 if not coordinate_matches(e,z,prev) or abs(st['fac']/e['factor_old']-1)>D('1e-11'):freeze_unknown(states,sid,st,'CASH_FACTOR_BRIDGE_UNKNOWN',d);return False
 old=st['fac'];new=D(str(z['adjustment_factor']));protections={}
 for k in ['addfloor','addpending']:
  if st.get(k) is not None:before=st[k];st[k]=before*old/new;protections[k]=dict(before=before,after=st[k])
 st['fac']=new;st['factor']=float(new)
 bridges.append(dict(arm=st['arm'],round_id=st['round_id'],day=d,economic_event_id=e['economic_event_id'],kind='HELD_COORDINATE',record_q=snap['record_q'],core_record_q=snap['core_record_q'],old_factor=old,new_factor=new,protections=protections,exitpending=st['exitpending'],addexitpending=st['addexitpending']))
 return True

def held_open(states,sid,st,d,prevd):
 global CURRENT_PHASE
 CURRENT_PHASE='OPEN'
 if before_held(states,sid,st,d):native_held_open(states,sid,st,d,prevd)
def entry_open(states,sid,st,d):
 global CURRENT_PHASE
 CURRENT_PHASE='OPEN';native_entry_open(states,sid,st,d)
def held_close(states,sid,st,d):
 global CURRENT_PHASE
 CURRENT_PHASE='CLOSE';native_held_close(states,sid,st,d)
 if MODE=='CORE_REGRESSION' and states.get(sid,{}).get('state')=='HELD':st['addpending']=None

def mark(st,px,d):
 val=native_mark(st,px,d)+st.get('receivable',D(0))
 if BRIDGE:marks.append(dict(arm=st['arm'],round_id=st['round_id'],day=d,phase=CURRENT_PHASE,net_equity=val,strictly_positive=val>0,receivable=st.get('receivable',0),caller=inspect.currentframe().f_back.f_code.co_name))
 return val

def record(st,status,d=None,**extra):
 native_record(st,status,d,**extra);st['_output_index']=len(rounds)-1;r=rounds[-1]
 r.update(execution_status=status,failure_phase=CURRENT_PHASE if 'UNKNOWN' in status else None,receivable_at_termination=float(st.get('receivable',0)),dividend_at_termination=float(st.get('dividend_total',0)))
 if status=='COMPLETE_CONDITIONAL_STOCK_ROUND':r.update(net_pnl=float(st['cash']+st.get('receivable',0)),net_return_on_buy_cash=float((st['cash']+st.get('receivable',0))/st['spent']))

def new_state(r,arm,rid,check):
 st=dict(r,state='BUY_PENDING',arm=arm,round_id=rid,signal_day=r['day'],birth_end=BIRTH_END,close_q=check['close_q'],prior20_capacity=check['prior20_capacity'],receivable=D(0),dividend_total=D(0),dividend_paid=D(0))
 archives[rid]=st;return st

def run_window(arm,stop=END):
 assert arm=='A_UNION_B','Only unchanged A+B baseline authorized'
 states={};seq={};groups={d:g for d,g in ev.groupby('day',sort=True)}
 for k,d in enumerate(cal):
  if d<START or d>stop:continue
  prevd=cal[k-1] if k else None;accrue_day(arm,d)
  for sid in list(states):
   st=states[sid]
   if st['state']=='BUY_PENDING':entry_open(states,sid,st,d)
   elif st['state']=='HELD':held_open(states,sid,st,d,prevd)
  for sid in list(states):
   st=states[sid]
   if st['state']=='HELD':held_close(states,sid,st,d)
  register(states,arm,d)
  if d in groups:
   for industry,g in groups[d].groupby('sector',sort=True):
    slots=0;queue_rank=0
    for r in queue(g,states,arm):
     sid=r['sid'];dec={k:r[k] for k in ['event_id','window','day','sid','name','industry','sector','event_type','PVR_score','I_qualified','PVR_known']}
     dec.update(arm=arm,selected=False,queue_rank=np.nan,stock_state_before=states.get(sid,{}).get('state','FLAT'))
     if sid in states:dec['decision']='BLOCKED_'+states[sid]['state'];dec['blocking_round_id']=states[sid]['round_id'];decisions.append(dec);continue
     if not true(r['I_qualified']):dec['decision']='I_INELIGIBLE';decisions.append(dec);continue
     if not true(r['PVR_known']) or not finite(r['PVR_score']):dec['decision']='PVR_UNKNOWN';decisions.append(dec);continue
     queue_rank+=1;dec['queue_rank']=queue_rank;check=checkclose(r);dec.update(check)
     if check['close_check']!='PASS':dec['decision']='CLOSE_'+check['close_check'];decisions.append(dec);continue
     if slots>=2:dec['decision']='PASS_NOT_TOP2';decisions.append(dec);continue
     slots+=1;dec.update(decision='SELECTED_PENDING',selected=True,selected_rank=slots);seq[sid]=seq.get(sid,0)+1;rid=f'{WINDOW}|{arm}|{sid}|{seq[sid]}'
     states[sid]=new_state(r,arm,rid,check);dec['round_id']=rid;decisions.append(dec)
  pay_day(arm,d)
  if k%250==0:print('DAY',arm,str(d.date()),'states',len(states),'rounds',len(rounds),flush=True)
 for sid,st in states.items():
  if st['state']=='HELD':record(st,'OPEN_CENSORED_AT_2026_06_30' if stop==END else 'PREFIX_CENSORED',stop,exit_pending_at_end=bool(st['exitpending']),add_pending_at_end=st['addpending'] is not None)
  elif st['state']=='BUY_PENDING':record(st,'BUY_PENDING_CENSORED_AT_DATA_END',stop)
  blocks.append(dict(window=WINDOW,arm=arm,sid=sid,final_state=st['state'],round_id=st['round_id']))
 finalize()

def run_fixed(rid,r,arm='A_UNION_B'):
 global ALLOWED_EVENT_IDS,snapshots
 eid=REGRESSION_EVENT_MAP.get(rid);ALLOWED_EVENT_IDS={eid} if eid else set();snapshots={}
 # Claims must be separate per independent fixed permit. Historical event keys can be reused only in this regression scope.
 claims.clear();check=checkclose(r);assert check['close_check']=='PASS';st=new_state(r,arm,rid,check);states={r['sid']:st};sid=r['sid']
 for k,d in enumerate(cal):
  if d<r['day']:continue
  if d>r['day']:
   accrue_day(arm,d)
   if states.get(sid,{}).get('state')=='BUY_PENDING':entry_open(states,sid,st,d)
   elif states.get(sid,{}).get('state')=='HELD':held_open(states,sid,st,d,cal[k-1])
   if states.get(sid,{}).get('state')=='HELD':held_close(states,sid,st,d)
  register(states,arm,d);pay_day(arm,d)
  if states.get(sid,{}).get('state') not in ('BUY_PENDING','HELD') and all(c['settled'] for c in claims.values()):break
 if states.get(sid,{}).get('state')=='HELD':record(st,'OPEN_CENSORED_AT_2026_06_30',END)
 elif states.get(sid,{}).get('state')=='BUY_PENDING':record(st,'BUY_PENDING_CENSORED_AT_DATA_END',END)
 finalize([st]);return rounds[st['_output_index']]

def finalize(sts=None):
 for st in sts if sts is not None else archives.values():
  if '_output_index' not in st:continue
  r=rounds[st['_output_index']];r.update(cash_after_payouts=float(st.get('cash',0)),receivable_after_payouts=float(st['receivable']),dividend_net80_total=float(st['dividend_total']),dividend_net80_paid=float(st['dividend_paid']))
  if r['status']=='COMPLETE_CONDITIONAL_STOCK_ROUND':r.update(net_pnl=float(st['cash']+st['receivable']),net_return_on_buy_cash=float((st['cash']+st['receivable'])/st['spent']))

def ledger_qa():
 aa=pd.DataFrame(actions);out=[]
 for r in rounds:
  g=aa[aa.round_id.eq(r['round_id'])];q=0;c=D(0);spent=D(0);fees=D(0);bought={}
  for x in g.to_dict('records'):
   n=int(x['q']);p=D(str(x['price']));f=D(str(x['fee']));day=x['day']
   if x['side'].startswith('buy'):q+=n;c-=n*p+f;spent+=n*p+f;bought[day]=bought.get(day,0)+n
   else:assert n<=q-bought.get(day,0),(r['round_id'],'T+1');q-=n;c+=n*p-f
   fees+=f;assert q>=0
  if len(g):
   assert abs(float(c)+r['dividend_net80_paid']-r['cash_after_payouts'])<1e-7,(r['round_id'],'cash')
   assert abs(float(fees)-r['all_fees'])<1e-7 and abs(float(spent)-r['total_buy_cash'])<1e-7
   assert q==r['core_qty']+r['add_qty']
  if r['status']=='COMPLETE_CONDITIONAL_STOCK_ROUND':assert q==0 and abs(float(c)+r['dividend_net80_total']-r['net_pnl'])<1e-7
  out.append(dict(round_id=r['round_id'],qty=q,trade_cash=float(c),paid=r['dividend_net80_paid'],receivable=r['receivable_after_payouts'],fees=float(fees),buy_cash=float(spent),reconciled=True))
 return out

def dump(dest):
 dest=Path(dest);dest.mkdir(exist_ok=False)
 for fn,rows in [('ROUNDS',rounds),('ACTIONS',actions),('DECISIONS',decisions),('RANKING_AUDIT',ranking_audit),('END_STATES',blocks),('REGISTRATIONS',registrations),('CLAIM_LEDGER',claim_ledger),('PROFIT_GATES',marks)]:pd.DataFrame(rows).to_csv(dest/(fn+'.csv'),index=False)
 save(dest/'CLAIMS.json',list(claims.values()));save(dest/'BRIDGES.json',bridges);save(dest/'LEDGER_QA.json',ledger_qa());save(dest/'SOURCE_HASHES.json',hashes)
 for p,h in hashes.items():assert sha(p)==h,(p,'source drift')
 save(dest/'OUTPUT_HASHES.json',{p.name:sha(p) for p in dest.iterdir() if p.is_file() and p.name!='OUTPUT_HASHES.json'})
