"""Conditional close/next-OPEN arithmetic per fixed receipt. No ranking award or actual account admission."""
from pathlib import Path
from decimal import Decimal as D
import json,sys
import pandas as pd,numpy as np
O=Path(__file__).resolve().parent;E=O.parent
U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
B=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025');sys.path.insert(0,str(B/'code'))
from market_rules import version_on,market_identity_on,RuleUnavailable
from sector_account import QuantityRule,FeeComponent,FeeSchedule
rules=json.loads((B/'inputs-v2/market-rules.json').read_text());proxies=json.loads((B/'inputs-v2/economic-protocol.json').read_text())['approved_proxy_ids'];meta={}
def getmeta(sid,d):
 key=(sid,str(d.date()))
 if key not in meta:
  day=key[1];ident=market_identity_on(rules,sid,day,proxies);v=version_on(rules['fee_versions'][ident['venue']],day,proxies)['schedule'];meta[key]=(QuantityRule(**version_on(rules['quantity_versions'][sid],day,proxies)['rule']),FeeSchedule(v['schedule_id'],tuple(FeeComponent(**x) for x in v['components'])),D(str(rules['security_metadata'][sid]['par_value'])))
 return meta[key]
def fee(q,p,fs,side,par):return sum(fs.incremental(side,D(q)*p,{}, {},1,shares=q,par_value=par).values(),D(0))
def size(sid,d,px,fl,cap):
 qr,fs,par=getmeta(sid,d);q=qr.buy_floor(min(int(D(24000)/px),int(cap)))
 while q>0:
  bf=fee(q,px,fs,'buy',par);sf=fee(q,fl*D('.9995'),fs,'sell',par);risk=max(D(0),q*(px-fl*D('.9995'))+bf+sf)
  if q*px+bf<=24000 and risk<=3000:return q,bf,risk
  q=qr.buy_floor(q-1)
 return 0,D(0),D(0)
ev=pd.read_csv(O/'RECEIPTS.csv',parse_dates=['day','arm_day']);ev=ev[ev.arm.eq('CACHED')].copy()
sm={x['symbol']:x for x in json.loads((U/'STOCK_MANIFEST.json').read_text())};im=json.loads((U/'INDUSTRY_MANIFEST.json').read_text())
cal=pd.DatetimeIndex(sorted(set().union(*[set(pd.read_parquet(x['refs']['CP1_input'],columns=[]).index) for x in im])));cal=cal[cal<=pd.Timestamp('2026-06-30')];di={d:i for i,d in enumerate(cal)}
old=pd.read_csv(E/'lifecycle_v1/ROUNDS.csv',parse_dates=['signal_day','entry_day','exit_day','status_day'],float_precision='round_trip')
old=old[old.arm.eq('A_UNION_B')]
dec=pd.read_csv(E/'lifecycle_v1/DECISIONS.csv',parse_dates=['day']);dec=dec[dec.arm.eq('A_UNION_B')]
pvr=pd.read_parquet(E.parent/'pvr_persistence_breadth_v1/STOCK_DAILY.parquet').set_index(['sid','day'])
def oldstate(win,sid,d):
 g=old[old.window.eq(win)&old.sid.eq(sid)].sort_values('signal_day')
 for r in g.itertuples():
  if r.signal_day>=d:continue
  if 'UNKNOWN' in r.status and r.status_day<=d:return 'UNKNOWN',r.round_id
  if r.entry_status=='CONDITIONAL_OPEN_PROXY':
   if r.entry_day>d:return 'BUY_PENDING',r.round_id
   if r.status=='COMPLETE_CONDITIONAL_STOCK_ROUND' and r.exit_day<=d:continue
   return 'HELD',r.round_id
  if r.status_day>d:return 'BUY_PENDING',r.round_id
 return 'FLAT',None
out=[];raw={}
for rr in ev.to_dict('records'):
 sid=rr['sid'];d=rr['day'];u=rr['arm_day']
 if sid not in raw:
  sp=next(p for p in sm[sid]['source_sha256'] if p.endswith('/signal.parquet'));raw[sid]=pd.read_parquet(sp).loc[:'2026-06-30']
 p=raw[sid];r=p.loc[d];factor=D(str(r.adjustment_factor));floor=D(str(rr['i_floor']))/factor
 z=dict(rr);z['floor_raw']=float(floor);z['arm_PVR_score']=pvr.loc[(sid,u),'score'] if (sid,u) in pvr.index else np.nan
 z['reference_old_state_at_arm'],z['reference_old_blocker_at_arm']=oldstate(rr['window'],sid,u)
 z['reference_old_state_at_receipt'],z['reference_old_blocker_at_receipt']=oldstate(rr['window'],sid,d)
 dd=dec[dec.window.eq(rr['window'])&dec.sid.eq(sid)&dec.day.eq(d)]
 z['reference_old_decision']=dd.decision.iloc[0] if len(dd) else 'NO_OLD_BIRTH'
 z['reference_only_NOT_new_model_state']=True
 vol=p.loc[:d,'raw_volume'];vol=vol[vol.gt(0)];cap=int(vol.iloc[-20:].mean()*.01) if len(vol)>=20 else None
 if cap is None:z['close_status']='CAPACITY_UNKNOWN';out.append(z);continue
 if D(str(r.raw_close))<=floor:z['close_status']='CLOSE_BELOW_FLOOR';out.append(z);continue
 try:cq,cf,cr=size(sid,d,D(str(r.raw_close))*D('1.0005'),floor,cap)
 except (RuleUnavailable,KeyError,ValueError):z['close_status']='DATED_RULE_UNKNOWN';out.append(z);continue
 z.update(close_q=cq,close_plan_risk=float(cr),close_status='PASS' if cq>0 else 'MIN_LOT_OR_PLAN_RISK_REJECT')
 if not cq:out.append(z);continue
 if di[d]+1>=len(cal):z['open_status']='NO_NEXT_OPEN_CENSORED';out.append(z);continue
 od=cal[di[d]+1];z['earliest_open_day']=od;q=p.reindex([od]).iloc[0]
 if not np.isfinite(q.raw_open) or q.raw_open<=0:z['open_status']='OPEN_UNKNOWN';out.append(z);continue
 if tuple(str(q[c]) for c in ['source_kind','source_path','segment_id'])!=tuple(str(r[c]) for c in ['source_kind','source_path','segment_id']):z['open_status']='SOURCE_CHANGE_UNKNOWN';out.append(z);continue
 if not np.isclose(q.adjustment_factor,r.adjustment_factor,rtol=1e-11):z['open_status']='FACTOR_CHANGE_UNKNOWN';out.append(z);continue
 op=D(str(q.raw_open))
 if op<=floor:z['open_status']='BELOW_FLOOR_NOFILL';out.append(z);continue
 oq,of,orr=size(sid,od,op*D('1.0005'),floor,cap)
 z.update(open_status='CONDITIONAL_OPEN_PROXY' if oq else 'MIN_LOT_NOFILL',open_q=oq,raw_open=float(op),buy_price=float(op*D('1.0005')),buy_fee=float(of),planned_floor_loss=float(orr),historical_orderability='UNKNOWN',full_market_rank_award='NOT_COMPUTED')
 out.append(z)
x=pd.DataFrame(out);x.to_csv(O/'CONDITIONAL_OPEN_PATHS.csv',index=False)
print(x[x.receipt_type.eq('DEFERRED')|((x.sid=='300570.SZ')&(x.day==pd.Timestamp('2024-09-25')))][['window','sid','name','arm_day','day','receipt_type','arm_PVR_score','PVR_score','floor_raw','close_status','earliest_open_day','open_status','open_q','raw_open','buy_price','buy_fee','planned_floor_loss','reference_old_state_at_arm','reference_old_state_at_receipt','reference_old_decision']].to_string(index=False))
