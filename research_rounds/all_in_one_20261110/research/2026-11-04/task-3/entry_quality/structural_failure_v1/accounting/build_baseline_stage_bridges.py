"""Baseline native snapshots only. Reuse sealed, audited period reader unchanged.

Calendar partition is additive; requested overlapping views are separate.
Campaigns are unions of actual holding intervals, never strategy simulation.
"""
from pathlib import Path
from collections import defaultdict,Counter
from decimal import Decimal as D,getcontext
import importlib.util,sys,json,hashlib,csv,argparse
getcontext().prec=65
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent;E=HERE.parents[1];H=E/'dec2022_authorization_v1';P=H/'account_comparison/results_v1';OUT=HERE/'results_v1';Z=D(0)
READER=H/'followup_robustness_v1/performance/analyze_performance.py'
spec=importlib.util.spec_from_file_location('readonly_sealed_baseline_stage_reader',READER);M=importlib.util.module_from_spec(spec);spec.loader.exec_module(M)
PART=[('P01_2022H1','2022-01-01','2022-06-30'),('P02_2022JulNov','2022-07-01','2022-11-30'),('P03_Dec2022','2022-12-01','2022-12-31'),('P04_2023JanApr','2023-01-01','2023-04-30'),('P05_2023MayJul','2023-05-01','2023-07-31'),('P06_2023Aug_2024Jan','2023-08-01','2024-01-31'),('P07_2024FebMay','2024-02-01','2024-05-31'),('P08_2024Jun_Sep23','2024-06-01','2024-09-23'),('P09_2024Sep24_Oct8','2024-09-24','2024-10-08'),('P10_after2024Oct8','2024-10-09','2024-12-31')]
VIEWS=[('FULL_2022_2024','2022-01-01','2024-12-31'),('YEAR2022','2022-01-01','2022-12-31'),('YEAR2023','2023-01-01','2023-12-31'),('YEAR2024','2024-01-01','2024-12-31'),('VIEW_2022H2','2022-07-01','2022-12-31'),('VIEW_ACTpause2022_to_resume','2022-04-20','2022-06-17'),('VIEW_ACTpause2023_to_resume2024','2023-07-20','2024-05-06'),('VIEW_from924_to_yearend','2024-09-24','2024-12-31')]
def save(n,v):
 with (OUT/n).open('x') as f:json.dump(v,f,ensure_ascii=False,indent=2,default=str);f.write('\n')
def eq(a,b,k):M.eq(a,b,k)
def sums(rr):return dict(layers=len(rr),stocks=len({r['sid'] for r in rr}),actual_buycash=sum((D(r['cost']) for r in rr),Z),strict_realized=sum((D(r['strict_realized']) for r in rr),Z),open_unrealized=sum((D(r['open_unrealized']) for r in rr),Z),AR=sum((D(r['AR']) for r in rr),Z),endpoint_net=sum((D(r['net']) for r in rr),Z))
def campaigns(r):
 bystock=defaultdict(list);out=[]
 for x in r['layers']:bystock[x['sid']].append(x)
 for sid,ll in bystock.items():
  group=[];end=None;ordinal=0
  def flush(g):
   nonlocal ordinal
   if not g:return
   ordinal+=1;closed=all(x['closed'] is not None for x in g);opened=min(x['opened'] for x in g)
   out.append(dict(campaign_id=r['win']+'|'+sid+'|'+str(ordinal)+'|'+opened,window=r['win'],sid=sid,name=M.META_ROWS[sid]['name'],industry=M.META_ROWS[sid]['industry'],sector=M.META_ROWS[sid]['sector_id'],opened=opened,closed=max(x['closed'] for x in g) if closed else None,layer_ids=[x['layer_in_this_book'] for x in g],entry_keys=[x['key'] for x in g],by_action=dict(Counter(x['actual_entry_action'] for x in g)),by_role=dict(Counter(x['role'] for x in g)),**sums(g)))
  for x in sorted(ll,key=lambda x:(x['opened'],x['layer_in_this_book'])):
   if group and end is not None and end<=x['opened']:flush(group);group=[]
   group.append(x);end=None if any(y['closed'] is None for y in group) else max(y['closed'] for y in group)
  flush(group)
 return out
def enrich_campaigns(r,cc,details):
 bylayer={lid:c for c in cc for lid in c['layer_ids']};buy={t['layer']:t for t in r['book']['trades'] if t['side']=='buy'};fees=defaultdict(lambda:Z);exitstats=defaultdict(lambda:defaultdict(lambda:dict(parts=0,shares=0,net_cash=Z,strict_realized=Z,allocated_sell_fee=Z)))
 for lid,t in buy.items():fees[lid]+=D(t['fees_cny'])
 sellfees={}
 for t in r['book']['trades']:
  if t['side']!='sell':continue
  allocations=[]
  for p in t['parts']:
   fee=D(t['price'])*D(p['shares'])-D(p['net_cash']);sellfees[p['layer'],t['at']]=fee;fees[p['layer']]+=fee;allocations.append(fee)
  eq(sum(allocations,Z),t['fees_cny'],'native part fee allocations')
 for p in r['parts']:
  c=bylayer[p['lid']];v=exitstats[c['campaign_id']][p['reason']];v['parts']+=1;v['shares']+=p['shares'];v['net_cash']+=p['net_cash'];v['strict_realized']+=p['strict_realized'];v['allocated_sell_fee']+=sellfees[p['lid'],p['at']]
 stage_layer={label:{x['lid']:x for x in d['layer_rows']} for label,d in details.items()}
 for c in cc:
  ids=set(c['layer_ids']);c['actual_fees']=sum((fees[lid] for lid in ids),Z);c['actual_exit_parts_by_reason']=dict(exitstats[c['campaign_id']]);c['stage_wealth']={}
  for label,rows in stage_layer.items():
   rr=[rows[lid] for lid in ids if lid in rows];c['stage_wealth'][label]=dict(wealth=sum((x['wealth'] for x in rr),Z),real=sum((x['real'] for x in rr),Z),unreal=sum((x['unreal'] for x in rr),Z),AR=sum((x['AR'] for x in rr),Z),actual_new_buycash=sum((x['actual_new_buycash'] for x in rr),Z))
  peaks=dict(mark=None,basis=None,held_close_unreal=None,known_recognized_wealth=None);peakdates={};points=[]
  for i,d in enumerate(r['daily']):
   held=ids&r['caps'][i].keys()
   if not held:continue
   mark=sum((r['caps'][i][lid]['mark'] for lid in held),Z);basis=sum((r['caps'][i][lid]['basis'] for lid in held),Z)
   state=[r['components'][i][lid] for lid in ids if lid in r['components'][i]];real=sum((x['real'] for x in state),Z);ar=sum((x['AR'] for x in state),Z);wealth=sum((x['wealth'] for x in state),Z)
   point=dict(day=d['day'],mark=mark,basis=basis,held_close_unreal=mark-basis,known_recognized_wealth=wealth,known_realized=real,known_AR=ar,mark_over_account_NAV=mark/D(d['NAV']),ACT_on=d['ACT_on'])
   for k in peaks:
    if peaks[k] is None or point[k]>peaks[k]:peaks[k]=point[k];peakdates[k]=d['day']
   points.append(point)
  c['holding_CLOSE_points']=len(points);c['peaks_on_actual_held_CLOSE_only']=dict(values=peaks,days=peakdates)
  c['maximum_mark_share_of_account_NAV']=max((x['mark_over_account_NAV'] for x in points),default=None)
  c['known_recognized_peak_to_endpoint_change']=None if peaks['known_recognized_wealth'] is None else c['endpoint_net']-peaks['known_recognized_wealth']
  c['peak_is_not_executable_counterfactual']=True;c['ACT_exit_part_count']=exitstats[c['campaign_id']].get('ACT_pause',{}).get('parts',0)
  c['capitaltime_previous_CLOSE_mark_yuan_observations']=sum((sum((r['caps'][i-1][lid]['mark'] for lid in ids&r['caps'][i-1].keys()),Z) for i in range(1,len(r['daily']))),Z)
 return cc
def act_episodes(r):
 raw=r['raw'];book=r['book'];risk=[x for x in book['audit'] if x['kind']=='risk_checkpoint' and x.get('event')];episodes=[];decisions={x['at'][:10]:x for x in book['decisions']}
 for event in risk:
  if event['event']!='pause':continue
  resume=next((x for x in risk if x['event']=='resume' and x['at']>event['at']),None);start=event['at'][:10];end=resume['at'][:10] if resume else raw[-1]['at'][:10]
  days=[x for x in raw if start<=x['at'][:10]<=end];paused=[x for x in days if not x['on']];flat=[x for x in paused if not x['layers']];firstflat=next((x for x in days if not x['layers']),None)
  postsales=[p for p in r['parts'] if start<=p['at'][:10]<=end];paused_fills=[t for t in book['trades'] if t['side']=='buy' and t['at'][:10] in {d['at'][:10] for d in paused}]
  episodes.append(dict(pause_request=event,resume_close=resume,paused_CLOSE_observations=len(paused),paused_flat_CLOSE_observations=len(flat),paused_held_CLOSE_observations=len(paused)-len(flat),first_flat_CLOSE=None if firstflat is None else firstflat['at'],first_flat_NAV=None if firstflat is None else firstflat['nav'],last_prior_resume_NAV=paused[-1]['nav'],
   pause_CLOSE_to_first_flat_wealth=None if firstflat is None else D(firstflat['nav'])-D(event['nav']),first_flat_to_last_paused_wealth=None if firstflat is None else D(paused[-1]['nav'])-D(firstflat['nav']),
   recorded_paused_native_intents=sum(len(decisions[d['at'][:10]]['intents']) for d in paused),actual_buy_fills_on_days_ending_paused=len(paused_fills),actual_buy_signal_clocks_on_these_days=[t['signal_at'] for t in paused_fills],
   actual_exit_parts_within_interval=len(postsales),actual_exit_realized=sum((x['strict_realized'] for x in postsales),Z),
   unexecuted_native_fundable_signal_set='NOT_RECORDED_BECAUSE_NATIVE_ACT_GUARD_SHORT_CIRCUITS_PLANNING',foregone_profit='NOT_IDENTIFIED',limitation='Flat paused observations and observed market appreciation are not actual fundable original signals or causal opportunity costs. Do not replace missing eligible-intent counterfactual by broad-market gains.'))
 return episodes

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,default=OUT);args=parser.parse_args();OUT=args.out
 assert not OUT.exists();OUT.mkdir(parents=True)
 M.META_ROWS=M.read(M.META);M.MANIFEST={x['symbol']:x for x in M.read(M.W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json')};M.VALID=M.read(P/'VALIDATION.json');M.SECTOR_NAMES={x['sector_id']:x['industry'] for x in M.META_ROWS.values()}
 semi=M.read(H/'followup_robustness_v1/performance/SEMICONDUCTOR_COHORT_FREEZE.json');M.SEMIBY={x['sid']:x for x in semi['all_metadata_members'] if x['in_frozen1709']}
 allrows=[];checks=[];camp_summaries={}
 try:
  for win in ['2022_2024','strong']:
   r=M.load('BASELINE',win);details={};metrics=[];allcc=campaigns(r)
   save(win+'_CAMPAIGN_PRELIMINARY_ALL.json',sorted(allcc,key=lambda x:x['endpoint_net']))
   specperiods=PART+VIEWS if win=='2022_2024' else [('STRONG_2025Jul_2026Jun','2025-07-01','2026-06-30')]
   for label,start,end in specperiods:
    m,d=M.period(r,label,start,end);m['is_disjoint_partition_member']=label.startswith('P');m['is_overlapping_observation_view']=label.startswith('VIEW') or label.startswith('YEAR') or label.startswith('FULL');metrics.append(m);details[label]=d;save(win+'_'+label+'_DETAIL.json',d)
   if win=='2022_2024':
    partition=[x for x in metrics if x['is_disjoint_partition_member']];assert sum(x['observations'] for x in partition)==726
    for field in ['net_wealth_change','strict_realized_change','open_unrealized_change','AR_change','fees','buy_gross','sell_gross','actual_buycash','actual_sell_net']:
     eq(sum((x[field] for x in partition),Z),next(x[field] for x in metrics if x['period']=='FULL_2022_2024'),'disjoint partition '+field)
    save('ACTUAL_ACT_EPISODES.json',act_episodes(r))
   allcc=enrich_campaigns(r,allcc,details);eq(sum((c['endpoint_net'] for c in allcc),Z),D(r['daily'][-1]['NAV'])-1000000,'all campaign wealth');eq(sum((c['actual_fees'] for c in allcc),Z),sum((D(t['fees_cny']) for t in r['book']['trades']),Z),'all campaign fees')
   if win=='2022_2024':
    cycles=M.read(E/'failure_no_progress/timeline/2022_2024_COMPLETED_STOCK_CYCLES.json');known={frozenset(x['layer_ids']):x for arr in cycles.values() for x in arr};assert len(known)==len(allcc)
    for c in allcc:eq(c['strict_realized'],known[frozenset(c['layer_ids'])]['net_trade_cash'],'old completed campaign cash');eq(c['AR'],known[frozenset(c['layer_ids'])]['recognized_dividend_AR'],'old campaign AR')
   for m in metrics:
    eq(sum((c['stage_wealth'][m['period']]['wealth'] for c in allcc),Z),m['net_wealth_change'],'campaign stage wealth')
    selected=[d for d in r['daily'] if m['start']<=d['day']<=m['end']];m['ACT_on_CLOSE_observations']=sum(d['ACT_on'] for d in selected);m['ACT_paused_flat_CLOSE_observations']=sum(not d['ACT_on'] and d['held_layers']==0 for d in selected);m['ACT_paused_held_CLOSE_observations']=sum(not d['ACT_on'] and d['held_layers']>0 for d in selected)
   save(win+'_CAMPAIGNS_FULL_ACCOUNTING.json',sorted(allcc,key=lambda x:x['endpoint_net']));save(win+'_TOP_CAMPAIGN_CANDIDATES.json',dict(selection='Descriptive endpoints and each fixed stage; not final representative10 selection or decision signal',most_negative=sorted(allcc,key=lambda x:x['endpoint_net'])[:20],most_positive=sorted(allcc,key=lambda x:x['endpoint_net'],reverse=True)[:10],most_negative_by_stage={m['period']:sorted(allcc,key=lambda c:c['stage_wealth'][m['period']]['wealth'])[:10] for m in metrics},profit_then_giveback=sorted([c for c in allcc if c['peaks_on_actual_held_CLOSE_only']['values']['known_recognized_wealth'] is not None and c['peaks_on_actual_held_CLOSE_only']['values']['known_recognized_wealth']>0],key=lambda c:c['known_recognized_peak_to_endpoint_change'])[:10]))
   allrows+=metrics;checks.append(dict(window=win,original_layers=len(r['layers']),native_CLOSEs=len(r['daily']),campaigns=len(allcc),maximum_daily_residual=r['maxres'],campaign_stage_cash_AR_fee_closures=True,original_baseline=True,new_accounts=0));print('FINISHED',win,len(allcc),'campaigns',flush=True)
  save('STAGE_WEALTH_CAPITAL_MATRIX.json',allrows)
  fields=[k for k,v in allrows[0].items() if not isinstance(v,dict)]
  with (OUT/'STAGE_WEALTH_CAPITAL_MATRIX.csv').open('x',newline='') as f:w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(allrows)
  save('VALIDATION.json',dict(status='PASS_BASELINE_ONLY_STAGE_AND_CAMPAIGN_BRIDGES',checks=checks,disjoint_three_year_partition_observations=726,overlapping_views_not_additive=True,cause_groups_are_overlapping_not_additive=True,new_accounts=0,new_account_events=0,financial_reader_imported_read_only=str(READER)))
 except BaseException as e:save('FAILURE.json',dict(error=repr(e),preserve=True,new_accounts=0));raise
 finally:
  M.SRC[str(Path(__file__).resolve())]=M.sha(__file__);M.SRC[str(READER)]=M.sha(READER);save('SOURCE_SHA256.json',M.SRC);save('DELIVERABLE_SHA256.json',{str(p.resolve()):M.sha(p) for p in OUT.iterdir() if p.is_file() and p.name!='DELIVERABLE_SHA256.json'})
