"""Arithmetic over saved actual fills, quantities and as-of snapshots only.
No strategies, indicators, accounts, markets or hypothetical orders are executed.
"""
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict,Counter
import json,gzip,hashlib,csv
O=Path(__file__).resolve().parent;ROOT=O.parents[1]
BASE=ROOT/'new_price_trend_v1/funding/runs/long_OFF/pair';Z=D(0);EPS=D('.000001');sources={}
def bind(p):
 p=Path(p);sources[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();return p
def read(p):return json.loads(bind(p).read_text())
def load(p,lines=False):
 with gzip.open(bind(p),'rt')as f:return list(map(json.loads,f))if lines else json.load(f)
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
def day(x):return str(x)[:10]
def eq(x,y,label):assert abs(x-y)<EPS,(label,str(x),str(y),str(x-y))
b=load(BASE/'B.json.gz');daily=load(BASE/'daily.jsonl.gz',True);byday={day(r['at']):r for r in daily};layers={l['id']:l for l in b['layers']}
meta={r['sid']:r for r in read(ROOT/'core_confirmed_v1/analysis/long_OFF_STOCKS.json')}
marks={r['sid']:D(r['saved_facts_raw_close'])for r in read(O/'END2022_STOCK_INVENTORY.json')['rows']}
txs=defaultdict(list)
for t in b['trades']:txs[day(t['at'])].append(t)
splits=defaultdict(list)
for a in b['audit']:
 if a['kind']=='split':splits[day(a['at'])].append(a)
# Original previous-CLOSE inventory assigns actual recognized dividend entitlement.
div_ev=defaultdict(list);prev_day={day(r['at']):daily[i-1] if i else None for i,r in enumerate(daily)}
for a in b['audit']:
 if a['kind']!='dividend_accrual':continue
 rec=a['receivable'];date=day(rec['ex_at']);prev=prev_day[date]
 entitled=[l for l in prev['layers']if l['sid']==rec['security_id'] and l['qty']]
 q=sum(l['qty']for l in entitled);assert q>0
 for l in entitled:div_ev[date].append((l['id'],D(rec['net_local'])*D(l['qty'])/D(q)))
# Classify every buy using actual pre-fill quantities; preserve original chronology.
seen=set();classes={};cycles=[];active={};last_cycle={};prev_layers=[];signal_fill_changes=[];cycle_id=0
for r in daily:
 date=day(r['at']);qby={l['id']:int(l['qty'])for l in prev_layers}
 for a in splits[date]:
  for lid in qby:
   if layers[lid]['sid']==a['sid']:qby[lid]=int(D(qby[lid])*D(a['ratio']))
 current=defaultdict(int)
 for lid,q in qby.items():current[layers[lid]['sid']]+=q
 for lid,amount in div_ev[date]:
  sid=layers[lid]['sid']
  if sid in active:active[sid]['recognized_dividend']+=amount
 for t in txs[date]:
  sid=t['security_id'];before=current[sid]
  if t['side']=='buy':
   classification='add_to_existing' if before else 'reentry' if sid in seen else 'first_account_entry'
   previous=last_cycle.get(sid)
   if not before:
    cycle_id+=1
    active[sid]={'cycle_id':cycle_id,'sid':sid,'name':meta.get(sid,{}).get('name'),'opened':t['at'],'closed':None,'buy_cash':Z,'net_sale_cash':Z,'recognized_dividend':Z,'layers':[],'opening_class':classification,'previous_closed_cycle_net':previous['closed_net']if previous else None,'previous_closed':previous['closed']if previous else None,'last_exit_reason':None}
    cycles.append(active[sid])
   cy=active[sid];prior_losing=cy['previous_closed_cycle_net']is not None and cy['previous_closed_cycle_net']<0
   record={'layer':t['layer'],'sid':sid,'name':meta.get(sid,{}).get('name'),'industry':meta.get(sid,{}).get('industry'),'opened':t['at'],'signal_at':t['signal_at'],'kind':t['kind'],'classification':classification,'actual_quantity_before_fill':before,'cycle_id':cy['cycle_id'],'cycle_opening_class':cy['opening_class'],'cycle_after_prior_closed_loss':prior_losing,'previous_closed_cycle_net':cy['previous_closed_cycle_net'],'previous_closed':cy['previous_closed'],'signal_CLOSE_quantity':byday[day(t['signal_at'])]['positions'].get(sid,0),'shares':t['shares'],'price':t['price'],'floor_a':t['floor'],'buy_cash_cost':D(t['gross_cny'])+D(t['fees_cny'])}
   classes[t['layer']]=record
   if bool(record['signal_CLOSE_quantity'])!=bool(before):signal_fill_changes.append(record)
   current[sid]+=t['shares'];seen.add(sid);cy['layers'].append(t['layer']);cy['buy_cash']+=record['buy_cash_cost']
  else:
   assert before>=t['shares'],('oversell',t['at'],sid,before,t['shares'])
   current[sid]-=t['shares'];cy=active[sid];cy['net_sale_cash']+=D(t['gross_cny'])-D(t['fees_cny']);cy['last_exit_reason']=t.get('reason')
   if not current[sid]:
    cy['closed']=t['at'];cy['closed_net']=cy['net_sale_cash']+cy['recognized_dividend']-cy['buy_cash'];last_cycle[sid]=cy;del active[sid]
 eq(sum((D(l['qty'])for l in r['layers']),Z),D(sum(r['positions'].values())),('saved layer quantities',date))
 assert {sid:q for sid,q in current.items()if q}==r['positions'],('quantity bridge',date)
 prev_layers=r['layers']
assert not active
assert len(classes)==len(layers)
# Reconstruct three anchors from saved actual cash parts and recognized rights.
anchors={}
for date in ['2022-01-04','2022-12-30','2023-12-29']:
 r=byday[date];cash=defaultdict(lambda:Z);div=defaultdict(lambda:Z)
 for d,ts in txs.items():
  if d>date:continue
  for t in ts:
   if t['side']=='buy':cash[t['layer']]-=D(t['gross_cny'])+D(t['fees_cny'])
   else:
    for part in t['parts']:cash[part['layer']]+=D(part['net_cash'])
 for d,items in div_ev.items():
  if d<=date:
   for lid,amount in items:div[lid]+=amount
 live={l['id']:l for l in r['layers']};vals={}
 for lid,l in layers.items():
  inv=D(live[lid]['qty'])*marks[l['sid']]if lid in live else Z
  vals[lid]={'cash':cash[lid],'dividend':div[lid],'inventory':inv,'wealth':cash[lid]+div[lid]+inv,'qty':live.get(lid,{}).get('qty',0)}
  if lid in live:
   eq(cash[lid],D(live[lid]['cash']),('cash',date,lid));eq(div[lid],D(live[lid]['dividend']),('dividend',date,lid))
 eq(sum((v['inventory']for v in vals.values()),Z),D(r['inventory']),('inventory anchor',date))
 eq(D(1000000)+sum((v['wealth']for v in vals.values()),Z),D(r['nav']),('NAV anchor',date));anchors[date]=vals
results={};layer_annual=[]
for year,start,end in [(2022,'2022-01-04','2022-12-30'),(2023,'2022-12-30','2023-12-29')]:
 groups={};stock=defaultdict(lambda:Z);industry=defaultdict(lambda:Z);yr_rows=[r for r in daily if day(r['at']).startswith(str(year))]
 for lid,l in layers.items():
  a,z=anchors[start][lid],anchors[end][lid];change=z['wealth']-a['wealth']
  if day(l['opened'])>end:continue
  cls=classes[lid];carry=day(l['opened'])<str(year)+'-01-01'
  row={**cls,'year':year,'carry_from_previous_year':carry,'begin_qty':a['qty'],'end_qty':z['qty'],'begin_inventory':a['inventory'],'end_inventory':z['inventory'],'begin_wealth':a['wealth'],'end_wealth':z['wealth'],'annual_wealth_change':change}
  if change or a['qty']or z['qty']:layer_annual.append(row)
  if change or a['qty']or z['qty']:
   stock[l['sid']]+=change;industry[cls['industry']]+=change
  group='carry_from_previous_year'if carry else cls['classification']
  for dimension,key in [('actual_entry_class',group),('role','carry_from_previous_year'if carry else l['kind']),('cycle_after_previous_loss','carry_from_previous_year'if carry else str(cls['cycle_after_prior_closed_loss']))]:
   name=dimension+'|'+key;g=groups.setdefault(name,{'dimension':dimension,'group':key,'layers':0,'annual_change':Z,'negative_layer_sum':Z,'positive_layer_sum':Z,'new_buy_cash':Z})
   if change or a['qty']or z['qty']:g['layers']+=1
   g['annual_change']+=change
   if change<0:g['negative_layer_sum']+=change
   elif change>0:g['positive_layer_sum']+=change
   if day(l['opened']).startswith(str(year)):g['new_buy_cash']+=cls['buy_cash_cost']
 eq(sum(stock.values(),Z),D(byday[end]['nav'])-D(byday[start]['nav']),('annual stock NAV',year))
 buys=[t for t in b['trades']if t['side']=='buy'and day(t['at']).startswith(str(year))];sells=[t for t in b['trades']if t['side']=='sell'and day(t['at']).startswith(str(year))]
 peak=D(byday[start]['nav']);peakday=start;mdd=Z;ddpair=None
 for r in yr_rows:
  nav=D(r['nav'])
  if nav>peak:peak=nav;peakday=day(r['at'])
  dd=(peak-nav)/peak
  if dd>mdd:mdd=dd;ddpair={'peak_day':peakday,'peak_NAV':peak,'trough_day':day(r['at']),'trough_NAV':nav,'wealth_change':nav-peak}
 result={'year':year,'begin_day':start,'end_day':end,'begin_NAV':byday[start]['nav'],'end_NAV':byday[end]['nav'],'annual_NAV_change':D(byday[end]['nav'])-D(byday[start]['nav']),'return_pct':(D(byday[end]['nav'])/D(byday[start]['nav'])-1)*100,'buy_fills':len(buys),'sell_fills':len(sells),'fees':sum((D(t['fees_cny'])for t in buys+sells),Z),'buy_cash':sum((D(t['gross_cny'])+D(t['fees_cny'])for t in buys),Z),'net_sale_cash':sum((D(t['gross_cny'])-D(t['fees_cny'])for t in sells),Z),'new_dividend_recognized':sum((amount for d,ev in div_ev.items()if d.startswith(str(year))for lid,amount in ev),Z),'maximum_CLOSE_drawdown_pct':100*mdd,'drawdown_pair':ddpair,'groups':list(groups.values()),'stock_negative_contributions_sum':sum((x for x in stock.values()if x<0),Z),'stock_positive_contributions_sum':sum((x for x in stock.values()if x>0),Z),'stock_contributions':[{'sid':sid,'name':meta.get(sid,{}).get('name'),'industry':meta.get(sid,{}).get('industry'),'annual_change':v}for sid,v in sorted(stock.items(),key=lambda x:x[1])],'industry_contributions':[{'industry':key,'annual_change':v}for key,v in sorted(industry.items(),key=lambda x:x[1])]}
 results[str(year)]=result
save('ORIGINAL_BUY_CLASSIFICATIONS.json',classes);save('ORIGINAL_POSITION_CYCLES.json',cycles);save('ANNUAL_LAYER_WEALTH_CHANGES.json',layer_annual);save('ANNUAL_CONTRIBUTION_SUMMARY.json',results)
save('QUANTITY_AND_CASH_BRIDGE_REVIEW.json',{'all_original_CLOSE_quantity_days_exact':len(daily),'classified_buys':len(classes),'original_cycles':len(cycles),'signal_CLOSE_vs_prefill_held_mismatches':signal_fill_changes,'anchor_inventory_and_NAV_exact':True,'new_accounts':0,'new_backtests':0,'native_modules_imported':False,'selection_outcomes_not_used_as_signals':True})
save('AGGREGATION_SOURCE_SHA256.json',sources)
for year,r in results.items():
 print(year,json.dumps({k:v for k,v in r.items()if k not in ['stock_contributions','industry_contributions','groups']},ensure_ascii=False,default=str));print(json.dumps(r['groups'],ensure_ascii=False,default=str));print('bottom10',json.dumps(r['stock_contributions'][:10],ensure_ascii=False,default=str));print('top5',json.dumps(r['stock_contributions'][-5:],ensure_ascii=False,default=str))
