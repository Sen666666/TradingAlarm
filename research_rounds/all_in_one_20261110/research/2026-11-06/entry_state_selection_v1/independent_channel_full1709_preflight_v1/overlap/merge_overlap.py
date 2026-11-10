"""Read sealed market states and old ledgers; no new lifecycle, account, fill or return."""
from pathlib import Path
from decimal import Decimal as D
import ast,json,hashlib,sys,time
import numpy as np,pandas as pd
O=Path(__file__).resolve().parent;N=O.parent;R=N.parent;E=R/'m3_stock_birth_during_sector_v1';F=R/'fast_entry_equity_2022_v1'
U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
B=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025')
H=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz')
SOURCES={};EXTRACTED={};INIT=D('24000');RISK=D('3000');SLIP=D('.0005');END=pd.Timestamp('2026-06-30')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def src(p,expected=None):
 p=Path(p);h=sha(p)
 if expected:assert h==expected,(str(p),'hash mismatch')
 if str(p) in SOURCES:assert SOURCES[str(p)]==h
 SOURCES[str(p)]=h;return p
def read(p):return json.loads(src(p).read_text())
def save(name,x):(O/name).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str,allow_nan=False)+'\n')
def csv(p):return pd.read_csv(src(p),low_memory=False,float_precision='round_trip')
def finite(x):
 try:return bool(np.isfinite(x))
 except (TypeError,ValueError):return False
def true(x):return pd.notna(x) and x in (True,1)
def false(x):return pd.notna(x) and x in (False,0)
def flags(z):return all(true(z.get(c)) for c in ('observed_bar','price_eligible','volume_eligible')) and false(z.get('source_invalid')) and false(z.get('synthetic_event_bar'))
def lineage(z):return tuple(str(z.get(c)) for c in ('source_kind','source_path','segment_id'))
def tri_and(*ss):
 ss=[s.astype('boolean') for s in ss];x=ss[0].copy()
 for s in ss[1:]:x=x&s
 return x

def load_reference(folder,sub,window,arm='A_UNION_B',report=True):
 rounds=csv(folder/('report/CORE_AND_FULL_ROUNDS.csv' if report else sub+'/ROUNDS.csv'))
 decisions=csv(folder/sub/'DECISIONS.csv');actions=csv(folder/sub/'ACTIONS.csv')
 rounds=rounds[rounds.arm.eq(arm)].copy();decisions=decisions[decisions.arm.eq(arm)].copy();actions=actions[actions.arm.eq(arm)].copy()
 for frame in (rounds,decisions,actions):
  frame['window']=window
  for c in ['day','signal_day','entry_day','status_day','exit_day']:
   if c in frame:frame[c]=pd.to_datetime(frame[c],format='mixed')
 assert rounds.round_id.is_unique
 assert set(rounds.round_id)==set(decisions.loc[decisions.selected,'round_id'])
 buys=actions[actions.side.eq('buy_core')].set_index('round_id')
 for rr in rounds.itertuples():
  if pd.notna(rr.entry_day):
   assert rr.round_id in buys.index
   aa=buys.loc[rr.round_id];assert aa.day==rr.entry_day and int(aa.q)==int(rr.entry_q)
  else:assert rr.round_id not in buys.index
 return rounds,decisions,actions

def reconstruct_states(x,rounds,decisions,windows,prefix):
 n=len(x);before=np.full(n,'UNKNOWN',dtype=object);after=before.copy();rid=np.full(n,None,dtype=object)
 known=x.window.isin(windows).to_numpy();before[known]='knownFLAT';after[known]='knownFLAT'
 groups=x.groupby(['window','sid'],sort=False).indices
 for rr in rounds.sort_values(['window','sid','signal_day']).itertuples():
  ix=groups.get((rr.window,rr.sid))
  if ix is None:continue
  days=x.day.iloc[ix];sig=rr.signal_day;stop=rr.status_day;entry=rr.entry_day
  # Same-close legacy admission is not known before its old queue decision.
  pending_end=entry if pd.notna(entry) else stop
  pm=(days>sig)&(days<pending_end);pa=(days>=sig)&(days<pending_end)
  before[ix[pm]]='PENDING';after[ix[pa]]='PENDING';rid[ix[pa]]=rr.round_id
  if pd.notna(entry):
   held=(days>=entry)&((days<=stop) if 'CENSORED' in rr.status else (days<stop))
   before[ix[held]]='HELD';after[ix[held]]='HELD';rid[ix[held]]=rr.round_id
  if 'UNKNOWN' in rr.status:
   mask=days>=stop;before[ix[mask]]='UNKNOWN';after[ix[mask]]='UNKNOWN';rid[ix[mask]]=rr.round_id
  elif 'BUY_PENDING_CENSORED' in rr.status:
   mask=days>=sig;after[ix[mask]]='PENDING';before[ix[(days>sig)]]='PENDING';rid[ix[mask]]=rr.round_id
  elif rr.status=='COMPLETE_CONDITIONAL_STOCK_ROUND' or 'NOFILL' in rr.status:
   pass
  elif 'OPEN_CENSORED' not in rr.status:raise AssertionError(('unknown status semantics',rr.status))
 x[prefix+'_state_before_old_admission']=before;x[prefix+'_state_after_old_admission']=after;x[prefix+'_blocking_round_id_after']=rid
 # Validate all old decision-day state observations, not only new receipts.
 lookup=x.set_index(['window','sid','day'])[prefix+'_state_before_old_admission']
 checks=0
 for dd in decisions.itertuples():
  key=(dd.window,dd.sid,dd.day)
  if key not in lookup.index:continue
  expected={'FLAT':'knownFLAT','BUY_PENDING':'PENDING'}.get(dd.stock_state_before,dd.stock_state_before)
  assert lookup.loc[key]==expected,(prefix,key,lookup.loc[key],expected)
  checks+=1
 return dict(rounds=len(rounds),decision_day_state_checks=checks,all_equal=True,source_windows=list(windows),other_windows='UNKNOWN_NOT_REBUILT',scope='sealed independent-stock conditional scenario, not actual account')

def enrich_old(x):
 old=pd.concat([pd.read_parquet(src(F/'ALL_MARKET_INPUTS_2022.parquet')),pd.read_parquet(src(O/'OLD_NATIVE_Q_EXTENDED.parquet'))],ignore_index=True)
 assert not old.duplicated(['sid','day']).any()
 cols=['event_Q','continuing_Q','event_Q_reasons','continuing_Q_reasons','i_buy','i_target','i_floor','e0_ready','e0_target','g_ready','g_grade','cp_fresh','cp_candidate','cp_id','cp_trace_known','cp_trace_unknown','PVR_score','PVR_known','native_H1_score','sector_H1_score','i_epoch','epoch_lineage_known','epoch_lineage_reason','AB_event_id','AB_event_type','AB_I_qualified','AB_PVR_known']
 old=old[['sid','day']+cols].rename(columns={c:'old_'+c for c in cols})
 x=x.merge(old,on=['sid','day'],how='left',validate='one_to_one',sort=False)
 assert x.old_event_Q_reasons.notna().all()
 for c in ['event_Q','continuing_Q','i_buy','i_target','cp_fresh','cp_trace_known','PVR_known','epoch_lineage_known','AB_I_qualified','AB_PVR_known']:x['old_'+c]=x['old_'+c].astype('boolean')
 x['old_ab_coverage']=np.where(x.window.eq('2026H1')&x.sector.ne('URFI881121'),'UNKNOWN_OUTSIDE_ORIGINAL_SEMICONDUCTOR_WINDOW','KNOWN_ORIGINAL_WINDOW')
 abknown=x.old_ab_coverage.eq('KNOWN_ORIGINAL_WINDOW')
 x['old_ab_raw_permit']=x.old_AB_event_id.notna().astype('boolean');x.loc[~abknown,'old_ab_raw_permit']=pd.NA
 x['old_ab_I_qualified_permit']=tri_and(x.old_ab_raw_permit,x.old_AB_I_qualified.where(x.old_ab_raw_permit.fillna(False),False))
 x['old_ab_I_PVR_qualified_permit']=tri_and(x.old_ab_I_qualified_permit,x.old_AB_PVR_known.where(x.old_ab_raw_permit.fillna(False),False))
 x.loc[~abknown,['old_ab_I_qualified_permit','old_ab_I_PVR_qualified_permit']]=pd.NA
 x['old_fast_core_market_prereq_ignoring_consumption']=tri_and(x.old_event_Q,x.old_epoch_lineage_known,x.old_i_epoch.notna())
 x['old_mobile_cp_market_prereq_ignoring_consumption']=tri_and(x.old_cp_fresh,x.old_continuing_Q,x.old_cp_trace_known.where(x.old_cp_fresh.fillna(False),False),x.old_cp_id.notna())
 # Separate old industry facts, never AND them into the new price root or size.
 for c in ['sector_known','sector_observed_today','sector_rs_ready_fresh','sector_up']:
  values=[]
  for s in x.old_event_Q_reasons:
   ss=set(str(s).split('|'));values.append(pd.NA if c+':unknown' in ss else False if c+':false' in ss else True)
  x['old_'+c]=pd.array(values,dtype='boolean')
 sectorcols=['old_'+c for c in ['sector_known','sector_observed_today','sector_rs_ready_fresh','sector_up']]
 x['old_sector_component_prereq']=tri_and(*(x[c] for c in sectorcols));x.loc[x[sectorcols].isna().any(axis=1),'old_sector_component_prereq']=pd.NA
 x['old_any_market_offer_prereq']=x.old_ab_I_PVR_qualified_permit|x.old_fast_core_market_prereq_ignoring_consumption|x.old_mobile_cp_market_prereq_ignoring_consumption
 # Direct canonical CP identity comparison. Absence is only false when native observation exists.
 canonical=pd.read_parquet(src(F/'CANONICAL_CP_2022_2026.parquet'))[['sid','day','cp_id']].rename(columns={'cp_id':'canonical_cp_id'})
 x=x.merge(canonical,on=['sid','day'],how='left',validate='one_to_one',sort=False)
 fresh=x.old_cp_fresh.fillna(False);assert x.loc[fresh,'old_cp_id'].eq(x.loc[fresh,'canonical_cp_id']).all()
 assert x.loc[x.canonical_cp_id.notna(),'old_cp_fresh'].fillna(False).all()
 return x

def add_decisions(x,decisions,prefix,windows):
 names=['selected','decision','stock_state_before','queue_rank','selected_rank','round_id','blocking_round_id','preferred_role','role_checks','close_check','source_mask']
 names=[c for c in names if c in decisions]
 dd=decisions[['sid','day']+names].rename(columns={c:prefix+'_'+c for c in names})
 assert not dd.duplicated(['sid','day']).any();x=x.merge(dd,on=['sid','day'],how='left',validate='one_to_one',sort=False)
 covered=x.window.isin(windows);x[prefix+'_covered']=covered
 x[prefix+'_selected']=x[prefix+'_selected'].astype('boolean');x.loc[covered,prefix+'_selected']=x.loc[covered,prefix+'_selected'].fillna(False)
 x.loc[covered&x[prefix+'_decision'].isna(),prefix+'_decision']='NO_ORIGINAL_CANDIDATE'
 x.loc[~covered,prefix+'_decision']='UNKNOWN_NO_SAMECONTRACT_RUN'
 return x

def sizing(receipts,manifest):
 sys.path.insert(0,str(B/'code'))
 from market_rules import version_on,market_identity_on,RuleUnavailable
 from sector_account import QuantityRule,FeeComponent,FeeSchedule
 env=dict(D=D,version_on=version_on,market_identity_on=market_identity_on,RuleUnavailable=RuleUnavailable,QuantityRule=QuantityRule,FeeComponent=FeeComponent,FeeSchedule=FeeSchedule,SLIP=SLIP,meta={},rules=read(B/'inputs-v2/market-rules.json'),proxies=read(B/'inputs-v2/economic-protocol.json')['approved_proxy_ids'])
 for p in [B/'code/market_rules.py',B/'code/sector_account.py',E/'relative_priority_equity_run_2022_v1/engine.py',E/'cash_equity_baseline_2024_v1/engine.py']:src(p)
 p=src(E/'relative_priority_v1/simulate.py');txt=p.read_text()
 for node in ast.parse(txt).body:
  if isinstance(node,ast.FunctionDef) and node.name in {'getmeta','fee','size'}:
   seg=ast.get_source_segment(txt,node);EXTRACTED[node.name]=hashlib.sha256(seg.encode()).hexdigest();exec(compile(seg,str(p)+':identical_size_only','exec'),env)
 with np.load(src(H),allow_pickle=False) as h:cal=pd.DatetimeIndex(h['dates'])
 datepos={d:i for i,d in enumerate(cal)};out=[]
 for n,(sid,g) in enumerate(receipts.groupby('sid',sort=True)):
  mm=manifest[sid];p=next(p for p in mm['source_sha256'] if p.endswith('/signal.parquet'));raw=pd.read_parquet(src(p,mm['source_sha256'][p])).loc[:END]
  vol=raw.raw_volume[raw.raw_volume.gt(0)];caps=(vol.rolling(20,min_periods=20).mean()*.01).reindex(raw.index).ffill()
  for rr in g.itertuples():
   d=rr.day;pos=datepos[d];nd=cal[pos+1] if pos+1<len(cal) else pd.NaT;z=raw.loc[d] if d in raw.index else {};oz=raw.loc[nd] if nd in raw.index else {}
   cap=caps.get(d,np.nan);fl=None
   row=dict(sid=sid,day=d,window=rr.window,root_day=rr.root_day,receipt_id=rr.receipt_id,born=rr.born,size_semantics='UNSTARTED_PARENT_ONLY_NOT_A_RETRY_OR_ADD',nominal_budget_cny=24000,plan_risk_budget_cny=3000,one_way_slippage_bp=5,volume_capacity_known_at=d,volume_capacity_clock='20 positive raw-volume observations through signal close; frozen at immediate next OPEN',volume_capacity_shares=int(cap) if finite(cap) else None,next_common_open_day=nd,close_conditional_q=None,open_conditional_q=None,historical_fill='UNKNOWN_NOT_SIMULATED',actual_ack='UNKNOWN_NOT_PROVIDED',new_parent_or_unsettled_state='UNKNOWN_NOT_SIMULATED')
   if not flags(z) or not finite(z.get('raw_close')) or z.get('raw_close',0)<=0 or not finite(z.get('adjustment_factor')) or z.get('adjustment_factor',0)<=0:row['close_size_check']='INVALID_CLOSE_UNKNOWN'
   elif not finite(rr.S_new) or rr.S_new<=0:row['close_size_check']='NEW_PRICE_FLOOR_UNKNOWN'
   elif not np.isclose(z['raw_close']*z['adjustment_factor'],rr.C,rtol=1e-10,atol=1e-9):row['close_size_check']='RAW_FACTOR_SIGNAL_COORDINATE_UNKNOWN'
   elif not finite(cap):row['close_size_check']='VOLUME_CAPACITY_UNKNOWN'
   else:
    fl=D(str(rr.S_new))/D(str(z['adjustment_factor']));cl=D(str(z['raw_close']));row['signal_floor_raw']=float(fl)
    if cl<=fl:row['close_size_check']='AT_OR_BELOW_FLOOR_NOFILL'
    else:
     try:
      q,bf,risk,_,_=env['size'](sid,d,cl*(1+SLIP),fl,INIT,RISK,int(cap));row.update(close_size_check='CONDITIONAL_UNSTARTED_TARGET_FEASIBLE' if q else 'Q0_MINIMUM_LOT_OR_RISK_NOFILL',close_conditional_q=q,close_fee=float(bf),close_plan_risk=float(risk))
     except (RuleUnavailable,KeyError,ValueError) as ex:row.update(close_size_check='DATED_RULE_UNKNOWN',close_error=str(ex))
   # This is a separate immediate-open observation check. Never feeds close qualification.
   if row['close_size_check']!='CONDITIONAL_UNSTARTED_TARGET_FEASIBLE':row['open_size_check']='NOT_REACHED_CLOSE_NOT_FEASIBLE'
   elif not finite(oz.get('raw_open')) or oz.get('raw_open',0)<=0:row['open_size_check']='MISSING_IMMEDIATE_OPEN_UNKNOWN'
   elif lineage(oz)!=lineage(z):row['open_size_check']='SOURCE_CHANGED_AT_OPEN_UNKNOWN'
   elif not finite(oz.get('adjustment_factor')) or not np.isclose(oz['adjustment_factor'],z['adjustment_factor'],rtol=1e-11):row['open_size_check']='FACTOR_BRIDGE_NOT_EVALUATED_UNKNOWN'
   else:
    op=D(str(oz['raw_open']));row['next_raw_open']=float(op)
    if op<=fl:row['open_size_check']='OPEN_AT_OR_BELOW_FLOOR_NOFILL'
    else:
     try:
      q,bf,risk,_,_=env['size'](sid,nd,op*(1+SLIP),fl,INIT,RISK,int(cap));row.update(open_size_check='CONDITIONAL_UNSTARTED_OPEN_FEASIBLE_NOT_FILL' if q else 'Q0_MINIMUM_LOT_OR_RISK_NOFILL',open_conditional_q=q,open_fee=float(bf),open_plan_risk=float(risk))
     except (RuleUnavailable,KeyError,ValueError) as ex:row.update(open_size_check='DATED_RULE_AT_OPEN_UNKNOWN',open_error=str(ex))
   # Daily one-price flag is post-hoc descriptive only, not referenced in either check above.
   row['next_daily_one_price_fact']=bool(oz.get('raw_open')==oz.get('raw_high')==oz.get('raw_low')==oz.get('raw_close')) if all(finite(oz.get(k)) for k in ['raw_open','raw_high','raw_low','raw_close']) else None
   out.append(row)
  if (n+1)%250==0:print('SIZE_STOCKS',n+1,flush=True)
 z=pd.DataFrame(out)
 z['conditional_unstarted_target_feasible']=z.close_size_check.eq('CONDITIONAL_UNSTARTED_TARGET_FEASIBLE')
 z['conditional_unstarted_open_feasible']=z.open_size_check.eq('CONDITIONAL_UNSTARTED_OPEN_FEASIBLE_NOT_FILL')
 assert z.loc[z.conditional_unstarted_target_feasible,'close_plan_risk'].le(3000+1e-8).all()
 assert z.loc[z.conditional_unstarted_open_feasible,'open_plan_risk'].le(3000+1e-8).all()
 return z

def opportunities(x,r,rounds,decisions):
 # Only outcomes in sealed OLD reports are labels. They never enter generation or sizing.
 labels=[];xi=x.set_index(['sid','day']);rg={k:g for k,g in r.groupby(['window','sector','day'])};sg=decisions[decisions.selected].groupby(['window','sector','day']).size()
 bystock={k:g.sort_values('day') for k,g in x.groupby(['window','sid'])}
 for oo in rounds.itertuples():
  group='OLD_CORE_GE50_COVERED' if true(oo.evidence_usable_closed) and finite(oo.core_return) and oo.core_return>=.5 else 'OLD_CORE_LOSS_COVERED' if true(oo.evidence_usable_closed) and finite(oo.core_return) and oo.core_return<0 else 'OTHER_OR_UNCOVERED'
  if group=='OTHER_OR_UNCOVERED':continue
  w='2026H1' if oo.window=='2026H1_SEMI' else str(oo.window);d=oo.signal_day;ss=bystock[(w,oo.sid)];z=xi.loc[(oo.sid,d)];peer=rg.get((w,oo.sector,d),r.iloc[0:0]);peer=peer[peer.sid.ne(oo.sid)]
  births=peer[peer.born];new=peer[peer.conditional_old_baseline_flat_unstarted_candidate];unique=peer[peer.conditional_unique_market_unstarted_candidate]
  rr=z.root_day;end=pd.Timestamp(oo.exit_day);hold=ss[(ss.day>=d)&(ss.day<end)];full=end<=ss.day.max()
  # UNKNOWN interrupts knowledge, not price survival. Never count source quarantine as failure.
  rootrows=hold[hold.root_day.eq(rr)] if pd.notna(rr) else hold.iloc[0:0]
  endings=rootrows[rootrows.failed|rootrows.root_unknown]
  if not bool(z.active):root_survives=None;survival_status='NO_ACTIVE_PRICE_ROOT_AT_OLD_SIGNAL'
  elif len(endings):
   ending=endings.iloc[0]
   if ending.failed:root_survives=False;survival_status='PRICE_FAILED_BEFORE_OLD_EXIT'
   else:root_survives=None;survival_status='SOURCE_BOUNDARY_UNKNOWN_BEFORE_OLD_EXIT' if bool(ending.valid) else 'INVALID_PRICE_UNKNOWN_BEFORE_OLD_EXIT'
  elif not full:root_survives=None;survival_status='CENSORED_AT_FIXED_WINDOW_END'
  else:
   root_survives=bool(len(hold) and hold.active.all() and hold.root_day.eq(rr).all())
   assert root_survives,('unexplained root discontinuity',oo.round_id)
   survival_status='SAME_PRICE_ROOT_SURVIVES_TO_OLD_EXIT_OPEN'
  slots=int(sg.get((w,oo.sector,d),0)) if w!='2026H1' else None
  labels.append(dict(window=w,round_id=oo.round_id,sid=oo.sid,name=oo.name,industry=oo.industry,sector=oo.sector,old_signal_day=d,old_entry_day=oo.entry_day,old_exit_day=end,old_core_return=oo.core_return,old_outcome_group=group,old_financial_coverage=oo.financial_coverage_status,new_price_active_at_old_signal=bool(z.active),new_receipt_at_old_signal=bool(z.receipt),new_birth_at_old_signal=bool(z.born),new_root_at_old_signal=rr,new_E0_at_old_signal=z.E0,new_I_at_old_signal=z.I,market_root_survives_to_old_exit_open=root_survives,root_survival_status=survival_status,root_survival_observation_scope='FULL_OLD_HOLDING_CLOSE_PATH' if full else 'CENSORED_AT_FIXED_WINDOW_END',new_births_in_observed_old_hold=int(hold.born.sum()),new_receipts_in_observed_old_hold=int(hold.receipt.sum()),new_failures_in_observed_old_hold=int(hold.failed.sum()),new_unknown_roots_in_observed_old_hold=int(hold.root_unknown.sum()),peer_market_births_same_sector_day=len(births),peer_close_q_feasible_unstarted_receipts=int(peer.conditional_unstarted_target_feasible.sum()),peer_old_baseline_flat_conditional_receipts=len(new),peer_unique_market_conditional_receipts=len(unique),old_selected_sector_day_slots=slots,potential_slot_competition_without_ranking=bool(slots==2 and len(unique)>0) if slots is not None else None,actual_displacement='NOT_TESTED_NO_NEW_QUEUE_OR_ACCOUNT',new_strategy_return='NOT_COMPUTED'))
 return pd.DataFrame(labels)

def retry_market_diagnostic(x,r):
 # Not execution. If a birth attempt failed, does fresh market evidence later exist?
 with np.load(src(H),allow_pickle=False) as h:cal=pd.DatetimeIndex(h['dates'])
 ci={d:i for i,d in enumerate(cal)};groups={k:g.sort_values('day') for k,g in x.groupby(['window','sid'])};rows=[]
 for b in r[r.born].itertuples():
  same=groups[(b.window,b.sid)];same=same[same.root_day.eq(b.root_day)&same.day.gt(b.day)]
  future=same[same.receipt];first=future.iloc[0] if len(future) else None
  terminals=same[same.failed|same.root_unknown];terminal=terminals.iloc[0] if len(terminals) else None
  categories=[]
  if true(b.next_daily_one_price_fact):categories.append('ONE_PRICE_FACT_NOT_NOFILL_PROOF')
  if b.open_size_check=='OPEN_AT_OR_BELOW_FLOOR_NOFILL':categories.append('OPEN_AT_OR_BELOW_FLOOR')
  if 'Q0' in b.close_size_check:categories.append('CLOSE_Q0')
  if 'Q0' in b.open_size_check:categories.append('OPEN_Q0')
  if 'UNKNOWN' in b.close_size_check or 'UNKNOWN' in b.open_size_check:categories.append('SIZE_OR_OPEN_UNKNOWN')
  if first is not None:ending='LATER_FRESH_FRONTIER_EXISTS'
  elif terminal is not None:ending='ROOT_PRICE_FAILED_WITHOUT_LATER_RECEIPT' if terminal.failed else 'ROOT_QUARANTINED_UNKNOWN_WITHOUT_LATER_RECEIPT'
  else:ending='NO_LATER_RECEIPT_THROUGH_WINDOW_END'
  rows.append(dict(window=b.window,sid=b.sid,sector=b.sector,day=b.day,root_day=b.root_day,receipt_id=b.receipt_id,birth_phase=b.phase,close_size_check=b.close_size_check,open_size_check=b.open_size_check,next_common_open_day=b.next_common_open_day,next_daily_one_price_fact=b.next_daily_one_price_fact,diagnostic_categories='|'.join(categories) if categories else 'ORDINARY_BIRTH_IF_UNFILLED',later_same_root_frontier_exists=first is not None,first_later_frontier_day=first.day if first is not None else pd.NaT,common_sessions_wait_to_later_frontier=ci[first.day]-ci[b.day] if first is not None else None,later_same_root_receipts=len(future),root_terminal_day=terminal.day if terminal is not None else pd.NaT,ending=ending,ack_and_fill_ledger='UNKNOWN_NOT_SIMULATED',parent_Q='FIXED_IF_PREVIOUSLY_CREATED_NO_RESIZING',retry_permission='UNASSESSED_REAL_ACK_MUST_PRECEDE_NEW_RECEIPT'))
 detail=pd.DataFrame(rows);sums=[]
 for w,g in detail.groupby('window'):
  for cat in ['ALL_BIRTHS_IF_UNFILLED','ONE_PRICE_FACT_NOT_NOFILL_PROOF','OPEN_AT_OR_BELOW_FLOOR','CLOSE_Q0','OPEN_Q0','SIZE_OR_OPEN_UNKNOWN']:
   h=g if cat=='ALL_BIRTHS_IF_UNFILLED' else g[g.diagnostic_categories.str.contains(cat,regex=False)]
   sums.append(dict(window=w,condition=cat,births=len(h),later_frontier_exists=int(h.later_same_root_frontier_exists.sum()),no_later_frontier=int((~h.later_same_root_frontier_exists).sum()),median_common_sessions_wait=float(h.common_sessions_wait_to_later_frontier.median()) if h.common_sessions_wait_to_later_frontier.notna().any() else None,p90_common_sessions_wait=float(h.common_sessions_wait_to_later_frontier.quantile(.9)) if h.common_sessions_wait_to_later_frontier.notna().any() else None,no_receipt_then_price_failed=int(h.ending.eq('ROOT_PRICE_FAILED_WITHOUT_LATER_RECEIPT').sum()),no_receipt_then_unknown=int(h.ending.eq('ROOT_QUARANTINED_UNKNOWN_WITHOUT_LATER_RECEIPT').sum()),no_receipt_to_window_end=int(h.ending.eq('NO_LATER_RECEIPT_THROUGH_WINDOW_END').sum()),actual_retry_or_fill='UNKNOWN_NOT_SIMULATED'))
 return detail,pd.DataFrame(sums)

def context_strata(x,r):
 births=r[r.born].copy()
 births['E0_maturity_context']=np.select([births.e0_ready.isna(),births.e0_ready.eq(0),births.e0_ready.eq(1)&births.E0.eq(0),births.e0_ready.eq(1)&births.E0.eq(1)&births.I.eq(0),births.e0_ready.eq(1)&births.E0.eq(1)&births.I.eq(1)],['E0_READY_UNKNOWN','E0_NOT_READY','E0_READY_TARGET_OFF','E0_READY_TARGET_ON_I_OFF','E0_READY_TARGET_ON_I_ON'],default='OTHER_NATIVE_UNKNOWN')
 b=[]
 for (w,ctx),g in births.groupby(['window','E0_maturity_context'],dropna=False):
  b.append(dict(window=w,E0_maturity_context=ctx,birth_stockdays=len(g),stocks=g.sid.nunique(),phase_probe=int(g.phase.eq('PROBE').sum()),phase_amount_unknown=int(g.phase.eq('PROBE_AMOUNT_UNKNOWN').sum()),phase_confirmed=int(g.phase.eq('CONFIRMED').sum()),G_unknown=int(g.G.isna().sum()),G_levels=json.dumps(g.G.value_counts(dropna=False).to_dict(),default=str),close_q_feasible=int(g.conditional_unstarted_target_feasible.sum()),old_baseline_flat_unstarted_conditional=int(g.conditional_old_baseline_flat_unstarted_candidate.sum()),unique_market_unstarted_conditional=int(g.conditional_unique_market_unstarted_candidate.sum()),not_mature_early_signal_proof=ctx in ['E0_READY_UNKNOWN','E0_NOT_READY']))
 z=x[x.window.eq('2026H1')].copy();z['source_boundary_period']=np.where(z.day<pd.Timestamp('2026-05-18'),'BEFORE_2026_05_18','ON_OR_AFTER_2026_05_18');rows=[]
 for (period,source),g in z.groupby(['source_boundary_period','source_kind'],dropna=False):
  rows.append(dict(window='2026H1',source_boundary_period=period,source_kind=str(source),stockdays=len(g),stocks=g.sid.nunique(),price_known=int(g.valid.sum()),price_unknown=int((~g.valid).sum()),births=int(g.born.sum()),receipts=int(g.receipt.sum()),price_failures=int(g.failed.sum()),root_quarantine_unknown=int(g.root_unknown.sum()),valid_price_source_boundary_root_unknown=int((g.root_unknown&g.valid).sum()),birth_amount_unknown=int((g.born&g.phase.eq('PROBE_AMOUNT_UNKNOWN')).sum()),receipt_amount_unknown=int((g.receipt&~g.volume_credit_known).sum()),old_baseline_occupancy='UNKNOWN_NOT_REBUILT',new_account_exit_or_flat='NOT_INFERRED'))
 return births,pd.DataFrame(b),pd.DataFrame(rows)

def main():
 began=time.monotonic();assert (N/'QA.json').exists(),'Wait for market source COMPLETE'
 qa=read(N/'QA.json');assert qa.get('errors')==[]
 assert not (O/'DAILY_OVERLAP.parquet').exists(),'Refuse to overwrite final merge'
 manifest={m['symbol']:m for m in read(U/'STOCK_MANIFEST.json')}
 for p in [Path(__file__),O/'export_native_q.py',N/'PROTOCOL.md',R/'independent_channel_probe_preflight_v1/PROTOCOL.md',F/'lifecycle.py',F/'run.py',F/'repair_ab_map.py']:src(p)
 x=pd.read_parquet(src(N/'DAILY_STATES.parquet'));x['day']=pd.to_datetime(x.day);x['window']=x.window.astype(str);x=x.sort_values(['window','sid','day']).reset_index(drop=True)
 x=enrich_old(x)
 refs=[load_reference(E/'relative_priority_equity_run_2022_v1','dynamic','2022'),load_reference(E/'cash_equity_baseline_2024_v1','economic','2024_924')]
 br=pd.concat([z[0] for z in refs],ignore_index=True);bd=pd.concat([z[1] for z in refs],ignore_index=True)
 fr,fd,fa=load_reference(F,'economic','2022',arm='AB_FAST_SMALL',report=False)
 stateqa={};stateqa['A_UNION_B']=reconstruct_states(x,br,bd,['2022','2024_924'],'old_ab')
 stateqa['AB_FAST_SMALL']=reconstruct_states(x,fr,fd,['2022'],'old_fast')
 x=add_decisions(x,bd,'old_ab_baseline',['2022','2024_924']);x=add_decisions(x,fd,'old_fast_AB_FAST_SMALL',['2022'])
 x['new_path_flat_or_parent_state']='UNKNOWN_NOT_SIMULATED';x['new_full_trade_eligibility']='UNSPECIFIED_SECTOR_AND_EXECUTION_POLICY'
 x['old_reference_state_scope']=np.where(x.window.eq('2026H1'),'UNKNOWN_NO_COHERENT_REPAIRED_2026_SELECTION_RUN','SEALED_INDEPENDENT_STOCK_SCENARIO_NOT_ACTUAL_ACCOUNT')
 x['price_source_coverage']=x.sid.map({sid:m['status'] for sid,m in manifest.items()})
 r=x[x.receipt].copy();size=sizing(r,manifest);assert len(size)==len(r)
 r=r.merge(size,on=['sid','day','window','root_day','receipt_id','born'],how='left',validate='one_to_one')
 r['conditional_old_baseline_flat_unstarted_candidate']=r.conditional_unstarted_target_feasible&r.old_ab_state_after_old_admission.eq('knownFLAT')
 r['conditional_unique_market_unstarted_candidate']=r.conditional_old_baseline_flat_unstarted_candidate&(~r.old_any_market_offer_prereq).fillna(False)
 r['unique_market_comparison_known']=r.old_any_market_offer_prereq.notna()
 # This column is intentionally never TRUE: no new-path responsibility state or complete resource policy exists.
 r['actual_new_empty_position_eligible']='UNKNOWN_NOT_SIMULATED'
 source26=E/'fixed_permit_recovery_2026_v1/report/CORE_AND_FULL_ROUNDS.csv';rr26=csv(source26)
 for c in ['signal_day','entry_day','exit_day','status_day']:rr26[c]=pd.to_datetime(rr26[c],format='mixed')
 src(E/'fixed_permit_recovery_2026_v1/report/READOUT.md');src(E/'fixed_permit_recovery_2026_v1/PROTOCOL.md')
 outcomes=opportunities(x,r,pd.concat([br,rr26],ignore_index=True),bd)
 retrydetail,retrysummary=retry_market_diagnostic(x,r)
 contextbirths,contextsummary,boundarysummary=context_strata(x,r)
 summary=[]
 for w,g in r.groupby('window'):
  scopes=[('ALL1709',g)]
  if w=='2026H1':scopes.append(('SEMICONDUCTOR_URFI881121',g[g.sector.eq('URFI881121')]))
  for scope,h in scopes:
   for stage,j in [('BIRTH',h[h.born]),('ALL_FRONTIER_RECEIPTS',h)]:
    q=dict(window=w,scope=scope,stage=stage,stockdays=len(j),stocks=j.sid.nunique(),market_roots=j[['sid','root_day']].drop_duplicates().shape[0],size_feasible_roots=j.loc[j.conditional_unstarted_target_feasible,['sid','root_day']].drop_duplicates().shape[0],E0_off=int(j.E0.eq(0).sum()),I_off=int(j.I.eq(0).sum()),E0_and_I_off=int((j.E0.eq(0)&j.I.eq(0)).sum()),i_buy_off=int(j.i_buy.eq(0).sum()),old_event_Q_true=int(j.old_event_Q.fillna(False).sum()),old_event_Q_unknown=int(j.old_event_Q.isna().sum()),old_ab_raw_true=int(j.old_ab_raw_permit.fillna(False).sum()),old_ab_raw_unknown=int(j.old_ab_raw_permit.isna().sum()),old_ab_I_PVR_true=int(j.old_ab_I_PVR_qualified_permit.fillna(False).sum()),old_fast_core_market_prereq=int(j.old_fast_core_market_prereq_ignoring_consumption.fillna(False).sum()),old_mobile_cp_market_prereq=int(j.old_mobile_cp_market_prereq_ignoring_consumption.fillna(False).sum()),old_cp_fresh=int(j.old_cp_fresh.fillna(False).sum()),old_fast_actual_selected=int(j.old_fast_AB_FAST_SMALL_selected.fillna(False).sum()),old_fast_actual_unknown=int(j.old_fast_AB_FAST_SMALL_selected.isna().sum()),old_ab_actual_selected=int(j.old_ab_baseline_selected.fillna(False).sum()),conditional_unstarted_target_feasible=int(j.conditional_unstarted_target_feasible.sum()),conditional_unstarted_open_feasible=int(j.conditional_unstarted_open_feasible.sum()),conditional_old_baseline_flat_unstarted=int(j.conditional_old_baseline_flat_unstarted_candidate.sum()),conditional_unique_market_unstarted=int(j.conditional_unique_market_unstarted_candidate.sum()),market_comparison_unknown=int(j.old_any_market_offer_prereq.isna().sum()),one_price_nextday_facts=int(j.next_daily_one_price_fact.fillna(False).sum()),factor_bridge_not_evaluated=int(j.open_size_check.eq('FACTOR_BRIDGE_NOT_EVALUATED_UNKNOWN').sum()),actual_new_orders=0)
    for st in ['HELD','PENDING','UNKNOWN','knownFLAT']:q['old_ab_after_'+st]=int(j.old_ab_state_after_old_admission.eq(st).sum())
    summary.append(q)
 summ=pd.DataFrame(summary)
 coverage=[]
 for w,g in x.groupby('window'):
  for component,known in [('OLD_NATIVE_Q_FACTS',g.old_event_Q.notna()),('OLD_AB_RAW_PERMIT_SCOPE',g.old_ab_raw_permit.notna()),('OLD_AB_REPAIRED_OCCUPANCY',g.old_ab_state_after_old_admission.ne('UNKNOWN')),('OLD_AB_SAMECONTRACT_RUN_EXISTS',g.old_ab_baseline_covered),('OLD_FAST_EXECUTED_ARM_EXISTS',g.old_fast_AB_FAST_SMALL_covered),('NEW_PRICE_VALID',g.valid)]:
   coverage.append(dict(window=w,component=component,all_stocks=g.sid.nunique(),all_stockdays=len(g),known_stockdays=int(known.sum()),known_stocks=g.loc[known,'sid'].nunique(),unknown_or_unavailable_stockdays=int((~known).sum()),first_common_day=g.day.min(),last_common_day=g.day.max(),manifest_no_local_history_stocks=g.loc[g.price_source_coverage.ne('complete'),'sid'].nunique(),unknown_is_not_false=True))
 outsummary=[]
 for (w,kind),g in outcomes.groupby(['window','old_outcome_group']):
  outsummary.append(dict(window=w,old_outcome_group=kind,old_rounds=len(g),new_price_active_at_old_signal=int(g.new_price_active_at_old_signal.sum()),new_receipt_at_old_signal=int(g.new_receipt_at_old_signal.sum()),new_birth_at_old_signal=int(g.new_birth_at_old_signal.sum()),new_root_survives_full_known_old_hold=int(g.market_root_survives_to_old_exit_open.fillna(False).sum()),root_survival_window_censored=int(g.root_survival_status.eq('CENSORED_AT_FIXED_WINDOW_END').sum()),root_survival_source_unknown=int(g.root_survival_status.eq('SOURCE_BOUNDARY_UNKNOWN_BEFORE_OLD_EXIT').sum()),root_survival_invalid_price_unknown=int(g.root_survival_status.eq('INVALID_PRICE_UNKNOWN_BEFORE_OLD_EXIT').sum()),root_price_failed=int(g.root_survival_status.eq('PRICE_FAILED_BEFORE_OLD_EXIT').sum()),no_active_price_root_at_old_signal=int(g.root_survival_status.eq('NO_ACTIVE_PRICE_ROOT_AT_OLD_SIGNAL').sum()),any_peer_unique_market_conditional_receipt=int(g.peer_unique_market_conditional_receipts.gt(0).sum()),potential_two_slot_competition=int(g.potential_slot_competition_without_ranking.fillna(False).sum()),actual_displacement='NOT_TESTED',new_strategy_returns='NOT_COMPUTED'))
 # Every output used for reporting is frozen before hash seal; no changes to old paths.
 x.to_parquet(O/'DAILY_OVERLAP.parquet',index=False);r.to_parquet(O/'RECEIPT_CONDITIONAL_OVERLAP.parquet',index=False);r[r.born].to_parquet(O/'BIRTH_CONDITIONAL_OVERLAP.parquet',index=False)
 r[r.window.eq('2026H1')&r.sector.eq('URFI881121')].to_parquet(O/'SEMICONDUCTOR_2026_RECEIPT_OVERLAP.parquet',index=False)
 size.to_parquet(O/'UNSTARTED_TARGET_SIZE_CHECKS.parquet',index=False);summ.to_csv(O/'OVERLAP_SUMMARY.csv',index=False);outcomes.to_csv(O/'OLD_OUTCOME_SURVIVAL_AND_COMPETITION.csv',index=False);pd.DataFrame(outsummary).to_csv(O/'OLD_OUTCOME_SUMMARY.csv',index=False)
 r[r.born&(r.E0.eq(0)|r.I.eq(0))].to_csv(O/'PURE_PRICE_E0_OR_I_OFF_BIRTHS.csv',index=False)
 retrydetail.to_csv(O/'IF_BIRTH_UNFILLED_LATER_FRONTIER.csv',index=False);retrysummary.to_csv(O/'IF_BIRTH_UNFILLED_SUMMARY.csv',index=False);pd.DataFrame(coverage).to_csv(O/'OLD_SOURCE_COVERAGE.csv',index=False)
 contextbirths.to_parquet(O/'BIRTH_E0_MATURITY_CONTEXT.parquet',index=False);contextsummary.to_csv(O/'BIRTH_E0_MATURITY_SUMMARY.csv',index=False);boundarysummary.to_csv(O/'SOURCE_BOUNDARY_2026_SUMMARY.csv',index=False)
 save('STATE_RECONSTRUCTION_QA.json',stateqa);save('SIZE_EXTRACTED_DEFINITIONS.json',EXTRACTED)
 save('CONTRACT.json',dict(stock_price_receipts_independent=True,industry_fields_only_descriptive=['sector_known','sector_observed_today','sector_rs_ready_fresh','sector_up'],new_industry_policy='NOT_FIXED_BY_THIS_PREFLIGHT',original_fast_arm='AB_FAST_SMALL',full_fast_executed_coverage='2022 only; 2024/26 native fact prerequisites do not include consumption, occupancy, PVR/size/queue outcomes',original_ab_2026_coverage='semiconductor permits only; fixed46 repair does not rebuild coherent selection or occupancy',new_parent_quantities='Not created. Per-receipt size is only hypothetical never-started parent; any existing parent must keep fixed Q and resume remaining Q-F only after real terminal ACK plus later fresh receipt.',old_flat='Only original independent-stock reference state, never proof the new path is flat',same_day_close_check_uses_no_next_open=True,open_current_HLC_flags_not_used=True,factor_bridge='Original repaired engine can translate some pending cash-event coordinates; this preflight does not evaluate that bridge and marks factor changes UNKNOWN, not NOFILL.',one_price_is_fill_evidence=False,tradeability='UNKNOWN',new_accounts=0,new_fills=0,new_strategy_returns=0,ranking='NOT_ASSUMED',old_outcome_labels='postprocessing only; no parameter or entry gate use'))
 for p,h in SOURCES.items():assert sha(p)==h,(p,'end source drift')
 save('SOURCE_HASHES.json',SOURCES)
 save('QA.json',dict(status='COMPLETE_OVERLAP_PENDING_INDEPENDENT_AUDIT',daily_rows=len(x),receipts=len(r),births=int(r.born.sum()),unique_keys=not x.duplicated(['sid','day']).any(),state_reconstruction=stateqa,all_source_hashes_unchanged=True,new_accounts=0,new_orders=0,new_fills=0,new_strategy_returns=0,new_path_flat_inference=False,old_states_2026_all_unknown=bool(x.loc[x.window.eq('2026H1'),'old_ab_state_after_old_admission'].eq('UNKNOWN').all()),seconds=time.monotonic()-began))
 save('OUTPUT_HASHES.json',{p.name:sha(p) for p in sorted(O.iterdir()) if p.is_file() and p.name not in ['OUTPUT_HASHES.json','MERGE_RUN.log']})
 print(summ.to_string(index=False));print(pd.DataFrame(outsummary).to_string(index=False));print('COMPLETE',len(x),len(r),round(time.monotonic()-began,1),flush=True)
if __name__=='__main__':main()
