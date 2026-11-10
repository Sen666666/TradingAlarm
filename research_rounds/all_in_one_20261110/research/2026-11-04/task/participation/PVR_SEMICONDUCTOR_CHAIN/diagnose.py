from pathlib import Path
from collections import Counter,defaultdict
from decimal import Decimal as D
import json,gzip,hashlib
import pandas as pd
O=Path(__file__).resolve().parent
W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds');P=W/'pvr-slot1-native-readiness-20261101';R=P/'runs/2025_26/pair';A=P/'semiconductor-2026H1-readonly';Z=D(0);SRC={}
def read(p):
 p=Path(p);SRC[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
 if p.suffix=='.gz':
  with gzip.open(p,'rt')as f:return json.load(f)
 return json.loads(p.read_text())
def records(p):
 SRC[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
 with gzip.open(p,'rt')as f:return [json.loads(x)for x in f]
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str))
funnel=read(A/'SEMICONDUCTOR_OPPORTUNITY_FUNNEL.json')['all_receipts'];chain=read(A/'SEMICONDUCTOR_ALL_ACTUAL_NEW_BUY_CHAINS.json');curves=read(A/'DAILY_ALIGNED_CAPITAL.json');b=read(R/'B.json.gz');daily=records(R/'daily.jsonl.gz');dd={x['at'][:10]:x for x in daily};dates=list(dd);before={d:dates[i-1]for i,d in enumerate(dates)if i};after={d:dates[i+1]for i,d in enumerate(dates[:-1])};intents={(x['at'][:10],i['sid'],i['role']):i for x in b['decisions']for i in x['intents']};decnav={x['at'][:10]:D(x['nav'])for x in b['decisions']}
sm={x['symbol']:x for x in read(W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json')};rules=read('/Users/bytedance/Documents/ChatGPT/money/research_rounds/pvr-act-comparison-20261027/execution-rules-v2.json');frames={};sizing=[]
for e in funnel:
 if e['category']!='not_planned_original_target_or_sizing':continue
 sid=e['sid'];d=e['signal_day'];assert e['raw_reasons']==['no_nominal_gap']
 if sid not in frames:
  p=Path(sm[sid]['refs']['facts']);SRC[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();assert SRC[str(p)]==sm[sid]['output_sha256'][str(p)];frames[sid]=pd.read_parquet(p,columns=['raw_close'])
 price=D(str(frames[sid].loc[d,'raw_close']));nav=decnav[d];held=D(dd[d]['positions'].get(sid,0));gap=max(Z,nav*D('.1')-held*price);budget=min(nav*D('.02'),gap);vers=[v for v in rules['quantity_versions'][sid]if v['from']<=d and(v['to']is None or d<=v['to'])];assert len(vers)==1;rule=vers[0]['rule'];minimum=D(rule['buy_minimum'])*price
 assert minimum>budget
 sizing.append(dict(sid=sid,day=d,receipt=e['receipt'],held_quantity=held,price=price,NAV=nav,remaining_10pct_stock_gap=gap,budget=budget,legal_minimum_quantity=rule['buy_minimum'],minimum_gross=minimum,shortfall=minimum-budget,shortfall_pct_NAV=(minimum-budget)/nav*100,classification='positive_budget_below_minimum'if budget>0 else'zero_remaining_stock_gap'))
assert len(sizing)==257
rankrows=[]
for e in funnel:
 i=intents.get((e['signal_day'],e['sid'],'mobile'))
 if not i:continue
 rankrows.append(dict(sid=e['sid'],signal_day=e['signal_day'],receipt=e['receipt'],category=e['category'],priority=i['priority_rank'],H1_rank=i['original_H1_rank'],PVR=i['PVR_score'],frozen_budget=i['budget'],frozen_cap=i['cap'],same_stock_core_planned=(e['signal_day'],e['sid'],'core')in intents,raw_reasons=e['raw_reasons']))
rs={}
for cat in sorted({r['category']for r in rankrows}):
 x=[r for r in rankrows if r['category']==cat];pr=sorted(r['priority']for r in x);rs[cat]={'n':len(x),'unique_stocks':len({r['sid']for r in x}),'priority_min':min(pr),'priority_median':pd.Series(pr).median(),'priority_max':max(pr),'priority_le_10':sum(r<=10 for r in pr),'priority_le_50':sum(r<=50 for r in pr),'same_stock_core_planned':sum(r['same_stock_core_planned']for r in x)}
reject=[r for r in rankrows if r['category']=='opening_rejected_raw_merged_constraints'];comb=Counter(','.join(sorted(set(','.join(r['raw_reasons']).split(','))))for r in reject);tags=Counter(t for r in reject for t in set(','.join(r['raw_reasons']).split(',')))
semcurve={x['day']:x for x in curves if x['sector']=='URFI881121'};days=[d for d in dates if '2026-01-01'<=d<='2026-06-30'];close=[]
for d in days:
 x=dd[d];c=semcurve[d];nav=D(x['nav']);probecap=D(str(x['pool_probe'][0]));proberisk=D(str(x['pool_probe'][1]));confcap=D(str(x['pool_confirmed'][0]));semcap=D(c['industry_capital']);semrisk=D(c['industry_nominal_risk']);level={'observe':D('.02'),'probe':D('.02'),'confirmed':D('.1'),'expanded':D('.2')}[c['industry_stage']]
 close.append(dict(day=d,NAV=nav,confirmed_capital=confcap,confirmed60_excess=confcap-nav*D('.6'),probe_risk=proberisk,probe_halfpct_excess=proberisk-nav*D('.005'),probe_capital=probecap,probe10_excess=probecap-nav*D('.1'),sector_capital=semcap,sector_nominal_risk=semrisk,sector_1pct_excess=semrisk-nav*D('.01'),sector_stage=c['industry_stage'],sector_stage_cap_excess=semcap-nav*level,cash_above_close10=D(x['available'])-nav*D('.1'),clock='actual signal CLOSE after all planning, not exact candidate OPEN state'))
assert len(close)==116
cs={k:sum(x[k]>0 for x in close)for k in ['confirmed60_excess','probe_halfpct_excess','probe10_excess','sector_1pct_excess','sector_stage_cap_excess']};cs['both_confirmed60_and_probe_risk_exceeded']=sum(x['confirmed60_excess']>0 and x['probe_halfpct_excess']>0 for x in close);cs['cash_above10_positive']=sum(x['cash_above_close10']>0 for x in close)
closeidx={x['day']:x for x in close};rsclose={k:sum(closeidx[r['signal_day']][k]>0 for r in reject)for k in ['confirmed60_excess','probe_halfpct_excess','sector_1pct_excess','sector_stage_cap_excess']}
for r in rankrows:
 r['signal_close_resource']=closeidx[r['signal_day']]
acts={}
for action in sorted({z['entry_action']for z in chain}):
 x=[z for z in chain if z['entry_action']==action];acts[action]={'filled_layers':len(x),'gross_buy':sum((D(z['quantity'])*D(z['price'])for z in x),Z),'fees':sum((D(z['fees'])for z in x),Z),'closed_layers':sum(z['remaining_qty']==0 for z in x),'open_layers':sum(z['remaining_qty']>0 for z in x),'net_layer_contribution':sum((D(z['layer_net'])for z in x),Z),'not_all_realized':any(z['remaining_qty']>0 for z in x)}
exits=[]
for z in chain:
 for e in z['actual_exit']:exits.append(dict(e,entry_action=z['entry_action'],buy_signal_day=z['signal_day']))
post=[]
for sid in {z['sid']for z in chain}:
 flatdays=sorted({e['fully_closed_at'][:10]for e in exits if e['sid']==sid and e['fully_closed_at']})
 for d in flatdays:
  # True stock-flat confirmation from saved daily positions; reject partial layer exits.
  if dd[d]['positions'].get(sid,0):continue
  eligible=[r for r in funnel if r['sid']==sid and r['signal_day']>=d]
  post.append({'sid':sid,'actual_flat_day':d,'later_confirmed_stage_mobile_CP1_events':len(eligible),'categories':dict(Counter(r['category']for r in eligible)),'later_events':eligible})
summary={'old_PVR_has_account6_gate':False,'old_PVR_has_account3_gate':False,'new_C10_NO_AR6_is_not_this_policy_or_cause':True,'unique_833_not_planning_sizing_breakdown':dict(Counter(z['classification']for z in sizing)),'sizing_unique_stocks':len({z['sid']for z in sizing}),'positive_budget_minimum_distinct_stocks':len({z['sid']for z in sizing if z['budget']>0}),'planning_priority_by_outcome':rs,'opening_merged_reject_tag_presence':dict(tags),'opening_merged_reject_combinations':dict(comb),'close_resource_pressure_days_of_116':cs,'rejected_plan_signal_close_pressure_events_of_537':rsclose,'actual_entry_actions':acts,'actual_exit_count':len(exits),'actual_exit_reasons':dict(Counter(e['reason']for e in exits)),'actual_exit_first_sell_lag':dict(Counter(str(e['market_observations_to_first_sell'])for e in exits)),'financial_events':0,'new_price_labels':0,'no_relaxed_route_projection':True,'interpretation':'Reject tag union is recorded across considered routes. Presence and close pressure do not isolate exclusive removal causes or foregone PnL; repeat signal budgets cannot be summed as missed capital.'}
save('SUMMARY.json',summary);save('SIZING_ALL257.json',sizing);save('PLANNED_ALL576.json',rankrows);save('DAILY_CLOSE_RESOURCE_ALL116.json',close);save('ACTUAL_EXITS.json',exits);save('POST_FLAT_OPPORTUNITIES.json',post);save('SOURCE_SHA256.json',SRC)
print(json.dumps(summary,ensure_ascii=False,indent=2,default=str))
