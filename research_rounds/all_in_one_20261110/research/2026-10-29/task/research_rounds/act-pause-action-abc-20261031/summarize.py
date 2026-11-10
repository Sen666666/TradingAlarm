import adapter as m
from pathlib import Path
from collections import defaultdict,Counter
from decimal import Decimal as D
from datetime import datetime
import csv,json,gzip,time,pandas as pd
w=m.w;O=m.O;Z=D(0);T=time.monotonic()
def rows(p):return list(csv.DictReader(Path(p).open()))
def gz(p):
 with gzip.open(p,'rt') as f:return [json.loads(x) for x in f]
def save(p,x):w.K.save(p,x)
def export(p,x):w.K.export(p,x)
def dt(s):return datetime.fromisoformat(s)
def recovery(ds):
 peak=D(1000000);peakday=dt(ds[0]['at']);under=trough=None;low=None;longest=completed=0
 for d in ds:
  t=dt(d['at']);n=D(d['nav'])
  if n>=peak:
   if under is not None:longest=max(longest,(t-under).days);completed=max(completed,(t-trough).days)
   peak=n;peakday=t;under=trough=None;low=None
  else:
   if under is None:under=peakday;trough=t;low=n
   if n<low:trough=t;low=n
 current=(dt(ds[-1]['at'])-under).days if under else 0
 return dict(longest_underwater_calendar_days=max(longest,current),longest_completed_trough_recovery_days=completed,current_underwater_calendar_days=current,current_unrecovered=under is not None)
def states(logs):
 q=defaultdict(int);buys=set();sells=set();out={}
 for x in logs:
  k=x['kind']
  if k=='reserve':buys.add(x['sid'])
  elif k=='release_buy':buys.discard(x['sid'])
  elif k=='exit_request':sells.add(x['sid'])
  elif k=='fill':
   f=x['receipt'];s=f['security_id'];q[s]+=f['shares'] if f['side']=='buy' else -f['shares']
   if not q[s]:sells.discard(s)
  elif k.startswith('split') and k in ['split','split_fraction_floor_proxy']:q[x['sid']]=int(D(q[x['sid']])*D(x['ratio']))
  elif k=='risk_checkpoint':
   held={s:n for s,n in q.items() if n};flat=not held and not buys and not sells;assert flat==x['flat'];out[x['at']]=dict(held=held,buys=tuple(sorted(buys)),sells=tuple(sorted(sells)),flat=flat,no_orders=not buys and not sells)
  elif k=='act_checkpoint':
   st=out[x['at']];assert st['held']==x['held'] and set(st['buys'])==set(x['buy_orders']) and set(st['sells'])==set(x['sell_orders']) and st['no_orders']==x['no_orders']
 return out

matrix=[];waiting=[];episodes=[];kept=[];post=[];snapshot=[];bridges=[];stockdiff=[];unknown=[];factcache={};waitingchecks=[];all_events=[]
for sec in ['TECH','DRUG']:
 for stage in ['off','on','prefix']:assert w.read(O/sec/stage/'TIMING.json')['status']=='complete'
 for stage in ['off','prefix']:assert w.read(O/sec/stage/'IDENTITY.json')['passed']
 for gate in ['accounting','funding']:assert w.read(O/sec/f'on/analysis/{gate}.json')['passed']
 assert w.read(O/sec/'on/POLICY_GATE.json')['passed']
 ref=w.RR/('pvr-local-finite-capital-20261029/baseline' if sec=='TECH' else 'innovative-drug-local-recovery-20261028/S0');mode='I' if sec=='TECH' else 'ACT';prep=Path(w.read(w.RR/'pvr-act-comparison-20261027/input.json')['snapshot']['path']) if sec=='TECH' else w.RR/'innovative-drug-sfw3-20261028/prepared';base_stocks={};base_net={}
 def native(s,t):
  key=(sec,s)
  if key not in factcache:factcache[key]=pd.read_parquet(prep/'facts'/f'{s}.parquet')
  f=factcache[key];j=f.index.searchsorted(pd.Timestamp(t[:10]),side='right')-1
  if j<0:return None,None
  r=f.iloc[j];return (None if pd.isna(r.i_target) or not bool(r.e0_ready) else bool(r.i_target),None if pd.isna(r.e0_target) or not bool(r.e0_ready) else bool(r.e0_target))
 for policy,root in [('A',ref),('B',O/sec/'on'),('C',O/sec/'on')]:
  summaries=rows(root/'analysis/summary.csv');caps=rows(root/'analysis/campaigns.csv');contrib=rows(root/'analysis/contributions.csv');dsall=gz(root/'accounts-v2/daily.jsonl.gz');deall=gz(root/'accounts-v2/decisions.jsonl.gz')
  for stress in ['base','cost2','delay1']:
   aid=f'{mode}__S0_{stress}' if policy=='A' else f'{mode}__{policy}_S0_{stress}';obj=w.read(root/'accounts-v2'/f'{aid}.json');logs=obj['audit_log'];ds=[d for d in dsall if d['account']==aid];de={r['at']:r for r in deall if r['account']==aid};risk=[r for r in logs if r['kind']=='risk_checkpoint'];st=states(logs);act={x['at']:x for x in logs if x['kind']=='act_checkpoint'};cc=[x for x in caps if x['account']==aid];ct=[x for x in contrib if x['account']==aid];cmap=defaultdict(list)
   for x in ct:cmap[x['symbol']].append(x)
   ss=defaultdict(lambda:Z)
   for c in cc:ss[c['symbol']]+=D(c['net_pnl'])
   exact_net=D(ds[-1]['nav'])-1000000;assert abs(sum(ss.values(),Z)-exact_net)<D('.00000001')
   if policy=='A':base_stocks[stress]=dict(ss);base_net[stress]=exact_net
   else:
    dif={s:ss.get(s,Z)-base_stocks[stress].get(s,Z) for s in set(ss)|set(base_stocks[stress])};expected=exact_net-base_net[stress];assert abs(sum(dif.values(),Z)-expected)<D('.00000001');bridges.append(dict(sector=sec,account=aid,delta=expected,stock_difference_sum=sum(dif.values(),Z),residual=sum(dif.values(),Z)-expected));stockdiff.extend(dict(sector=sec,account=aid,policy=policy,pressure=stress,symbol=s,difference=v) for s,v in sorted(dif.items(),key=lambda x:-abs(x[1])))
   combos=Counter();prim=Counter();masks=Counter();laston=True;current=None;seen=set();valid_events=0;kept_start=len(kept);post_start=len(post)
   for j,r in enumerate(risk):
    t=r['at'];z=st[t];event=r['event'];on=r['on'];iswaiting=not laston and not on
    if iswaiting:
     blockers=[]
     if not z['no_orders']:blockers.append('orders')
     if policy!='C' and z['held']:blockers.append('flat')
     if not r['breakout']:blockers.append('market')
     assert blockers;combos['+'.join(blockers)]+=1;prim[blockers[0]]+=1
     for b in blockers:masks[b]+=1
    if event=='pause':
     current=dict(sector=sec,account=aid,policy=policy,pressure=stress,pause_at=t,pause_NAV=r['nav'],peak=r['peak'],held=z['held'],resume_at=None,paused_observations=0,first_unpaused_after=None)
     for s,n in z['held'].items():
      iv,ev=native(s,t)
      if policy!='A':
       snap=next(x for x in logs if x['kind']=='act_pause_holdings' and x['at']==t);iv=snap['original_I'][s];ev=snap['original_E0'][s]
      if iv is not True or ev is not True or s in z['sells']:continue
      valid_events+=1;cs=[c for c in cc if c['symbol']==s and dt(c['entry_at'])<=dt(t) and(c['closed']!='True' or dt(c['exit_at'])>dt(t))];assert len(cs)==1,(aid,t,s,'cycle link');c=cs[0];key=(s,c['entry_at'])
      if key in seen:continue
      seen.add(key);end=c['exit_at'][:10] if c['closed']=='True' else ds[-1]['at'][:10];pnl=sum((D(v['net_contribution']) for v in cmap[s] if t[:10]<v['date']<=end),Z);kept.append(dict(sector=sec,account=aid,policy=policy,pressure=stress,symbol=s,name=c['name'],entry_at=c['entry_at'],first_pause=t,end_at=c['exit_at'] if c['closed']=='True' else ds[-1]['at'],closed=c['closed'],shares_at_pause=n,subsequent_actual_stock_contribution=pnl,whole_cycle_net=c['net_pnl'],window='after_pause_close_to_actual_same_cycle_exit_or_cutoff',is_ACT_forced_sale=policy=='A'))
     episodes.append(current)
    if current is not None and not on:current['paused_observations']+=1
    if event=='resume':
     assert current is not None;current['resume_at']=t;current['first_unpaused_after']=t;current['NAV_at_resume']=r['nav'];current['held_at_resume']=z['held'];current['nonempty_resume']=bool(z['held']);current=None
    if event is not None:all_events.append(dict(r,sector=sec,account=aid,policy=policy,pressure=stress,held=z['held'],orders=dict(buys=z['buys'],sells=z['sells'])))
    if t[:10] in (['2024-09-25','2024-09-26','2024-09-27','2025-01-02','2025-04-01'] if sec=='DRUG' else ['2024-12-31','2025-02-10','2025-10-20','2025-11-20','2026-01-05']):snapshot.append(dict(sector=sec,account=aid,policy=policy,pressure=stress,risk=r,held=z['held'],orders=dict(buys=z['buys'],sells=z['sells']),accepted=de[t]['accepted'],actual_rejected=de[t]['rejected'],occupancy=de[t]['occupancy']))
    laston=on
   # Entry decision belongs to its actual active phase; old holdings at C resume are excluded.
   contracts={x['order_id']:x for x in logs if x['kind']=='entry_contract'};firstbuy={(x['receipt']['security_id'],x['receipt']['at']):x for x in logs if x['kind']=='fill' and x['receipt']['side']=='buy'}
   riskmap={r['at']:r for r in risk}
   for c in cc:
    f=firstbuy[c['symbol'],c['entry_at']];decision=contracts[f['order_id']]['decision_at'];r=riskmap[decision]
    if r['episode']>0:
     assert r['on'];post.append(dict(c,sector=sec,model=policy,pressure=stress,decision_at=decision,phase=r['episode'],measure='actual_new_initial_cycle_after_resume_not_causal_increment'))
   krows=kept[kept_start:];pr=post[post_start:];row=dict(next(r for r in summaries if r['account']==aid));row.update(sector=sec,engine_mode=mode,policy=policy,pressure=stress,status='off_exact_reference' if policy=='A' else 'full_actual_path_policy_accounting_prefix_verified',paused_days=sum(not r['on'] for r in risk),pause_count=sum(r['event']=='pause' for r in risk),resume_count=sum(r['event']=='resume' for r in risk),nonempty_resumes=sum(r['event']=='resume' and bool(st[r['at']]['held']) for r in risk),original_valid_holdings_pause_events=valid_events,unique_original_valid_cycles_at_pause=len(krows),subsequent_valid_holdings_positive=sum((max(Z,D(x['subsequent_actual_stock_contribution'])) for x in krows),Z),subsequent_valid_holdings_negative=sum((min(Z,D(x['subsequent_actual_stock_contribution'])) for x in krows),Z),post_resume_new_cycles=len(pr),post_resume_new_net=sum((D(x['net_pnl']) for x in pr),Z),post_resume_new_negative=sum((min(Z,D(x['net_pnl'])) for x in pr),Z),worst_closed_cycle_return=min((D(c['net_return']) for c in cc if c['closed']=='True'),default=Z),**recovery(ds));fills=[x for x in logs if x['kind']=='fill'];row['gross_turnover_cny']=sum((D(x['receipt']['gross_cny']) for x in fills),Z);row['execution_slippage_cny']=sum((abs(D(x['price'])-D(x['raw_open']))*x['receipt']['shares']*D(x['fx_rate']) for x in fills),Z);matrix.append(row);waiting.append(dict(sector=sec,account=aid,policy=policy,pressure=stress,paused_days=row['paused_days'],waiting_days=sum(combos.values()),mutually_exclusive_combinations=dict(combos),sequential_primary=dict(prim),overlapping_condition_counts=dict(masks)))
   for d in ds:
    for s,at in d['mark_observed_at'].items():
     if at[:10]!=d['at'][:10]:unknown.append(dict(sector=sec,account=aid,at=d['at'],symbol=s,mark_observed_at=at))
   waitingchecks.append(dict(account=aid,holding_and_order_pre_step_reconstructed=True,waiting_combinations_sum=sum(combos.values()),original_valid_cycles_linked=len(krows)))
export(O/'MATRIX_18.csv',matrix);export(O/'PAUSE_EPISODES.csv',episodes);export(O/'HELD_AFTER_PAUSE.csv',kept);export(O/'POST_RESUME_NEW_CYCLES.csv',post);export(O/'STOCK_DIFFERENCES.csv',stockdiff);save(O/'WAITING.json',waiting);save(O/'KEY_SNAPSHOTS.json',snapshot);save(O/'ACT_EVENTS.json',all_events);save(O/'PRICE_CONDITIONS.json',unknown);save(O/'SUMMARY.json',dict(matrix=matrix,seconds=time.monotonic()-T,stock_bridges=bridges,waiting_checks=waitingchecks,trade_replay=False));print('SUMMARY_COMPLETE',len(matrix),'seconds',time.monotonic()-T)
