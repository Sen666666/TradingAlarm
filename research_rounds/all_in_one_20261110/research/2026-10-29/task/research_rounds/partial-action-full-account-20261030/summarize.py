"""Frozen-matrix reporting from completed ledgers only."""
import integrated as I
from collections import Counter,defaultdict
import time,gzip
O=I.O;pd=I.pd;D=I.D;t0=time.monotonic();summary=[];groups=[];operations=[];competition=[];unknown=[];acts=[];diffs=[]
def duration(ds):
 peak=1e6;peakday=pd.Timestamp(ds[0]['at']);count=0;episodes=[]
 for r in ds:
  day=pd.Timestamp(r['at']);v=float(r['nav'])
  if v>=peak:
   if count:episodes.append(dict(observations=count,calendar_days=(day-peakday).days,recovered=True))
   peak=v;peakday=day;count=0
  else:count+=1
 if count:episodes.append(dict(observations=count,calendar_days=(day-peakday).days,recovered=False))
 return dict(longest_underwater_observations=max([e['observations'] for e in episodes] or [0]),longest_underwater_calendar_days=max([e['calendar_days'] for e in episodes] or [0]),longest_completed_recovery_days=max([e['calendar_days'] for e in episodes if e['recovered']] or [0]),ongoing_underwater_days=episodes[-1]['calendar_days'] if episodes and not episodes[-1]['recovered'] else 0)
for sector,mode,ref in [('TECH','I',I.RR/'pvr-local-finite-capital-20261029/baseline'),('DRUG','ACT',I.RR/'innovative-drug-local-recovery-20261028/S0')]:
 root=O/sector/'on';assert I.W.read(root/'analysis/accounting.json')['passed'] and I.W.read(root/'analysis/funding.json')['passed'];assert I.W.read(O/sector/'prefix/IDENTITY.json')['passed'];base=pd.read_csv(ref/'analysis/summary.csv').set_index('account');new=pd.read_csv(root/'analysis/summary.csv');cs=pd.read_csv(root/'analysis/campaigns.csv',dtype={'net_pnl':str,'buy_gross':str,'buy_fees':str,'sell_fees':str});refcs=pd.read_csv(ref/'analysis/campaigns.csv');contrib=pd.read_csv(root/'analysis/contributions.csv',dtype={'market_value':str});newdaily=I.W.rows(root/'accounts-v2/daily.jsonl.gz');olddaily=I.W.rows(ref/'accounts-v2/daily.jsonl.gz');newdec=I.W.rows(root/'accounts-v2/decisions.jsonl.gz');olddec=I.W.rows(ref/'accounts-v2/decisions.jsonl.gz')
 for stress in ['base','cost2','delay1']:
  oldid=f'{mode}__S0_{stress}';ads=[d for d in olddaily if d['account']==oldid];aref=base.loc[oldid].to_dict();aref.update(sector=sector,policy='A',account=oldid,reference_reused=True,**duration(ads));summary.append(aref);tails=refcs[refcs.account.eq(oldid)&refcs.closed.eq(True)&refcs.tail_closed.eq(True)];window=set()
  for c in tails.itertuples():
   for d in ads:
    day=d['at'][:10]
    if c.entry_at[:10]<=day<c.exit_at[:10] and d['positions'].get(c.symbol,0)>0:window.add((day,c.symbol))
  for policy in ['B','L']:
   aid=f'{mode}__{policy}_S0_{stress}';row=new[new.account.eq(aid)].iloc[0].to_dict();row.update(sector=sector,policy=policy,reference_reused=False);ds=[d for d in newdaily if d['account']==aid];row.update(duration(ds));obj=I.W.read(root/'accounts-v2'/f'{aid}.json');row.update(delta_vs_ACT=row['net_profit']-aref['net_profit'],turnover_gross_cny=sum(float(f['gross_cny']) for f in obj['fills']),slippage_cny=sum(float(abs(D(r['price'])-D(r['raw_open']))*int(r['receipt']['shares'])) for r in obj['audit_log'] if r['kind']=='fill'),minimum_cash=float(min(D(d['available']) for d in ds)),holding_observation_days=sum(len(d['positions']) for d in ds));row['tail_reference_stockday_coverage']=sum((d['at'][:10],s) in window for d in ds for s in d['positions'])/len(window) if window else None;row['tail_reference_stockdays']=len(window)
   if policy=='L':assert row['minimum_cash']>=500000
   currentcs=cs[cs.account.eq(aid)];row['closed_gains']=float(sum((D(c.net_pnl) for c in currentcs.itertuples() if c.closed and D(c.net_pnl)>0),D(0)));row['negative_cycles']=sum(c.closed and D(c.net_pnl)<0 for c in currentcs.itertuples());row['mean_calendar_holding_days']=float((pd.to_datetime(currentcs.exit_at.fillna(ds[-1]['at']),utc=True)-pd.to_datetime(currentcs.entry_at,utc=True)).dt.total_seconds().mean()/86400)
   events=[];fees_bygroup=defaultdict(D);trims=Counter();restores=Counter();rolefills=Counter();restoreorders={r['order_id'] for r in obj['audit_log'] if r['kind']=='reserve' and r['purpose']=='risk_restore'};restorefills=[r for r in obj['audit_log'] if r['kind']=='fill' and r['order_id'] in restoreorders];counts=Counter()
   for idx,r in enumerate(obj['audit_log']):
    if r['kind']=='partial_event':
     e=r['detail'];counts[e['kind']]+=1
     if e['kind']=='restore_application':restores[e['group']]+=1
     if e['kind']=='risk_trim_request':trims[e['sid']]+=1
     if e['kind'] in ['actual_role_buy','actual_role_sell']:
      fees_bygroup[e['group']]+=D(e['receipt']['fees_cny']);rolefills[e['group']]+=1
     if e['kind']!='role_close':operations.append(dict(sector=sector,policy=policy,scenario=stress,account=aid,source_audit_row=idx,**e))
    elif r['kind']=='partial_admission':
     d=r['decisions'][-1];competition.append(dict(sector=sector,policy=policy,scenario=stress,account=aid,at=r['at'],source_audit_row=idx,accepted=r['accepted'],ledger_rejected=r['rejected'],admission_rejected=d['rejected'],waiting=d['waiting'],occupancy=r['occupancy']))
    elif r['kind']=='partial_input' and not(r['price_known'] and r['event_known'] and r['source_unit_known']):unknown.append(dict(sector=sector,policy=policy,scenario=stress,account=aid,at=r['at'],sid=r['sid'],group=r['group'],price_known=r['price_known'],event_known=r['event_known'],source_unit_known=r['source_unit_known']))
   riskfills=[e for e in operations if e['account']==aid and e['sector']==sector and e['kind']=='actual_role_sell' and e['action']=='risk_trim'];row.update(risk_trim_requests=counts['risk_trim_request'],risk_trim_fill_count=len(riskfills),risk_trim_shares=sum(e['receipt']['shares'] for e in riskfills),restore_applications=counts['restore_application'],restore_orders=len(restoreorders),restore_buy_fill_count=len(restorefills),restore_buy_shares=sum(r['receipt']['shares'] for r in restorefills),restore_orders_no_fill=len(restoreorders-{r['order_id'] for r in restorefills}),restore_order_target_shares=sum(r['target_shares'] for r in obj['audit_log'] if r['kind']=='reserve' and r['purpose']=='risk_restore'),unknown_position_days=sum(r['account']==aid and r['sector']==sector for r in unknown))
   if policy=='B':
    final=I.W.read(root/f'{aid}-role-final.json');cash={k:D(v) for k,v in final['group_cash'].items()};div={k:D(v) for k,v in final['group_dividend'].items()};mv=defaultdict(D);c=contrib[contrib.account.eq(aid)&contrib.date.eq(ds[-1]['at'][:10])].set_index('symbol')
    for sid,r in final['roles'].items():mv[r['group']]+=D(c.loc[sid,'market_value'])
    total=D(0)
    for gid in set(cash)|set(div)|set(mv):
     net=cash.get(gid,D(0))+div.get(gid,D(0))+mv[gid];total+=net;groups.append(dict(sector=sector,account=aid,scenario=stress,structure_id=gid,net_contribution=str(net),all_actual_fees=str(fees_bygroup[gid]),actual_fills=rolefills[gid],restore_applications=restores[gid],open_market_value=str(mv[gid])))
    assert abs(total-(D(ds[-1]['nav'])-D(1000000)))<D('1e-8'),(aid,'structure contribution mismatch')
   summary.append(row)
   risk=[dict(at=r['at'],event=r['event'],nav=r['nav'],episode=r['episode']) for r in obj['audit_log'] if r['kind']=='risk_checkpoint' and r['event']];acts.append(dict(sector=sector,account=aid,policy=policy,scenario=stress,events=risk))
   old={r['at']:r for r in olddec if r['account']==oldid};newd={r['at']:r for r in newdec if r['account']==aid};ad={r['at']:r for r in ads};dd={r['at']:r for r in ds}
   for at,r in newd.items():
    changed=[k for k in ['accepted','rejected','exits','occupancy'] if old[at][k]!=r[k]]
    if changed:diffs.append(dict(sector=sector,policy=policy,scenario=stress,at=at,fields=changed,old_accepted=old[at]['accepted'],new_accepted=r['accepted'],old_exits=old[at]['exits'],new_exits=r['exits'],old_positions=ad[at]['positions'],new_positions=dd[at]['positions'],old_cash=ad[at]['available'],new_cash=dd[at]['available'],delta_nav=str(D(dd[at]['nav'])-D(ad[at]['nav']))))
pd.DataFrame(summary).to_csv(O/'SUMMARY_18.csv',index=False);pd.DataFrame(groups).to_csv(O/'STRUCTURE_TRIALS.csv',index=False)
for name,data in [('ROLE_OPERATIONS',operations),('COMPETITION',competition),('UNKNOWN',unknown),('ACT_EVENTS',acts),('DIVERGENCE',diffs)]:
 with gzip.open(O/f'{name}.jsonl.gz','wt',compresslevel=1) as f:
  for r in data:f.write(I.json.dumps(r,ensure_ascii=False,default=str)+'\n')
p=O/'COMPUTE_TIME.json';b=I.W.read(p);s=time.monotonic()-t0;b['seconds']+=s;b['stages'].append(dict(stage='read_only_summary',status='complete',seconds=s));p.write_text(I.json.dumps(b,indent=2));(O/'SUMMARY_VERIFICATION.json').write_text(I.json.dumps(dict(passed=True,accounts=18,new_economic=12,structure_money_exact=True,baseline_off6_exact=True,prefix_group_runs=2,prefix_accounts=4,seconds=s),indent=2));print(pd.DataFrame(summary)[['sector','policy','scenario','net_return','max_drawdown','mean_exposure','fees','tail_profit','all_closed_losses']].to_string(index=False))
