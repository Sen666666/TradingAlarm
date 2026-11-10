"""Read completed account/audit results only; no signal or strategy execution."""
import wire as w
from collections import defaultdict,Counter
import time
O=w.O;D=w.D;pd=w.pd;t0=time.monotonic();summary=[];divergence=[];structures=[];cycles=[];competition=[];lifecycle=[];unknown=[];stages=[]
def duration(ds):
 peak=1e6;peakday=pd.Timestamp(ds[0]['at']);start=None;count=0;episodes=[]
 for r in ds:
  day=pd.Timestamp(r['at']);v=float(r['nav'])
  if v>=peak:
   if start is not None:episodes.append(dict(observations=count,calendar_days=(day-peakday).days,recovered=True,peak_date=str(peakday.date()),end=str(day.date())))
   peak=v;peakday=day;start=None;count=0
  else:
   if start is None:start=day
   count+=1
 if start is not None:episodes.append(dict(observations=count,calendar_days=(day-peakday).days,recovered=False,peak_date=str(peakday.date()),end=str(day.date())))
 return dict(longest_underwater_observations=max([e['observations'] for e in episodes] or [0]),longest_underwater_calendar_days=max([e['calendar_days'] for e in episodes] or [0]),longest_completed_recovery_calendar_days=max([e['calendar_days'] for e in episodes if e['recovered']] or [0]),ongoing_underwater_calendar_days=episodes[-1]['calendar_days'] if episodes and not episodes[-1]['recovered'] else 0,drawdown_episodes=episodes)
for sector,ref in [('TECH',w.RR/'pvr-local-finite-capital-20261029/baseline'),('DRUG',w.RR/'innovative-drug-local-recovery-20261028/S0')]:
 root=O/sector/'on';assert w.read(root/'analysis/accounting.json')['passed'] and w.read(root/'analysis/funding.json')['passed'];assert w.read(O/sector/'prefix/IDENTITY.json')['passed']
 mode='I' if sector=='TECH' else 'ACT';base={r['account']:r for r in pd.read_csv(ref/'analysis/summary.csv').to_dict('records')};new={r['account']:r for r in pd.read_csv(root/'analysis/summary.csv').to_dict('records')};old_daily=w.rows(ref/'accounts-v2/daily.jsonl.gz');new_daily=w.rows(root/'accounts-v2/daily.jsonl.gz');old_dec=w.rows(ref/'accounts-v2/decisions.jsonl.gz');new_dec=w.rows(root/'accounts-v2/decisions.jsonl.gz');cs=pd.read_csv(root/'analysis/campaigns.csv',dtype={'net_pnl':str,'buy_gross':str,'buy_fees':str,'sell_fees':str,'dividends':str})
 for stress in ['base','cost2','delay1']:
  aid=f'{mode}__S0_{stress}';obj=w.read(root/'accounts-v2'/f'{aid}.json');a=w.read(ref/'accounts-v2'/f'{aid}.json');ds=[r for r in new_daily if r['account']==aid];ads=[r for r in old_daily if r['account']==aid];row=new[aid];row.update(sector=sector,policy_label='ACT+RB2',baseline_referenced=False,**{k:v for k,v in duration(ds).items() if k!='drawdown_episodes'});row['turnover_gross_cny']=sum(float(f['gross_cny']) for f in obj['fills']);row['turnover_over_initial']=row['turnover_gross_cny']/1e6;row['slippage_cny']=sum(float(abs(D(r['price'])-D(r['raw_open']))*int(r['receipt']['shares'])) for r in obj['audit_log'] if r['kind']=='fill');row['gain_closed']=float(sum((D(c.net_pnl) for c in cs[cs.account.eq(aid)].itertuples() if c.closed and D(c.net_pnl)>0),D(0)));row['delta_net_cny']=row['net_profit']-base[aid]['net_profit'];summary.append(row)
  b=dict(base[aid]);b.update(sector=sector,policy_label='ACT',baseline_referenced=True,**{k:v for k,v in duration(ads).items() if k!='drawdown_episodes'});b['turnover_gross_cny']=sum(float(f['gross_cny']) for f in a['fills']);b['turnover_over_initial']=b['turnover_gross_cny']/1e6;b['slippage_cny']=sum(float(abs(D(r['price'])-D(r['raw_open']))*int(r['receipt']['shares'])) for r in a['audit_log'] if r['kind']=='fill');summary.append(b)
  stageevents=[dict(at=r['at'],event=r['event'],nav=r['nav'],episode=r['episode']) for r in obj['audit_log'] if r['kind']=='risk_checkpoint' and r['event']];oldstage=[dict(at=r['at'],event=r['event'],nav=r['nav'],episode=r['episode']) for r in a['audit_log'] if r['kind']=='risk_checkpoint' and r['event']];stages.append(dict(sector=sector,scenario=stress,challenger=stageevents,baseline=oldstage,drawdown=duration(ds)))
  starts={};lastends={};req={};notes=Counter();same_reentry=0;risk_same_reentry=0;rawunknown=Counter();riskflat=[]
  for i,r in enumerate(obj['audit_log']):
   k=r['kind']
   if k=='rb_start':
    starts[(r['sid'],r['at'])]=r;prev=lastends.get(r['sid']);same=bool(prev and prev['context']['structure_id']==r['context']['structure_id']);same_reentry+=same;risk_same_reentry+=bool(same and prev['reason']=='risk_boundary')
    lifecycle.append(dict(sector=sector,scenario=stress,kind='actual_start',symbol=r['sid'],at=r['at'],cycle_id=r['cycle_id'],structure_id=r['context']['structure_id'],previous_exit_reason=prev['reason'] if prev else None,same_structure_reentry=same,shares=r['shares']))
   elif k=='rb_end':lastends[r['sid']]=r;riskflat.append(r) if r['reason']=='risk_boundary' else None
   elif k=='rb_checkpoint':
    notes[r['note']]+=1
    if r['exit_reason']=='risk_boundary' and r['cycle_id'] not in req:req[r['cycle_id']]=r
    if r['current_unknown']:
     unknown.append(dict(sector=sector,scenario=stress,symbol=r['sid'],at=r['at'],cycle_id=r['cycle_id'],issues=r['current_unknown']));rawunknown.update(r['current_unknown'])
   elif k=='rb_admission':
    last=r['decisions'][-1];competition.append(dict(sector=sector,scenario=stress,at=r['at'],available=r['before']['available'],reserved=r['before']['order_reserved'],nav=r['before']['nav'],accepted=r['accepted'],cash_rejected=r['rejected'],admission_rejected=last['rejected'],qtrue=[e['security_id'] for e in last['eligibility'] if e['q'] is True],waiting=last['waiting'],occupancy=r['occupancy'],audit_row=i))
  row.update(risk_requests=len(req),risk_completed=len(riskflat),safe_handoffs=notes['safe_handoff_return_to_observation'],same_structure_actual_reentries=same_reentry,risk_exit_same_structure_actual_reentries=risk_same_reentry,unknown_rows=sum(x['sector']==sector and x['scenario']==stress for x in unknown),unknown_cycles=len({x['cycle_id'] for x in unknown if x['sector']==sector and x['scenario']==stress}),unknown_types=dict(rawunknown),position_observation_days=sum(len(r['positions']) for r in ds),mean_calendar_holding_days=float((pd.to_datetime(cs.loc[cs.account.eq(aid),'exit_at'].fillna(ds[-1]['at']),utc=True)-pd.to_datetime(cs.loc[cs.account.eq(aid),'entry_at'],utc=True)).dt.total_seconds().mean()/86400))
  grouped=defaultdict(list)
  for c in cs[cs.account.eq(aid)].to_dict('records'):
   s=starts.get((c['symbol'],c['entry_at']));assert s,(sector,aid,c['symbol'],c['entry_at'],'missing unique start');key=s['context']['structure_id'] or 'UNKNOWN_STRUCTURE';c.update(sector=sector,cycle_id=s['cycle_id'],structure_id=key,risk_exit_requested=s['cycle_id'] in req);cycles.append(c);grouped[key].append(c)
  total=D(0)
  for key,g in grouped.items():
   pnl=sum((D(c['net_pnl']) for c in g),D(0));total+=pnl;structures.append(dict(sector=sector,scenario=stress,structure_id=key,symbol=g[0]['symbol'],cycles=len(g),risk_exits=sum(c['risk_exit_requested'] for c in g),net_pnl=str(pnl),all_negative_cycles=str(-sum((D(c['net_pnl']) for c in g if D(c['net_pnl'])<0),D(0))),buy_fees=str(sum((D(c['buy_fees']) for c in g),D(0))),sell_fees=str(sum((D(c['sell_fees']) for c in g),D(0))),open_cycles=sum(not c['closed'] for c in g)))
  assert abs(total-(D(ds[-1]['nav'])-D(1000000)))<D('1e-8')
  od={r['at']:r for r in old_dec if r['account']==aid};nd={r['at']:r for r in new_dec if r['account']==aid};oldd={r['at']:r for r in ads};newd={r['at']:r for r in ds};first=None
  for at,r in nd.items():
   old=od[at];fields=[k for k in ['accepted','rejected','selected','exits','eligible','occupancy'] if r[k]!=old[k]]
   if fields:
    if first is None:first=at
    divergence.append(dict(sector=sector,scenario=stress,at=at,fields=fields,old_accepted=old['accepted'],new_accepted=r['accepted'],old_exits=old['exits'],new_exits=r['exits'],old_rejected=old['rejected'],new_rejected=r['rejected'],old_positions=oldd[at]['positions'],new_positions=newd[at]['positions'],old_available=oldd[at]['available'],new_available=newd[at]['available'],delta_nav=str(D(newd[at]['nav'])-D(oldd[at]['nav']))))
  row['first_decision_divergence']=first;row['decision_divergence_days']=sum(r['sector']==sector and r['scenario']==stress for r in divergence)
pd.DataFrame(summary).to_csv(O/'SUMMARY_12.csv',index=False);pd.DataFrame(structures).to_csv(O/'STRUCTURE_TRIALS.csv',index=False);pd.DataFrame(cycles).to_csv(O/'CHALLENGER_CYCLES.csv',index=False)
for name,data in [('DIVERGENCE',divergence),('COMPETITION',competition),('LIFECYCLE',lifecycle),('UNKNOWN',unknown),('ACT_AND_DRAWDOWN',stages)]:
 with w.gzip.open(O/f'{name}.jsonl.gz','wt',compresslevel=1) as f:
  for r in data:f.write(w.json.dumps(r,ensure_ascii=False,default=str)+'\n')
seconds=time.monotonic()-t0;record=w.read(O/'COMPUTE_TIME.json');record['seconds']+=seconds;record['stages'].append(dict(stage='read_only_summary',seconds=seconds,status='complete'));(O/'COMPUTE_TIME.json').write_text(w.json.dumps(record,indent=2));(O/'SUMMARY_VALIDATION.json').write_text(w.json.dumps(dict(passed=True,structure_cycle_money_exact=True,mother_accounts=6,identity_six=True,prefix_two=True,seconds=seconds),indent=2));print(pd.DataFrame(summary)[['sector','policy_label','scenario','net_return','max_drawdown','fees','tail_profit','all_closed_losses','delta_net_cny','risk_requests','same_structure_actual_reentries']].to_string(index=False))
