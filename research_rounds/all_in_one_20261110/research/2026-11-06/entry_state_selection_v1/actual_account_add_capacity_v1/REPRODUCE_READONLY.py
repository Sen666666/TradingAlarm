import json,gzip,csv,sys,collections
from pathlib import Path
from decimal import Decimal as D
import pandas as pd
sys.dont_write_bytecode=True
base=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1/account_comparison_continuous_v1')
root=base/'no_loss_add_v1/run_1200000/pair'
a=json.load(gzip.open(root/'PVR.json.gz','rt'))
ds={x['at'][:10]:x for line in gzip.open(root/'daily.jsonl.gz','rt') if (x:=json.loads(line))['account']=='PVR'}
day='2024-09-25'; d=ds[day]; old=ds['2024-09-23']
sm={x['symbol']:x for x in json.load(open('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json'))}
master={x['symbol']:x for x in csv.DictReader(open('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/data-adjudicated-v2/master-input.csv'))}
rb=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025')
sys.path.insert(0,str(rb/'code'))
from market_rules import version_on,market_identity_on
from sector_account import QuantityRule,FeeComponent,FeeSchedule
rules=json.load(open(rb/'inputs-v2/market-rules.json'));proxies=json.load(open(rb/'inputs-v2/economic-protocol.json'))['approved_proxy_ids']
def fee(sid,q,px,dt,side='sell'):
 ident=market_identity_on(rules,sid,dt,proxies); v=version_on(rules['fee_versions'][ident['venue']],dt,proxies)['schedule']; fs=FeeSchedule(v['schedule_id'],tuple(FeeComponent(**x) for x in v['components']));par=D(str(rules['security_metadata'][sid]['par_value']))
 return sum(fs.incremental(side,D(q)*px,{}, {},1,shares=q,par_value=par).values(),D(0)) if q else D(0)
state={}
for j in a['journal']:
 if j['at'][:10]>day:break
 k=j['kind']
 if k not in ['real_buy_fill','real_sell_fill','actual_split']:continue
 sid=j['sid'];s=state.setdefault(sid,dict(q=0,cost=D(0),opened=None,n_buy=0))
 if k=='real_buy_fill':
  if not s['q']:s.update(cost=D(0),opened=j['at'][:10],n_buy=0)
  s['q']+=j['shares'];s['cost']+=D(j['shares'])*D(j['price'])+D(j['fees']);s['n_buy']+=1
 elif k=='real_sell_fill':
  s['cost']*=D(s['q']-j['shares'])/D(s['q']);s['q']-=j['shares']
 else:s['q']=int(D(s['q'])*D(j['ratio']))
assert {sid:s['q'] for sid,s in state.items() if s['q']}==d['positions']
raw={}
def getraw(sid):
 if sid not in raw: raw[sid]=pd.read_parquet(next(p for p in sm[sid]['source_sha256'] if p.endswith('/signal.parquet')))
 return raw[sid]
def px(sid,dt,col='raw_close'):
 p=getraw(sid);return D(str(p.loc[:dt].iloc[-1][col]))
def cohort_value(layers,dt):
 ids={x['id'] for x in layers};remain={x['id']:x for x in ds[dt]['layers']}
 mark=sum(D(remain[x]['qty'])*px(remain[x]['sid'],dt) for x in ids if x in remain)
 sell=sum(D(p['net_cash']) for j in a['journal'] if j['kind']=='real_sell_fill' and day<j['at'][:10]<=dt for p in j['parts'] if p['layer'] in ids)
 return mark+sell
records=[]
for sid,q in d['positions'].items():
 ls=[x for x in d['layers'] if x['sid']==sid];s=state[sid];mark=D(q)*px(sid,day);netmark=D(q)*px(sid,day)*D('.9995')-fee(sid,q,px(sid,day)*D('.9995'),day)
 prevls=[x for x in ls if x['opened'][:10]<'2024-09-24'];newls=[x for x in ls if x['opened'][:10]>='2024-09-24']
 coreq=sum(x['qty'] for x in ls if x['kind']=='core');mobileq=q-coreq
 ids_here={z['id'] for z in ls}; firstsell=next((j for j in a['journal'] if j['kind']=='real_sell_fill' and j['sid']==sid and j['at'][:10]>day and any(p['layer'] in ids_here for p in j['parts'])),None)
 fulls=[x for x in a['layers'] if x['id'] in {z['id'] for z in ls}]
 allclosed=all(x['closed'] is not None for x in fulls)
 records.append(dict(sid=sid,name=master[sid]['name'],industry=master[sid]['industry_name'],qty=q,mark=float(mark),cost=float(s['cost']),net_unrealized=float(netmark-s['cost']),first_current_round=s['opened'],age_days=(pd.Timestamp(day)-pd.Timestamp(s['opened'])).days,first_layer=min(x['opened'][:10] for x in ls),n_buys_round=s['n_buy'],layers=len(ls),core_q=coreq,mobile_q=mobileq,pre924_mark=float(sum(D(x['qty'])*px(sid,day) for x in prevls)),new924_mark=float(sum(D(x['qty'])*px(sid,day) for x in newls)),gain_thru_1008=float(cohort_value(ls,'2024-10-08')-mark),gain_thru_1031=float(cohort_value(ls,'2024-10-31')-mark),first_sell=None if firstsell is None else firstsell['at'][:10],first_exit_reason=None if firstsell is None else '|'.join(sorted({p['reason'] for p in firstsell['parts']})),cohort_closed=max(x['closed'][:10] for x in fulls) if allclosed else None))
records.sort(key=lambda x:-x['mark'])
assert abs(sum(x['mark'] for x in records)-float(d['inventory']))<1e-6


gate={}
for line in gzip.open(root.parent/'PROFIT_GATE_EVENTS.jsonl.gz','rt'):
 x=json.loads(line)
 if x['at'][:10] in ['2024-09-24','2024-09-25','2024-09-26']:gate[(x['at'][:10],x['sid'],x['role'])]=x
def risk(sid,q,buy,fl,dt):
 return max(D(0),D(q)*buy+fee(sid,q,buy,dt,'buy')-D(q)*fl*D('.9995')+fee(sid,q,fl*D('.9995'),dt))
def getseed(sid,opendate):
 t=next(t for t in a['trades'] if t['security_id']==sid and t['side']=='buy' and t['at'][:10]==opendate)
 dt=t['at'][:10];fl=D(t['floor'])/D(str(getraw(sid).loc[dt].adjustment_factor));r=risk(sid,t['shares'],D(t['price']),fl,dt)
 return t,fl,r
qstate=dict(old['positions']);results=[]
for t in a['trades']:
 dt=t['at'][:10]
 if not '2024-09-24'<=dt<=day:continue
 sid=t['security_id'];before=qstate.get(sid,0)
 if t['side']=='sell':qstate[sid]=before-t['shares'];continue
 qstate[sid]=before+t['shares']
 if not before:continue
 gt=gate[(dt,sid,'mobile')];U=D(gt['net_profit']);opened=next(r['first_current_round'] for r in records if r['sid']==sid)
 seed,seedfl,R0=getseed(sid,opened)
 buy=D(t['price']);fl=D(t['floor'])/D(str(getraw(sid).loc[dt].adjustment_factor));qr=QuantityRule(**version_on(rules['quantity_versions'][sid],dt,proxies)['rule'])
 qtop=qr.buy_floor(min(t['shares'],before));cap=min(R0,U+D('.25')*R0)
 def sizing(cap):
  q=qtop
  while q:
   if risk(sid,q,buy,fl,dt)<=cap:return q
   q=qr.buy_floor(q-1)
  return 0
 nq=sizing(cap);u2=sizing(U/D(2))
 results.append(dict(sid=sid,name=master[sid]['name'],date=dt,seed_day=opened,seed_q=seed['shares'],seed_floor=float(seedfl),R0=float(R0),U=float(U),existing_q=before,old_q=t['shares'],qcap_only=qtop,cap_Dadd=float(cap),new_q=nq,u2_q_with_same_qcap=u2,newrisk=float(risk(sid,nq,buy,fl,dt)) if nq else 0,minlotrisk=float(risk(sid,qr.buy_minimum,buy,fl,dt)),oldrisk=float(risk(sid,t['shares'],buy,fl,dt)),cash_old=float(D(t['gross_cny'])+D(t['fees_cny'])),cash_new=float(D(nq)*buy+fee(sid,nq,buy,dt,'buy')) if nq else 0))
print('RESULTS',json.dumps(results,ensure_ascii=False))
sid='300085.SZ';dt='2024-09-26';gt=gate[(dt,sid,'mobile')];seed,seedfl,R0=getseed(sid,'2024-09-25');U=D(gt['net_profit']);i=next(i for de in a['decisions'] if de['at'][:10]=='2024-09-25' for i in de['intents'] if i['sid']==sid and i['role']=='mobile');fl=D(i['floor'])/D(str(getraw(sid).loc[dt].adjustment_factor));buy=D(gt['buy_proxy']);cap=min(R0,U+D('.25')*R0);rmin=risk(sid,100,buy,fl,dt)
print('SILVER',json.dumps(dict(date=dt,R0=float(R0),U=float(U),old_q=100,candidate_floor=float(fl),candidate_buy=float(buy),minlotrisk=float(rmin),cap=float(cap),u2cap=float(U/2),newrule_q=100 if rmin<=cap else 0,original_cash_gate_q=0,available=ds['2024-09-25']['available'],required_reserve=str(D(ds['2024-09-25']['nav'])*D('.1'))),ensure_ascii=False))
print('TOTALS',json.dumps(dict(n=len(results),old_cash=sum(r['cash_old'] for r in results),new_cash=sum(r['cash_new'] for r in results),new_q_nonzero=sum(r['new_q']>0 for r in results),u2_q_nonzero=sum(r['u2_q_with_same_qcap']>0 for r in results),oldrisk=sum(r['oldrisk'] for r in results),newrisk=sum(r['newrisk'] for r in results)),ensure_ascii=False))
