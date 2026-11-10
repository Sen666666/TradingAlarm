"""Completed native outputs only. No account, runner, scoring, or strategy invocation."""
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict, Counter
from bisect import bisect_left
import argparse, gzip, json, hashlib, sys, traceback
import numpy as np
import pandas as pd
R=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1')
CROOT=R/'account_comparison_continuous_v1'
Z=D(0); EPS=D('1e-8')
def read(p): return json.loads(Path(p).read_text())
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def gz(p):
 with gzip.open(p,'rt') as f: return json.load(f)
def stream(p):
 with gzip.open(p,'rt') as f:
  for line in f: yield json.loads(line)
def save(p,x): p.write_text(json.dumps(x,indent=2,default=str,allow_nan=False))
def csv(p,x):
 q=pd.DataFrame(x)
 for c in q.columns:
  if q[c].map(lambda v:isinstance(v,(dict,list,tuple))).any():q[c]=q[c].map(lambda v:json.dumps(v,default=str)if isinstance(v,(dict,list,tuple))else v)
 q.to_csv(p,index=False)
def decsum(v):return sum((D(str(x))for x in v),Z)
def stats(rows):
 p=[D(str(r['pnl']))for r in rows];w=[x for x in p if x>0];l=[x for x in p if x<0];n=len(p)
 mw=sum(w,Z)/len(w)if w else None;ml=sum(l,Z)/len(l)if l else None
 ret=[float(r['pnl']/r['buy_cost'])for r in rows if r['buy_cost']>0]
 sortp=sorted(p);sortret=sorted(ret);k=max(1,int(np.ceil(n*.05)))if n else 0
 return dict(n=n,wins=len(w),losses=len(l),flat=n-len(w)-len(l),win_rate=len(w)/n if n else None,mean_pnl=sum(p,Z)/n if n else None,mean_win=mw,mean_loss=ml,payoff_ratio=float(mw/-ml)if mw is not None and ml else None,net_pnl=sum(p,Z),gross_wins=sum(w,Z),gross_losses=sum(l,Z),worst_pnl=min(p)if p else None,best_pnl=max(p)if p else None,pnl_p05=float(np.quantile([float(v)for v in p],.05))if p else None,worst5pct_count=k,worst5pct_mean_pnl=sum(sortp[:k],Z)/k if k else None,median_return_on_all_buy_cost=float(np.median(ret))if ret else None,mean_return_on_all_buy_cost=float(np.mean(ret))if ret else None,p05_return_on_all_buy_cost=float(np.quantile(ret,.05))if ret else None,worst_return_on_all_buy_cost=min(ret)if ret else None,worst5pct_mean_return_on_all_buy_cost=float(np.mean(sortret[:k]))if k else None,return_denominator='all BUY gross plus BUY fees including all ADD; not initial stake')
def nav_stats(ds,initial):
 vals=np.array([float(initial)]+[float(r['nav'])for r in ds]);dd=vals/np.maximum.accumulate(vals)-1;i=int(np.argmin(dd));peak=int(np.argmax(vals[:i+1]));dates=['START_NAV']+[r['at'][:10]for r in ds]
 return dict(start_nav=initial,end_nav=D(ds[-1]['nav']),return_fraction=float(D(ds[-1]['nav'])/initial-1),max_drawdown_fraction=float(dd[i]),drawdown_peak_day=dates[peak],drawdown_trough_day=dates[i],days=len(ds))
def replay_account(a,label,daily,days,marks):
 layers={l['id']:dict(l)for l in a['layers']};positions={};cost={};buycost={};gross={};fees={};rounds=[];live={};assignment={};realized=Z
 events=[(r['at'],0,i,r)for i,r in enumerate(a['journal'])if r['kind']=='actual_split']+[(r['at'],1,i,r)for i,r in enumerate(a['trades'])]
 events.sort(key=lambda r:r[:3]);daily_cost={};event_day=None
 def total(s):return sum(v['qty']for v in positions.values()if v['sid']==s)
 for at,typ,i,t in events:
  if event_day is not None and at[:10]!=event_day:daily_cost[event_day]=sum(cost.values(),Z)
  event_day=at[:10]
  if typ==0:
   s=t['sid'];keys=[k for k,p in positions.items()if p['sid']==s and p['qty']>0];old=sum(positions[k]['qty']for k in keys)
   if not old:continue
   rat=D(t['ratio']);target=int(D(old)*rat);parts=[int(D(positions[k]['qty'])*rat)for k in keys]
   for j in range(target-sum(parts)):parts[j%len(parts)]+=1
   for k,q in zip(keys,parts):
    positions[k]['qty']=q
    if not q:realized-=cost[k];cost[k]=Z
   if s in live:live[s]['split_events']+=1
  elif t['side']=='buy':
   s=t['security_id'];k=t['layer'];assert k not in positions
   if total(s)==0:
    rr=dict(account=label,sid=s,round_id=len(rounds)+1,opened=at,closed=None,layer_ids=[],max_shares=0,buy_fills=0,sell_fills=0,partial_sell_fills=0,split_events=0)
    rounds.append(rr);live[s]=rr
   rr=live[s];rr['layer_ids'].append(k);rr['buy_fills']+=1;assignment[k]=rr['round_id'];positions[k]=dict(sid=s,qty=t['shares']);cost[k]=D(t['gross_cny'])+D(t['fees_cny']);buycost[k]=cost[k];gross[k]=D(t['gross_cny']);fees[k]=D(t['fees_cny']);rr['max_shares']=max(rr['max_shares'],total(s))
  else:
   s=t['security_id'];assert s in live;rr=live[s];rr['sell_fills']+=1
   for part in t['parts']:
    k=part['layer'];q=part['shares'];assert assignment[k]==rr['round_id'];assert 0<q<=positions[k]['qty'];allocated=cost[k]*D(q)/D(positions[k]['qty']);realized+=D(part['net_cash'])-allocated;cost[k]-=allocated;positions[k]['qty']-=q
   if total(s)==0:rr['closed']=at;del live[s]
   else:rr['partial_sell_fills']+=1
 if event_day:daily_cost[event_day]=sum(cost.values(),Z)
 for k,l in layers.items():
  assert positions[k]['qty']==l['qty'],('share replay mismatch',label,k)
  m=a['metadata'].get(str(k),{});structure=m.get('stock_structure');parts=structure.split('|')if structure else []
  birth=parts[-1]if len(parts)==3 and parts[0]==l['sid']else 'UNKNOWN'
  l.update(account=label,round_id=assignment[k],stock_structure=structure,birth_day=birth,birth_year=birth[:4]if birth!='UNKNOWN'else 'UNKNOWN',birth_event=(l['sid']+':'+birth)if birth!='UNKNOWN'else 'UNKNOWN',buy_cost=buycost[k],buy_gross=gross[k],buy_fees=fees[k],remaining_cost=cost[k],ending_inventory=D(l['qty'])*marks[days[-1]].get(l['sid'],Z),cash=D(l['cash']),dividend=D(l['dividend']))
  l['pnl']=l['cash']+l['dividend']+l['ending_inventory'];l['return_on_all_buy_cost']=float(l['pnl']/l['buy_cost']);l['initial_layer']=False
 for rr in rounds:
  ls=[layers[k]for k in rr['layer_ids']];anchor=min(ls,key=lambda l:(l['opened'],l['id']));anchor['initial_layer']=True
  rr.update(layers=len(ls),initial_layer=anchor['id'],initial_kind=anchor['kind'],core_layers=sum(l['kind']=='core'for l in ls),add_layers=sum(l['kind']=='add'for l in ls),pnl=sum((l['pnl']for l in ls),Z),cash=sum((l['cash']for l in ls),Z),booked_dividend_accrual=sum((l['dividend']for l in ls),Z),buy_cost=sum((l['buy_cost']for l in ls),Z),buy_gross=sum((l['buy_gross']for l in ls),Z),ending_quantity=sum(l['qty']for l in ls),ending_inventory=sum((l['ending_inventory']for l in ls),Z),remaining_cost=sum((l['remaining_cost']for l in ls),Z),anchor_birth=anchor['birth_event'],birth_year=anchor['birth_year'],birth_events=sorted(set(l['birth_event']for l in ls)),initial_layer_pnl=anchor['pnl'])
  rr['multi_birth']=len(rr['birth_events'])>1;rr['return_on_all_buy_cost']=float(rr['pnl']/rr['buy_cost']);rr['calendar_days']=(pd.Timestamp(rr['closed']or daily[days[-1]]['at'])-pd.Timestamp(rr['opened'])).total_seconds()/86400
  assert bool(rr['closed'])==(rr['ending_quantity']==0),('strict round status',label,rr)
  if rr['closed']:assert max(l['closed']for l in ls)==rr['closed']
  # Interval-union audit: all layers in a replay round strictly overlap the held spell.
  right=None
  for j,l in enumerate(ls):
   if j and right is not None:assert l['opened']<right,('round interval disagrees with ledger replay',label,rr['round_id'])
   if l['closed']is None:right=None
   elif j==0:right=l['closed']
   elif right is not None:right=max(right,l['closed'])
 net=sum((l['pnl']for l in layers.values()),Z);final=daily[days[-1]];assert abs(net-(D(final['nav'])-D(1200000)))<EPS
 inv=D(final['inventory']);unreal=inv-sum(cost.values(),Z);div=sum((l['dividend']for l in layers.values()),Z)
 assert abs(realized+unreal+div-net)<EPS
 assert abs(sum((r['pnl']for r in rounds),Z)-net)<EPS
 assert abs(sum((D(t['fees_cny'])for t in a['trades']),Z)-D(final['fees_cny']))<EPS
 # Entire actual closing position vector is independently checked from live snapshot layers.
 for d in days:
  ss=defaultdict(int)
  for l in daily[d]['layers']:ss[l['sid']]+=l['qty']
  assert dict(ss)==daily[d]['positions'],('snapshot shares mismatch',label,d)
 return rounds,list(layers.values()),dict(net_pnl=net,realized_sale_pnl_including_buy_sell_fees=realized,unrealized_inventory_minus_remaining_buy_cost=unreal,booked_dividend_accrual=div,ending_dividend_receivable=D(final['dividend_receivable']),ending_sale_receivable=D(final['sale_receivable']),ending_available=D(final['available']),remaining_buy_cost=sum(cost.values(),Z),all_buy_gross=sum(gross.values(),Z),all_buy_cost_including_fees=sum(buycost.values(),Z),fees=decsum(t['fees_cny']for t in a['trades']),embedded_price_slippage=sum((D(t['shares'])*abs(D(t['price'])-D(t['raw_open']))for t in a['trades']),Z),share_replay_and_nav_bridge_pass=True)
def analyze(run,out,baseline_only):
 assert not out.exists(),('Never overwrite analysis',out);out.mkdir(parents=True)
 pre=read(run/'PREDECLARED.json');assert read(run/'DONE.json')['completed']is True
 assert pre['start']=='2022-01-01'and pre['end']=='2026-05-15'and D(pre['initial_cash_each'])==D(1200000)
 arms=['PVR']if baseline_only else ['PVR','NOACT'];assert all(a in pre['arms']for a in arms)
 sources={str(p):sha(p)for p in [run/'PREDECLARED.json',run/'DONE.json',run/'pair/daily.jsonl.gz',Path(__file__),Path(__file__).with_name('DEFINITIONS.md')]}
 for p,h in pre['source_freeze'].items():assert sha(p)==h,('source changed',p)
 by={a:{}for a in arms}
 for r in stream(run/'pair/daily.jsonl.gz'):
  if r['account']in by:
   d=r['at'][:10];assert d not in by[r['account']];by[r['account']][d]=r
 days=sorted(by['PVR']);assert days[-1]=='2026-05-15'and len(days)==1054
 for a in arms:assert sorted(by[a])==days
 # Original immutable raw marks only; no account construction, indicator calculation, or data writes.
 sys.dont_write_bytecode=True;sys.path.insert(0,str(CROOT/'inputs'));import continuous_inputs as C
 ids=read(C.U/'FREEZE.json')['stocks'];assert len(ids)==1709;_,market,_=C.J.M.context(days[-1],ids=ids)
 marks={};maxgap=Z;navgap=Z
 for d in days:
  held=set().union(*(set(v[d]['positions'])for v in by.values()));at=C.J.M.N.iso(by['PVR'][d]['at']);marks[d]={s:m.cny_price(at)for s,m in market.marks(at,held).items()}
  for a in arms:
   r=by[a][d];assert set(r['positions'])<=set(ids);inv=sum((D(q)*marks[d][s]for s,q in r['positions'].items()),Z);maxgap=max(maxgap,abs(inv-D(r['inventory'])))
   nv=sum((D(r[k])for k in ['available','order_reserved','settlement_locked','sale_receivable','dividend_receivable','inventory']),Z)-D(r['payable']);navgap=max(navgap,abs(nv-D(r['nav'])))
 assert maxgap<EPS and navgap<EPS
 annual=[];risk=[];allrounds=[];alllayers=[];accounts={};summaries={};trades=[];risk_events=[];closeyear=[];birthyear=[];equity=[];tail=[];periods=[]
 original=read(run/'ANNUAL_METRICS.json')if (run/'ANNUAL_METRICS.json').exists()else []
 for a in arms:
  acc=gz(run/f'pair/{a}.json.gz');accounts[a]=acc;sources[str(run/f'pair/{a}.json.gz')]=sha(run/f'pair/{a}.json.gz');ds=[by[a][d]for d in days];prev=D(1200000)
  for y in sorted(set(d[:4]for d in days)):
   s=[r for r in ds if r['at'].startswith(y)];n=nav_stats(s,prev);n.update(account=a,year=y,partial_year=y=='2026',mean_inventory_fraction=float(np.mean([float(D(r['inventory'])/D(r['nav']))for r in s])),mean_stock_count=float(np.mean([len(r['positions'])for r in s])))
   old=next((v for v in original if v['account']==a and str(v['year'])==y),None)
   if old:
    assert abs(n['return_fraction']-old['return_fraction'])<1e-12 and abs(n['max_drawdown_fraction']-old['max_drawdown_fraction'])<1e-12
   n['native_annual_rechecked']=old is not None;annual.append(n);prev=D(s[-1]['nav'])
  for r in ds:
   d=r['at'][:10];nav=D(r['nav']);weights=[float(D(q)*marks[d][s]/nav)for s,q in r['positions'].items()]
   risk.append(dict(account=a,day=d,nav=nav,inventory=D(r['inventory']),inventory_NAV_fraction=float(D(r['inventory'])/nav),largest_stock_NAV_fraction=max(weights,default=0),stock_count=len(r['positions']),ACT_on=r['on'],available=r['available'],dividend_receivable=r['dividend_receivable'],sale_receivable=r['sale_receivable'],pending_intents=r['pending_intents'],pool_probe=r['pool_probe'],pool_confirmed=r['pool_confirmed'],shared_loss=r['shared_loss']))
  rr,ll,bridge=replay_account(acc,a,by[a],days,marks);allrounds+=rr;alllayers+=ll;closed=[r for r in rr if r['closed']];opened=[r for r in rr if not r['closed']];risk_a=[r for r in risk if r['account']==a]
  s=dict(**nav_stats(ds,D(1200000)),**bridge,closed_rounds=stats(closed),open_rounds=dict(n=len(opened),net_pnl=sum((r['pnl']for r in opened),Z),ending_inventory=sum((r['ending_inventory']for r in opened),Z)),initial_layers_of_closed_rounds=stats([l for l in ll if l['initial_layer']and next(r for r in rr if r['round_id']==l['round_id'])['closed']]),initial_layers_caution='Layer diagnostic only, not full-round win rate',mean_inventory_fraction=float(np.mean([r['inventory_NAV_fraction']for r in risk_a])),p95_inventory_fraction=float(np.quantile([r['inventory_NAV_fraction']for r in risk_a],.95)),max_inventory_fraction=max(r['inventory_NAV_fraction']for r in risk_a),max_stock_count=max(r['stock_count']for r in risk_a),max_single_stock_NAV_fraction=max(r['largest_stock_NAV_fraction']for r in risk_a),off_sessions=sum(not r['on']for r in ds),multi_birth_rounds=sum(r['multi_birth']for r in rr),unknown_birth_rounds=sum(r['birth_year']=='UNKNOWN'for r in rr));summaries[a]=s
  for y in sorted(set(r['closed'][:4]for r in closed)):closeyear.append(dict(account=a,close_year=y,**stats([r for r in closed if r['closed'].startswith(y)]),note='Entire round PnL assigned to closing year; not annual NAV PnL'))
  for y in sorted(set(r['birth_year']for r in rr)):
   z=[r for r in rr if r['birth_year']==y];birthyear.append(dict(account=a,birth_year=y,**stats([r for r in z if r['closed']]),open_rounds=sum(not r['closed']for r in z),open_round_pnl=sum((r['pnl']for r in z if not r['closed']),Z),multi_birth_rounds=sum(r['multi_birth']for r in z),note='First actual buy layer native stock-structure birth anchors complete round'))
  for st,z in [('COMPLETE',[r for r in rr if r['closed']]),('OPEN',[r for r in rr if not r['closed']])]:
   for hasdiv in [False,True]:
    zz=[r for r in z if bool(r['booked_dividend_accrual'])==hasdiv];equity.append(dict(account=a,round_status=st,has_booked_dividend_accrual=hasdiv,rounds=len(zz),pnl=sum((r['pnl']for r in zz),Z),booked_dividend=sum((r['booked_dividend_accrual']for r in zz),Z),model_accounting='RECONCILED',historical_terms_available='UNKNOWN',actual_external_payout='UNKNOWN',historical_exchange_tradability='UNKNOWN',excluded_from_round_stats=False))
  for order in ['pnl','return_on_all_buy_cost']:
   for rank,r in enumerate(sorted(closed,key=lambda r:r[order])[:20],1):tail.append(dict(tail_basis=order,tail_rank=rank,**r))
  for i,t in enumerate(acc['trades']):trades.append(dict(account=a,trade_index=i,**t))
  risk_events += [dict(account=a,**r)for r in acc['audit']if r['kind']=='risk_checkpoint'and r.get('event')]
  for name,start,end in [('2022_NANWANG','2022-04-21','2022-07-29'),('2024_0924_1008','2024-09-24','2024-10-08'),('2026_0101_0130','2026-01-01','2026-01-30'),('2026_0115_0130','2026-01-15','2026-01-30')]:
   selected=[d for d in days if start<=d<=end];before=[d for d in days if d<start];v0=D(by[a][before[-1]]['nav'])if before else D(1200000);periods.append(dict(account=a,window=name,first_day=selected[0],last_day=selected[-1],**nav_stats([by[a][d]for d in selected],v0),mean_inventory_fraction=float(np.mean([float(D(by[a][d]['inventory'])/D(by[a][d]['nav']))for d in selected]))))
 # Independent signal birth aggregation, not account-local round ID matching.
 birthmap=defaultdict(lambda:defaultdict(list))
 for l in alllayers:birthmap[(l['sid'],l['stock_structure']or 'UNKNOWN')][l['account']].append(l)
 lineage=[]
 for (sid,structure),armsrows in sorted(birthmap.items()):
  row=dict(sid=sid,stock_structure=structure,birth_event=next(iter(armsrows.values()))[0]['birth_event'])
  for a in arms:
   ls=armsrows.get(a,[]);row.update({a+'_layers':len(ls),a+'_rounds_touched':len(set(l['round_id']for l in ls)),a+'_booked_pnl':sum((l['pnl']for l in ls),Z),a+'_buy_cost':sum((l['buy_cost']for l in ls),Z),a+'_live_layers':sum(l['qty']>0 for l in ls),a+'_first_buy':min((l['opened']for l in ls),default=None),a+'_last_close':max((l['closed']for l in ls if l['closed']),default=None)})
  if 'NOACT'in arms:
   row['change']='BOTH'if row['PVR_layers']and row['NOACT_layers']else 'NOACT_ONLY_ADDED'if row['NOACT_layers']else'PVR_ONLY_LOST';row['delta_pnl']=row['NOACT_booked_pnl']-row['PVR_booked_pnl'];row['strict_closed_both']=bool(row['PVR_layers']and row['NOACT_layers']and not row['PVR_live_layers']and not row['NOACT_live_layers']);row['winner_state']='OPEN_OR_ONE_ARM_ABSENT'if not row['strict_closed_both']else 'WINNER_REGAINED'if row['PVR_booked_pnl']<=0<row['NOACT_booked_pnl']else'WINNER_LOST'if row['NOACT_booked_pnl']<=0<row['PVR_booked_pnl']else'BOTH_WIN'if row['PVR_booked_pnl']>0 and row['NOACT_booked_pnl']>0 else'BOTH_NONWIN'
  lineage.append(row)
 # Shared immutable original-I event denominator and forward labels are diagnostic only.
 labelfile=R/'equal_entry_validation_v1/FIXED_ORIGINAL_I_ENTRY_LABELS.parquet';f=pd.read_parquet(labelfile);f=f[f.sid.isin(ids)];sources[str(labelfile)]=sha(labelfile);assert not f.original_epoch.duplicated().any();big=f[f.complete60.eq(True)&f.mfe60.ge(.30)&f.ret60.ge(.20)];events=[];excluded=[]
 for row in big.to_dict('records'):
  d=str(row['entry_day'])[:10];k=bisect_left(days,d)
  if k>=len(days)or days[k]!=d or k+6>len(days):excluded.append(dict(sid=row['sid'],event=row['original_epoch'],reason='entry absent or fewer than six sessions'));continue
  win=days[k:k+6];sid=row['sid'];e=dict(sid=sid,event=row['original_epoch'],birth_day=row['original_root_day'],birth_year=str(row['original_root_day'])[:4],entry_day=d,entry_year=d[:4],end_day60=row['end_day60'],mfe60=row['mfe60'],ret60=row['ret60'],early_window_end=win[-1],baseline_ACT_off_days=sum(not by['PVR'][w]['on']for w in win))
  for a in arms:
   flags=[int(by[a][w]['positions'].get(sid,0))>0 for w in win];weights=[float(D(by[a][w]['positions'].get(sid,0))*marks[w].get(sid,Z)/D(by[a][w]['nav']))for w in win];e.update({a+'_participated':any(flags),a+'_held_days':sum(flags),a+'_early_mean_NAV_fraction':float(np.mean(weights)),a+'_entry_close_shares':by[a][d]['positions'].get(sid,0),a+'_held_previous_close':bool(k and by[a][days[k-1]]['positions'].get(sid,0)),a+'_first_held_day':next((w for w,v in zip(win,flags)if v),None)})
  if 'NOACT'in arms:e['change']='BOTH'if e['PVR_participated']and e['NOACT_participated']else'NOACT_ONLY_ADDED'if e['NOACT_participated']else'PVR_ONLY_LOST'if e['PVR_participated']else'NEITHER';e['pause_window_recovered']=e['change']=='NOACT_ONLY_ADDED'and e['baseline_ACT_off_days']>0
  events.append(e)
 es=[]
 for y in sorted(set(e['entry_year']for e in events))+['ALL']:
  z=[e for e in events if y=='ALL'or e['entry_year']==y];rr=dict(entry_year=y,events=len(z))
  for a in arms:rr.update({a+'_participated':sum(e[a+'_participated']for e in z),a+'_participation_rate':float(np.mean([e[a+'_participated']for e in z])),a+'_mean_early_NAV_fraction':float(np.mean([e[a+'_early_mean_NAV_fraction']for e in z]))})
  if 'NOACT'in arms:rr.update({c:sum(e['change']==c for e in z)for c in ['BOTH','NOACT_ONLY_ADDED','PVR_ONLY_LOST','NEITHER']});rr['pause_window_recovered']=sum(e['pause_window_recovered']for e in z)
  es.append(rr)
 # Actual holdings and trades around requested examples, with units explicitly shares.
 cases=[];case_trades=[]
 for a in arms:
  for name,start,end,sids in [('NANWANG_2022','2022-01-01','2022-12-31',['688248.SH']),('RALLY_2024','2024-09-20','2024-10-15',['002583.SZ','688660.SH','605488.SH','002241.SZ','600396.SH','601336.SH']),('EARLY_2026','2026-01-01','2026-01-30',None)]:
   for d in [d for d in days if start<=d<=end]:
    r=by[a][d]
    for sid in sids or sorted(r['positions']):
     q=r['positions'].get(sid,0);cases.append(dict(account=a,case=name,day=d,sid=sid,actual_proxy_shares=q,raw_mark=str(marks[d].get(sid))if q else None,position_value=D(q)*marks[d].get(sid,Z),NAV=r['nav'],weight=float(D(q)*marks[d].get(sid,Z)/D(r['nav'])),ACT_on=r['on']))
   case_trades += [dict(case=name,**t)for t in trades if t['account']==a and start<=t['at'][:10]<=end and (sids is None or t['security_id']in sids)]
 # Pause windows use original PVR's actually observed pauses solely as attribution windows.
 pausewindows=[];pausepaths=[]
 for event in [e for e in risk_events if e['account']=='PVR'and e['event']=='pause']:
  d=event['at'][:10];resume=next((e['at'][:10]for e in risk_events if e['account']=='PVR'and e['event']=='resume'and e['at']>event['at']),days[-1]);k=days.index(d);endk=days.index(resume);begin=days[max(0,k-5)];end=days[min(len(days)-1,endk+5)]
  for a in arms:
   selected=[w for w in days if d<=w<=resume];v0=D(by[a][days[k-1]]['nav'])if k else D(1200000);pausewindows.append(dict(account=a,pause_day=d,resume_day=resume,**nav_stats([by[a][w]for w in selected],v0),actual_buy_gross=decsum(t['gross_cny']for t in trades if t['account']==a and t['side']=='buy'and d<=t['at'][:10]<=resume),actual_sell_gross=decsum(t['gross_cny']for t in trades if t['account']==a and t['side']=='sell'and d<=t['at'][:10]<=resume),mean_inventory_fraction=float(np.mean([float(D(by[a][w]['inventory'])/D(by[a][w]['nav']))for w in selected]))))
   pausepaths += [dict(pause_day=d,resume_day=resume,**r)for r in risk if r['account']==a and begin<=r['day']<=end]
 # Funding rejections remain native. Repeated rejected budgets are not added up as saved cash.
 fundingcounts=Counter();fundingfile=run/'pair/funding.jsonl.gz'
 if fundingfile.exists():
  sources[str(fundingfile)]=sha(fundingfile)
  for r in stream(fundingfile):
   if r['account']in arms:fundingcounts[(r['account'],r['at'][:4],r.get('role'),r.get('result'))]+=1
 funded=[dict(account=k[0],year=k[1],role=k[2],result=k[3],rows=v)for k,v in fundingcounts.items()]
 feeannual=[]
 for a in arms:
  for y in sorted(set(d[:4]for d in days)):
   ts=[t for t in trades if t['account']==a and t['at'].startswith(y)];buys=[t for t in ts if t['side']=='buy'];feeannual.append(dict(account=a,year=y,buy_fills=len(buys),sell_fills=len(ts)-len(buys),buy_gross=decsum(t['gross_cny']for t in buys),buy_fees=decsum(t['fees_cny']for t in buys),all_fees=decsum(t['fees_cny']for t in ts),sell_gross=decsum(t['gross_cny']for t in ts if t['side']=='sell')))
 outputs={'ANNUAL_METRICS':annual,'DAILY_RISK':risk,'STOCK_ROUNDS':allrounds,'LAYER_ATTRIBUTION':alllayers,'CLOSED_ROUNDS_BY_CLOSE_YEAR':closeyear,'CLOSED_ROUNDS_BY_BIRTH_YEAR':birthyear,'EQUITY_ACCOUNTING_AND_EXTERNAL_UNKNOWN':equity,'COMPLETE_ROUND_WORST_TAILS':tail,'SIGNAL_BIRTH_LINEAGE_COMPARISON':lineage,'BIG60_EVENT_PARTICIPATION':events,'BIG60_ANNUAL_PARTICIPATION':es,'SPECIFIED_PERIODS':periods,'CASE_DAILY_HOLDINGS':cases,'CASE_ACTUAL_TRADES':case_trades,'ACT_NATIVE_EVENTS':risk_events,'BASELINE_PAUSE_WINDOWS':pausewindows,'BASELINE_PAUSE_DAILY_PATH':pausepaths,'NATIVE_FUNDING_CONSTRAINT_COUNTS':funded,'ANNUAL_FEES_AND_BUY_PRINCIPAL':feeannual}
 for n,rows in outputs.items():csv(out/(n+'.csv'),rows)
 save(out/'BIG60_EXCLUDED.json',excluded)
 summary=dict(status='PASS_COMPLETED_OUTPUT_ONLY_ANALYSIS',account_runs=0,baseline_only=baseline_only,run=str(run),common_sessions=len(days),fixed_pool=1709,industry_count=90,max_inventory_reconstruction_gap=maxgap,max_NAV_identity_gap=navgap,summary=summaries,annual=annual,big60=es,sources=sources,limitations=['In-sample diagnostic only; no OOS or live suitability claim.','Frozen future stock pool and preknown corporate-action terms inherited.','Known-open +/-5bp proxy, prior20 volume constraint; actual historical tradability UNKNOWN.','Booked dividend accrual included; receivables are not spendable cash. External payout evidence UNKNOWN, not omitted sample.','Complete rounds include all ADD and partial sales. Initial-layer figures are diagnostic only.','Birth lineage aggregates layers across distinct actual rounds and is not a paired-trade match.','big60 and pause-window labels are posthoc attribution only. They do not establish isolated direct ACT causality.','No forced terminal liquidation. Open rounds are marked and separately reported.'])
 save(out/'SUMMARY.json',summary)
 for p,h in sources.items():assert sha(p)==h,('input changed during analysis',p)
 for p,h in pre['source_freeze'].items():assert sha(p)==h,('source changed during analysis',p)
 save(out/'OUTPUT_SHA256.json',{p.name:sha(p)for p in out.iterdir()if p.is_file()and p.name!='OUTPUT_SHA256.json'})
 print(json.dumps(dict(status=summary['status'],out=str(out),summary=summaries,big60=es),indent=2,default=str),flush=True)
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--run',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--baseline-only',action='store_true');args=ap.parse_args()
 try:analyze(args.run.resolve(),args.out.resolve(),args.baseline_only)
 except Exception as e:
  if args.out.exists():save(args.out/'ANALYSIS_FAILURE.json',dict(error=repr(e),traceback=traceback.format_exc(),account_runs=0,partial_outputs_not_results=True))
  raise
if __name__=='__main__':main()
