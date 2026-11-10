"""One disclosed capital-sequence hypothesis. Bounded chosen paths, not native portfolio test."""
from pathlib import Path
import json,math,gzip,hashlib
import pandas as pd
import numpy as np
O=Path(__file__).resolve().parent
P=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared')
C=Path('/Users/bytedance/Documents/Codex/2026-11-04/task-3/entry_quality/daily_signal_cache_pilot20_v1/full_universe_v1/artifacts')
N=1200000.;SLIP=.0005
CASES=[('300085.SZ','2024-09-18','2024-10-14'),('002583.SZ','2024-09-18','2024-11-05'),('600675.SH','2022-04-07','2022-04-21'),('601298.SH','2023-04-25','2023-05-31')]
CONTRACT=dict(initial_equity=N,signal='Original ready I-buy OR fresh CP with I target. No new RR, probability, breakout-age, market-breadth, wait-days or truth/false-rally filter. Native market/industry Q and full universe not integrated in bounded paths.',initial_stop='Original I floor, raised to original fresh CP candidate if available; no added local-low filter.',risk_unit='.001*known_E/(1+same_stock_loss_debt/(.005*known_E)); freeze at signal, reduce if OPEN E lower.',campaign_principal_cap='min(first_probe_frozen_budget,current dynamic risk unit); never increased merely because price rises.',add='Fresh CP plus existing same-stock liquidation net U>0 at signal AND actual/proxy OPEN. New stop=max(old stop,I,fresh CP). Marginal risk <= min(.0025*E,.5*U,campaign_cap+old stress-net L). Thus L need not already be positive; combined campaign stress loss stays within original principal cap.',stress='X=S*exp(-2*s63)*(1-.0005), s63=1.4826*median(abs(prior63 log returns)); signal-day return excluded. Not worst-case loss or guaranteed sale.',trial_bucket='Shared T initially .01E; refill .0001 prior-close E each observed common day, cap .01 prior-close E. Actual negative realized campaign PnL debits fully; half positive realized PnL credits. Negative balance carried, not erased. All live principal risks and pending obligations consume it.',same_day='New buy gross<=.10*prior-close E, new probe risk<=.0025*prior-close E. Pending orders count.',account='Post-buy single-name gross<=.10 E, total gross<=.60 E, cash>=.10 E, total mark-to-stress giveback<=.05 E, total principal-at-stress risk<=max(0,T). Existing breaches stop new risk, do not pretend an immediate fill or force retrospective disposal.',debt='Per-stock D=max(0,D-realized campaign net PnL), retained across empty/reentry, no fixed freeze.',exits='Old common stock stop checked at CLOSE before raising it; break or native I off sells next OPEN. All campaign shares share stop, explicitly changes old CORE I-only holding. T+1 respected.',execution='Close fixes qcap, next OPEN only reduces. Near-upper-limit sensitivity refuses buys if O/priorC>=1.195 on 300085 or >=1.095 on the three main-board names. Near-lower-limit sells deferred when O/priorC<=.805 on 300085 or <=.905 on main-board cases; carry the exit order until an OPEN passes. Not exact PIT limit metadata. Otherwise O +/-5bp assumed; no HLV admissibility, no actual quotes/ACK/fills. Limits are conservative admissibility sensitivities, not lower bounds on PnL.',scope='Four already-seen isolated paths and the two 2024 names jointly. No original account initialization, no native full-account run, no parameter search, no OOS or validated-investment claim.',existing_comparison='Do not modify or conflate with original 1.2m PVR/E31 or separate no-losing-add single-variable experiment.')
(O/'FREEZE.json').write_text(json.dumps(CONTRACT,ensure_ascii=False,indent=2))
def fee(q,p,side,day):
 if not q:return 0.
 g=q*p;h=.0000487 if day<'2023-08-28'else .0000341;tr=.00002 if day<'2022-04-29'else .00001;stamp=(.001 if day<'2023-08-28'else .0005)if side=='sell'else 0.
 return max(5,g*.0002)+g*(h+.00002+tr+stamp)
def risk(q,p,x,day):return q*(p-x)+fee(q,p,'buy',day)+fee(q,x,'sell',day)
def qmax(cap,p,x,budget,day):
 q=int(max(0,cap)//100)*100
 while q>0 and risk(q,p,x,day)>budget+1e-7:q-=100
 return q
raw={};sig={};sources={}
for sid,start,end in CASES:
 rp=P/'bars'/f'{sid}.parquet';cp=C/f'{sid}.parquet';ap=P/'actions'/f'{sid}.json'
 r=pd.read_parquet(rp).set_index('trade_date');r.index=pd.to_datetime(r.index);r=r.sort_index();f=pd.read_parquet(cp).set_index('day');f.index=pd.to_datetime(f.index);f=f.reindex(r.index);scale=r.close/f.price__close
 f['Iraw']=f.native__i_floor*scale;f['CPraw']=f.cp__candidate*scale;f['s63']=1.4826*np.log(r.close/r.close.shift()).abs().shift().rolling(63).median()
 assert not [e for e in json.load(open(ap))['events']if start<=e['effective_date']<=end]
 raw[sid]=r;sig[sid]=f
 for p in [rp,cp,ap]:sources[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()

def run(cases,label):
 ids=[x[0]for x in cases];start=min(x[1]for x in cases);end=max(x[2]for x in cases);windows={s:(a,b)for s,a,b in cases};days=sorted(set().union(*(set(raw[s].loc[start:end].index)for s in ids)))
 st={s:dict(q=0,K=0.,S=None,vol=0.,D=0.,cap=0.,realized=0.,campaign=0)for s in ids};cash=N;bucket=.01*N;previousE=N;pending=[];orders=[];daily=[];account=[]
 def snapshot(marks,day,override=None):
  gross=principal=giveback=0.
  for sid,z in st.items():
   if not z['q']:continue
   M=marks[sid];q=z['q'];K=z['K'];S=z['S'];v=z['vol']
   if override and sid==override[0]:q,K,S,v=override[1:]
   X=min(S,M)*math.exp(-2*v)*(1-SLIP);V=q*X-fee(q,X,'sell',day);gross+=q*M;principal+=max(0,K-V);giveback+=max(0,q*M-V)
  if override and not st[override[0]]['q']:
   sid,q,K,S,v=override;M=marks[sid];X=min(S,M)*math.exp(-2*v)*(1-SLIP);V=q*X-fee(q,X,'sell',day);gross+=q*M;principal+=max(0,K-V);giveback+=max(0,q*M-V)
  return gross,principal,giveback
 def unit(s,E):return .001*E/(1+st[s]['D']/(.005*E))
 for t in days:
  day=str(t.date());op={s:float(raw[s].loc[t,'open'])if t in raw[s].index else float(raw[s].loc[:t].iloc[-1].close)for s in ids};cl={s:float(raw[s].loc[t,'close'])if t in raw[s].index else op[s]for s in ids}
  bucket=min(.01*previousE,bucket+.0001*previousE);todaygross=0.;todayrisk=0.;carry=[]
  for o in [x for x in pending if x['kind']=='sell']:
   s=o['sid'];z=st[s];q=z['q'];prev=float(raw[s].close.shift().loc[t])
   if op[s]/prev<=(.805 if s.startswith('300')else .905):
    carry.append(o);orders.append(dict(run=label,sid=s,day=day,signal=o['signal'],action='REJECT_SELL',reason='near_lower_limit_not_assumed_fill',q=q));continue
   p=op[s]*(1-SLIP);fees=fee(q,p,'sell',day);net=q*p-fees;pnl=net-z['K'];cash+=net;z['realized']+=pnl;z['D']=max(0,z['D']-pnl);bucket=bucket-max(0,-pnl)+.5*max(0,pnl);orders.append(dict(run=label,sid=s,day=day,signal=o['signal'],action='SELL',q=q,p=p,gross=q*p,fee=fees,pnl=pnl,bucket=bucket,debt=z['D'],campaign=z['campaign']));z.update(q=0,K=0.,S=None,cap=0.)
  for o in sorted([x for x in pending if x['kind']!='sell'],key=lambda x:(-x['pvr'],x['sid'])):
   s=o['sid'];z=st[s];E=cash+sum(v['q']*op[k]for k,v in st.items());Ecap=min(E,o['E']);p=op[s]*(1+SLIP);bid=op[s]*(1-SLIP);U=z['q']*bid-z['K']-fee(z['q'],bid,'sell',day);x=o['S']*math.exp(-2*o['vol'])*(1-SLIP);L=z['q']*x-z['K']-fee(z['q'],x,'sell',day);why=None
   prev=float(raw[s].close.shift().loc[t])
   if not np.isfinite(op[s])or op[s]<=o['S']:why='invalid_open_or_below_stop'
   elif op[s]/prev>=(1.195 if s.startswith('300')else 1.095):why='near_upper_limit_not_assumed_fill'
   elif o['kind']=='add' and U<=0:why='same_stock_liquidation_net_not_positive'
   gross0,pr0,gb0=snapshot(op,day)
   cap0=min(z['cap'],unit(s,Ecap))if o['kind']=='add'else unit(s,Ecap)
   budget=min(o['budget'],.0025*Ecap,.5*U,cap0+L)if o['kind']=='add'else min(o['budget'],cap0,max(0,bucket-pr0),max(0,.0025*previousE-todayrisk))
   q=0 if why else qmax(min(o['qcap'],int(max(0,.1*Ecap-z['q']*op[s])/p),int(max(0,.1*previousE-todaygross)/p)),p,x,max(0,budget),day)
   while q:
    fees=fee(q,p,'buy',day);newK=z['K']+q*p+fees;post=snapshot(op,day,(s,z['q']+q,newK,o['S'],o['vol']));eafter=E-q*(p-op[s])-fees
    passes=((z['q']+q)*op[s]<=.10*eafter+1e-7 and cash-q*p-fees>=.1*eafter-1e-7 and post[0]<=.60*eafter+1e-7 and post[1]<=max(0,bucket)+1e-7 and post[2]<=.05*eafter+1e-7 and newK-(z['q']+q)*x+fee(z['q']+q,x,'sell',day)<=cap0+1e-7)
    if passes:break
    q-=100
   if not q:orders.append(dict(run=label,sid=s,day=day,signal=o['signal'],action='REJECT',reason=why or 'risk_lot_or_account_budget',U=U,L=L,budget=budget,E=E));continue
   fees=fee(q,p,'buy',day);cash-=q*p+fees;z['q']+=q;z['K']+=q*p+fees;z['S']=o['S'];z['vol']=o['vol'];todaygross+=q*p
   if o['kind']=='probe':z['campaign']+=1;z['cap']=cap0;todayrisk+=risk(q,p,x,day)
   orders.append(dict(run=label,sid=s,day=day,signal=o['signal'],action=o['kind'].upper(),q=q,p=p,gross=q*p,fee=fees,total_q=z['q'],total_cost=z['K'],E=E,U=U,L=L,stop=z['S'],stress=x,budget=budget,risk=risk(q,p,x,day),campaign_principal_cap=cap0,post_campaign_stress_loss=max(0,z['K']-z['q']*x+fee(z['q'],x,'sell',day)),bucket=bucket,debt=z['D'],campaign=z['campaign']))
   assert o['kind']!='add'or U>0
  pending=carry;E=cash+sum(v['q']*cl[k]for k,v in st.items());bucket=min(bucket,.01*E)
  for s,z in st.items():
   if t not in raw[s].index:continue
   f=sig[s].loc[t];C0=cl[s];v=float(f.s63);native=bool((f.native__i_buy==True or f.cp__receipt==True)and f.native__i_target==1 and f.native__e0_ready==1 and f.native__g_ready==True);fresh=f.cp__receipt==True
   if any(o['sid']==s for o in carry):pass
   elif z['q'] and (C0<=z['S']or f.native__i_target!=1):pending.append(dict(sid=s,kind='sell',signal=day))
   else:
    S=max([z['S']or 0.,float(f.Iraw)if np.isfinite(f.Iraw)else 0.,float(f.CPraw)if fresh and np.isfinite(f.CPraw)else 0.])
    if z['q']:z['S']=S;z['vol']=v
    U=z['q']*C0*(1-SLIP)-z['K']-fee(z['q'],C0*(1-SLIP),'sell',day);X=S*math.exp(-2*v)*(1-SLIP);L=z['q']*X-z['K']-fee(z['q'],X,'sell',day)
    eligible=(z['q']>0 and fresh and U>0)or(z['q']==0 and native)
    if eligible and windows[s][0]<=day<windows[s][1] and S>0 and C0>S:
     cap0=min(z['cap'],unit(s,E))if z['q']else unit(s,E);budget=min(.0025*E,.5*U,cap0+L)if z['q']else min(cap0,max(0,bucket-snapshot(cl,day)[1]));p=C0*(1+SLIP);qcap=qmax(int(max(0,.1*E-z['q']*C0)/p),p,X,max(0,budget),day)
     if qcap:pending.append(dict(sid=s,kind='add'if z['q']else'probe',signal=day,S=S,vol=v,qcap=qcap,budget=budget,E=E,pvr=float(f.pvr__score)if np.isfinite(f.pvr__score)else -1.))
   currentX=min(z['S'],C0)*math.exp(-2*v)*(1-SLIP)if z['q']else 0.;stress=z['q']*currentX-z['K']-fee(z['q'],currentX,'sell',day)
   daily.append(dict(run=label,sid=s,day=day,q=z['q'],mark=C0,nominal=z['q']*C0,cost=z['K'],unrealized=z['q']*C0-z['K'],realized=z['realized'],stock_total_pnl=z['realized']+z['q']*C0-z['K'],stress_scenario_pnl=stress,stop=z['S'],debt=z['D'],next_risk_unit=unit(s,E),equity=E,bucket=bucket))
  gross,pr,gb=snapshot(cl,day);account.append(dict(run=label,day=day,equity=E,cash=cash,bucket=bucket,gross=gross,principal_stress_risk=pr,giveback_stress_risk=gb,new_gross=todaygross,new_probe_risk=todayrisk));previousE=E
  assert abs(E-(N+sum(z['realized']+z['q']*cl[s]-z['K']for s,z in st.items())))<1e-6
 ar=pd.DataFrame(account);reports=[]
 for s,z in st.items():
  d=pd.DataFrame(daily);d=d[d.sid.eq(s)];oo=[o for o in orders if o['sid']==s];reports.append(dict(run=label,sid=s,realized=z['realized'],ending_q=z['q'],ending_marked_pnl=float(d.iloc[-1].stock_total_pnl),contribution_to_initial_1200000=float(d.iloc[-1].stock_total_pnl/N),max_nominal=float(d.nominal.max()),max_nominal_fraction_of_dynamic_E=float((d.nominal/d.equity).max()),max_q=int(d.q.max()),max_unrealized=float(d.unrealized.max()),probes=sum(o['action']=='PROBE'for o in oo),adds=sum(o['action']=='ADD'for o in oo),sells=sum(o['action']=='SELL'for o in oo),end_loss_debt=z['D']))
 reports.append(dict(run=label,sid='ACCOUNT_CASES_ONLY',ending_equity=float(ar.iloc[-1].equity),total_pnl=float(ar.iloc[-1].equity-N),max_gross=float(ar.gross.max()),max_gross_fraction=float((ar.gross/ar.equity).max()),max_principal_stress_risk=float(ar.principal_stress_risk.max()),max_giveback_stress_risk=float(ar.giveback_stress_risk.max()),minimum_trial_bucket=float(ar.bucket.min()),max_drawdown=float((ar.equity/ar.equity.cummax()-1).min())))
 return orders,daily,account,reports
orders=[];daily=[];accounts=[];summary=[]
for case in CASES:
 o,d,a,s=run([case],case[0]);orders+=o;daily+=d;accounts+=a;summary+=s
for label,cases in [('JOINT_2024_AUTUMN',CASES[:2])]:
 o,d,a,s=run(cases,label);orders+=o;daily+=d;accounts+=a;summary+=s
pd.DataFrame(orders).to_csv(O/'ORDERS.csv',index=False);pd.DataFrame(daily).to_csv(O/'DAILY.csv',index=False);pd.DataFrame(accounts).to_csv(O/'ACCOUNT_CASES_ONLY.csv',index=False);(O/'SUMMARY.json').write_text(json.dumps(summary,indent=2));(O/'SOURCE_SHA256.json').write_text(json.dumps(sources,indent=2));print(json.dumps(summary,indent=2));print(pd.DataFrame(orders)[pd.DataFrame(orders).action.ne('REJECT')][['run','sid','day','action','q','gross','pnl','U','L','budget','debt']].to_string(index=False))
