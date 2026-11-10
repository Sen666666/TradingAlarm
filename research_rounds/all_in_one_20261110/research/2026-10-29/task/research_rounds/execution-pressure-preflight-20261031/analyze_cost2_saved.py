"""Only saved reference books; no execution or signal recomputation."""
import collections,gzip,inspect,json
from decimal import Decimal as D
from pathlib import Path
import pandas as pd
import pressure_runner as R
from initialization_guard import IO
J=R.J;L=R.L;Z=D(0)
M=J.W.load('pressure_saved_book_analyzer',J.O/'analyze_saved.py')
META=L.read(Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/inputs-v2/metadata.json'))
MAN={x['symbol']:x for x in L.read(L.U/'STOCK_MANIFEST.json')}
def gz(path):
 with gzip.open(path,'rt') as f:return json.load(f)
def lines(path):
 with gzip.open(path,'rt') as f:return [json.loads(x) for x in f]
def detail(origin):
 a=gz(origin/'pair/B.json.gz');daily=[r for r in lines(origin/'pair/daily.jsonl.gz') if r['account']=='B'];fund=[r for r in lines(origin/'pair/funding.jsonl.gz') if r['account']=='B'];prices={};series={}
 for sid in {x['sid'] for x in a['layers']}:
  f=pd.read_parquet(MAN[sid]['refs']['facts'],columns=['raw_close']).raw_close
  series[sid]=f;prices[sid]=D(str(f.asof(pd.Timestamp(J.END))))
 partitions=collections.defaultdict(lambda:Z);stock=collections.defaultdict(lambda:Z);layer_cost=collections.defaultdict(lambda:Z)
 # Actual original buy fills are the cost denominator; never mark appreciation as new cash.
 for t in a['trades']:
  if t['side']=='buy':layer_cost[t['layer']]=layer_cost.get(t['layer'],Z)+D(str(t['gross_cny']))+D(str(t['fees_cny']))
 for x in a['layers']:
  value=D(str(x['qty']))*prices[x['sid']];net=D(str(x['cash']))+D(str(x['dividend']))+value
  prefix='open' if x['qty'] else 'closed';cost=layer_cost[x['id']]
  cat=prefix+('_loss' if net<0 else '_tail_profit' if cost and net/cost>=D('.3') else '_ordinary_profit')
  partitions[cat]+=net;stock[x['sid']]+=net
 assert abs(sum(partitions.values(),Z)-(D(a['ending_NAV'])-D(1000000)))<D('.00001')
 filled={x.get('CP1_id') for x in a['journal'] if x['kind']=='real_buy_fill' and x.get('CP1_id')}
 admitted={x.get('CP1_id') for x in fund if x['role']=='mobile' and x['result']=='reserved' and x.get('CP1_id')}
 reentries=[];prior=collections.defaultdict(list)
 for x in sorted(a['layers'],key=lambda z:(z['opened'],z['id'])):
  earlier=prior[x['sid']]
  if earlier and all(q['closed'] and q['closed']<=x['opened'] for q in earlier):reentries.append(dict(sid=x['sid'],at=x['opened'],role=a['metadata'][str(x['id'])]['role']))
  prior[x['sid']].append(x)
 military=[dict(**t,name=META[t['security_id']]['name']) for t in a['trades'] if t['side']=='buy' and META[t['security_id']]['sector_id']=='URFI881276']
 positive=sorted(stock,key=stock.get,reverse=True)[:10]
 top=[dict(sid=s,name=META[s]['name'],industry=META[s]['industry'],net_contribution=stock[s],first_buy=next(t['at'] for t in a['trades'] if t['side']=='buy' and t['security_id']==s),peak_weight_pct=max((D(r['positions'].get(s,0))*D(str(series[s].asof(pd.Timestamp(r['at'][:10])))))/D(r['nav'])*100 for r in daily)) for s in positive]
 balance=[r for r in lines(origin/'pair/balances.jsonl.gz') if r['account']=='B'];keys=['independent_NAV_difference','budget_NAV_difference','spendable_difference','reserved_difference','capital_occupancy_difference','maximum_stock_quantity_difference']
 checks={k:max(abs(D(str(r[k]))) for r in balance) for k in keys}
 return dict(layer_signed_NAV_partitions=dict(partitions),partition_unit='actual buy layers; overlapping layers are descriptive, not independent trials',tail_definition='layer terminal net / actual buy cash >= 30%; same diagnostic as prior normal report',mobile_receipts_reserved=len(admitted),mobile_receipts_with_fill=len(filled),mobile_receipts_without_fill=len(admitted-filled),exit_requests=sum(x['kind']=='exit_request' for x in a['audit']),sell_fill_records=sum(t['side']=='sell' for t in a['trades']),terminal_pending_stock_exits=len(a['exits']),actual_flat_reentries=reentries,military_actual_buys=military,top10_positive_stock=top,named_stocks=[dict(sid=s,name=META[s]['name'],buy_fills=sum(t['side']=='buy' and t['security_id']==s for t in a['trades']),net_contribution=stock[s]) for s in ('300308.SZ','300502.SZ')],account_days=len(balance),maximum_accounting_differences=checks)
def analyze(ref,normal,stress):
 out=R.O/'analysis'/ref;out.mkdir(parents=True,exist_ok=True)
 if not (stress/'DONE.json').exists():return
 freeze=L.read(stress/'FREEZE.json')['sources'];assert all(L.sha(Path(p))==h for p,h in freeze.items()),'input/code changed during pressure run'
 def accounts(path):return gz((normal if Path(path).name=='A.json.gz' else stress)/'pair/B.json.gz')
 def rows(path):
  for alias,origin in [('A',normal),('B',stress)]:
   for r in lines(origin/'pair'/Path(path).name):
    if r['account']=='B':yield dict(r,account=alias)
 source=inspect.getsource(M.main);needle="out=J.O/('run-'+scope);pair=out/'pair';assert L.read(out/'DONE.json')['completed']";assert source.count(needle)==1
 source=source.replace(needle,"out=OUT;pair=out/'source_alias_only';assert all(L.read(p/'DONE.json')['completed'] for p in (NORMAL,STRESS))")
 # Native position dictionaries can retain a zero-share cancelled-order key.
 # It contributes exactly zero inventory and is not a held-price observation.
 needle="for sid,q in r['positions'].items():vals[sector[sid]]+=D(q)*price(sid,d)";assert source.count(needle)==1
 source=source.replace(needle,"for sid,q in r['positions'].items():\n    if q:vals[sector[sid]]+=D(q)*price(sid,d)")
 env=dict(M.__dict__,gz=accounts,rows=rows,OUT=out,NORMAL=normal,STRESS=stress);exec(source,env);env['main']('unused')
 summary=L.read(out/'SUMMARY.json');summary['metrics']={('normal' if k=='A' else 'cost2'):v for k,v in summary['metrics'].items()};summary['reference']=ref
 IO.write_json(out/'SUMMARY.json',summary)
 IO.write_json(out/'BEHAVIOR_AND_ACCOUNTING.json',J.W.canon({k:detail(p) for k,p in [('normal',normal),('cost2',stress)]}))
 books={k:gz(p/'pair/B.json.gz') for k,p in [('normal',normal),('cost2',stress)]}
 stockbooks={}
 for k,a in books.items():
  sbook=collections.defaultdict(lambda:dict(gross_trade_cashflow=Z,fees=Z,dividends=Z,terminal_inventory=Z))
  for t in a['trades']:
   x=sbook[t['security_id']];x['gross_trade_cashflow']+=D(t['gross_cny'])*(1 if t['side']=='sell' else -1);x['fees']+=D(t['fees_cny'])
  for x in a['audit']:
   if x['kind']=='dividend_accrual':
    v=x['receivable'];sbook[v['security_id']]['dividends']+=D(v['net_local'])
  for x in a['layers']:
   if x['qty']:
    f=pd.read_parquet(MAN[x['sid']]['refs']['facts'],columns=['raw_close']).raw_close
    sbook[x['sid']]['terminal_inventory']+=D(x['qty'])*D(str(f.asof(pd.Timestamp(J.END))))
  for s,x in sbook.items():x['net']=x['gross_trade_cashflow']-x['fees']+x['dividends']+x['terminal_inventory']
  assert abs(sum((x['net'] for x in sbook.values()),Z)-(D(a['ending_NAV'])-D(1000000)))<D('.00001')
  stockbooks[k]=dict(sbook)
 deltas=[]
 for sid in set(stockbooks['normal'])|set(stockbooks['cost2']):
  aa=stockbooks['normal'].get(sid,{});bb=stockbooks['cost2'].get(sid,{})
  x={n:bb.get(n,Z)-aa.get(n,Z) for n in ('gross_trade_cashflow','fees','dividends','terminal_inventory','net')}
  deltas.append(dict(sid=sid,name=META[sid]['name'],industry=META[sid]['industry'],normal=aa,cost2=bb,delta=x))
 bridge={n:sum((x['delta'][n] for x in deltas),Z) for n in ('gross_trade_cashflow','fees','dividends','terminal_inventory','net')}
 assert abs(bridge['net']-(D(books['cost2']['ending_NAV'])-D(books['normal']['ending_NAV'])))<D('.00001')
 IO.write_json(out/'DESCRIPTIVE_TERMINAL_BRIDGE.json',J.W.canon(dict(components=bridge,identity='delta gross trade cashflow - delta fees + delta accrued dividends + delta final inventory = delta NAV',not_single_mechanism_causal_attribution=True,stocks=sorted(deltas,key=lambda x:x['delta']['net']))))
 maps={}
 for k,a in books.items():
  mm=collections.defaultdict(lambda:dict(shares=0,gross=Z,fees=Z))
  for t in a['trades']:
   key=(t['at'],t['side'],t['security_id']);mm[key]['shares']+=t['shares'];mm[key]['gross']+=D(t['gross_cny']);mm[key]['fees']+=D(t['fees_cny'])
  maps[k]=mm
 keys=sorted(set(maps['normal'])|set(maps['cost2']));first_econ=next((k for k in keys if maps['normal'].get(k)!=maps['cost2'].get(k)),None)
 first_qty=next((k for k in keys if maps['normal'].get(k,{}).get('shares',0)!=maps['cost2'].get(k,{}).get('shares',0)),None)
 days={k:{r['at'][:10]:r for r in lines(p/'pair/daily.jsonl.gz') if r['account']=='B'} for k,p in [('normal',normal),('cost2',stress)]}
 act=next((d for d in sorted(days['normal']) if days['normal'][d]['on']!=days['cost2'][d]['on']),None)
 IO.write_json(out/'FIRST_DIVERGENCES.json',J.W.canon(dict(first_economic_fill_key=first_econ,first_economic_fill={k:maps[k].get(first_econ) for k in maps},first_quantity_fill_key=first_qty,first_quantity_fill={k:maps[k].get(first_qty) for k in maps},first_ACT_close_difference=act,unchanged_source_hashes_after_run=True,normal_books_not_replayed=True)))
 print('PRESSURE_KEY',ref,json.dumps({k:{n:float(v[n]) for n in ('return_pct','DD_pct','fees','average_exposure_pct','peak_exposure_pct')} for k,v in summary['metrics'].items()}),flush=True)
if __name__=='__main__':
 analyze('B3',J.O/'run-universe',R.O/'cost2-runs/B3')
 analyze('B_diag',R.BASE.O/'run',R.O/'cost2-runs/B_diag')
