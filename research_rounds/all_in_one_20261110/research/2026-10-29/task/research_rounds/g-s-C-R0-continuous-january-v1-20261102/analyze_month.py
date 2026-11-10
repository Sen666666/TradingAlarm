"""Saved financial objects only. Original audited accounting reused, no events."""
from pathlib import Path
from decimal import Decimal as D
from collections import Counter,defaultdict
import json,time,sys,argparse
import jan_r0 as X
sys.path.insert(0,str(X.M.HERE));from analyze_short import accounting,grouped
sys.path.insert(0,str(X.M.C.OLD));from verify_saved import check_json
E=X.E;P=X.HERE;O=P/'analysis';Z=D(0)
def read(p):return X.read(p)
def save(n,x):X.save(O/n,x)
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--modes',nargs='+',choices=['C10','C_BATCH20'],default=['C10','C_BATCH20']);args=parser.parse_args()
 O.mkdir(exist_ok=True);t=time.perf_counter();results=[];days={};stockrows={};sectorrows={};alllayers={};allsales={};checks=[];riskrows={};timing=[]
 baseline=read(P/'baseline_readonly/RESULTS.json');original_layers=read(P/'baseline_readonly/ALL_LAYERS.json');original=[];original_stocks={}
 for v in baseline:
  m=v['mode'];z=v['summary'];original.append(dict(arm='2022-'+m,NAV=z['final_NAV'],return_from_original_1m=D(z['return_pct'])/100,max_close_drawdown=D(z['close_drawdown']['max_drawdown_pct'])/100,fees=z['fees'],buy_gross=z['buy_gross'],sell_gross=z['sell_gross'],pnl=v['pnl']))
  by=defaultdict(lambda:dict(buy=Z,contribution=Z,first_buy=None))
  for q in original_layers[m]:
   w=by[q['sid']];w['buy']+=D(q['buy_gross']);w['contribution']+=D(q['total_contribution']);w['first_buy']=min(w['first_buy'],q['opened']) if w['first_buy'] else q['opened']
  original_stocks['2022-'+m]=[dict(sid=k,**v) for k,v in by.items()]

 names=read(X.M.HERE/'inputs/2022/metadata.json')
 for mode in args.modes:
  root=P/'runs'/mode;pr=read(root/'PROGRESS.json');done=read(root/'COMPLETED.json');assert pr['phase']=='CLOSE' and pr['cursor'][:10]=='2022-01-28'
  final=read(Path(pr['checkpoint']).with_suffix('.json'));a=final['account'];b=a['balance']
  assert not [z for z in final['action_log'] if z.get('ratio',z.get('actual_share_ratio'))!='1' and z['old_shares']],'held split needs explicit cost allocation; preserve account and stop analysis'
  ll,ss,pnl=accounting(final);alllayers[mode]=ll;allsales[mode]=ss
  daily=[];peak=D(1000000);dd=Z;ddat=None;stock=defaultdict(lambda:dict(buy=Z,realized=Z,unrealized=Z,dividend=Z,contribution=Z,qty=0,first_buy=None,peak_close_weight=Z));sector=defaultdict(lambda:dict(buy=Z,realized=Z,unrealized=Z,dividend=Z,contribution=Z,first_buy=None,peak_close_weight=Z))
  for z in ll:
   for d in (stock[z['sid']],sector[z['sector']]):
    for dest,src in [('buy','buy_gross'),('realized','realized_trade_PNL'),('unrealized','unrealized_net_buy_cost'),('dividend','booked_dividend_income'),('contribution','total_contribution')]:d[dest]+=D(z[src])
    d['first_buy']=min(d['first_buy'],z['opened']) if d['first_buy'] else z['opened']
   stock[z['sid']]['qty']+=z['remaining_qty']
  for path in sorted(root.glob('20*-*.json')):
   phase=path.stem.split('-')[-1]
   if phase not in ('ACTION','OPEN','CLOSE'):continue
   x=read(path);aa=x['account'];bal=aa['balance'];flow=read(path.with_name(path.stem+'-FLOW.json'));diff=check_json(path);checks.append(dict(mode=mode,file=str(path),sha256=X.sha(path),differences=diff));timing.append(dict(mode=mode,day=path.name[:10],phase=phase,seconds=flow['seconds'],memo_hits=flow['memo_hits'],memo_misses=flow['memo_misses']))
   if phase!='CLOSE':continue
   nav=D(bal['nav']);peak=max(peak,nav);draw=D(1)-nav/peak
   if draw>dd:dd=draw;ddat=path.name[:10]
   cap=defaultdict(lambda:Z);scap=defaultdict(lambda:Z);rolecap=defaultdict(lambda:Z)
   for z in aa['layers']:
    if not z['qty']:continue
    meta=aa['capital_meta'][str(z['id'])];v=D(z['qty'])*D(aa['market_marks'][z['sid']]);cap[z['sid']]+=v;scap[meta['sector']]+=v;rolecap[meta['role']+'|'+meta['pool']]+=v
   for sid,v in cap.items():stock[sid]['peak_close_weight']=max(stock[sid]['peak_close_weight'],v/nav)
   for sec,v in scap.items():sector[sec]['peak_close_weight']=max(sector[sec]['peak_close_weight'],v/nav)
   tr=[z for z in aa['trades'] if z['at'][:10]==path.name[:10]];bk=json.loads(x['budget'])['body']['batch']
   daily.append(dict(day=path.name[:10],NAV=nav,drawdown=draw,exposure=D(bal['inventory'])/nav,available=bal['available'],nominal_risk=D(bal['resources']['risk']),risk_NAV_fraction=D(bal['resources']['risk'])/nav,buy_gross=sum((D(z['gross_cny']) for z in tr if z['side']=='buy'),Z),sell_gross=sum((D(z['gross_cny']) for z in tr if z['side']=='sell'),Z),industries=[dict(sector=s,capital=v,weight=v/nav) for s,v in sorted(scap.items(),key=lambda kv:-kv[1])],role_pool_capital=dict(rolecap),ACT=aa['policy']['act'],batch=bk,active_buy=len(aa['buys']),active_exit=len(aa['exits']),pending_intents=len(x['pending'])))
  st=[dict(sid=s,name=names[s]['name'],sector=names[s]['sector'],**v) for s,v in sorted(stock.items(),key=lambda kv:-kv[1]['contribution'])];se=[dict(sector=s,**v) for s,v in sorted(sector.items(),key=lambda kv:-kv[1]['contribution'])];stockrows[mode]=st;sectorrows[mode]=se;days[mode]=daily
  trades=aa['trades'];both=defaultdict(list)
  for tr in a['trades']:both[(tr['at'],tr['security_id'])].append(tr)
  roundtrips=[dict(at=k[0],sid=k[1],gross=sum((D(z['gross_cny']) for z in ts),Z),fees=sum((D(z['fees_cny']) for z in ts),Z),transactions=ts) for k,ts in both.items() if {'buy','sell'}<={z['side'] for z in ts}]
  risk=final['approved_risk'];riskrows[mode]=risk
  rows=dict(mode=mode,NAV=D(b['nav']),return_from_1m=D(b['nav'])/D(1000000)-1,max_close_DD=dd,max_close_DD_at=ddat,mean_close_exposure=sum((d['exposure'] for d in daily),Z)/len(daily),max_close_exposure=max(d['exposure'] for d in daily),terminal_exposure=daily[-1]['exposure'],mean_close_nominal_risk_NAV=sum((d['risk_NAV_fraction'] for d in daily),Z)/len(daily),max_close_nominal_risk_NAV=max(d['risk_NAV_fraction'] for d in daily),fees=D(b['fees_cny']),buy_gross=sum((D(f['gross_cny']) for f in a['fills'] if f['side']=='buy'),Z),sell_gross=sum((D(f['gross_cny']) for f in a['fills'] if f['side']=='sell'),Z),buy_fills=sum(f['side']=='buy' for f in a['fills']),sell_fills=sum(f['side']=='sell' for f in a['fills']),actual_funded_stocks=len(st),layers=len(ll),pnl=pnl,role_pool_first_add_reentry=grouped(ll,['role','pool','entry_class']),same_day_exit_requests=sum(z['same_buy_day_exit_requested'] for z in ll),same_open_roundtrip=roundtrips,active_native_buys=len(a['buys']),active_native_exits=len(a['exits']),pending_intents=len(final['pending']),ACT=a['policy']['act'],completion=done,checkpoint=pr)
  old=next(z for z in original if z['arm']=='2022-'+mode);oldst={z['sid']:z for z in original_stocks[old['arm']]};newst={z['sid']:z for z in st};delta=[]
  for sid in oldst.keys()|newst.keys():
   n=newst.get(sid,{});o=oldst.get(sid,{});delta.append(dict(sid=sid,name=names[sid]['name'],sector=names[sid]['sector'],old_first=o.get('first_buy'),new_first=n.get('first_buy'),old_buy=o.get('buy',Z),new_buy=n.get('buy',Z),old_contribution=o.get('contribution',Z),new_contribution=n.get('contribution',Z),contribution_difference=D(n.get('contribution',0))-D(o.get('contribution',0))))
  delta.sort(key=lambda z:z['contribution_difference'],reverse=True)
  rows['vs_original']=dict(NAV_difference=rows['NAV']-D(old['NAV']),return_percentage_point_difference=(rows['return_from_1m']-D(old['return_from_original_1m']))*100,fee_difference=rows['fees']-D(old['fees']),buy_gross_difference=rows['buy_gross']-D(old['buy_gross']),sell_gross_difference=rows['sell_gross']-D(old['sell_gross']),new_funded_stocks=sorted(newst.keys()-oldst.keys()),lost_funded_stocks=sorted(oldst.keys()-newst.keys()),pnl_difference={k:D(pnl[k])-D(old['pnl'][k]) for k in pnl},stock_differences=delta,not_trade_deletion_counterfactual=True)
  assert abs(sum((z['contribution_difference'] for z in delta),Z)-rows['vs_original']['NAV_difference'])<D('0.00000000001')
  results.append(rows);print('ANALYZED',mode,rows['NAV'],rows['vs_original']['NAV_difference'],flush=True)
 save('RESULTS.json',results);save('DAILY.json',days);save('ALL_STOCKS.json',stockrows);save('ALL_SECTORS.json',sectorrows);save('ALL_LAYERS.json',alllayers);save('ALL_SALE_PARTS.json',allsales);save('RISK_BOOKS.json',riskrows);save('PERFORMANCE.json',timing);save('VERIFICATION.json',dict(passed=True,completed_modes=args.modes,not_claiming_other_mode_complete=True,event_states=len(checks),checks=checks,financial_events=0,seconds=time.perf_counter()-t))
if __name__=='__main__':main()
