"""Fixed original permits only. Definition extraction never executes legacy scripts."""
from pathlib import Path
from decimal import Decimal as D
import ast,sys,json,hashlib,inspect,copy
import numpy as np
import pandas as pd
O=Path(__file__).resolve().parent;E=O.parent;R=E.parent
U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
B=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025')
AS=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024')
sys.path.insert(0,str(B/'code'))
from market_rules import version_on,market_identity_on,RuleUnavailable
from sector_account import QuantityRule,FeeComponent,FeeSchedule
NAV=D('1200000');INIT=D('24000');SLOT=D('48000');RISK=D('3000');SLIP=D('.0005');NET=D('.8')
END=pd.Timestamp('2026-06-30');WINDOW='2026H1_SEMI';START=pd.Timestamp('2026-01-01');BIRTH_END=END
BRIDGE=False;SOURCE_BRIDGE=False;MODE='FULL';CURRENT_PHASE='UNSET';ALLOWED_EVENT_IDS=None
EVENTS=[];EVENT_AT={};EVENT_BY_ID={};BY_RECORD={};BY_EX={};BY_PAY={}
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2,default=str)+'\n')
hashes={};definition_hashes={}
def extract(path,names,patch=None):
 text=path.read_text();found=set();hashes[str(path)]=sha(path)
 for n in ast.parse(text).body:
  if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name in names:
   seg=ast.get_source_segment(text,n);definition_hashes[str(path)+':'+n.name]=hashlib.sha256(seg.encode()).hexdigest()
   if patch:seg=patch(n.name,seg)
   exec(compile(seg,str(path)+':definitions_only','exec'),globals());found.add(n.name)
 assert found==set(names),(path,set(names)-found)
def native_patch(name,seg):
 if name=='load':seg=seg.replace("'raw_open','raw_close'","'raw_open','raw_high','raw_low','raw_volume','amount','volume_factor','raw_close'")
 if name=='entry_open':
  needle=" if not finite(z.get('adjustment_factor')) or not np.isclose(z['adjustment_factor'],prev['adjustment_factor'],rtol=1e-11):return freeze_unknown(states,sid,st,'FACTOR_AT_ENTRY_UNKNOWN',d)"
  assert seg.count(needle)==1
  seg=seg.replace(needle," if unadmitted_action_at(sid,d):return freeze_unknown(states,sid,st,'UNADMITTED_ACTION_AT_ENTRY_UNKNOWN',d)\n if pending_bridge(st,d,z,prev):prev=dict(prev,adjustment_factor=z['adjustment_factor'])\n"+needle)
 return seg
extract(E/'lifecycle_v1/simulate.py',{'finite','true','false','lineage','flags','DayFrame','load','getmeta','fee','size','checkclose','act','record','freeze_unknown','mark','entry_open','held_open','held_close'},native_patch)
native_record=record;native_mark=mark;native_held_open=held_open;native_held_close=held_close;native_entry_open=entry_open;native_load=load
extract(E/'cash_equity_baseline_2024_v1/engine.py',{'local_actions','enabled','claim_key','register','accrue_day','pay_day','coordinate_matches','pending_bridge','unadmitted_action_at','before_held','held_open','entry_open','held_close','mark','record','new_state','finalize','ledger_qa'})
cash_before_held=before_held
manifest={x['symbol']:x for x in read(U/'STOCK_MANIFEST.json')}
rules=read(B/'inputs-v2/market-rules.json');proxies=read(B/'inputs-v2/economic-protocol.json')['approved_proxy_ids']
panel_path=R/'momentum_persistence_breadth_v1/canonical_mu3_comparison_v2/COMMON_K_COMPARISON.parquet'
panel=pd.read_parquet(panel_path).sort_values(['sector','day']);cal=pd.DatetimeIndex(sorted(panel.day.unique()));cal=cal[cal<=END]
sector={s:g.set_index('day').M3_candidate.to_dict() for s,g in panel.groupby('sector')}
ev=pd.read_csv(E/'SEALED_ALL_BIRTH_EVENTS.csv',parse_dates=['day','previous_common_day'],low_memory=False)
ev=ev[ev.window.eq(WINDOW)&ev.event_type.isin(['A_SECTOR_BIRTH','B_STOCK_BIRTH_DURING_SECTOR'])]
original=pd.read_csv(E/'lifecycle_v1/ALL_2026H1_SEMI_ROUNDS.csv',float_precision='round_trip');original=original[original.arm.eq('A_UNION_B')].copy();assert len(original)==46
permits={r['round_id']:ev[ev.event_id.eq(r['event_id'])].iloc[0].to_dict() for r in original.to_dict('records')}
assert len(permits)==46 and original.status.str.contains('UNKNOWN').sum()==20
for p in [U/'STOCK_MANIFEST.json',panel_path,E/'SEALED_ALL_BIRTH_EVENTS.csv',E/'lifecycle_v1/ALL_2026H1_SEMI_ROUNDS.csv',E/'lifecycle_v1/ACTIONS.csv',B/'inputs-v2/market-rules.json',B/'inputs-v2/economic-protocol.json',B/'code/market_rules.py',B/'code/sector_account.py',O/'PROTOCOL.md']:
 hashes[str(p)]=sha(p)
for p,h in read(E/'EVENT_SEAL.json')['outputs'].items():assert sha(E/p)==h,(p,'original event output drift');hashes[str(E/p)]=h
for p,h in read(E/'EVENT_SEAL.json')['source_hashes'].items():assert sha(p)==h;hashes[p]=h
raw={};facts={};cp={};capacity={};meta={};closecache={};actions_sources={};load_count=0
rounds=[];actions=[];decisions=[];blocks=[];ranking_audit=[];bridges=[];registrations=[];claim_ledger=[];marks=[];archives={};claims={};snapshots={};all_claims=[];source_checks=[]
def load(sid):
 if sid in raw:return
 native_load(sid)
 m=manifest[sid];expected={**m['source_sha256'],**m['output_sha256']}
 for p in [next(p for p in m['source_sha256'] if p.endswith('/signal.parquet')),m['refs']['facts'],m['refs']['CP1']]:assert hashes[p]==expected[p],(sid,p,'manifest drift')
 assert raw[sid].frame.index.is_unique

def reset(bridge=False,source=False):
 global BRIDGE,SOURCE_BRIDGE,ALLOWED_EVENT_IDS,CURRENT_PHASE
 for x in [rounds,actions,decisions,blocks,ranking_audit,bridges,registrations,claim_ledger,marks,all_claims,source_checks]:x.clear()
 for x in [archives,claims,snapshots,closecache]:x.clear()
 BRIDGE=bridge;SOURCE_BRIDGE=source;ALLOWED_EVENT_IDS=None;CURRENT_PHASE='UNSET'

CANDIDATES=read(E/'source_bridge_2026_feasibility_v1/SOURCE_BRIDGE_CANDIDATES.json')
assert len(CANDIDATES)==16
SOURCE_AT={(r['sid'],pd.Timestamp(r['transition_day'])):r for r in CANDIDATES};assert len(SOURCE_AT)==16
OVERLAP={};SOURCE_SEALED=False

def validate_overlap(can,ths,d,previous_day):
 """Only physical d-1 prefixes are eligible; future duplicate/bad values are ignored."""
 if not isinstance(can,pd.DataFrame) or not isinstance(ths,pd.DataFrame) or not isinstance(can.index,pd.DatetimeIndex) or not isinstance(ths.index,pd.DatetimeIndex):return False
 can=can.loc[can.index<d];ths=ths.loc[ths.index<d]
 if not can.index.is_unique or not ths.index.is_unique:return False
 ix=can.index.intersection(ths.index)
 if len(ix)==0 or ix.max()!=previous_day:return False
 for c in ['open','high','low','close','volume','amount']:
  if c not in can or c not in ths:return False
  a=can.loc[ix,c].to_numpy(dtype=float);b=ths.loc[ix,c].to_numpy(dtype=float)
  if not np.isfinite(a).all() or not np.isfinite(b).all():return False
  atol,rtol=(1e-6,0) if c in ['open','high','low','close'] else (1.,1e-6)
  if not np.isclose(a,b,atol=atol,rtol=rtol).all():return False
 return True

def prepare_sources():
 global SOURCE_SEALED
 root=E/'source_bridge_2026_feasibility_v1'
 assert sha(root/'SOURCE_BRIDGE_CANDIDATES.json')=='893de6c397e9ad68d4b97bd984b0c3f22d176c44d96d1caf65fb4e35c614be2f'
 for name,h in read(root/'FINAL_OUTPUT_HASHES.json').items():assert sha(root/name)==h,(name,'feasibility seal drift')
 for p,h in read(root/'SOURCE_HASHES.json').items():assert sha(p)==h,(p,'source evidence drift');hashes[p]=h
 hashes[str(root/'SOURCE_BRIDGE_CANDIDATES.json')]=sha(root/'SOURCE_BRIDGE_CANDIDATES.json')
 p=Path(CANDIDATES[0]['from_lineage'][1]);can=pd.read_parquet(p,filters=[('symbol','in',[r['sid'] for r in CANDIDATES])]);assert set(can.source)=={'tushare'}
 for r in CANDIDATES:
  assert r['status']=='CANDIDATE_NOT_ACTIVATED' and r['existing_tolerance_conflicts']==0
  for p,h in [(r['from_lineage'][1],r['old_source_sha256']),(r['to_lineage'][1],r['new_source_sha256']),(r['signal_path'],r['signal_sha256'])]:assert sha(p)==h,(p,'whitelist hash drift')
  d=pd.Timestamp(r['transition_day']);prev=pd.Timestamp(r['previous_day'])
  a=can[can.symbol.eq(r['sid'])].set_index('trade_date').copy();a['volume']*=100;a['amount']*=1000
  b=pd.DataFrame(read(r['to_lineage'][1])['bars']).set_index('date');b.index=pd.to_datetime(b.index)
  assert validate_overlap(a,b,d,prev),(r['sid'],'overlap conflict')
  OVERLAP[(r['sid'],d)]=(a.loc[a.index<d].copy(),b.loc[b.index<d].copy())
 SOURCE_SEALED=True

def source_transition_ok(sid,d,origin,z,prev,previous_day):
 r=SOURCE_AT.get((sid,d))
 if not SOURCE_BRIDGE or not SOURCE_SEALED or r is None:return False
 if previous_day!=pd.Timestamp(r['previous_day']):return False
 if tuple(map(str,r['from_lineage']))!=tuple(origin) or lineage(prev)!=tuple(origin):return False
 if lineage(z)!=tuple(map(str,r['to_lineage'])):return False
 if not finite(z.get('raw_open')) or z['raw_open']<=0:return False
 for col,want in [('adjustment_factor',r['factor']),('volume_factor',r['volume_factor'])]:
  if not all(finite(x) and x>0 and x==want for x in [z.get(col),prev.get(col)]):return False
 a,b=OVERLAP.get((sid,d),(pd.DataFrame(),pd.DataFrame()))
 if not validate_overlap(a,b,d,previous_day):return False
 return True

def before_held(states,sid,st,d):
 if BRIDGE or SOURCE_BRIDGE:
  z=raw[sid].get(d,{})
  if finite(z.get('raw_open')) and z['raw_open']>0 and lineage(z)==st['origin']:
   ix=raw[sid].frame.index;past=ix[ix<d];pv=raw[sid].get(past[-1],{}).get('volume_factor') if len(past) else None
   if not finite(pv) or not finite(z.get('volume_factor')) or pv<=0 or z['volume_factor']!=pv:
    freeze_unknown(states,sid,st,'VOLUME_FACTOR_PATH_UNKNOWN',d);return False
 if SOURCE_BRIDGE:
  z=raw[sid].get(d,{})
  if lineage(z)!=st['origin']:
   ix=raw[sid].frame.index;past=ix[ix<d];prevday=past[-1] if len(past) else None;prev=raw[sid].get(prevday,{})
   if source_transition_ok(sid,d,st['origin'],z,prev,prevday) and st['factor']==z['adjustment_factor']:
    old=st['origin'];st['origin']=lineage(z)
    bridges.append(dict(round_id=st['round_id'],sid=sid,day=d,kind='EXACT_SOURCE_TRANSITION',from_lineage=old,to_lineage=st['origin'],factor=st['factor']))
 return cash_before_held(states,sid,st,d)

def install_events(rows):
 """Called only with sealed independently reviewed fact adapters. No implied admission."""
 global EVENTS,EVENT_AT,EVENT_BY_ID,BY_RECORD,BY_EX,BY_PAY
 EVENTS=rows;EVENT_AT={(r['sid'],r['ex_date']):r for r in rows};EVENT_BY_ID={r['economic_event_id']:r for r in rows}
 assert len(EVENT_AT)==len(rows)==len(EVENT_BY_ID)
 BY_RECORD={};BY_EX={};BY_PAY={}
 for e in rows:
  BY_RECORD.setdefault(e['coordinate_snapshot_day'],[]).append(e);BY_EX.setdefault(e['ex_date'],[]).append(e);BY_PAY.setdefault(e['pay_date'],[]).append(e)

def run_fixed(rid,stop=END):
 global ALLOWED_EVENT_IDS,CURRENT_PHASE
 assert rid in permits
 r=permits[rid];sid=r['sid'];arm='A_UNION_B';ALLOWED_EVENT_IDS={e['economic_event_id'] for e in EVENTS if e['sid']==sid}
 # Every permit is an independent replay. Persist claims before resetting next permit.
 claims.clear();snapshots.clear();check=checkclose(r);assert check['close_check']=='PASS'
 st=new_state(r,arm,rid,check);states={sid:st}
 for k,d in enumerate(cal):
  if d<r['day'] or d>stop:continue
  if d>r['day']:
   CURRENT_PHASE='OPEN';accrue_day(arm,d)
   if states.get(sid,{}).get('state')=='BUY_PENDING':entry_open(states,sid,st,d)
   elif states.get(sid,{}).get('state')=='HELD':held_open(states,sid,st,d,cal[k-1])
   if states.get(sid,{}).get('state')=='HELD':held_close(states,sid,st,d)
  CURRENT_PHASE='CLOSE';register(states,arm,d);pay_day(arm,d)
  if states.get(sid,{}).get('state') not in ('BUY_PENDING','HELD') and all(c['settled'] for c in claims.values()):break
 if states.get(sid,{}).get('state')=='HELD':record(st,'OPEN_CENSORED_AT_2026_06_30' if stop==END else 'PREFIX_CENSORED',stop,exit_pending_at_end=bool(st['exitpending']),add_pending_at_end=st['addpending'] is not None)
 elif states.get(sid,{}).get('state')=='BUY_PENDING':record(st,'BUY_PENDING_CENSORED_AT_DATA_END',stop)
 finalize([st]);all_claims.extend(copy.deepcopy(list(claims.values())));return rounds[st['_output_index']]

def dump(dest):
 dest=Path(dest);dest.mkdir(exist_ok=False)
 for fn,rows_ in [('ROUNDS',rounds),('ACTIONS',actions),('REGISTRATIONS',registrations),('CLAIM_LEDGER',claim_ledger),('PROFIT_GATES',marks)]:pd.DataFrame(rows_).to_csv(dest/(fn+'.csv'),index=False)
 save(dest/'CLAIMS.json',all_claims);save(dest/'BRIDGES.json',bridges);save(dest/'LEDGER_QA.json',ledger_qa());save(dest/'SOURCE_HASHES.json',hashes)
 for p,h in hashes.items():assert sha(p)==h,(p,'source drift')
 save(dest/'OUTPUT_HASHES.json',{p.name:sha(p) for p in dest.iterdir() if p.is_file() and p.name!='OUTPUT_HASHES.json'})

def verify_frozen_inputs(expected=None):
 for p,h in (hashes if expected is None else expected).items():
  assert Path(p).is_file() and sha(p)==h,(p,'frozen input drift')
 return True

def load_cash_candidates():
 """Validate 10 fact adapters but do not install or activate them."""
 p=E/'cash_facts_2026_v1/EVENT_ADAPTER_CANDIDATES.json';t=read(p);assert len(t)==10
 hashes[str(p)]=sha(p);rows=[]
 targets=pd.read_csv(E/'source_bridge_2026_feasibility_v1/CASH_FACTOR_EVENTS.csv');allowed={(r.sid,pd.Timestamp(r.day)) for r in targets.itertuples()}
 assert {(r['sid'],pd.Timestamp(r['ex_date'])) for r in t}==allowed
 for r in t:
  assert r['production_admitted'] is False and r['coordinate_verified_for_production'] is False and r['entitlement_verified_for_production'] is False
  verify_frozen_inputs(r['evidence_sources']);hashes.update(r['evidence_sources'])
  sid=r['sid'];d=pd.Timestamp(r['ex_date']);rec=pd.Timestamp(r['record_date']);pay=pd.Timestamp(r['pay_date']);load(sid)
  a=local_actions(sid);assert a['_source_integrity_ok'];term=a['events'][r['local_action_ordinal']-1]
  assert term['effective_date']==r['ex_date'] and D(str(term['split_ratio']))==1 and D(str(term['cash_per_old_share']))==D(r['d_source'])
  f=raw[sid].frame;previous=f[f.index<d].iloc[-1];current=f.loc[d]
  ds=D(r['d_source']);dc=D(r['d_cash']);fo=D(r['factor_old']);fn=D(r['factor_new']);pc=D(r['previous_close'])
  assert all(v.is_finite() and v>0 for v in [ds,dc,fo,fn,pc]) and pc>ds
  assert lineage(previous)==lineage(current) and previous.volume_factor==current.volume_factor
  assert str(previous.name.date())==r['previous_day'] and rec==previous.name and rec<d<=pay and START<=rec and d<=END
  assert all(x in cal for x in [rec,d,pay])
  assert abs(D(str(previous.adjustment_factor))/fo-1)<=D('1e-11') and abs(D(str(current.adjustment_factor))/fn-1)<=D('1e-11')
  assert D(str(previous.raw_close))==pc and abs(fo*pc/(pc-ds)/fn-1)<=D('1e-11')
  notice=r['notice'];assert notice['code_gross_A_share_RMB_dates_context_verified'] is True
  assert all(notice[k]==r[k] for k in ['record_date','ex_date','pay_date']) and D(notice['d_cash'])==dc
  rows.append(dict(r,record_date=rec,ex_date=d,pay_date=pay,coordinate_snapshot_day=rec,previous_day=rec,d_source=ds,d_cash=dc,factor_old=fo,factor_new=fn,previous_close=pc,coordinate_verified=True,entitlement_verified=True,coordinate_scope='FROZEN_SOURCE_TRANSLATION_ONLY',entitlement_scope='OWN_REGISTER_Q_NET80_NOT_ACTUAL_TAX',scenario_not_PIT=True))
 assert len({r['economic_event_id'] for r in rows})==10
 return rows

def verify_cash_fact_review():
 root=E/'cash_facts_2026_v1';p=root/'INDEPENDENT_AUDIT.json';review=read(p)
 assert review['result']=='PASS_COMPANY_FACT_EVIDENCE_ONLY' and review['audited_events']==10
 assert review['event_adapter_sha256']==sha(root/'EVENT_ADAPTER_CANDIDATES.json')
 assert review['economic_run_permitted'] is False and review['production_admitted'] is False
 verify_frozen_inputs(review['evidence_file_sha256']);hashes.update(review['evidence_file_sha256']);hashes[str(p)]=sha(p)
 return True
