"""Saved No60 records only; portfolio risk contract audit, no strategy run."""
from pathlib import Path
from decimal import Decimal as D
from collections import Counter
import json,gzip,hashlib,time
O=Path(__file__).resolve().parent;ROOT=O.parents[1];P=ROOT/'new_price_trend_v1/funding/runs/long_OFF/pair';SHA={}
def bind(p):
 p=Path(p);SHA[str(p.resolve())]=hashlib.sha256(p.read_bytes()).hexdigest();return p
def read(p):return json.loads(bind(p).read_text())
def load(p,lines=False):
 with gzip.open(bind(p),'rt')as f:return list(map(json.loads,f))if lines else json.load(f)
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
start=time.monotonic();bind(__file__)
b=load(P/'B.json.gz');daily=load(P/'daily.jsonl.gz',True);meta={r['sid']:r for r in read(ROOT/'core_confirmed_v1/analysis/long_OFF_STOCKS.json')}
snapshot=[]
for day in ['2024-09-23','2024-10-08','2024-10-09','2024-10-31','2024-12-23']:
 r=next(x for x in daily if x['at'][:10]==day);held=[dict(sid=s,shares=q,name=meta.get(s,{}).get('name'),industry=meta.get(s,{}).get('industry'))for s,q in r['positions'].items()];risk=sum((D(str(r[k][1]))for k in ['pool_probe','pool_confirmed']),D(0));capital=sum((D(str(r[k][0]))for k in ['pool_probe','pool_confirmed']),D(0))
 finance=[x for x in held if any(w in (x['industry']or'')for w in ['证券','保险','多元金融','银行'])]
 snapshot.append(dict(day=day,NAV=r['nav'],inventory=r['inventory'],stocks=len(held),actual_live_layers=len(r['layers']),ACT_on=r['on'],probe_resources=r['pool_probe'],confirmed_resources=r['pool_confirmed'],saved_line_distance_risk_sum=risk,saved_line_distance_risk_pct_NAV=100*risk/D(r['nav']),saved_capital_sum=capital,finance_stock_count=len(finance),finance_group_counts=dict(Counter(x['industry']for x in finance)),finance_holdings=finance,all_industry_stock_counts=dict(Counter(x['industry']for x in held)),pending_sells=r['pending_sells']))
events=[]
for day in ['2024-10-09','2024-12-23']:
 rs=[r for r in b['audit']if r.get('kind')=='pilot_layer_exit'and r.get('at','')[:10]==day];sids={r['sid']for r in rs};ids={i for r in rs for i in r['layers']}
 events.append(dict(day=day,exit_proposal_records=len(rs),stocks=len(sids),layers=len(ids),reason_counts=dict(Counter(r['reason']for r in rs)),industry_stock_counts=dict(Counter(meta.get(s,{}).get('industry')for s in sids)),proposals=rs))
sell_stats=[]
for day in ['2024-10-10','2024-12-24','2024-12-25']:
 rs=[r for r in b['trades']if r['at'][:10]==day and r['side']=='sell'];sell_stats.append(dict(day=day,sell_fills=len(rs),stocks=len({r['security_id']for r in rs}),net=sum((D(r['gross_cny'])-D(r['fees_cny'])for r in rs),D(0)),stocks_list=[r['security_id']for r in rs]))
save('ACCOUNT_RISK_CONTRACT_FACTS.json',dict(scope='Only native saved resource metrics and native stock/layer/exits. Risk sum is current marked price-to-known-line distance, not a loss guarantee; excludes gap/T+1/delay and cannot be read as prospective drawdown bound. Industry names are descriptive frozen metadata grouping, not empirical correlations or a live cluster rule.',snapshots=snapshot,coincident_exit_proposals=events,actual_sell_stats=sell_stats))
save('RISK_CONTRACT_SOURCE_SHA256.json',SHA);save('RISK_CONTRACT_SCOPE.json',dict(no_new_trading_object=True,no_new_parameter_or_backtest=True,runtime_seconds=time.monotonic()-start))
for x in snapshot:print(x['day'],x['stocks'],x['saved_line_distance_risk_sum'],x['saved_line_distance_risk_pct_NAV'],x['finance_group_counts'])
for x in events:print(x['day'],x['stocks'],x['layers'],x['industry_stock_counts'])
