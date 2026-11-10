"""Saved-output research only. No strategy import, Data, replay, network, or changed frozen input."""
from pathlib import Path
from decimal import Decimal as D, ROUND_CEILING, ROUND_HALF_UP
from collections import defaultdict, Counter
import json, csv, hashlib, sys
sys.dont_write_bytecode=True
import pandas as pd
import numpy as np
R=Path('/Users/bytedance/Documents/Codex/2026-11-09/sector51_924_entry_review_v1')
O=R/'mainline_winner_funding_design_v1'
B=R/'mainline_m7_cash_batch_design_v6/once_20260630'
A=R/'mainline_v11_account_audit_v2'
Z=D(0)
read=lambda p: json.loads(Path(p).read_text())
sha=lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
inputs={}
def checked(p, expected=None):
 p=Path(p); h=sha(p)
 if expected is not None: assert h==expected, ('hash',str(p))
 inputs[str(p)]=h
 return p
def load(n):
 p=B/(n+'.json'); checked(p, hashes[n+'.json']);return read(p)
def save(n,x):
 (O/(n+'.json')).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
 if isinstance(x,list) and x:
  with (O/(n+'.csv')).open('w',newline='') as f:
   w=csv.DictWriter(f,fieldnames=list(dict.fromkeys(k for r in x for k in r)));w.writeheader()
   w.writerows({k:json.dumps(v,ensure_ascii=False,default=str) if isinstance(v,(list,dict)) else v for k,v in r.items()} for r in x)
def is_true(x):return isinstance(x,(bool,np.bool_)) and bool(x)
def finite(x):
 try:return np.isfinite(float(x))
 except (TypeError,ValueError):return False
def version(rows,day,proxies):
 vals=[x for x in rows if x['from']<=day and (not x.get('to') or day<x['to'])];assert len(vals)==1
 v=vals[0];assert v['basis']=='official_rule' and v.get('verification_status')=='verified' or v['basis']=='explicit_research_proxy' and v.get('proxy_id') in proxies
 return v
def fee(sid,day,qty,price,side):
 venue=version(rules['venue_versions'][sid],day,proxies)['venue']
 sched=version(rules['fee_versions'][venue],day,proxies)['schedule'];out=Z
 for c in sched['components']:
  if c.get('side','both') not in ['both',side]:continue
  typ=c.get('amount_basis','notional');base=qty*price if typ=='notional' else D(qty) if typ=='shares' else D(qty)*D(rules['security_metadata'][sid]['par_value'])
  v=max(D(c.get('minimum_local','0')),base*D(c['rate']))
  if c.get('maximum_local') is not None:v=min(v,D(c['maximum_local']))
  if c.get('rounding_unit'):
   u=D(c['rounding_unit']);v=(v/u).to_integral_value(rounding=ROUND_CEILING if c.get('rounding_mode')=='ceil' else ROUND_HALF_UP)*u
  out+=v
 return out
def sm(rows,key):return sum((D(r.get(key,0) or 0) for r in rows),Z)
hashes=read(checked(B/'OUTPUT_HASHES.json'))
sources=read(checked(B/'SOURCE_HASHES.json'))
names=['ORDERS','CAPITAL_LOTS','HOLDINGS','CP_EVENTS','INFORMATION_CONFIRMATIONS','TRANSFERS','REFERENCE_DAILY','REFERENCE_REQUESTS','SECTOR_DAILY','EQUITY_EVENTS','FUNDING_REQUESTS','DAY_LEDGER']
data={n:load(n) for n in names}
orders=data['ORDERS'];caps=data['CAPITAL_LOTS'];holds=data['HOLDINGS'];cp=data['CP_EVENTS'];info=data['INFORMATION_CONFIRMATIONS'];trans=data['TRANSFERS']
rounds=read(checked(A/'M7_COMMON_ROUNDS.json'));roundmap={r['round_id']:r for r in rounds}
cs=read(checked(A/'CHANGSHAN_1024_FUNDING_APPENDIX.json'))
checked(A/'CHANGSHAN_1024_FUNDING_APPENDIX.md')
checked(A/'INDEPENDENT_READOUT.md')
rulespath=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025/inputs-v2/market-rules.json')
rules=read(checked(rulespath,sources[str(rulespath)]))
protocolpath=rulespath.parent/'economic-protocol.json'
proxies=read(checked(protocolpath,sources[str(protocolpath)]))['approved_proxy_ids']
mp=next(p for p in sources if p.endswith('/universe-cp1-inputs-20261031/STOCK_MANIFEST.json'))
manifest={x['symbol']:x for x in read(checked(mp,sources[mp]))}
rawcache={};cpcache={};factcache={}
def frames(sid):
 if sid not in rawcache:
  m=manifest[sid];p=next(p for p in m['source_sha256'] if p.endswith('/signal.parquet'))
  rawcache[sid]=pd.read_parquet(checked(p,sources[p])).loc[:'2025-01-20']
  assert rawcache[sid].loc['2024-09-01':'2025-01-20','symbol'].dropna().eq(sid).all()
  cpcache[sid]=pd.read_parquet(checked(m['refs']['CP1'],sources[m['refs']['CP1']])).loc[:'2025-01-20']
  factcache[sid]=pd.read_parquet(checked(m['refs']['facts'],sources[m['refs']['facts']])).loc[:'2025-01-20']
 return rawcache[sid],cpcache[sid],factcache[sid]
def snapshot_lot(c,close,op):
 sid=c['sid'];rid=c['round_id'];lid=c['lot_id'];h=next(h for h in holds if h['day']==close and h['lot_id']==lid)
 raw,cpf,facts=frames(sid);rc=raw.loc[close];ro=raw.loc[op];cf=D(str(rc['adjustment_factor']));of=D(str(ro['adjustment_factor']))
 closep=D(str(rc['raw_close']));openp=D(str(ro['raw_open']));floor=D(h['protection_signal'])
 proof=[x for x in info if x['round_id']==rid and x['day']<=close and x['phase']=='OPEN' and x['decision']=='INFORMATION_CONFIRMED' and is_true(x.get('confirmed_history'))]
 assert (len(proof)>0)==is_true(c['confirmed_history'])
 allhs=[x for x in holds if x['day']==close and x['round_id']==rid];q=sum(h['qty'] for h in allhs)
 cflo=sm([x for x in orders if x['round_id']==rid and x['day']<=close],'cash_delta')
 div=sum((D(x['receivable_delta']) for x in data['EQUITY_EVENTS'] if x.get('round_id')==rid and x['day']<=close and D(x.get('receivable_delta',0))>0),Z)
 liqc=cflo+div+q*closep*D('.9995')-fee(sid,close,q,closep*D('.9995'),'sell')
 liqo=cflo+div+q*openp*D('.9995')-fee(sid,op,q,openp*D('.9995'),'sell')
 assert abs(liqc-D(c['round_net']))<D('1e-16')
 i=facts.loc[close,'i_target']; i_known=isinstance(i,(int,np.integer,bool,np.bool_)) and int(i) in [0,1]
 cp_state_known=isinstance(cpf.loc[close,'receipt'],(bool,np.bool_))
 pproof=[]
 for p in proof:
  created=next(x for x in cp if x['round_id']==rid and x['cp_id']==p['cp_id'] and x['event']=='CREATED_AFTER_SEED')
  z=cpf.loc[created['day']]
  assert is_true(z['receipt']) and D(str(z['candidate']))==D(created['candidate'])
  assert roundmap[rid]['actual_seed_OPEN']<=created['day']<p['day']<=close
  pproof.append(dict(cp_id=p['cp_id'],receipt_CLOSE=created['day'],confirmation_OPEN=p['day'],floor=created['candidate']))
 orig=None
 if h.get('cp_id'):
  orig=next(x for x in cp if x['cp_id']==h['cp_id'] and x['event']=='CREATED_AFTER_SEED')
  assert is_true(cpf.loc[orig['day'],'receipt']) and D(str(cpf.loc[orig['day'],'candidate']))==D(orig['candidate'])
  assert floor>=D(orig['candidate'])
 known=not c['unknown'] and not c['locked'] and h['locked_exit'] is None and i_known and int(i)==1 and cp_state_known
 intactclose=closep*cf>floor; intactopen=openp*of>floor
 protectclose=bool(known and proof and liqc>0 and intactclose)
 protectopen=bool(protectclose and liqo>0 and intactopen)
 return dict(sid=sid,name=roundmap[rid]['name'],round_id=rid,lot_id=lid,kind=c['kind'],capital_role=c['capital_role'],qty=c['qty'],bought=c['bought'],M=c['M'],stock_state=c['stock_state'],sector_state=c['sector_state'],unknown=c['unknown'],locked=c['locked'],round_liquidation_net_CLOSE=liqc,round_liquidation_net_OPEN=liqo,confirmed_history=c['confirmed_history'],verified_postseed_CP=pproof,current_i_target=int(i) if i_known else None,current_CP_receipt_type=type(cpf.loc[close,'receipt']).__name__,effective_protection_signal=floor,original_lot_CP=orig,raw_CLOSE=closep,raw_OPEN=openp,adjusted_CLOSE=closep*cf,adjusted_OPEN=openp*of,unbroken_CLOSE=intactclose,unbroken_OPEN=intactopen,healthy_verified_positive_CLOSE=protectclose,healthy_verified_positive_OPEN=protectopen,final_actual_round_PnL_evaluation_only=roundmap[rid]['marked_net_pnl'])
def case(close,op):
 ds=[o for o in orders if o['day']==op and o.get('transfer_rank')]
 bs=[o for o in orders if o['day']==op and o['side'].startswith('BUY')]
 closeplan=next(x for x in trans if x['day']==close and x['event']=='DEMAND_PLAN')
 openplan=next(x for x in trans if x['day']==op and x['event']=='TRANSFER_CASH')
 log=next(x for x in trans if x['day']==op and x['event']=='RECEIVER_FUNDING')
 assert abs(sm(ds,'cash_delta')-D(openplan['net_cash_released']))<D('1e-16')
 assert abs(-sm(bs,'cash_delta')-D(openplan['M_desired_cost']))<D('1e-16')
 def grouping(rs):
  groups={}
  for o in rs:
   phase=o.get('allocation_phase','MATURE' if o['side']=='BUY_ADD' else None);key=(o['sector51'],o['side'],phase)
   if key not in groups:groups[key]=dict(sector51=key[0],side=key[1],phase=key[2],count=0,buy_cost=Z,whole_round_final_PnL_evaluation_only=Z,negative_final_rounds=0,sids=[])
   g=groups[key];g['count']+=1;g['buy_cost']-=D(o['cash_delta']);g['whole_round_final_PnL_evaluation_only']+=D(roundmap[o['round_id']]['marked_net_pnl']);g['negative_final_rounds']+=int(D(roundmap[o['round_id']]['marked_net_pnl'])<0);g['sids'].append(o['sid'])
  return list(groups.values())
 return dict(close=close,open=op,close_plan=closeplan,open_plan=openplan,funding=log,actual_donor_orders=ds,actual_buy_orders=bs,actual_receiver_groups=grouping(bs),source='M7 saved actual path; cash is fungible. No per-yuan donor-receiver causality.')
cases={'PV_1108':case('2024-11-07','2024-11-08'),'STARTUP_0925':case('2024-09-24','2024-09-25')}
pv=[]
for o in cases['PV_1108']['actual_donor_orders']:
 if o['sector51']!='光伏风电设备':continue
 assert len(o['lots'])==1
 c=next(x for x in caps if x['day']=='2024-11-07' and x['lot_id']==o['lots'][0])
 row=snapshot_lot(c,'2024-11-07','2024-11-08');row.update(actual_sold_qty=o['qty'],actual_sold_net=D(o['cash_delta']),actual_order_seq=o['order_seq'],actual_reason=o['reason']);pv.append(row)
save('PV_1108_LOT_CHECKS',pv)
pvsum={}
for k,pred in [('all',lambda x:True),('healthy_at_both',lambda x:x['healthy_verified_positive_OPEN']),('nonpositive_round',lambda x:D(x['round_liquidation_net_CLOSE'])<=0),('not_postseed_confirmed',lambda x:not x['verified_postseed_CP'])]:
 rs=[r for r in pv if pred(r)];pvsum[k]=dict(lots=len(rs),stock_count=len({r['sid'] for r in rs}),net_proceeds=sm(rs,'actual_sold_net'),sids=sorted({r['sid'] for r in rs}))
cases['PV_1108']['lot_category_summary']=pvsum
cases['PV_1108']['known_sector_CLOSE']=[s for s in data['SECTOR_DAILY'] if s['day']=='2024-11-07' and s['sector51'] in ['光伏风电设备','证券保险','白酒','旅游酒店','医疗服务']]
cases['PV_1108']['mandatory_protection_sale_previous_OPEN']=[o for o in orders if o['day']=='2024-11-07' and o['sid']=='601865.SH' and o['side'].startswith('SELL')]
startup=[]
for o in cases['STARTUP_0925']['actual_donor_orders']:
 for lid in o['lots']:
  c=next(x for x in caps if x['day']=='2024-09-24' and x['lot_id']==lid)
  if c['confirmed_history'] is True and D(c['round_net'])>0:
   row=snapshot_lot(c,'2024-09-24','2024-09-25');row.update(actual_sold_qty=o['qty'],actual_sold_net=D(o['cash_delta']),actual_order_seq=o['order_seq'],actual_reason=o['reason']);startup.append(row)
save('STARTUP_0925_CONFIRMED_DONORS',startup)
cases['STARTUP_0925']['known_sector_CLOSE']=[s for s in data['SECTOR_DAILY'] if s['day']=='2024-09-24' and s['sector51'] in ['互联网电商','化工材料','软件与IT服务','房地产开发','白酒']]
focus_rids=['300085.SZ|1|2024-09-23','603369.SH|1|2024-09-23','002024.SZ|1|2024-09-02','601208.SH|1|2024-09-02']
cases['STARTUP_0925']['focus_whole_rounds']=[roundmap[rid] for rid in focus_rids]
silver_lid='300085.SZ|1|2024-09-23|407'
silverbuy=next(o for o in orders if o.get('lot_id')==silver_lid)
silversell=next(o for o in orders if o.get('lots')==[silver_lid])
assert silversell['qty']==silverbuy['qty']==1200
cases['STARTUP_0925']['silver_actual_ADD_lot']=dict(buy=silverbuy,sell=silversell,exact_lot_realized_net=D(silverbuy['cash_delta'])+D(silversell['cash_delta']))
cases['STARTUP_0925']['healthy_sold_total']=sm([x for x in startup if x['healthy_verified_positive_OPEN']],'actual_sold_net')
save('SAVED_PATH_FACTS',cases)
save('SOURCE_HASHES',inputs)
save('READOUT_NUMBERS',dict(pv=pvsum,pv_receiver_groups=cases['PV_1108']['actual_receiver_groups'],startup_healthy_sold=cases['STARTUP_0925']['healthy_sold_total'],silver_ADD_realized=cases['STARTUP_0925']['silver_actual_ADD_lot']['exact_lot_realized_net'],no_history=True,no_strategy_import=True,no_network=True))
print(json.dumps(read(O/'READOUT_NUMBERS.json'),ensure_ascii=False,default=str))
