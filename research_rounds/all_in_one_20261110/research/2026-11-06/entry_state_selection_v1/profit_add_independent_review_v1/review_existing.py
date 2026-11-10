"""Independent arithmetic only. Never import or instantiate any trading engine."""
from pathlib import Path
from decimal import Decimal as D, ROUND_CEILING, ROUND_HALF_UP
from collections import Counter
import gzip,json,csv,hashlib,bisect
Z=D(0);EPS=D('0.0000001');R=Path(__file__).resolve().parent.parent;OUT=Path(__file__).resolve().parent
RUN=R/'mobile_first_probe_protection_v1/conditional_paths_v1/run'
RULE=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/pvr-act-comparison-20261027/execution-rules-v2.json')
rules=json.loads(RULE.read_text());source={};checks=Counter();rows=[];paths=[]
def dec(x):return D(str(x))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):source[str(p)]=sha(p);return json.load(gzip.open(p,'rt')) if p.suffix=='.gz' else json.loads(p.read_text())
def eq(a,b,tag):
 assert abs(dec(a)-dec(b))<EPS,(tag,str(a),str(b));checks[tag]+=1
def version(a,at):
 z=[v for v in a if v['from']<=at[:10] and (not v.get('to') or at[:10]<v['to'])];assert len(z)==1;return z[0]
def fee(sid,at,side,q,p):
 if not q:return Z
 ven=version(rules['venue_versions'][sid],at)['venue'];sch=version(rules['fee_versions'][ven],at)['schedule'];s=Z
 for c in sch['components']:
  if c.get('side','both') not in ('both',side):continue
  basis=c.get('amount_basis','notional');base=dec(q)*p if basis=='notional' else dec(q)
  if basis=='par_value':base*=dec(rules['security_metadata'][sid]['par_value'])
  x=max(dec(c.get('minimum_local',0)),base*dec(c['rate']))
  if c.get('maximum_local') is not None:x=min(x,dec(c['maximum_local']))
  if c.get('rounding_unit') is not None:
   u=dec(c['rounding_unit']);x=(x/u).to_integral_value(rounding=ROUND_CEILING if c.get('rounding_mode')=='ceil' else ROUND_HALF_UP)*u
  s+=x
 return s
source[str(RULE)]=sha(RULE)
for f in sorted(RUN.glob('*/PATH.json.gz')):
 p=read(f);sid=p['case']['sid'];case=p['case']['round_id'];arm=p['summary']['arm'];q=0;k=Z;buy=Z;sell=Z;real=Z;cy=0;book={};snap=[];seedadd=0
 daily=p['daily'];dates=[z['at'] for z in daily];tr={(z['at'],z['layer']):z for z in p['trades'] if z['side']=='buy'}
 acc=[z for z in p['audit'] if z['kind']=='dividend_accrual'];assert not any('paid' in z['kind'] for z in p['audit']);checks['accrual_records_without_paid_timestamp']+=sum(z['receivable']['paid_at'] is None for z in acc)
 for j in p['journal']:
  at=j['at'];kind=j['kind']
  if kind=='real_buy_fill':
   if q==0:assert k==0;cy+=1;buy=Z;sell=Z;real=Z;book={}
   t=tr[at,j['layer']];n=j['shares'];px=dec(j['price']);bf=dec(j['fees']);op=dec(t['raw_open']);cost=dec(n)*px+bf
   eq(px,op*D('1.0005'),'buy_open_slippage');eq(bf,fee(sid,at,'buy',n,px),'dated_buy_fee');eq(dec(n)*px,t['gross_cny'],'gross')
   assert t['signal_at']<at;checks['signal_precedes_fill']+=1
   if q>0 and t['kind']=='add':
    g=[g for g in p['profit_gate'] if g['at']==at and g['qty']==q and abs(dec(g['cost'])-k)<EPS];assert len(g)==1,(case,arm,at,'gate ambiguity');g=g[0]
    sp=op*D('.9995');v=dec(q)*sp-fee(sid,at,'sell',q,sp);u=v-k;cycle=sell+v-buy
    eq(v,g['net_liquidation'],'actual_ADD_gate_value');assert g['allowed']==(u>0);eq(cycle,u+real,'cycle_identity');eq(k,buy-(sell-real),'remaining_cost_identity')
    prev=daily[bisect.bisect_left(dates,at)-1];factor=dec(prev['close_factor']);assert not any(x['kind']=='actual_split' and prev['at']<x['at']<=at for x in p['journal']),'action factor requires separate review'
    floor=dec(t['floor'])/factor;stop=floor*D('.9995');sf=fee(sid,at,'sell',n,stop);risk=max(Z,dec(n)*(px-stop)+bf+sf)
    layercost=sum(v['k'] for v in book.values());layerreal=sell-(buy-layercost);eq(cycle,(v-layercost)+layerreal,'layer_cycle_identity')
    row=dict(case_id=case,sid=sid,name=p['case']['name'],arm=arm,cycle=cy,seed_cycle=cy==1 and p['rounds'][0]['origin']=='SEED_MOBILE',at=at,signal_at=t['signal_at'],layer=j['layer'],q_before=q,new_q=n,pooled_K=k,buy_to_date=buy,sell_to_date=sell,pooled_realized=real,net_liquidation=v,inventory_U=u,cycle_trade_U=cycle,paid_dividend_credit=Z,paid_dividend_status='NO_PAYMENT_EVIDENCE_NOT_VERIFIED_ZERO',surviving_layer_cost=layercost,layer_realized=layerreal,factor_from_prior_close=factor,raw_floor=floor,raw_buy=px,raw_stop_sell=stop,buy_fee=bf,stop_sell_fee=sf,new_plan_risk=risk,new_buy_cash=cost,risk_gt_inventory_U=risk>u,risk_gt_cycle_trade_U=risk>cycle,positive_cycle=cycle>0)
    rows.append(row);seedadd+=int(row['seed_cycle'])
   q+=n;k+=cost;buy+=cost;book[j['layer']]={'q':n,'k':cost}
  elif kind=='real_sell_fill':
   n=j['shares'];assert 0<n<=q;ret=k*dec(n)/dec(q);net=dec(n)*dec(j['price'])-dec(j['fees']);sell+=net;real+=net-ret;k-=ret;q-=n
   eq(sum(dec(v['net_cash']) for v in j['parts']),net,'sell_parts_net')
   for z in j['parts']:
    b=book[z['layer']];b['k']*=dec(b['q']-z['shares'])/dec(b['q']);b['q']-=z['shares']
   if q==0:k=Z
  elif kind=='actual_split':
   q=int(dec(q)*dec(j['ratio']))
   for b in book.values():b['q']=int(dec(b['q'])*dec(j['ratio']))
  snap.append((at,q,k,cy))
 assert sum(b['q'] for b in book.values())==q
 si=0
 for d in daily:
  while si<len(snap) and snap[si][0]<=d['at']:si+=1
  qq,kk,cc=snap[si-1][1:] if si else (0,Z,0)
  eq(kk,d['remaining_stock_cost'],'daily_remaining_cost');eq(qq,d['positions'].get(sid,0),'daily_qty')
 # Closed whole-cycle trade cash is independent of the pooled/layer allocation.
 for rr in p['rounds']:
  ids=set(rr['layers']);bs=sum((dec(t['gross_cny'])+dec(t['fees_cny']) for t in p['trades'] if t['side']=='buy' and t['layer'] in ids),Z);ss=sum((dec(z['net_cash']) for t in p['trades'] if t['side']=='sell' for z in t['parts'] if z['layer'] in ids),Z)
  eq(ss-bs,rr['trade_cash'],'round_trade_cash')
 paths.append(dict(case_id=case,sid=sid,name=p['case']['name'],arm=arm,actual_buys=len(tr),true_ADDs=sum(x['case_id']==case and x['arm']==arm for x in rows),seed_true_ADDs=seedadd,rounds=len(p['rounds'])))
# This does not approve a candidate and does not change any eligibility/path.
for name,rr in [('INDEPENDENT_CONDITIONAL_ADDS.csv',rows),('PATH_COUNTS.csv',paths)]:
 with (OUT/name).open('w') as f:
  w=csv.DictWriter(f,fieldnames=list(rr[0]));w.writeheader();w.writerows(rr)
seed=[r for r in rows if r['seed_cycle']]
report=dict(status='PASS_ARITHMETIC_WITH_FACTOR_SCOPE_NOTE',checks=checks,paths=len(paths),all_path_true_ADDs=len(rows),seed_true_ADDs=len(seed),seed_risk_gt_inventory=sum(r['risk_gt_inventory_U'] for r in seed),seed_risk_gt_cycle=sum(r['risk_gt_cycle_trade_U'] for r in seed),seed_nonpositive_cycle=sum(not r['positive_cycle'] for r in seed),source_accounts_or_strategy_runs=0,paid_credit='No evidenced payments credited. Not a claim that actual payments were zero.',factor_scope='Risk uses immediately prior CLOSE factor; no same-OPEN split at true ADD. Author-table comparison must independently verify other effective actions and OPEN mapping.',Gree_seed=[r for r in seed if r['sid']=='000651.SZ'])
(OUT/'CHECKS.json').write_text(json.dumps(report,indent=2,ensure_ascii=False,default=str)+'\n');(OUT/'SOURCE_SHA256.json').write_text(json.dumps(source,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k!='Gree_seed'},ensure_ascii=False,default=str))
for r in report['Gree_seed']:print({k:str(r[k]) for k in ['arm','at','inventory_U','cycle_trade_U','pooled_realized','surviving_layer_cost','layer_realized','new_plan_risk']})
