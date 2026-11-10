"""Existing ledgers only: no Runner, fills or policy replay."""
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict
from datetime import datetime
import json,gzip,csv,sys
O=Path(__file__).resolve().parent;W=O.parent;BASE=W/'entry-loss-budget-full-account-20261031';COST=W/'entry-loss-budget-cost2-funnel-20261031';sys.path.insert(0,str(BASE));import wire as w
Z=D(0)
def gz(p):
 with gzip.open(p,'rt') as f:return [json.loads(x) for x in f]
def save(p,x):w.K.save(p,x)
def load(root,sec,aid,market=None):
 path=root/sec/'on';a=w.read(path/'accounts-v2'/f'{aid}.json');logs=a['audit_log'];daily={x['at']:x for x in gz(path/'accounts-v2/daily.jsonl.gz') if x['account']==aid};end=list(daily.values())[-1];st=w.read(path/f'{aid}-structure-final.json');stock=defaultdict(lambda:Z)
 for x in logs:
  if x['kind']=='loss_end':stock[x['sid']]+=D(x['net'])
 for x in st['open']:
  s=x['symbol'];stock[s]+=D(end['positions'][s])*market.latest_mark(s,datetime.fromisoformat(end['at'])).cny_price(datetime.fromisoformat(end['at']))+D(x['div'])+D(x['sales'])-D(x['K'])
 assert sum(stock.values(),Z)==D(end['nav'])-1000000,(aid,'stock bridge')
 raw=Z;slip=Z;fees=Z;div=Z
 for x in logs:
  if x['kind']=='fill':
   r=x['receipt'];sgn=1 if r['side']=='sell' else -1;raw+=sgn*D(x['raw_open'])*r['shares']*D(x['fx_rate']);slip+=abs(D(x['price'])-D(x['raw_open']))*r['shares']*D(x['fx_rate']);fees+=D(r['fees_cny'])
  elif x['kind']=='dividend_accrual':div+=D(x['receivable']['net_local'])
 bridge=dict(raw_open_trade_cashflow=raw,attributed_dividends=div,terminal_inventory=D(end['inventory']),explicit_fees=fees,execution_slippage=slip,net=sum(stock.values(),Z));assert raw+div+D(end['inventory'])-fees-slip==bridge['net'],(aid,'raw cashflow bridge')
 caps=list(csv.DictReader((path/'analysis/campaigns.csv').open()));names={x['symbol']:x['name'] for x in caps};return dict(a=a,logs=logs,daily=daily,end=end,stock=stock,bridge=bridge,root=path,aid=aid,names=names)
def first(a,b,kind,signature):
 aa={x['at']:signature(x) for x in a['logs'] if x['kind']==kind};bb={x['at']:signature(x) for x in b['logs'] if x['kind']==kind}
 t=next((t for t in sorted(set(aa)|set(bb)) if aa.get(t)!=bb.get(t)),None);return dict(at=t,left=aa.get(t),right=bb.get(t))
def fills_bydate(x):
 d=defaultdict(list)
 for f in x['a']['fills']:d[f['at']].append((f['security_id'],f['side'],f['shares']))
 return {k:sorted(v) for k,v in d.items()}
def pair(label,a,b,dates):
 delta={s:b['stock'].get(s,Z)-a['stock'].get(s,Z) for s in set(a['stock'])|set(b['stock'])};netdelta=b['bridge']['net']-a['bridge']['net'];assert sum(delta.values(),Z)==netdelta
 bd={k:b['bridge'][k]-a['bridge'][k] for k in a['bridge']};assert bd['raw_open_trade_cashflow']+bd['attributed_dividends']+bd['terminal_inventory']-bd['explicit_fees']-bd['execution_slippage']==netdelta
 ff=fills_bydate(a);gg=fills_bydate(b);tf=next((t for t in sorted(set(ff)|set(gg)) if ff.get(t)!=gg.get(t)),None)
 aq={x['at']:x for x in a['logs'] if x['kind']=='risk_checkpoint'};bq={x['at']:x for x in b['logs'] if x['kind']=='risk_checkpoint'};ta=next((t for t in aq if aq[t]['on']!=bq[t]['on']),None)
 log_adm={z['aid']:{x['at']:x for x in z['logs'] if x['kind']=='loss_admission'} for z in [a,b]};snap=[]
 for day in dates:
  for z in [a,b]:
   t=next((t for t in z['daily'] if t.startswith(day)),None)
   if t:
    l=log_adm[z['aid']][t];d=z['daily'][t];snap.append(dict(arm=z['aid'],at=t,ACT=next(x for x in z['logs'] if x['kind']=='risk_checkpoint' and x['at']==t),daily=d,accepted=l['accepted'],rejected=l['rejected'],eligible=[e for e in l['decisions'][0]['eligibility'] if e['q'] is True],exit_requests=l['decisions'][0]['exit_requests'],budget_requests=[x for x in z['logs'] if x['kind']=='loss_budget_request' and x['at']==t],actual_fills=[f for f in z['a']['fills'] if f['at'].startswith(day)]))
 names=dict(a['names'],**b['names']);out=dict(label=label,left=a['aid'],right=b['aid'],left_money=a['bridge'],right_money=b['bridge'],difference=bd,exact_delta=netdelta,stock_difference=[dict(symbol=s,name=names.get(s),left=a['stock'].get(s,Z),right=b['stock'].get(s,Z),delta=d) for s,d in sorted(delta.items(),key=lambda x:-abs(x[1]))],first_reserve=first(a,b,'reserve',lambda x:{k:x[k] for k in ['sid','gross_budget_cny','fee_reserved_cny','target_shares']}),first_actual_fill_set_or_quantity_difference=dict(at=tf,left=ff.get(tf),right=gg.get(tf)),first_budget_request_difference=first(a,b,'loss_admission',lambda x:[(y['sid'],y['at']) for y in a['logs'] if y['kind']=='loss_budget_request' and y['at']==x['at']]) if False else None,first_ACT_on_difference=dict(at=ta,left=aq.get(ta),right=bq.get(ta)),first_acceptance_difference=first(a,b,'loss_admission',lambda x:x['accepted']),snapshots=snap)
 ar={(x['sid'],x['at']):x for x in a['logs'] if x['kind']=='loss_budget_request'};br={(x['sid'],x['at']):x for x in b['logs'] if x['kind']=='loss_budget_request'};diff=sorted(set(ar)^set(br),key=lambda k:(k[1],k[0]));out['first_budget_request_difference']=dict(key=diff[0],left=ar.get(diff[0]),right=br.get(diff[0])) if diff else None
 save(O/f'{label}.json',out);w.K.export(O/f'{label}-stock-difference.csv',out['stock_difference']);print(label,'delta',netdelta,'fees',bd['explicit_fees'],'slip',bd['execution_slippage'],'raw',bd['raw_open_trade_cashflow']+bd['attributed_dividends']+bd['terminal_inventory']);print('first set/qty',tf,ff.get(tf),gg.get(tf));print('first ACT',out['first_ACT_on_difference']);print('first accepted',out['first_acceptance_difference']);print('top',out['stock_difference'][:6])
tmp=O/'quote-context';tmp.mkdir(exist_ok=True);import shutil;shutil.copyfile(w.RR/'pvr-act-comparison-20261027/execution-rules-v2.json',tmp/'execution-rules-v2.json');R,E,_,_,_=w.setup('DRUG',tmp,False);_,market=R.context()
a=load(BASE,'DRUG','ACT__C10_S0_base',market);b=load(COST,'DRUG','ACT__C10_S0_cost2',market);pair('DRUG-C10-normal-vs-cost2',a,b,['2023-12-29','2024-01-02','2024-09-24','2024-09-25','2024-09-26','2024-09-27','2024-12-18','2024-12-19','2024-12-23','2025-01-10'])
a=load(BASE,'TECH','I__C20_S0_base');b=load(BASE,'TECH','I__C20_S0_delay1');pair('TECH-C20-normal-vs-delay',a,b,['2024-01-02','2024-01-03','2024-12-30','2024-12-31','2025-01-02','2025-02-10','2025-06-10','2025-10-20','2025-11-20','2025-11-21','2026-01-05','2026-07-07','2026-07-13'])
