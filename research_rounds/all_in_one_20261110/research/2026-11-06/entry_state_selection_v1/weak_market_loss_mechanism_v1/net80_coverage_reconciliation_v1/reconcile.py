"""Reporting reconciliation only; no execution, ranking, selection or economic rerun."""
from pathlib import Path
from decimal import Decimal as D
import json,hashlib,math,sys
import pandas as pd,numpy as np
O=Path(__file__).resolve().parent;W=O.parent;R=W.parent
E=R/'m3_stock_birth_during_sector_v1';S=E/'cash_dividend_402_scenario_v2';C=S/'report_coverage_overlay'
U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
B=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025')
H=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz')
sys.path.insert(0,str(B/'code'))
from market_rules import market_identity_on,version_on
from sector_account import FeeSchedule,FeeComponent
sources={str(p) for p in [Path(__file__),W/'ALL_CORE_PATH_DIAGNOSTICS.csv',C/'CORE_ONLY_FIXED_PERMITS.csv',C/'BASELINE_CORE_ONLY.csv',C/'SUMMARY.json',S/'full/DAILY_MARKS.csv',S/'full/ROUNDS.csv',S/'full/DIVIDEND_LEDGER.csv',S/'full/ACTIONS.csv',S/'run_scenario.py',S/'CONTRACT_SEAL.json',E/'lifecycle_v1/DECISIONS.csv',U/'STOCK_MANIFEST.json',H,B/'inputs-v2/market-rules.json',B/'inputs-v2/economic-protocol.json',B/'code/market_rules.py',B/'code/sector_account.py']}
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
rules=read(B/'inputs-v2/market-rules.json');proxies=read(B/'inputs-v2/economic-protocol.json')['approved_proxy_ids'];meta={}
manifest={x['symbol']:x for x in read(U/'STOCK_MANIFEST.json')}
with np.load(H,allow_pickle=False) as hz:cal=pd.DatetimeIndex(hz['dates'])
cal=cal[cal<=pd.Timestamp('2026-06-30')];di={d:i for i,d in enumerate(cal)}
def fee(sid,d,q,px):
 k=(sid,str(d.date()))
 if k not in meta:
  ident=market_identity_on(rules,sid,k[1],proxies)
  v=version_on(rules['fee_versions'][ident['venue']],k[1],proxies)['schedule']
  meta[k]=(FeeSchedule(v['schedule_id'],tuple(FeeComponent(**z) for z in v['components'])),D(str(rules['security_metadata'][sid]['par_value'])))
 fs,pa=meta[k]
 return sum(fs.incremental('sell',D(q)*px,{}, {},1,shares=q,par_value=pa).values(),D(0))
def pathclass(v,no='NO_KNOWN_PATH'):
 if pd.isna(v):return no
 if v<=0:return 'NEVER_POSITIVE'
 if v<.1:return 'POSITIVE_BELOW_10PCT'
 if v<.2:return 'PEAK_10_20PCT'
 return 'PEAK_GE20PCT'
def pathfields(ns,dates,K,entry):
 ns=np.asarray(ns,float);rt=ns/float(K)
 aft=rt[dates>entry]
 return dict(path_known=True,held_days=len(ns),peak_core_net=float(ns.max()),peak_core_return=float(rt.max()),min_core_return=float(rt.min()),ever_core_positive=bool((ns>0).any()),peak_after_entry_return=float(aft.max()) if len(aft) else np.nan,ever_after_entry_positive=bool((aft>0).any()) if len(aft) else None,only_entry_positive=bool(ns[0]>0 and not (aft>0).any()),positive_close_days=int((ns>0).sum()),last_core_mark=float(ns[-1]),first_close_return=float(rt[0]),first5_min=float(rt[:5].min()))
x=pd.read_csv(W/'ALL_CORE_PATH_DIAGNOSTICS.csv',float_precision='round_trip');x=x[x.window.eq('2022')].set_index('round_id')
y=pd.read_csv(C/'CORE_ONLY_FIXED_PERMITS.csv',float_precision='round_trip').set_index('round_id')
base=pd.read_csv(C/'BASELINE_CORE_ONLY.csv',float_precision='round_trip').set_index('round_id')
marks=pd.read_csv(S/'full/DAILY_MARKS.csv',float_precision='round_trip',parse_dates=['day']);marks=marks[marks['mode'].eq('CORE_ONLY')]
ledger=pd.read_csv(S/'full/DIVIDEND_LEDGER.csv',float_precision='round_trip',parse_dates=['day']);ledger=ledger[ledger['mode'].eq('CORE_ONLY')]
closed=y.status.isin(['CORE_ONLY_CLOSED_ALGEBRAIC','SCENARIO_CLOSED_NOT_FACT'])
assert len(y)==2432 and y.index.is_unique and closed.sum()==2311
cols=['path_known','held_days','peak_core_net','peak_core_return','min_core_return','ever_core_positive','peak_after_entry_return','ever_after_entry_positive','only_entry_positive','positive_close_days','last_core_mark','first_close_return','first5_min']
cache={};qa={'mark_net_max_error':0.,'mark_cash_max_error':0.,'mark_receivable_max_error':0.,'terminal_core_max_error':0.,'reconstructed_marks':0,'baseline_same_cohort_count':0,'baseline_same_cohort_max_error':0.}
def raw(sid):
 if sid not in cache:
  m=manifest[sid];p=next(p for p in m['source_sha256'] if p.endswith('/signal.parquet'));assert sha(p)==m['source_sha256'][p];sources.add(p)
  cache[sid]=pd.read_parquet(p).reindex(cal)
 return cache[sid]
rows=[]
for rid,r in y.iterrows():
 row=r.to_dict();row['round_id']=rid;row['closed']=bool(closed.loc[rid]);row['win']=bool(row['closed'] and r.net_pnl>0);row['core_net']=r.net_pnl if row['closed'] else np.nan;row['core_return']=r.net_return_on_buy_cash if row['closed'] else np.nan
 row['path_known']=False;row['path_evidence']='NONE'
 if r.status=='CORE_BASELINE_ACTION_COVERAGE_UNKNOWN':
  row['path_evidence']='UNVERIFIED_CORPORATE_ACTION_COVERAGE_DO_NOT_CLASSIFY'
 elif r.report_cohort=='RECOVERED_402_NET80_SCENARIO' or r.report_cohort=='TEN_ENTRY_FACTOR_BRIDGES':
  sid=r.sid;p=raw(sid);entry=pd.Timestamp(r.entry_day);last=cal[di[pd.Timestamp(r.exit_day)]-1] if row['closed'] else pd.Timestamp(r.last_known_mark_day)
  z=p.loc[entry:last];assert len(z)==di[last]-di[entry]+1 and z.raw_close.notna().all()
  for c in ['observed_bar','price_eligible','volume_eligible']:assert z[c].all()
  for c in ['synthetic_event_bar','source_invalid']:assert (~z[c]).all()
  for c in ['source_kind','source_path','segment_id']:assert z[c].nunique(dropna=False)==1
  q=int(r.entry_q);K=D(q)*D(str(r.entry_price))+D(str(r.entry_fee));ns=[]
  if r.report_cohort=='RECOVERED_402_NET80_SCENARIO':
   mm=marks[marks.original_round_id.eq(rid)].sort_values('day').set_index('day');assert mm.index.equals(z.index) and mm.core.eq(q).all() and mm['add'].eq(0).all()
   ll=ledger[ledger.original_round_id.eq(rid)];assert len(ll)==2
   ac=ll[ll.event.eq('ACCRUE_NET80_RECEIVABLE')].iloc[0];pay=ll[ll.event.eq('PAY_CLOSE_TRANSFER')].iloc[0]
   assert abs(ac.amount-pay.amount)<1e-8
   for day,bar in z.iterrows():
    accrued=D(str(ac.amount)) if day>=ac.day else D(0);paid=D(str(pay.amount)) if day>pay.day else D(0)
    cash=-K+paid;rec=accrued-paid;px=D(str(bar.raw_close))*D('.9995');net=cash+rec+D(q)*px-fee(sid,day,q,px);m=mm.loc[day]
    qa['mark_net_max_error']=max(qa['mark_net_max_error'],abs(float(net)-m.net_equity_at_close))
    qa['mark_cash_max_error']=max(qa['mark_cash_max_error'],abs(float(cash)-m.cash_before_payout))
    qa['mark_receivable_max_error']=max(qa['mark_receivable_max_error'],abs(float(rec)-m.receivable_before_payout));ns.append(float(net));qa['reconstructed_marks']+=1
   row['path_evidence']='NET80_MARKS_RECONCILED_WITH_RAW_DATED_FEE_AND_LEDGER'
   div=D(str(r.dividend_net80_total))
  else:
   assert np.isclose(z.adjustment_factor,z.adjustment_factor.iloc[0],rtol=1e-11).all()
   for day,bar in z.iterrows():
    px=D(str(bar.raw_close))*D('.9995');ns.append(float(D(q)*px-fee(sid,day,q,px)-K))
   row['path_evidence']='ENTRY_BRIDGE_CORE_PATH_STANDALONE_FEE';div=D(0)
  row.update(pathfields(ns,z.index,K,entry))
  if row['closed']:
   end=pd.Timestamp(r.exit_day);px=D(str(r.exit_price));net=D(q)*px-fee(sid,end,q,px)-K+div
   qa['terminal_core_max_error']=max(qa['terminal_core_max_error'],abs(float(net)-r.net_pnl))
 else:
  old=x.loc[rid];row.update({k:old[k] for k in cols});row['path_evidence']='UNCHANGED_OLD_CORE_PATH_OR_KNOWN_PREFIX'
  if row['closed']:
   assert old.closed;err=abs(old.core_net-r.net_pnl);qa['baseline_same_cohort_max_error']=max(qa['baseline_same_cohort_max_error'],err);qa['baseline_same_cohort_count']+=1;assert err<1e-7
 row['profit_path']=pathclass(row.get('peak_core_return',np.nan))
 row['t1_profit_path']=('UNVERIFIED_PATH' if r.status=='CORE_BASELINE_ACTION_COVERAGE_UNKNOWN' else 'NO_KNOWN_PATH') if not row['path_known'] else pathclass(row.get('peak_after_entry_return',np.nan),'NO_T1_CLOSE')
 row['loss']=bool(row['closed'] and row['core_net']<0)
 rows.append(row)
z=pd.DataFrame(rows).set_index('round_id');assert qa['baseline_same_cohort_count']==1902
assert all(qa[k]<1e-7 for k in ['mark_net_max_error','mark_cash_max_error','mark_receivable_max_error','terminal_core_max_error','baseline_same_cohort_max_error'])
z.reset_index().to_csv(O/'RECONCILED_PATHS.csv',index=False)
for field in ['profit_path','t1_profit_path']:
 z[z.loss].groupby(field).agg(n=('sid','size'),loss_cny=('core_net',lambda a:-a.sum()),median_held_days=('held_days','median')).to_csv(O/(field.upper()+'_LOSSES.csv'))
 z[z.loss].groupby(['report_cohort',field]).agg(n=('sid','size'),loss_cny=('core_net',lambda a:-a.sum())).to_csv(O/(field.upper()+'_LOSSES_BY_COHORT.csv'))
z[z.status.str.contains('UNKNOWN')].groupby(['path_evidence','profit_path','t1_profit_path']).agg(n=('sid','size')).to_csv(O/'UNKNOWN_PREFIX.csv')
oldclosed=x[x.closed];newclosed=z[z.closed];n=len(newclosed);wins=int(newclosed.win.sum());loss=z[z.loss];never=int(loss.profit_path.eq('NEVER_POSITIVE').sum());t1never=int(loss.t1_profit_path.eq('NEVER_POSITIVE').sum());not1=int(loss.t1_profit_path.eq('NO_T1_CLOSE').sum())
summary={'scope':'Original fixed 2432 permits; restored NET80 scenario, not account or PIT/actual-tax evidence; only reporting, no new backtest.','old':{'closed':len(oldclosed),'wins':int(oldclosed.win.sum()),'loss':int((~oldclosed.win).sum()),'small_positive_losses':int((x.loss&x.profit_path.eq('POSITIVE_BELOW_10PCT')).sum()),'never_positive_losses':int((x.loss&x.profit_path.eq('NEVER_POSITIVE')).sum())},'current':{'permits':len(z),'closed':n,'wins':wins,'losses':len(loss),'win_rate':wins/n,'unknown':int(z.status.str.contains('UNKNOWN').sum()),'nofill':int(z.status.str.contains('NOFILL').sum()),'small_positive_losses':int(loss.profit_path.eq('POSITIVE_BELOW_10PCT').sum()),'never_positive_losses':never,'only_entry_positive_losses':int(loss.only_entry_positive.fillna(False).sum()),'t1_never_positive_losses':t1never,'no_t1_close_losses':not1,'net_pnl_independent_sum':float(newclosed.core_net.sum()),'gross_loss_cny':float(-loss.core_net.sum())},'label_arithmetic_not_strategy':{'target':.35,'old_oracle_delete_never':506/(1913-338),'current_oracle_delete_never':wins/(n-never),'current_oracle_delete_t1_never_only':wins/(n-t1never),'current_oracle_delete_t1_never_plus_no_observation_separately':wins/(n-t1never-not1),'current_perfect_loss_deletions_to_35':n-math.floor(wins/.35),'current_net_win_increase_fixed_n_to_35':math.ceil(.35*n)-wins,'current_required_total_wins_fixed_n_to_35':math.ceil(.35*n)},'remaining_unknown':z[z.status.str.contains('UNKNOWN')].status.value_counts().to_dict(),'unknown_prefix':{'known_prefix_count':int((z.status.str.contains('UNKNOWN')&z.path_known.fillna(False)).sum()),'positive_prefix_count':int(z[z.status.str.contains('UNKNOWN')].ever_core_positive.fillna(False).sum()),'action_coverage_unknown_unclassified':11},'qa':qa}
# Exact original same-day/industry feasible queue. No new queue is simulated.
d=pd.read_csv(E/'lifecycle_v1/DECISIONS.csv',float_precision='round_trip',low_memory=False)
d=d[d.window.eq('2022')&d.arm.eq('A_UNION_B')]
f=d[d.decision.isin(['SELECTED_PENDING','PASS_NOT_TOP2'])].copy()
keys=['window','day','sector']
queues=f.groupby(keys).agg(queue_n=('sid','size'),queue_K=('selected','sum'))
f=f.merge(queues,on=keys,validate='many_to_one')
selected=f[f.decision.eq('SELECTED_PENDING')].set_index('round_id')
assert len(selected)==2432 and selected.index.is_unique and set(selected.index)==set(z.index)
matched=z.join(selected[['event_id','sid','sector','day','queue_n','queue_K']],rsuffix='_queue',validate='one_to_one')
assert matched.event_id.eq(matched.event_id_queue).all() and matched.sid.eq(matched.sid_queue).all() and matched.sector.eq(matched.sector_queue).all() and matched.signal_day.eq(matched.day).all()
matched['swappable']=matched.queue_n>matched.queue_K
oldq=x[x.closed].join(selected[['queue_n','queue_K']])
oldq['swappable']=oldq.queue_n>oldq.queue_K
oldcheck=oldq.groupby('swappable').agg(n=('sid','size'),wins=('win','sum'))
assert oldcheck.loc[False].tolist()==[1017,262] and oldcheck.loc[True].tolist()==[896,244]
newq=matched[matched.closed]
fixed=newq[~newq.swappable];changeable=newq[newq.swappable]
need=math.ceil(.35*len(newq))-int(fixed.win.sum())
summary['fixed_original_queue_label_arithmetic_not_new_strategy']={
 'definition':'2022 A_UNION_B same day, sector; feasible decisions SELECTED_PENDING or PASS_NOT_TOP2. K=original selected count, n>K is swappable. All 2432 round/event/stock/sector/signal-day identities matched.',
 'old_reproduced':{'fixed_n':1017,'fixed_wins':262,'swappable_n':896,'swappable_wins':244,'required_swappable_wins':408,'required_rate':408/896},
 'current':{'fixed_n':len(fixed),'fixed_wins':int(fixed.win.sum()),'swappable_n':len(changeable),'swappable_wins':int(changeable.win.sum()),'current_swappable_rate':float(changeable.win.mean()),'required_swappable_wins':need,'required_rate':need/len(changeable),'net_more_wins_needed':need-int(changeable.win.sum())},
 'unknowns_by_swappability':matched[matched.status.str.contains('UNKNOWN')].groupby('swappable').size().to_dict(),
 'nofill_by_swappability':matched[matched.status.str.contains('NOFILL')].groupby('swappable').size().to_dict(),
 'limitation':'Arithmetic only at current fixed 2311 closed denominator, holding non-swappable labels fixed. Ranking could change closure, outcomes, later held/flat availability, new event eligibility and fees. Unselected candidates have no terminal labels here. Repaired actual lifecycle cannot be inferred from frozen DECISIONS.'}
matched.reset_index().to_csv(O/'FIXED_QUEUE_MATCH.csv',index=False)
matched.groupby(['report_cohort','closed','swappable']).agg(n=('sid','size'),wins=('win','sum')).to_csv(O/'FIXED_QUEUE_BY_COHORT.csv')
summary['cohort_reconciliation']={'old_1913_closed':{'wins':506,'losses':1407},'removed_to_action_coverage_unknown':{'count':11,'wins':3,'losses':8},'strict_old_remaining':{'count':1902,'wins':503,'losses':1399},'ten_entry_bridges':{'count':10,'wins':5,'losses':5},'restored_NET80':{'count':399,'wins':219,'losses':180},'new_2311_closed':{'wins':727,'losses':1584}}
summary['current']['small_positive_loss_count_fraction']=int(loss.profit_path.eq('POSITIVE_BELOW_10PCT').sum())/len(loss)
summary['current']['small_positive_loss_money_fraction']=float(loss[loss.profit_path.eq('POSITIVE_BELOW_10PCT')].core_net.sum()/loss.core_net.sum())
summary['current']['peak_below10_loss_money_fraction']=float(loss[loss.profit_path.isin(['NEVER_POSITIVE','POSITIVE_BELOW_10PCT'])].core_net.sum()/loss.core_net.sum())
summary['fixed_permit_extremes_not_forecast']={'denominator_without_nofill':2431,'lower_if_all120unknown_lose':727/2431,'upper_if_all120unknown_win':847/2431,'unknown_never_treated_as_loss_or_win_in_report':True}

save(O/'SUMMARY.json',summary)
save(O/'SOURCE_HASHES.json',{p:sha(p) for p in sorted(sources)})
save(O/'OUTPUT_HASHES.json',{p.name:sha(p) for p in O.iterdir() if p.is_file() and p.name!='OUTPUT_HASHES.json'})
print(json.dumps(summary,ensure_ascii=False,indent=2))
