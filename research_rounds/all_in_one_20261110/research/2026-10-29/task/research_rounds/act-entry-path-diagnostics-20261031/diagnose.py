import time
START=time.monotonic()
from pathlib import Path
from datetime import datetime,time as tm,timezone
from decimal import Decimal as D
from collections import Counter,defaultdict
import json,gzip,csv,hashlib
import pandas as pd
import numpy as np
O=Path(__file__).resolve().parent;W=O.parent;R=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds');Z=D(0);ONE=D(1)

def read(p):return json.loads(Path(p).read_text())
def rows(p):return list(csv.DictReader(Path(p).open()))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def default(x):
 if isinstance(x,(D,datetime,pd.Timestamp)):return str(x)
 if isinstance(x,np.generic):return x.item()
 raise TypeError(type(x))
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2,default=default,allow_nan=False))
def export(p,x):pd.DataFrame(x).to_csv(p,index=False)
def stamp(s):return datetime.fromisoformat(s)
def close_at(day):return stamp(day+'T15:10:00+08:00')
def valid(v):return v is not None and pd.notna(v) and np.isfinite(float(v))

sources={
 'TECH':dict(account=R/'pvr-local-finite-capital-20261029/baseline/accounts-v2/I__S0_base.json',daily=R/'pvr-local-finite-capital-20261029/baseline/accounts-v2/daily.jsonl.gz',campaign=R/'pvr-local-finite-capital-20261029/baseline/analysis/campaigns.csv',path=W/'act-loss-facts-20261030/actual-holding-close-paths.csv',prep=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261027-153013-2ffe04/prepared'),aid='I__S0_base',policy=None,count=69),
 'DRUG':dict(account=R/'innovative-drug-local-recovery-20261028/S0/accounts-v2/ACT__S0_base.json',daily=R/'innovative-drug-local-recovery-20261028/S0/accounts-v2/daily.jsonl.gz',campaign=R/'innovative-drug-local-recovery-20261028/S0/analysis/campaigns.csv',path=W/'rearm-risk-boundary-drug84-20261030/ACTUAL_CLOSE_PATHS.csv',prep=R/'innovative-drug-sfw3-20261028/prepared',aid='ACT__S0_base',policy='ACT',count=84)}
identity={str(O/'PROTOCOL.txt'):sha(O/'PROTOCOL.txt'),str(Path(__file__)):sha(Path(__file__))};contexts={};checks=[]
for sec,ss in sources.items():
 for k in ['account','daily','campaign','path']:identity[str(ss[k])]=sha(ss[k])
 obj=read(ss['account']);logs=obj['audit_log'];ca=[x for x in rows(ss['campaign']) if x['scenario']=='base' and (ss['policy'] is None or x['policy']==ss['policy'])];assert len(ca)==ss['count'];cr={f"{x['symbol']}|{x['entry_at'][:10]}":x for x in ca};assert len(cr)==len(ca)
 with gzip.open(ss['daily'],'rt') as f:ds={x['at'][:10]:x for line in f if (x:=json.loads(line))['account']==ss['aid']}
 ps=defaultdict(list)
 for x in rows(ss['path']):ps[x['cycle_id']].append(x)
 assert set(ps)==set(cr)
 facts={};events={};signals={};epochs={}
 for sid in sorted({c['symbol'] for c in ca}):
  fp=ss['prep']/'facts'/f'{sid}.parquet';ep=R/'ph1-cross-sector-20261028/events'/sec/f'{sid}.parquet';sp=ss['prep']/'signals'/f'{sid}.parquet'
  for p in [fp,ep,sp]:identity[str(p)]=sha(p)
  f=pd.read_parquet(fp);facts[sid]=f;events[sid]=pd.read_parquet(ep);signals[sid]=pd.read_parquet(sp,columns=['observed_bar','source_invalid','synthetic_event_bar']);starts={};prev=False;prevseg=None;eid=None
  for t,v in f.iterrows():
   active=bool(v.e0_target);seg=int(v.segment_id)
   if active and (not prev or seg!=prevseg):eid=f'{sid}|source={seg}|E0={t.date()}'
   starts[t]=eid if active else None;prev=active;prevseg=seg
  epochs[sid]=starts
 contexts[sec]=dict(cr=cr,ps=ps,ds=ds,logs=logs,facts=facts,events=events,signals=signals,epochs=epochs)
save(O/'INPUT_IDENTITY.json',dict(captured_before_derived_path_summary=True,at=datetime.now(timezone.utc),sha256=identity))
allpath=[];allcycles=[];eventrows=[];transactionrows=[];checks=[]
legacy={r['cycle_id']:r for r in rows(W/'act-loss-facts-20261030/actual-cycles.csv')}

def analyze(sec,cid):
 cc=contexts[sec];camp=cc['cr'][cid];sid=camp['symbol'];entry=stamp(camp['entry_at']);closed=camp.get('closed','True')=='True';end=stamp(camp['exit_at']) if closed else close_at('2026-10-27');basis=D(camp['buy_gross'])+D(camp['buy_fees']);logs=cc['logs'];fills=[x for x in logs if x['kind']=='fill' and x['receipt']['security_id']==sid and entry<=stamp(x['receipt']['at'])<=end];bs=[x for x in fills if x['receipt']['side']=='buy'];sells=[x for x in fills if x['receipt']['side']=='sell'];assert len(bs)==int(camp.get('buy_fills','1'))==1;assert len(sells)==int(camp.get('sell_fills','1'))==int(closed)
 assert sum((D(x['receipt']['gross_cny'])+D(x['receipt']['fees_cny']) for x in bs),Z)==basis
 contracts=[x for x in logs if x['kind']=='entry_contract' and x['order_id']==bs[0]['order_id']];assert len(contracts)==1;co=contracts[0];floor0=D(co['floor_signal']);previousfloor=floor0;f=cc['facts'][sid];ev=cc['events'][sid];sg=cc['signals'][sid];entfactor=D(str(f.loc[pd.Timestamp(entry.date()),'factor']));initialraw=floor0/entfactor;initialdistance=1-initialraw/D(bs[0]['price']);hist=[];prevmax=None;prevmin=None;prevmaxday=None;prevminday=None;peak=basis;peakday='preinvestment_capital_reference';firstpos=None;firstback=None;unknown=[];upcount=0;floorraises=0
 for v in cc['ps'][cid]:
  day=v['day'];t=pd.Timestamp(day);q=int(v['shares']);assert q==int(cc['ds'][day]['positions'][sid]);rights=D(v['accrued_dividend']);mark=D(v['raw_mark']);pnl=D(v['nav_mark_pnl']);assert pnl==D(q)*mark+rights-basis
  native=t in f.index;er=ev.loc[t] if t in ev.index else None;state=f.loc[t] if native else None;priceknown=(v['mark_known_at'][:10]==day);observed=bool(t in sg.index and sg.loc[t,'observed_bar'] and not sg.loc[t,'source_invalid'] and not sg.loc[t,'synthetic_event_bar']);missing=not(native and er is not None and observed and priceknown)
  if missing:unknown.append(day)
  ret=pnl/basis;maxbefore=prevmax;minbefore=prevmin;ec=mark*D(str(state.factor)) if native else None;newfloor=D(str(state.i_floor)) if state is not None and valid(state.i_floor) else None;event=int(er.event) if er is not None else None
  if firstpos is None and ret>Z:firstpos=day
  if firstpos and day>firstpos and ret<Z and firstback is None:firstback=day
  raised=bool(newfloor is not None and newfloor>previousfloor);floorraises+=int(raised);upcount+=int(event==1)
  row=dict(sector=sec,cycle_id=cid,symbol=sid,name=camp['name'],day=day,at=str(close_at(day)),kind='holding_close',basis=basis,shares=q,raw_mark=mark,mark_known_at=v['mark_known_at'],dividend_equity=rights,net_pnl=pnl,net_return=ret,previous_highest_net_return=maxbefore,previous_lowest_net_return=minbefore,previous_highest_day=prevmaxday,previous_lowest_day=prevminday,previous_capital_peak_return=peak/basis-1,previous_capital_peak_day=peakday,drawdown_from_prior_capital_peak=min((pnl+basis)/peak-1,Z),drawdown_from_prior_positive_peak=min((pnl+basis)/peak-1,Z) if peak>basis else None,initial_floor_economic=floor0,old_floor_economic=previousfloor,new_floor_economic=newfloor,economic_mark=ec,old_floor_distance=1-previousfloor/ec if ec else None,new_floor_distance=1-newfloor/ec if ec and newfloor is not None else None,native_event=event,positive_confirmations_to_date=upcount,floor_raises_to_date=floorraises,I_valid=bool(state.i_target) if state is not None else None,source_unknown=missing,price_observation_known=priceknown,first_positive_seen=firstpos is not None,market_epoch=cc['epochs'][sid].get(t))
  hist.append(row)
  if newfloor is not None:previousfloor=newfloor
  
  if prevmax is None or ret>prevmax:prevmax=ret;prevmaxday=day
  if prevmin is None or ret<prevmin:prevmin=ret;prevminday=day
  if pnl+basis>peak:peak=pnl+basis;peakday=day
  if event not in [None,0]:eventrows.append(dict(sector=sec,cycle_id=cid,symbol=sid,name=camp['name'],confirmed_at=str(close_at(day)),event=event,pivot=er.get('pivot'),pivot_date=str(er.get('pivot_date')) if pd.notna(er.get('pivot_date')) else None,floor_before=row['old_floor_economic'],floor_after=newfloor,net_return=ret,source_unknown=missing))
 assert hist
 hmax=max(hist,key=lambda x:x['net_return']);hmin=min(hist,key=lambda x:x['net_return']);known=[x for x in hist if not x['source_unknown']];observedmax=max(known,key=lambda x:x['net_return']) if known else None;observedmin=min(known,key=lambda x:x['net_return']) if known else None;final=D(camp['net_pnl']);finalret=final/basis
 if closed:
  sf=sells[0];finalcheck=D(sf['receipt']['gross_cny'])-D(sf['receipt']['fees_cny'])+D(camp['dividends'])-basis;assert finalcheck==final
 else:assert D(hist[-1]['net_pnl'])==final
 assert D(hist[-1]['dividend_equity'])==D(camp['dividends'])
 terminal=dict(sector=sec,cycle_id=cid,symbol=sid,name=camp['name'],kind='actual_exit' if closed else 'unrealized_cutoff',at=str(end),net_pnl=final,net_return=finalret,fees=D(camp['sell_fees']) if closed else Z,shares=sells[0]['receipt']['shares'] if closed else int(camp['final_shares']))
 transactionrows.extend([dict(sector=sec,cycle_id=cid,kind='actual_'+x['receipt']['side'],**x['receipt'],execution_price=x['price'],raw_open=x['raw_open']) for x in fills]);transactionrows.append(dict(sector=sec,cycle_id=cid,symbol=sid,kind='entry_decision',at=co['decision_at'],floor=floor0))
 reqs=[x for x in logs if x['kind']=='exit_request' and x['sid']==sid and entry<=stamp(x['at'])<=end]
 for x in reqs:transactionrows.append(dict(sector=sec,cycle_id=cid,symbol=sid,kind='original_exit_request',at=x['at']))
 allmin=min((x['net_return'],x['at'],x['kind']) for x in hist+[terminal]);allmax=max((x['net_return'],x['at'],x['kind']) for x in hist+[terminal]);priorpositive=[x for x in hist if firstpos and x['day']<firstpos];afterpositive=[x for x in hist if firstpos and x['day']>=firstpos];first10=next((x['day'] for x in hist if x['net_return']>=D('.1')),None);below=[x for x in hist if x['net_return']<Z];last_run=longest=0
 for x in hist:
  last_run=last_run+1 if x['net_return']<Z else 0;longest=max(longest,last_run)
 stage='never_below_cost_on_recorded_closes' if hmin['net_return']>=Z else ('no_positive_close' if firstpos is None else ('before_first_positive_close' if hmin['day']<firstpos else 'after_first_positive_close'));leg=legacy.get(cid) if sec=='TECH' else None
 r=dict(sector=sec,cycle_id=cid,symbol=sid,name=camp['name'],industry=camp['industry'],entry_decision=co['decision_at'],entry_at=camp['entry_at'],exit_at=camp['exit_at'],endpoint=str(end),closed=closed,basis=basis,initial_shares=bs[0]['receipt']['shares'],exit_or_final_shares=terminal['shares'],buy_fills=len(bs),sell_fills=len(sells),economic_epoch=hist[0]['market_epoch'],initial_floor_economic=floor0,initial_floor_raw=initialraw,initial_floor_distance=initialdistance,final_net_pnl=final,final_net_return=finalret,final_group=('open' if not closed else ('loss' if final<0 else ('tail_profit_30pct' if finalret>=D('.3') else 'other_profit'))),holding_close_rows=len(hist),unknown_dates=json.dumps(unknown),unknown_count=len(unknown),MAE_close=hmin['net_return'],maximum_recorded_cost_below_loss=min(hmin['net_return'],Z),MAE_day=hmin['day'],MFE_close=hmax['net_return'],MFE_day=hmax['day'],MAE_including_actual_exit=allmin[0],MAE_all_at=allmin[1],MAE_all_kind=allmin[2],MFE_including_actual_exit=allmax[0],MFE_all_at=allmax[1],MFE_all_kind=allmax[2],known_observation_MAE=observedmin['net_return'] if observedmin else None,known_observation_MFE=observedmax['net_return'] if observedmax is not None else None,first_positive_close=firstpos,first_negative_after_positive=firstback,MAE_vs_first_positive=stage,MAE_before_first_positive=min((x['net_return'] for x in priorpositive),default=None),MAE_after_first_positive=min((x['net_return'] for x in afterpositive),default=None),positive_confirmations_at_MAE=hmin['positive_confirmations_to_date'],floor_raises_at_MAE=hmin['floor_raises_to_date'],prior_peak_return_at_MAE=hmin['previous_highest_net_return'],max_drawdown_from_prior_positive_peak=min((x['drawdown_from_prior_positive_peak'] for x in hist if x['drawdown_from_prior_positive_peak'] is not None),default=None),below_cost_close_rows=len(below),longest_recorded_below_cost_run=longest,first_plus10_close=first10,loss_after10_NAV=closed and final<0 and first10 is not None,legacy_loss_after10=leg['trajectory_class']=='loss_after_10pct' if leg else None,legacy_MFE_estimated_liquidation=D(leg['MFE_close']) if leg else None,legacy_MFE_NAV=D(leg['MFE_NAV_close']) if leg else None,old_NAV_MFE_difference=hmax['net_return']-D(leg['MFE_NAV_close']) if leg else None)
 return r,hist,terminal
# Fixed earliest entry, then code; no future-return choice.
samples=[]
for sec in ['TECH','DRUG']:
 cid=min(contexts[sec]['cr'],key=lambda c:(contexts[sec]['cr'][c]['entry_at'],c));r,_,_=analyze(sec,cid);samples.append(dict(sector=sec,cycle_id=cid,basis=r['basis'],final=r['final_net_pnl']))
eventrows.clear();transactionrows.clear();save(O/'SAMPLE_VERIFICATION.json',dict(passed=True,samples=samples,seconds=time.monotonic()-START));print('SAMPLES_PASS',time.monotonic()-START,flush=True)
for sec in ['TECH','DRUG']:
 for cid in sorted(contexts[sec]['cr'],key=lambda c:(contexts[sec]['cr'][c]['entry_at'],c)):
  r,h,t=analyze(sec,cid);allcycles.append(r);allpath.extend(h);allpath.append(t)
 net=sum((r['final_net_pnl'] for r in allcycles if r['sector']==sec),Z);expected=D(list(contexts[sec]['ds'].values())[-1]['nav'])-D(1000000);assert net==expected,(sec,net,expected);checks.append(dict(sector=sec,cycles=sum(r['sector']==sec for r in allcycles),cycle_net=net,account_net=expected,residual=Z));print(sec,'MONEY_EXACT',str(net),time.monotonic()-START,flush=True)
export(O/'CYCLE_PATH_FACTS.csv',allcycles);export(O/'DAILY_PATHS.csv',allpath);export(O/'NATIVE_CONFIRMATION_EVENTS.csv',eventrows);export(O/'ACTUAL_TRANSACTIONS.csv',transactionrows)
assert all(sha(p)==h for p,h in identity.items());save(O/'VERIFICATION.json',dict(passed=True,checks=checks,cycles=len(allcycles),close_rows=sum(r['kind']=='holding_close' for r in allpath),unknown_cycles=sum(bool(r['unknown_count']) for r in allcycles),unknown_rows=sum(r['unknown_count'] for r in allcycles),one_actual_buy_per_cycle=True,one_actual_sell_per_closed_cycle=True,no_new_trades=True,seconds=time.monotonic()-START));print('DONE',read(O/'VERIFICATION.json'),flush=True)
