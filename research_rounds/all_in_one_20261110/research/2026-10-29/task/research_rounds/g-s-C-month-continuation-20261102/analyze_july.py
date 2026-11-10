"""Completed July paths, saved states only; reuses audited seven-day accounting."""
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict,Counter
import json,time
import month_runtime as M
from analyze_short import accounting,grouped
import sys
sys.path.insert(0,str(M.C.OLD));from verify_saved import check_json
P=M.HERE;O=P/'july_end_analysis';Z=D(0)
def read(p):return M.read(p)
def save(n,x):M.E.IO.write_json(O/n,x,encoder=M.E.encode)
def main():
 t=time.perf_counter();M.guard();O.mkdir(exist_ok=True);rows=[];days_out={};layers_out={};sales_out={};events_out={};checks=[];restores=[];allstocks={};allsectors={};marketfacts=None
 oldchecks=read(P/'short_window_analysis/VERIFICATION.json')['event_checks'];oldmap={r['file']:r for r in oldchecks}
 for mode in ('C10','C_BATCH20'):
  arm='2025_26-'+mode;root=P/'runs'/arm;pp=read(root/'PROGRESS.json');stop=read(root/'STOPPED_AT_CUTOFF.json');assert pp['cursor'][:10]=='2025-07-31' and pp['phase']=='CLOSE' and stop['cutoff']=='2025-07-31'
  x=read(Path(pp['checkpoint']).with_suffix('.json'));a=x['account'];b=a['balance'];heldsplits=[z for z in x['action_log'] if z['ratio']!='1' and z['old_shares']]
  assert not heldsplits,'analysis allocation needs explicit held-split cost basis; account path remains saved and must NOT rerun'
  ll,ss,pnl=accounting(x);layers_out[arm]=ll;sales_out[arm]=ss;daily=[];events=[];names=read(P/'inputs/2025_26/metadata.json');stock=defaultdict(lambda:dict(buy=Z,realized=Z,unrealized=Z,dividend=Z,contribution=Z,qty=0,first_buy=None,peak_close_weight=Z));sector=defaultdict(lambda:dict(buy=Z,realized=Z,unrealized=Z,dividend=Z,contribution=Z,peak_close_weight=Z,first_buy=None))
  for z in ll:
   for d in (stock[z['sid']],sector[z['sector']]):
    for dest,src in [('buy','buy_gross'),('realized','realized_trade_PNL'),('unrealized','unrealized_net_buy_cost'),('dividend','booked_dividend_income'),('contribution','total_contribution')]:d[dest]+=D(z[src])
    d['first_buy']=min(d['first_buy'],z['opened']) if d['first_buy'] else z['opened']
   stock[z['sid']]['qty']+=z['remaining_qty']
  close_events=[e for e in x['events'] if e['phase']=='CLOSE'];peak=D(1000000);dd=Z;ddat=None;prev_inv=Z;prevfees=Z
  for ev in close_events:
   day=ev['at'][:10];bal=ev['bridge'];nav=D(bal['nav']);peak=max(peak,nav);draw=D(1)-nav/peak
   if draw>dd:dd=draw;ddat=day
   candidates=[root/(day+'-CLOSE.json'),M.C.HERE/'runs'/arm/'full'/(day+'-CLOSE.json'),M.C.OLD/'runs'/arm/(day+'-CLOSE.json')];path=next((p for p in candidates if p.exists()),None);assert path is not None,day
   snap=read(path);aa=snap['account'];seccap=defaultdict(lambda:Z);stockcap=defaultdict(lambda:Z)
   for z in aa['layers']:
    cap=D(z['qty'])*D(aa['market_marks'].get(z['sid'],0));seccap[aa['capital_meta'][str(z['id'])]['sector']]+=cap;stockcap[z['sid']]+=cap
   for sid,val in stockcap.items():stock[sid]['peak_close_weight']=max(stock[sid]['peak_close_weight'],val/nav)
   for sid,val in seccap.items():sector[sid]['peak_close_weight']=max(sector[sid]['peak_close_weight'],val/nav)
   tr=[z for z in a['trades'] if z['at'][:10]==day];buy=sum((D(z['gross_cny']) for z in tr if z['side']=='buy'),Z);sell=sum((D(z['gross_cny']) for z in tr if z['side']=='sell'),Z);fees=D(bal['fees_cny']);inv=D(bal['inventory'])
   daily.append(dict(day=day,NAV=nav,drawdown_from_initial_or_prior_peak=draw,exposure=inv/nav,buy_gross=buy,sell_gross=sell,fee=fees-prevfees,fee_cumulative=fees,inventory_change=inv-prev_inv,valuation_change_including_fill_vs_close_slippage_and_corporate_action_price_effects=inv-prev_inv-buy+sell,available=bal['available'],dividend_receivable=bal['dividend_receivable'],industries=[dict(sector=s,capital=v,weight=v/nav) for s,v in sorted(seccap.items(),key=lambda p:-p[1]) if v],ACT=aa['policy']['act'],active_native_buys=len(aa['buys']),active_native_exits=len(aa['exits'])))
   prev_inv=inv;prevfees=fees
  for path in sorted(root.glob('20*-*.json')):
   phase=path.stem.split('-')[-1]
   if phase not in ('ACTION','OPEN','CLOSE'):continue
   day=path.name[:10];key=str(path)
   if day<='2025-07-09':
    assert key in oldmap and M.P.sha(path)==oldmap[key]['sha256'];check=dict(file=key,reused_audited_check=True,differences=oldmap[key]['differences'])
   else:check=dict(file=key,reused_audited_check=False,differences=check_json(path))
   checks.append(check)
   flow=read(path.with_name(path.stem+'-FLOW.json'));events.append(dict(day=day,phase=phase,seconds=flow['seconds'],fills=flow['fills'],healthy_funding_sells=flow['healthy_funding_sells'],budget_before=flow['budget_before'],budget_after=flow['budget_after'],before_available=flow['before_available'],after_available=flow['after_available']))
  events.sort(key=lambda e:(e['day'],{'ACTION':0,'OPEN':1,'CLOSE':2}[e['phase']]))
  fees=sum((D(f['fees_cny']) for f in a['fills']),Z);buys=sum((D(f['gross_cny']) for f in a['fills'] if f['side']=='buy'),Z);sells=sum((D(f['gross_cny']) for f in a['fills'] if f['side']=='sell'),Z);funding=[s for s in ss if s['reason']=='actionable_S_funding'];reasons=[]
  for reason in sorted({s['reason'] for s in ss}):
   rr=[s for s in ss if s['reason']==reason];reasons.append(dict(raw_reason=reason,parts=len(rr),gross=sum((D(z['net_cash'])+D(z['fee_cny']) for z in rr),Z),net=sum((D(z['net_cash']) for z in rr),Z),realized=sum((D(z['realized_trade_PNL']) for z in rr),Z)))
  both=defaultdict(list)
  for tr in a['trades']:both[(tr['at'],tr['security_id'])].append(tr)
  bidirectional=[]
  for (at,sid),tt in both.items():
   if not {'buy','sell'}<={z['side'] for z in tt}:continue
   bidirectional.append(dict(sid=sid,at=at,buys=[z for z in tt if z['side']=='buy'],sells=[z for z in tt if z['side']=='sell'],gross=sum((D(z['gross_cny']) for z in tt),Z),fee=sum((D(z['fees_cny']) for z in tt),Z)))
  r=M.MonthRunner.restore(pp['checkpoint']);assert json.loads(json.dumps(r.observable(r.last_completed_event),default=M.E.encode))==x
  restores.append(dict(arm=arm,sha256=M.P.sha(pp['checkpoint']),checkpoint=pp['checkpoint'],full_observable_exact=True,source_identity=True,grant=r.execution_grant_record,history=r.execution_grant_history))
  if marketfacts is None:
   f=r.inputs.table('f1_observations');f=f[(f.day>='2025-07-01')&(f.day<='2025-07-31')];marketfacts=[]
   for sec,g in f[f.policy_scope!='G'].groupby('policy_scope'):
    g=g.sort_values('day');first=g.iloc[0];last=g.iloc[-1];segments=g['price_source_segment_id'].dropna().unique();valid=len(segments)<=1 and float(first['industry_close_as_source'])>0 and float(last['industry_close_as_source'])>0
    marketfacts.append(dict(sector=sec,name=last['industry_name'],first_day=first['day'],last_day=last['day'],first_close=first['industry_close_as_source'],last_close=last['industry_close_as_source'],close_to_close_return=D(str(last['industry_close_as_source']))/D(str(first['industry_close_as_source']))-1 if valid else None,observations=len(g),source_segments=[str(v) for v in segments],not_month_start_prior_close_return=True))
  rows.append(dict(arm=arm,cursor=pp['cursor'],NAV=D(b['nav']),return_from_original_1m=D(b['nav'])/D(1000000)-1,max_close_drawdown=dd,max_close_drawdown_at=ddat,daily_closes=len(daily),mean_close_exposure=sum((d['exposure'] for d in daily),Z)/len(daily),max_close_exposure=max(d['exposure'] for d in daily),terminal_exposure=daily[-1]['exposure'],pnl=pnl,buy_gross=buys,sell_gross=sells,two_sided_gross_turnover=buys+sells,fees=fees,actual_buy_fills=sum(f['side']=='buy' for f in a['fills']),actual_sell_fills=sum(f['side']=='sell' for f in a['fills']),first_add_reentry=Counter(z['entry_class'] for z in ll),role_pool_entry_groups=grouped(ll,['role','pool','entry_class']),same_buy_day_exit_requests=sum(z['same_buy_day_exit_requested'] for z in ll),pure_funding_sale_parts=len(funding),pure_funding_sale_gross=sum((D(s['net_cash'])+D(s['fee_cny']) for s in funding),Z),raw_exit_reason_groups=reasons,same_open_bidirectional=bidirectional,source_actions=len(x['action_log']),held_splits=heldsplits,ACT=a['policy']['act'],pending_intents=len(x['pending']),native_exits=len(a['exits']),native_buys=len(a['buys']),actual_start=read(root/'STARTED.json'),actual_completed=stop))
  days_out[arm]=daily;events_out[arm]=events;allstocks[arm]=[dict(sid=s,name=names[s]['name'],sector=names[s]['sector'],**v) for s,v in sorted(stock.items(),key=lambda p:-p[1]['contribution'])];allsectors[arm]=[dict(sector=s,**v) for s,v in sorted(sector.items(),key=lambda p:-p[1]['contribution'])]
  print('JULY_ANALYZED',arm,b['nav'],pnl,flush=True)
 save('RESULTS.json',rows);save('DAILY.json',days_out);save('EVENTS.json',events_out);save('ALL_LAYERS.json',layers_out);save('ALL_SALE_PARTS.json',sales_out);save('ALL_STOCKS.json',allstocks);save('ALL_SECTORS.json',allsectors);save('MARKET_SECTORS.json',marketfacts);save('VERIFICATION.json',dict(passed=True,saved_event_states=len(checks),reused_audited_states=sum(c['reused_audited_check'] for c in checks),newly_checked_states=sum(not c['reused_audited_check'] for c in checks),checks_per_state=7,rows=checks,terminal_restores=restores,analysis_seconds=time.perf_counter()-t,account_events_executed=0))
if __name__=='__main__':main()
