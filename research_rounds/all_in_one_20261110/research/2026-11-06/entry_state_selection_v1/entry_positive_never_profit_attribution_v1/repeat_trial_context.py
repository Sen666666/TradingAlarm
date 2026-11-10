from pathlib import Path
import pandas as pd,numpy as np,json,hashlib,sys
from decimal import Decimal as D
O=Path(__file__).resolve().parent;R=O.parent;U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031');B=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025')
sys.path.insert(0,str(B/'code'))
from market_rules import version_on,market_identity_on
from sector_account import FeeComponent,FeeSchedule
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
sources=[Path(__file__),O/'EVENT_CONTEXT_AND_COST.csv',R/'breadth_single_day_dependency_v1/ALL_M3_RESULTS.csv',R/'entry_protection_migration_mechanism_v1/BASELINE_PATH_DIAGNOSTICS.csv',R/'momentum_persistence_breadth_v1/canonical_mu3_comparison_v2/COMMON_K_COMPARISON.parquet',R/'breadth_trade_contract_v1/ALL_EVENTS.csv',U/'STOCK_MANIFEST.json',B/'inputs-v2/market-rules.json',B/'inputs-v2/economic-protocol.json',B/'code/market_rules.py',B/'code/sector_account.py']
hashes={str(f):sha(f) for f in sources}
e=pd.read_csv(sources[1],dtype={'window':str});p=pd.read_csv(sources[2],dtype={'window':str},low_memory=False);p=p[p.event_type.eq('FALSE_TO_TRUE')&p.baseline_selected].copy()
b=pd.read_csv(sources[3],dtype={'window':str},low_memory=False);p=p.merge(b[['event_id','sid','entry_risk']],on=['event_id','sid'],validate='one_to_one')
panel=pd.read_parquet(sources[4]);cal=pd.DatetimeIndex(sorted(panel.day.unique()));dates={t.strftime('%Y-%m-%d'):i for i,t in enumerate(cal)}
panel=panel.sort_values(['sector','day']);panel['onset']=panel.M3_candidate.eq(1)&panel.groupby('sector').M3_candidate.shift().eq(0)
events=pd.read_csv(sources[5],dtype={'window':str});events=events[events.arm.eq('M3')&events.event_type.eq('FALSE_TO_TRUE')]
onsets={s:g[g.onset].day.dt.strftime('%Y-%m-%d').tolist() for s,g in panel.groupby('sector')}
evmap={(r.day,r.sector):r.event_id for r in events.itertuples()};ps={k:v for k,v in p.groupby('event_id')}
manifest={z['symbol']:z for z in json.load(open(sources[6]))};rules=json.load(open(sources[7]));proxies=json.load(open(sources[8]))['approved_proxy_ids'];cache={}
def fee(q,price,sid,day,side):
 identity=market_identity_on(rules,sid,day,proxies);v=version_on(rules['fee_versions'][identity['venue']],day,proxies)['schedule'];fs=FeeSchedule(v['schedule_id'],tuple(FeeComponent(**z) for z in v['components']));par=D(str(rules['security_metadata'][sid]['par_value']))
 return float(sum(fs.incremental(side,D(int(q))*D(str(price)),{}, {},1,shares=int(q),par_value=par).values(),D(0)))
def data(sid):
 if sid not in cache:
  m=manifest[sid];sp=Path(next(z for z in m['source_sha256'] if z.endswith('/signal.parquet')));fp=Path(m['refs']['facts']);cache[sid]=(pd.read_parquet(sp),pd.read_parquet(fp));hashes[str(sp)]=sha(sp);hashes[str(fp)]=sha(fp)
 return cache[sid]
rows=[];legs=[]
for r in e.itertuples():
 past=[d for d in onsets[r.sector] if d<r.day];prev=past[-1] if past else None;gap=dates[r.day]-dates[prev] if prev else np.nan
 eid=evmap.get((prev,r.sector));prevrows=ps.get(eid,p.iloc[0:0])
 active=[];uncertain=[];inactive=[];risk=[];gross=[];pending=[]
 for a in prevrows.itertuples():
  status='NOT_OPEN'
  if a.label=='NO_ENTRY':status='KNOWN_NO_ENTRY'
  elif pd.notna(a.unknown_day) and str(a.unknown_day)[:10]<=r.day:status='UNKNOWN_PRIOR_PATH'
  elif pd.isna(a.entry_q) or a.entry_q<=0:status='UNKNOWN_PRIOR_ENTRY'
  elif pd.notna(a.exit_day) and str(a.exit_day)[:10]<=r.day:status='ALREADY_CLOSED'
  elif str(a.entry_day)[:10]<=r.day:status='KNOWN_ACTIVE'
  x=dict(event_id=r.event_id,day=r.day,industry=r.industry,previous_event_id=eid,previous_day=prev,previous_sid=a.sid,previous_name=a.name,prior_status_at_current_close=status,prior_net_pnl_DIAGNOSTIC_ONLY=a.net_pnl,prior_entry_risk=a.entry_risk)
  if status=='KNOWN_ACTIVE':
   active.append(a.sid);raw,fact=data(a.sid);d=pd.Timestamp(r.day);rr=raw.loc[d];ff=fact.loc[d];floor=ff.i_floor/rr.adjustment_factor;cl=rr.raw_close
   # Existing core only. No mark-to-floor zero-risk inference after an exit trigger.
   pending_exit=not bool(ff.i_target) or not np.isfinite(floor) or cl<=floor
   prisk=np.nan if pending_exit else a.entry_q*(cl-floor*(1-.0005))+fee(a.entry_q,floor*(1-.0005),a.sid,r.day,'sell')
   risk.append(prisk);gross.append(a.entry_q*cl);pending.append(pending_exit)
   x.update(prior_core_q=a.entry_q,current_close=cl,current_I_floor=floor,current_I_active=bool(ff.i_target),exit_pending_do_not_free_budget=pending_exit,core_mark_to_floor_reference_risk=prisk,core_marked_capital=a.entry_q*cl)
  elif status.startswith('UNKNOWN'):uncertain.append(a.sid)
  else:inactive.append(a.sid)
  legs.append(x)
 if prev is None:state='PREVIOUS_ONSET_NOT_OBSERVED'
 elif eid is None:state='PREVIOUS_EVENT_OUTSIDE_EVALUATED_WINDOWS'
 elif not len(prevrows):state='PREVIOUS_EVENT_NO_SELECTED_TRIAL'
 elif active:state='PREVIOUS_TRIAL_STILL_ACTIVE'
 elif uncertain:state='PREVIOUS_TRIAL_STATUS_UNKNOWN'
 else:state='PREVIOUS_TRIAL_ALREADY_CLOSED_OR_NO_ENTRY'
 curr=ps[r.event_id];duplicate=set(active)&set(curr.sid);newrisk=[];newgross=[]
 for a in curr.itertuples():
  if a.sid in duplicate:continue
  q=a.close_quantity;cl=a.known_close_raw;fl=a.close_floor_raw;buy=cl*(1+.0005);sell=fl*(1-.0005)
  newrisk.append(q*(buy-sell)+fee(q,buy,a.sid,r.day,'buy')+fee(q,sell,a.sid,r.day,'sell'));newgross.append(q*buy)
 row=r._asdict();row.update(previous_onset_day=prev,previous_onset_gap_sessions=gap,previous_event_id=eid,previous_reference_state=state,previous_selected_n=len(prevrows),previous_known_active_n=len(active),previous_unknown_n=len(uncertain),previous_exit_pending_n=sum(pending),duplicate_selected_sid_n=len(duplicate),duplicate_selected_sids='|'.join(sorted(duplicate)),prior_known_active_entry_plan_risk=sum(a.entry_risk for a in prevrows.itertuples() if a.sid in active),prior_core_mark_reference_risk=sum(risk) if active and not any(pending) else (0 if not active else np.nan),prior_core_marked_capital=sum(gross),current_nonduplicate_close_plan_risk=sum(newrisk),current_nonduplicate_close_plan_capital=sum(newgross),current_plus_previous_core_reference_risk=(sum(risk)+sum(newrisk) if not any(pending) and not uncertain and eid is not None else np.nan),current_plus_previous_core_reference_capital=sum(gross)+sum(newgross),short_gap_diagnostic_band='FIRST_NOT_OBSERVED' if prev is None else ('WITHIN_20_SESSIONS' if gap<=20 else 'OVER_20_SESSIONS'))
 rows.append(row)
d=pd.DataFrame(rows);d.to_csv(O/'ADJACENT_EVENT_TRIAL_CONTEXT.csv',index=False);pd.DataFrame(legs).to_csv(O/'PREVIOUS_TRIAL_AT_CURRENT_CLOSE.csv',index=False)
summ=[]
for dim in ['previous_reference_state','short_gap_diagnostic_band']:
 for (w,val),g in d.groupby(['window',dim]):
  comp=g[g.all_candidates_complete];bad=g[g.event_class.eq('ALL_COMPLETE_NO_FULL_WIN')]
  summ.append(dict(window=w,dimension=dim,value=val,events=len(g),dates=g.day.nunique(),all_complete=len(comp),complete_no_full_win=len(bad),no_full_win_fraction_complete=len(bad)/len(comp) if len(comp) else np.nan,selected_closed=g.selected_closed_n.sum(),selected_wins=g.selected_win_n.sum(),selected_tail30=g.selected_tail30_n.sum(),selected_net_sum_NOT_ACCOUNT=g.selected_net_sum_NOT_ACCOUNT.sum(),all_loss_event_selected_n=bad.selected_closed_n.sum(),all_loss_event_net_sum_NOT_ACCOUNT=bad.selected_net_sum_NOT_ACCOUNT.sum(),duplicate_new_selected_rows=g.duplicate_selected_sid_n.sum(),target_positive_never_n=g.target_positive_never_n.sum()))
ss=pd.DataFrame(summ);ss.to_csv(O/'ADJACENT_EVENT_SUMMARY.csv',index=False)
case_sectors=['旅游及酒店','化学原料','军工装备','光伏设备','半导体']
d[d.industry.isin(case_sectors)].to_csv(O/'FIXED_ADJACENT_EVENT_CASES.csv',index=False)
assert e.selected_n.max()<=2
assert all(sha(p)==h for p,h in hashes.items());save('REPEAT_SOURCE_HASHES.json',hashes)
save('REPEAT_QA.json',dict(no_new_rank_or_economic_simulation=True,short_window_definition='20 common sessions is one descriptive month bucket only; not optimized, gated, or replayed.',previous_onsets='Original canonical M3 0->1 on full existing daily panel, including outside birth windows. No observed predecessor is left-censored, never assumed true first.',active_status_clock='Only entry/exit/unknown path dates through current signal close. Final PnL and future exit used solely retrospective outcomes, not risk state.',risk_clock='At current signal close, prior adjacent-event CORE quantities and current native I floor/raw close, dated fees. New nonduplicate selections use frozen t-close quantity/current price/current floor. Open gap excluded. Pending I exit or unknown prior state prevents finite combined risk claim.',risk_scope='Reference core-only adjacent-event diagnostic, excluding add holdings, other earlier events, shared capital/actual account gating. Not an account budget or guarantee.',same_stock_duplicates_are_not_add_contract=True,source_hashes_unchanged=True))
print(ss.to_string(index=False))
print('CASE_TOURISM\n',d[d.industry.eq('旅游及酒店')&d.window.eq('2022')][['day','event_class','previous_onset_day','previous_onset_gap_sessions','previous_reference_state','duplicate_selected_sid_n','selected_net_sum_NOT_ACCOUNT','current_plus_previous_core_reference_risk','current_plus_previous_core_reference_capital']].to_string(index=False))
print('RISK_DESCRIPTION\n',d[d.previous_reference_state.eq('PREVIOUS_TRIAL_STILL_ACTIVE')].groupby('window').agg(events=('event_id','size'),duplicates=('duplicate_selected_sid_n','sum'),median_core_risk=('current_plus_previous_core_reference_risk','median'),max_core_risk=('current_plus_previous_core_reference_risk','max'),median_core_capital=('current_plus_previous_core_reference_capital','median')).to_string())
