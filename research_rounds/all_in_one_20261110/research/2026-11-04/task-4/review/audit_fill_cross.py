from pathlib import Path
from decimal import Decimal,localcontext
from collections import defaultdict,Counter
import json,gzip,hashlib
import pandas as pd,numpy as np
O=Path('/Users/bytedance/Documents/Codex/2026-11-04/task-4');T=O.parent/'task';W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
D=Decimal;read=lambda p:json.loads(Path(p).read_text())
f=pd.read_parquet(O/'INDUSTRY_DAILY_BEHAVIOR.parquet').set_index(['day','sector'])
source={};cross=read(O/'ACTUAL_FILL_EVIDENCE_CROSS.json');summary=read(O/'ACTUAL_FILL_EVIDENCE_SUMMARY.json')
long=read(T/'loss_correction/entry_risk_commitment_review/2022_2024_ENTRIES.json');strong=read(T/'loss_correction/entry_risk_commitment_review/strong_ENTRIES.json')
sets={'2022_entries_lifecycle_to2024end':[x for x in long if x['opened'].startswith('2022')], '2023_entries_lifecycle_to2024end':[x for x in long if x['opened'].startswith('2023')], 'POST924_strict303_newfills_to2024end':[x for x in long if '2024-10-09'<=x['opened'][:10]<='2024-12-31'], '2026H1_semiconductor_toJun30':[x for x in strong if x['industry']=='半导体' and '2026-01-01'<=x['opened'][:10]<='2026-06-30']}
computed={}
with localcontext() as ctx:
 ctx.prec=70
 for case,rows in sets.items():
  produced={x['layer']:x for x in cross if x['case']==case};assert len(produced)==len(rows)
  groups=defaultdict(list)
  for x in rows:
   r=f.loc[(x['signal_day'],x['sector'])]
   promoted=bool(r.original_permit and r.first_promotion is not None and str(r.first_promotion)<=x['signal_day'])
   key=('BREAK_promoted_permit' if r.origin=='break_started' else 'REPAIR_promoted_permit') if promoted else 'not_promoted_and_permitted'
   assert produced[x['layer']]['evidence_group']==key
   assert produced[x['layer']]['net']==x['net'] and produced[x['layer']]['cost']==x['cost']
   groups[key].append(x)
  computed[case]={}
  for g,rs in groups.items():
   net=sum((D(x['net']) for x in rs),D(0));cost=sum((D(x['cost']) for x in rs),D(0))
   assert len(rs)==summary[case][g]['layers']
   assert abs(net-D(summary[case][g]['actual_original_net']))<D('1e-19')
   assert abs(cost-D(summary[case][g]['buy_cost']))<D('1e-19')
   computed[case][g]={'layers':len(rs),'net':str(net),'cost':str(cost)}
 assert len(sets['POST924_strict303_newfills_to2024end'])==303
 den=read(W/'pvr-slot1-native-readiness-20261101/semiconductor-2026H1-readonly/SEMICONDUCTOR_ALL_STOCKS_HINDSIGHT_DENOMINATOR.json')
 sm={x['symbol']:x for x in read(W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json')}
 assert len(den)==126
 facts={};known=[]
 for x in den:
  p=Path(sm[x['sid']]['refs']['facts']);source[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
  a=pd.read_parquet(p,columns=['close','raw_close','segment_id'])
  facts[x['sid']]=a
  before=a.loc[:'2025-12-31'];after=a.loc['2026-01-01':'2026-06-30']
  ok=len(before)>0 and len(after)>0 and after.index[-1]==pd.Timestamp('2026-06-30') and before.segment_id.iloc[-1]==after.segment_id.iloc[-1]
  assert ok==(x['status']=='comparable')
  if ok:
   ret=(D(str(after.close.iloc[-1]))/D(str(before.close.iloc[-1]))-1)*100
   assert abs(ret-D(x['price_return_pct']))<D('1e-20')
   known.append(x['sid'])
 assert len(known)==114
 with gzip.open(T/'pvr_pool_feasibility/runs/2025_26/pair/B.json.gz','rt') as file:b=json.load(file)
 actual=sets['2026H1_semiconductor_toJun30'];ids={x['layer'] for x in actual};native={x['id']:x for x in b['layers'] if x['id'] in ids}
 assert len(native)==25
 cash=defaultdict(lambda:D(0));fills=[];sells=defaultdict(list)
 for tr in b['trades']:
  if tr['side']=='buy' and tr['layer'] in ids:
   cash[tr['layer']]-=D(tr['gross_cny'])+D(tr['fees_cny']);fills.append(tr)
  elif tr['side']=='sell':
   for part in tr['parts']:
    if part['layer'] in ids:
     cash[part['layer']]+=D(part['net_cash']);sells[part['layer']].append({'day':tr['at'][:10],'qty':part['shares'],'reason':part['reason'],'price':tr['price']})
 assert len(fills)==25
 stocknative=defaultdict(lambda:dict(cost=D(0),net=D(0),layers=[]))
 for x in actual:
  n=native[x['layer']];assert cash[x['layer']]==D(n['cash'])
  mark=D(str(facts[x['sid']].loc[:'2026-06-30'].raw_close.iloc[-1]))
  net=cash[x['layer']]+D(n['dividend'])+D(n['qty'])*mark
  assert abs(net-D(x['net']))<D('1e-20')
  z=stocknative[x['sid']];z['cost']+=D(x['cost']);z['net']+=net
  z['layers'].append({'id':x['layer'],'signal':x['signal_day'],'opened':x['opened'],'closed':x['closed'],'role':x['role'],'net':str(net),'actual_sells':sells[x['layer']]})
 assert len(stocknative)==18
 decomp=read(O/'SEMICONDUCTOR_STOCK_DELTA_DECOMPOSITION.json')
 newids={r['sid'] for r in decomp['No60_only']['members']};common={r['sid'] for r in decomp['both']['members']}
 assert len(newids)==7 and len(common)==11 and newids|common==set(stocknative)
 newcost=sum((stocknative[s]['cost'] for s in newids),D(0));newnet=sum((stocknative[s]['net'] for s in newids),D(0));commonnet=sum((stocknative[s]['net'] for s in common),D(0))
 assert abs(newcost-D(str(decomp['No60_only']['PVR_NO60']['cost'])))<D('1e-9')
 assert abs(newnet-D(str(decomp['No60_only']['PVR_NO60']['net'])))<D('1e-9')
 fundedlabels=[float(next(x['price_return_pct'] for x in den if x['sid']==s)) for s in stocknative]
 median=float(np.median(fundedlabels));assert abs(median-116.56943677305381)<1e-12
 assert sum(v>=100 for v in fundedlabels)==11
 funnel=read(T/'loss_correction/no60_behavior_v1/PVR_NO60-SEMICONDUCTOR_FUNNEL.json')['all_market_receipts']
 keypaths={}
 for sid,end in [('300666.SZ','2026-02-06'),('603061.SH','2026-02-12'),('301611.SZ','2026-01-30')]:
  after=[x for x in funnel if x['sid']==sid and x['signal_day']>=end]
  keypaths[sid]={'H1_hindsight_price_return_pct':next(x['price_return_pct'] for x in den if x['sid']==sid),'actual_cost':str(stocknative[sid]['cost']),'actual_net':str(stocknative[sid]['net']),'actual_layers':stocknative[sid]['layers'],'subsequent_same833_mother_receipts':[{'day':x['signal_day'],'category':x['category'],'raw_opening_reasons':x['raw_opening_reasons'],'normalized_no_plan':x['normalized_no_plan']} for x in after]}
result={'status':'PASS_WITH_SCOPE','actualfill_groups_independently_joined':computed,'semiconductor_full126_known_price114_unknown12':{'all':126,'known':len(known),'unknown':126-len(known)},'actual18_stocks':{'H1_hindsight_price_return_median_pct':median,'H1_hindsight_price_return_ge100_stocks':11,'native_layer_net':str(sum((z['net'] for z in stocknative.values()),D(0))),'new7_cost':str(newcost),'new7_net':str(newnet),'common11_net':str(commonnet)},'actual_holding_and_refunding_keypaths':keypaths,'scope':'H1 endpoint price labels are hindsight adjusted-price returns, not actual account returns. Original layer outcomes are descriptive; no deletion/reallocation savings or strategy counterfactual. Native layer cash reconstructed from actual fills/parts; terminal dividend field reused, no independent rights entitlement recomputation.','label_warning':'not_promoted_and_permitted is the complement of (promoted AND permitted); it includes unpermitted observations and should be described as other, not unpromoted-but-permitted.','new_accounts':0}
result['reviewed_files_sha256']={str(O/n):hashlib.sha256((O/n).read_bytes()).hexdigest() for n in ['ACTUAL_FILL_CROSS_PROTOCOL.txt','cross_and_plot.py','ACTUAL_FILL_EVIDENCE_CROSS.json','ACTUAL_FILL_EVIDENCE_SUMMARY.json','SEMICONDUCTOR_STOCK_DELTA_DECOMPOSITION.json']}
result['price_source_sha256']=source
(O/'review/ACTUAL_FILL_AND_H1_PRICE_AUDIT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
print(json.dumps({k:v for k,v in result.items() if k not in ['actual_holding_and_refunding_keypaths','price_source_sha256','reviewed_files_sha256']},ensure_ascii=False,indent=2))
