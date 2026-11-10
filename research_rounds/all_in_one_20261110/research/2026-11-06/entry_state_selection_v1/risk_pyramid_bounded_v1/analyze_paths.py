"""Four isolated 1.2m paper paths, not an account backtest or tradability claim."""
from pathlib import Path
import json,gzip,hashlib,math
import pandas as pd
import numpy as np
O=Path(__file__).resolve().parent
P=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared')
C=Path('/Users/bytedance/Documents/Codex/2026-11-04/task-3/entry_quality/daily_signal_cache_pilot20_v1/full_universe_v1/artifacts')
B=Path('/Users/bytedance/Documents/Codex/2026-11-04/task-3/entry_quality/trend_exit_controls_v1/runs/BASELINE/2022_2024/pair')
N=1200000.;SLIP=.0005
CASES=[('300085.SZ','2024-09-18','2024-10-11'),('002583.SZ','2024-09-18','2024-11-05'),('600675.SH','2022-04-07','2022-04-21'),('601298.SH','2023-04-25','2023-05-31')]
CONTRACT=dict(capital=N,initial_risk=.001,trial_bucket_cap=.01,daily_refill=.0001,realized_win_refill=.5,loss_brake_scale=.005,add_financing_fraction=.5,add_max_risk=.0025,stock_cap=.10,slippage=SLIP,
 initial_stop='max(native I floor, prior5 raw lows minus .25 prior20ATR); excludes signal day from windows',stress='X=S*exp(-2*s63)*(1-.0005), s63=1.4826*median(abs(prior63 log returns)), exclude signal-day return',
 entry='flat: original ready I buy, new initial risk budget=min(.001*N/(1+D/(.005*N)), free trial balance). Native universe/rank/industry/cash not integrated',
 exit='At CLOSE test old campaign S before updating; C<=S or native I off queues all shares for immediately next common OPEN; one-day T+1 satisfied; no intraday stop fill.',
 protection='If survived, S=max(old S,native I,current fresh CP candidate), never lowered. This applies to ALL shares and intentionally changes original CORE I-only holding rule.',
 add='Fresh CP, C above previous add signal C; existing real Q>0. L=Q*X-K-sellfees(Q,X)>0. New q risk<=min(.5*L,.0025*N); same frozen S/s at next OPEN; no borrowed profit from other stocks.',
 execution='Signal CLOSE freezes qty cap. Next positive OPEN can reduce, never enlarge. O<=S rejects. Missing O no roll-forward. OPEN +/-5bp is an optimistic daily price proxy, no queue/fill proof, no use of HLV for eligibility.',
 cumulative='D=max(0,D-realized campaign net PnL). Bucket refills each common day by .0001*N, plus .5 positive realized PnL, cap .01*N; debit realized negative PnL. Pending/live initial risk reserved until actual exit; no fixed cooldown. Negative bucket is carried as deficit, never reset to zero.',
 evidence='All history already seen, four chosen cases; parameters designed now, not OOS; not comparison of 1.2m complete accounts; original account is 1m-start historical baseline, never mechanically scaled.',
 exclusions='No original sector/probe pool/portfolio cash/rank feedback, no current pool replacement, no actual intraday quotes/fills, no correlated gap guarantee; these individual windows have no raw corporate action.')
(O/'PREDECLARED.json').write_text(json.dumps(CONTRACT,ensure_ascii=False,indent=2))
source={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def fee(q,p,side,day):
 gross=q*p
 # Original account dated fees. SZ/SH same schedule in these four cases.
 handling=.0000487 if day<'2023-08-28' else .0000341
 transfer=.00002 if day<'2022-04-29' else .00001
 stamp=(.001 if day<'2023-08-28' else .0005) if side=='sell' else 0
 return max(5,gross*.0002)+gross*(handling+.00002+transfer+stamp) if q else 0.
def risk(q,p,x,day):return q*(p-x)+fee(q,p,'buy',day)+fee(q,x,'sell',day)
def maxq(cap,p,x,budget,day):
 n=int(cap//100)*100
 while n>0 and risk(n,p,x,day)>budget+1e-8:n-=100
 return n
raws={};signals={}
def get(sid):
 if sid in raws:return raws[sid],signals[sid]
 rp=P/'bars'/f'{sid}.parquet';cp=C/f'{sid}.parquet'
 raw=pd.read_parquet(rp).set_index('trade_date');raw.index=pd.to_datetime(raw.index);raw=raw.sort_index()
 f=pd.read_parquet(cp).set_index('day');f.index=pd.to_datetime(f.index);f=f.reindex(raw.index)
 f['scale_to_raw']=raw.close/f.price__close
 f['Iraw']=f.native__i_floor*f.scale_to_raw;f['CPraw']=f.cp__candidate*f.scale_to_raw
 tr=pd.concat([raw.high-raw.low,(raw.high-raw.close.shift()).abs(),(raw.low-raw.close.shift()).abs()],axis=1).max(axis=1)
 f['atr']=tr.shift().rolling(20).mean();f['low5']=raw.low.shift().rolling(5).min()
 lr=np.log(raw.close/raw.close.shift()).abs();f['s63']=1.4826*lr.shift().rolling(63).median()
 for p in [rp,cp,P/'actions'/f'{sid}.json']:source[str(p)]=sha(p)
 raws[sid]=raw;signals[sid]=f;return raw,f
allrows=[];allorders=[];summaries=[]
for sid,start,end in CASES:
 raw,f=get(sid);q=0;cost=0.;stop=None;pending=None;bucket=.01*N;D=0.;reserved=0.;realized=0.;lastadd=-math.inf;campaign=0;daily=[];orders=[];prev_day=None;first=True
 actions=json.loads((P/'actions'/f'{sid}.json').read_text())['events'];assert not [e for e in actions if start<=e['effective_date']<=end],(sid,'Corporate action requires explicit accounting')
 for t in raw.loc[start:end].index:
  day=str(t.date());r=raw.loc[t];s=f.loc[t];bucket=min(.01*N,bucket+.0001*N)
  if pending is not None:
   o=pending;pending=None;op=float(r.open);x=o['S']*math.exp(-2*o['s63'])*(1-SLIP)
   if o['kind']=='sell':
    p=op*(1-SLIP);net=q*p-fee(q,p,'sell',day);pnl=net-cost;realized+=pnl;D=max(0.,D-pnl);bucket=min(.01*N,bucket-max(0,-pnl)+.5*max(0,pnl));orders.append(dict(sid=sid,day=day,signal=o['signal'],action='SELL',q=q,p=p,gross=q*p,fee=fee(q,p,'sell',day),net_pnl=pnl,stop=stop,stress_stop=x,bucket=bucket,D=D,campaign=campaign));q=0;cost=0.;reserved=0.;stop=None;lastadd=-math.inf
   elif not np.isfinite(op) or op<=o['S']:
    orders.append(dict(sid=sid,day=day,signal=o['signal'],action='REJECT_OPEN',q=0,reason='missing_open_or_at_below_stop',campaign=campaign))
   else:
    p=op*(1+SLIP)
    L=q*x-cost-fee(q,x,'sell',day)
    budget=o['budget'] if o['kind']=='probe' else min(o['budget'],.5*max(0,L))
    cap=min(o['cap'],max(0,int((.10*N-q*op)/p)))
    z=maxq(cap,p,x,budget,day)
    if z:
     bfee=fee(z,p,'buy',day);q+=z;cost+=z*p+bfee
     if o['kind']=='probe':campaign+=1;reserved=risk(z,p,x,day)
     stop=o['S'];lastadd=o['signal_C'];orders.append(dict(sid=sid,day=day,signal=o['signal'],action=o['kind'].upper(),q=z,p=p,gross=z*p,fee=bfee,total_q=q,total_cost=cost,budget=budget,risk=risk(z,p,x,day),stop=stop,stress_stop=x,protected_net_before=L,protected_net_after=q*x-cost-fee(q,x,'sell',day),bucket=bucket,D=D,campaign=campaign,flat_OHLC_ex_post=bool(r.high==r.low)))
    else:orders.append(dict(sid=sid,day=day,signal=o['signal'],action='REJECT_SIZE',q=0,budget=budget,campaign=campaign))
  # CLOSE: execution has already finished; old protection tested first.
  if q and (float(r.close)<=stop or s.native__i_target!=1):
   pending=dict(kind='sell',S=stop,s63=float(s.s63),signal=day)
  elif q:
   stop=max(stop,float(s.Iraw) if np.isfinite(s.Iraw) else stop)
   if s.cp__receipt==True and np.isfinite(s.CPraw):stop=max(stop,float(s.CPraw))
   if s.cp__receipt==True and float(r.close)>lastadd and np.isfinite(s.s63):
    x=stop*math.exp(-2*float(s.s63))*(1-SLIP);L=q*x-cost-fee(q,x,'sell',day);budget=min(.0025*N,.5*max(0,L));p=float(r.close)*(1+SLIP);cap=maxq(max(0,int((.10*N-q*float(r.close))/p)),p,x,budget,day)
    if cap:pending=dict(kind='add',S=stop,s63=float(s.s63),signal=day,signal_C=float(r.close),cap=cap,budget=budget)
  elif s.native__i_buy==True and s.native__i_target==1 and s.native__e0_ready==1 and s.native__g_ready==True and np.isfinite(s.s63):
   S=max(float(s.Iraw),float(s.low5)-.25*float(s.atr));p=float(r.close)*(1+SLIP);x=S*math.exp(-2*float(s.s63))*(1-SLIP);budget=min(.001*N/(1+D/(.005*N)),max(0,bucket-reserved));cap=maxq(int(.10*N/p),p,x,budget,day)
   if cap:pending=dict(kind='probe',S=S,s63=float(s.s63),signal=day,signal_C=float(r.close),cap=cap,budget=budget)
  mark=q*float(r.close);daily.append(dict(sid=sid,day=day,open=float(r.open),high=float(r.high),low=float(r.low),close=float(r.close),q=q,cost=cost,unrealized=mark-cost,realized=realized,combined_pnl=realized+mark-cost,stop=stop,bucket=bucket,debt=D,reserved_trial_risk=reserved,pending_kind=pending['kind'] if pending else '',native_i_buy=s.native__i_buy,cp_receipt=s.cp__receipt))
 ds=pd.DataFrame(daily);eq=N+ds.combined_pnl;dd=(eq/eq.cummax()-1).min();summary=dict(sid=sid,start=start,end=end,initial_capital=N,realized=realized,ending_q=q,ending_unrealized=float(ds.iloc[-1].unrealized),ending_marked_pnl=float(ds.iloc[-1].combined_pnl),max_drawdown_fraction=float(dd),max_gross_exposure=float((ds.q*ds.close).max()),max_shares=int(ds.q.max()),probes=sum(o['action']=='PROBE' for o in orders),adds=sum(o['action']=='ADD' for o in orders),sells=sum(o['action']=='SELL' for o in orders),unknown_flat_fills=sum(o.get('flat_OHLC_ex_post',False) for o in orders),ending_bucket=bucket,ending_loss_debt=D)
 summaries.append(summary);allrows+=daily;allorders+=orders
# Original ledger: exact historical amounts, with initial-capital provenance.
a=json.load(gzip.open(B/'B.json.gz','rt'));orig=[]
for sid,start,end in CASES:
 for tr in a['trades']:
  if tr['security_id']==sid and start<=tr['at'][:10]<=end:orig.append(tr)
# Full repeated-failure and winner chains retain their complete ledger dates.
for sid,year in [('600675.SH','2022'),('601298.SH','2023')]:
 for tr in a['trades']:
  if tr['security_id']==sid and tr['at'].startswith(year) and tr not in orig:orig.append(tr)
source[str(B/'B.json.gz')]=sha(B/'B.json.gz')
pd.DataFrame(allrows).to_csv(O/'DAILY_PAPER_PATHS.csv',index=False)
pd.DataFrame(allorders).to_csv(O/'PAPER_ORDERS.csv',index=False)
(O/'SUMMARY.json').write_text(json.dumps(summaries,ensure_ascii=False,indent=2))
(O/'ORIGINAL_LEDGER_EXCERPTS.json').write_text(json.dumps(dict(initial_capital=1000000,not_1200000_scaled=True,trades=orig),ensure_ascii=False,indent=2))
(O/'SOURCE_SHA256.json').write_text(json.dumps(source,indent=2))
print(json.dumps(summaries,ensure_ascii=False,indent=2))
print(pd.DataFrame(allorders).to_string(index=False))
# Verify legal units, accounting, and same-window corporate actions; not a portfolio validation.
orders=pd.DataFrame(allorders)
assert ((orders.loc[orders.action.isin(['PROBE','ADD','SELL']),'q']%100)==0).all()
for sid,g in orders.groupby('sid'):
 buys=g[g.action.isin(['PROBE','ADD'])];sells=g[g.action=='SELL'];delta=(sells.gross-sells.fee).sum()-(buys.gross+buys.fee).sum();sm=next(x for x in summaries if x['sid']==sid);assert sm['ending_q']==0 and abs(delta-sm['realized'])<1e-7
 for _,o in buys.iterrows():assert o.day>o.signal and o.risk<=o.budget+1e-7
assert all(o['protected_net_after']>0 for o in allorders if o['action']=='ADD')
# Add explicit daily protected vs marked profit; X is a stress scenario, never guaranteed executable proceeds.
for row in allrows:
 sid=row['sid'];day=pd.Timestamp(row['day']);f=signals[sid];x=row['stop']*math.exp(-2*float(f.loc[day,'s63']))*(1-SLIP) if row['q'] else 0.
 row['stress_exit_value']=row['q']*x-fee(row['q'],x,'sell',row['day']);row['stress_scenario_pnl']=row['stress_exit_value']-row['cost'];row['marked_profit_above_stress_scenario']=row['unrealized']-row['stress_scenario_pnl'];row['nominal_equity_fraction']=row['q']*row['close']/N;row['paper_pnl_fraction_of_1200000']=row['combined_pnl']/N
pd.DataFrame(allrows).to_csv(O/'DAILY_PAPER_PATHS.csv',index=False)
(O/'CHECKS.json').write_text(json.dumps(dict(lot_units=True,cashflow_reconciles=True,next_day_only=True,budget_at_proxy=True,positive_preadd_stress_profit=True,whole_account_test=False,actual_tradability_certified=False,fee_scope='verified original 2022/2023/2024 schedules for these cases',version='one frozen economic design, bounded development evidence only'),indent=2))
