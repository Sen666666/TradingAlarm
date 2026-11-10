"""Full saved-book repetition/actual sale attribution, no model or runner."""
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict,Counter
from datetime import datetime
import json,gzip,hashlib,time
P=Path(__file__).resolve().parent;O=P/'absolute_loss_2022_2023';W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds');Z=D(0);SRC={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):SRC[str(p)]=sha(p);return json.loads(Path(p).read_text())
def gz(p):
 SRC[str(p)]=sha(p)
 with gzip.open(p,'rt') as f:return json.load(f)
def rows(p):
 SRC[str(p)]=sha(p)
 with gzip.open(p,'rt') as f:return [json.loads(l) for l in f]
def save(name,x):
 with (O/name).open('x') as f:json.dump(x,f,ensure_ascii=False,indent=2,default=str)
def n(x):return D(str(x))
def day(x):return str(x)[:10]
def agg(ll):
 cost=sum((n(x['cost']) for x in ll),Z);net=sum((n(x['net']) for x in ll),Z);neg=[x for x in ll if n(x['net'])<0];pos=[x for x in ll if n(x['net'])>0]
 return dict(layers=len(ll),stocks=len({x['sid'] for x in ll}),buy_cash=cost,net=net,positive_net=sum((n(x['net']) for x in pos),Z),negative_net=sum((n(x['net']) for x in neg),Z),negative_layer_buy_cash=sum((n(x['cost']) for x in neg),Z),positive_layer_buy_cash=sum((n(x['cost']) for x in pos),Z),net_per_turnover_buy_cash=net/cost if cost else None,quantity_open_layers=sum(bool(x['qty']) for x in ll),interpretation='Net/buycash is descriptive turnover efficiency, not account return or causal avoidable loss')
def analyze(label,bookroot,export,layerpath):
 b=gz(bookroot/'pair/B.json.gz');daily=rows(bookroot/'pair/daily.jsonl.gz');ls=read(layerpath);acts=read(export/(label.split(':')[0]+'-ENTRY_ACTIONS.json'));cc=read(export/(label.split(':')[0]+'-CAMPAIGNS.json'));am={x['layer']:x for x in acts};rm={x['id']:x for x in b['layers']}
 assert len(ls)==len(am)==len(rm) and {x['layer'] for x in ls}==set(rm)
 assert abs(sum((n(x['net']) for x in ls),Z)-(n(b['ending_NAV'])-D(1000000)))<D('.00000001')
 assert abs(sum((n(c['net']) for c in cc),Z)-sum((n(x['net']) for x in ls),Z))<D('.00000001')
 sale=defaultdict(list)
 for t in b['trades']:
  if t['side']=='sell':
   for part in t['parts']:sale[part['layer']].append(dict(at=t['at'],reason=part['reason'],shares=part['shares'],actual_net_cash=part['net_cash']))
 checkpoints=sorted([(datetime.fromisoformat(r['at']),r['on']) for r in daily]);entries=[]
 for l in ls:
  lid=l['layer'];raw=rm[lid];a=am[lid];clock=datetime.fromisoformat(l['opened']);prior=[(t,on) for t,on in checkpoints if t<clock];assert prior
  reasons=sorted({s['reason'] for s in sale[lid]});entry=dict(l,signal_at=raw['signal_at'],original_watch_epoch=raw['epoch'],action=a['action'],quantity_before=a['quantity_before'],ACT_at_actual_OPEN=prior[-1][1],ACT_source_CLOSE=str(prior[-1][0]),actual_sale_parts=sale[lid],actual_sale_reason_set=reasons,actual_sale_reason_class='|'.join(reasons) if reasons else 'still_held')
  entries.append(entry)
 assert not [x for x in entries if not x['ACT_at_actual_OPEN']]
 cohorts={}
 for k in ['first_actual_participation','add_to_existing_stock','fresh_reentry_after_actual_flat']:cohorts['action|'+k]=agg([x for x in entries if x['action']==k])
 for k in sorted({x['role'] for x in entries}):cohorts['role|'+k]=agg([x for x in entries if x['role']==k])
 for k in sorted({x['actual_sale_reason_class'] for x in entries}):cohorts['actual_sale_reason|'+k]=agg([x for x in entries if x['actual_sale_reason_class']==k])
 stocks=[]
 for sid in sorted({x['sid'] for x in entries}):
  ll=[x for x in entries if x['sid']==sid];c=[x for x in cc if x['sid']==sid];receipts=[x.get('receipt') for x in ll if x.get('receipt')];negative=[x for x in c if n(x['net'])<0]
  stocks.append(dict(sid=sid,name=ll[0]['name'],industry=ll[0]['industry'],campaigns=len(c),cash_closed_campaigns=sum(x['cash_closed'] for x in c),negative_campaigns=len(negative),negative_campaign_net=sum((n(x['net']) for x in negative),Z),negative_campaign_buy_cash=sum((n(x['buy_cash']) for x in negative),Z),actions=dict(Counter(x['action'] for x in ll)),independent_actual_CP1_ids=len(set(receipts)),repeated_actual_CP1_id_count=len(receipts)-len(set(receipts)),**agg(ll)))
 stocks.sort(key=lambda x:x['net']);stockloss=[x for x in stocks if x['net']<0];gross_stockloss=-sum((x['net'] for x in stockloss),Z)
 tails=[];predecessors=[]
 for sid in sorted({x['sid'] for x in entries}):
  c=sorted([x for x in cc if x['sid']==sid],key=lambda x:x['campaign_number']);tt=[x for x in c if n(x['net'])/n(x['buy_cash'])>=D('.3')]
  if not tt:continue
  first=tt[0];pre=[x for x in c if x['campaign_number']<first['campaign_number']];neg=[x for x in pre if n(x['net'])<0]
  tails.append(dict(sid=sid,first_tail_campaign=first,previous_campaigns=pre,previous_negative_campaigns=neg,prior_negative_campaigns=len(neg),prior_negative_net=sum((n(x['net']) for x in neg),Z),prior_negative_buy_cash=sum((n(x['buy_cash']) for x in neg),Z),all_stock_net=next(x['net'] for x in stocks if x['sid']==sid),tail_status='cashclosed' if first['cash_closed'] else 'flat_unpaid_claim' if first['position_closed'] else 'marked_active',scope='Terminal >=30% is an ex-post control label only; previous campaigns count once before earliest such tail per stock'))
  predecessors.extend(pre)
 summary=dict(reference=label,endingNAV=b['ending_NAV'],cumulative_net=sum((n(x['net']) for x in entries),Z),all=agg(entries),cohorts=cohorts,stocks_with_multiple_flat_to_flat_campaigns=sum(x['campaigns']>1 for x in stocks),stocks_with_two_or_more_negative_campaigns=sum(x['negative_campaigns']>=2 for x in stocks),negative_stock_outcomes=len(stockloss),gross_negative_stock_outcomes=gross_stockloss,top2_negative_stock_loss_share_pct=-sum((x['net'] for x in stockloss[:2]),Z)/gross_stockloss*100,top5_negative_stock_loss_share_pct=-sum((x['net'] for x in stockloss[:5]),Z)/gross_stockloss*100,all_actual_CP1_ids=len({x['receipt'] for x in entries if x.get('receipt')}),tail_stock_controls=len(tails),tail_stocks_with_prior_negative_campaign=sum(x['prior_negative_campaigns']>0 for x in tails),unique_prior_negative_campaigns=sum(x['prior_negative_campaigns'] for x in tails),prior_negative_campaign_net=sum((x['prior_negative_net'] for x in tails),Z),prior_negative_campaign_buy_cash=sum((x['prior_negative_buy_cash'] for x in tails),Z),scope='Full endogenous saved book; layer and repeat observations dependent; actual reason tags not avoidable-loss claims')
 prefix=label.replace(':','-');save(prefix+'-ENTRIES.json',entries);save(prefix+'-STOCKS.json',stocks);save(prefix+'-TAIL_PREDECESSORS.json',tails);save(prefix+'-SUMMARY.json',summary)
 return summary,stocks,tails
def main():
 O.mkdir(exist_ok=True);summ={};stocks={};tails={};continu=P/'no60_behavior_v1/continuation2023';strong=P/'pvr_no60_2025_26'
 for label,root,export,layer in [('PVR_BASELINE:2022_2023',W/'pvr-slot1-native-readiness-20261101/continuation-2023-readiness/run-2023',continu,continu/'analysis/2023/PVR_BASELINE/LAYERS.json'),('PVR_NO60:2022_2023',P.parent/'pvr_pool_feasibility/continuation2023/run-2023',continu,continu/'analysis/2023/PVR_NO60/LAYERS.json'),('PVR_NO60:strong',P.parent/'pvr_pool_feasibility/runs/2025_26',strong,strong/'analysis/2025_26/PVR_NO60/LAYERS.json')]:
  summ[label],stocks[label],tails[label]=analyze(label,root,export,layer)
 adverse=stocks['PVR_NO60:2022_2023'];worst=adverse[0];repeat=sorted((x for x in adverse if x['sid']!=worst['sid'] and x['net']<0),key=lambda x:(-x['negative_campaigns'],x['net'],x['sid']))[0]
 recovery=sorted((x for x in tails['PVR_NO60:2022_2023'] if x['prior_negative_campaigns'] and x['all_stock_net']>0),key=lambda x:(-x['all_stock_net'],x['sid']))[0]
 strongrecovery=sorted((x for x in tails['PVR_NO60:strong'] if x['prior_negative_campaigns'] and x['all_stock_net']>0),key=lambda x:(-x['all_stock_net'],x['sid']))[0]
 cases=[dict(sid=worst['sid'],scope='2022_2023',criterion='largest cumulative negative stock wealth',frozen_row=worst),dict(sid=repeat['sid'],scope='2022_2023',criterion='most negative closed campaigns among net-negative stocks excluding first case; tie most negative wealth',frozen_row=repeat),dict(sid=recovery['sid'],scope='2022_2023',criterion='largest final positive stock wealth among tail controls with preceding negative flat campaign',frozen_row=recovery),dict(sid=strongrecovery['sid'],scope='strong',criterion='largest strong-window positive stock wealth among tails with preceding negative flat campaign',frozen_row=strongrecovery)]
 save('FIXED_FOUR_CASES.json',dict(selection='post-result exploratory; frozen before viewing newly selected raw OHLCV/state plots; no real-time labels',cases=cases,additional_cases=0));save('POPULATION_SUMMARY.json',summ);save('SOURCE_BINDING-PHASE1.json',dict(sources=SRC,script_sha256=sha(__file__),account_events=0,new_signals=0))
 print(json.dumps(dict(summaries=summ,cases=[{k:v for k,v in x.items() if k!='frozen_row'} for x in cases]),ensure_ascii=False,indent=2,default=str))
if __name__=='__main__':main()
