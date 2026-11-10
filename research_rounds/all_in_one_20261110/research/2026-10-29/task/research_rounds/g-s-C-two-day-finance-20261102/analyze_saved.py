"""Analyze the four saved two-session prefixes, never executes an account event."""
from pathlib import Path
from decimal import Decimal as D
from collections import Counter,defaultdict
import json,csv,hashlib
HERE=Path(__file__).resolve().parent;Z=D(0)
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
def flatten(x):
 if isinstance(x,list):return [z for y in x for z in flatten(y)]
 return [str(x)]
MASTER=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/current-pool-20261022/audit-snapshot/current-stock-master.industry-resolved.csv')
names={}
with MASTER.open() as f:
 for r in csv.DictReader(f):names[r['industry_index_symbol']]=r['industry_name']
def paths(window,mode):
 days=['2022-01-04','2022-01-05'] if window=='2022' else ['2025-07-01','2025-07-02']
 out=[]
 for day in days:
  for phase in ['OPEN','CLOSE']:
   root=HERE/'runs'/f'{window}-{mode}'
   if window=='2022' and mode=='C10' and day==days[-1] and phase=='CLOSE':root=HERE/'runs/2022-C10-recovered'
   out.append(root/(day+'-'+phase+'.json'))
 return out
def economy(x):
 a=x['account']
 return {k:a[k] for k in ['balance','layers','trades','fills','native_inventory','inventory_map','physical_lot_ids','native_settlements','native_dividends','native_actions','native_completed','exit_duties','buys','exits','cancel_requests','core_epochs','share_ratio']}
def summarize(p):
 x=read(p);a=x['account'];b=a['balance'];n=D(b['nav']);sectors=defaultdict(lambda:Z);roles=defaultdict(lambda:Z);pools=defaultdict(lambda:Z);uses=defaultdict(lambda:Z)
 holdings=[]
 for z in a['layers']:
  m=a['capital_meta'][str(z['id'])];v=D(z['qty'])*D(a['market_marks'][z['sid']]);sectors[m['sector']]+=v;roles[m['role']]+=v;pools[m['pool']]+=v;uses[m['purpose']]+=v
  holdings.append(dict(layer=z['id'],sid=z['sid'],qty=z['qty'],role=m['role'],pool=m['pool'],purpose=m['purpose'],sector=m['sector'],market_value=v,weight=v/n))
 rejections=Counter(tuple(sorted(set(flatten(r['route']['why'])))) for r in a['rejections'])
 plans=[]
 for result in x['results']:
  t=result['projection'];trace=t['trace'];diag=Counter()
  for row in trace:
   if row['q']==0:
    for k,v in row.get('blockers_or_necessary_bounds',{}).items():diag[k]+=v
  plans.append(dict(at=result['at'],demand_rows=len(trace),positive_Q={s:q for s,q in t['Q'].items() if q},zero_Q=sum(q==0 for q in t['Q'].values()),D=t['D'],validation_ok=t['validation']['ok'],zero_Q_diagnostics=dict(diag),diagnostic_unit='raw necessary-bound occurrences, may coexist; not independent opportunities'))
 lastplan=plans[-1] if plans else None
 budget=json.loads(x['budget'])['body']['batch'] if x['budget'] else None
 return dict(file=str(p.relative_to(HERE)),cursor=x['last_completed'],balance=b,exposure=D(b['inventory'])/n,
  buy_gross=sum((D(f['gross_cny']) for f in a['fills'] if f['side']=='buy'),Z),sell_gross=sum((D(f['gross_cny']) for f in a['fills'] if f['side']=='sell'),Z),fill_count=len(a['fills']),stock_count=len(b['quantities']),
  industry_market_values=[dict(sector=s,name=names.get(s),market_value=v,weight=v/n) for s,v in sorted(sectors.items(),key=lambda z:(-z[1],z[0]))],role_market_value=dict(roles),pool_market_value=dict(pools),purpose_market_value=dict(uses),holdings=holdings,
  pending_next_open_intents=len(x['pending']),active_buy_orders=a['buys'],sell_obligations=a['exits'],exit_duties=a['exit_duties'],locks=a['policy']['locks'],
  native_route_rejection_records=len(a['rejections']),native_route_rejection_signatures=[dict(reasons=list(k),records=v) for k,v in rejections.most_common()],
  native_route_rejection_unit='failed stock route attempts at OPEN, core/mobile alternative reasons combined; not canonical-receipt count',
  plans=plans,batch_budget=budget,actions=x['action_log'],last_plan=lastplan)
def main():
 out=HERE/'analysis';out.mkdir(exist_ok=False);arms={};comparisons={}
 for window in ['2022','2025_26']:
  for mode in ['C10','C_BATCH20']:
   arms[window+'-'+mode]=[summarize(p) for p in paths(window,mode)]
  checks=[]
  for pa,pb in zip(paths(window,'C10'),paths(window,'C_BATCH20')):
   a,b=read(pa),read(pb)
   checks.append(dict(cursor=a['last_completed'],native_economic_objects_equal=economy(a)==economy(b),pending_intents_equal=a['pending']==b['pending'],Q_D_equal=[(r['projection']['Q'],r['projection']['D']) for r in a['results']]==[(r['projection']['Q'],r['projection']['D']) for r in b['results']]))
  assert all(c['native_economic_objects_equal'] and c['pending_intents_equal'] and c['Q_D_equal'] for c in checks)
  comparisons[window]=checks
 fixed={p:sha(HERE.parent/p) for p in [
  'g-s-C-native-mixed-order-v1-20261102/native_c.py','g-s-C-native-mixed-order-v1-20261102/dispatch_order.py','g-s-C-two-day-entry-preparation-r2-20261102/prefix_entry.py',
  'g-s-readonly-historical-loader-r2-20261101/loader.py','g-s-readonly-historical-loader-r2-20261101/INPUT_PACKAGE_SHA256.json']}
 result=dict(scope='four exact two-session technical prefixes; no efficacy conclusion; no further account event',arms=arms,comparisons=comparisons,frozen_sources=fixed,financial_events_executed_by_analysis=0)
 save(out/'RESULTS.json',result)
 terminal={k:v[-1] for k,v in arms.items()};save(out/'TERMINALS.json',terminal)
 print(json.dumps({k:{f:v[f] for f in ['stock_count','fill_count','buy_gross','sell_gross','exposure','pending_next_open_intents','native_route_rejection_records']} for k,v in terminal.items()},ensure_ascii=False,indent=2,default=str))
if __name__=='__main__':main()
