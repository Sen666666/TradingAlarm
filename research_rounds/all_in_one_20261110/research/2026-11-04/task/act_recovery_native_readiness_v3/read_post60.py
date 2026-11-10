"""Bounded original 60-CLOSE/303-buy arithmetic; no strategy execution."""
from pathlib import Path
from decimal import Decimal as D
import json,gzip,collections,hashlib
O=Path(__file__).resolve().parent;T=O.parent
paths={
 'book':T/'capacity_cost_guard_v1/runs/long-v1/arms/B/pair/B.json.gz',
 'daily':T/'capacity_cost_guard_v1/runs/long-v1/arms/B/pair/daily.jsonl.gz',
 'groups':T/'attribution_2024_chain_v2/No60_post_oct8_ALL_LAYERS.json',
 'initial_risk':T/'risk_constraints/entry_initial_risk_scale_v1/RESULTS.json',
 'initial_risk_readout':T/'risk_constraints/entry_initial_risk_scale_v1/READOUT.md',
 'initial_risk_review':T/'independent_review/ENTRY_INITIAL_NOMINAL_RISK_SCALE_AUDIT.json',
}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
with gzip.open(paths['book'],'rt')as f:b=json.load(f)
with gzip.open(paths['daily'],'rt')as f:all_daily=[json.loads(x)for x in f]
rows=[r for r in all_daily if '2024-10-08'<r['at'][:10]<='2024-12-31'];assert len(rows)==60
initial=next(r for r in all_daily if r['at'].startswith('2024-10-08'))
def risk(r):return D(str(r['pool_probe'][1]))+D(str(r['pool_confirmed'][1]))
def frac(r,v):return D(v)/D(r['nav'])*100
def fields(r):return {k:r[k]for k in ('at','nav','inventory','available','pool_probe','pool_confirmed','shared_loss','on','counts')}|dict(gross_pct_NAV=str(frac(r,r['inventory'])),nominal=str(risk(r)),nominal_pct_NAV=str(frac(r,risk(r))),confirmed_capital_pct_NAV=str(frac(r,r['pool_confirmed'][0])))
def desc(values):
 v=sorted(values);n=len(v)
 def q(p):
  z=D(n-1)*D(p);a=int(z);w=z-a
  return v[a]*(1-w)+v[min(a+1,n-1)]*w
 return dict(n=n,min=str(v[0]),mean=str(sum(v,D(0))/n),P50=str(q('.5')),P90=str(q('.9')),P95=str(q('.95')),max=str(v[-1]))
post_j=[r for r in b['journal']if r['kind']=='real_buy_fill'and '2024-10-08'<r['at'][:10]<='2024-12-31'];assert len(post_j)==303
tr=[r for r in b['trades']if '2024-10-08'<r['at'][:10]<='2024-12-31']
by=[r for r in tr if r['side']=='buy'];sells=[r for r in tr if r['side']=='sell'];assert len(by)==303
groups=json.loads(paths['groups'].read_text());new=[r for r in groups if r['group']=='new_actual_fill_in_phase'];assert len(new)==303
for r in new:
 assert r['layer']in{j['layer']for j in post_j}
pop=json.loads(paths['initial_risk'].read_text())['post_Oct8_new303_at_2024_cutoff']
result=dict(scope='Saved60CLOSE_resources_and_303_actual_buys; not intraday risk, new valuation or counterfactual',new_accounts=0,new_backtests=0,
 saved_closes=60,nonflat_closes=sum(D(r['inventory'])>0 for r in rows),ACT_on_closes=sum(bool(r['on'])for r in rows),
 initial_close=fields(initial),last_close=fields(rows[-1]),
 distributions_all_60=dict(gross_pct_NAV=desc([frac(r,r['inventory'])for r in rows]),nominal_pct_NAV=desc([frac(r,risk(r))for r in rows]),confirmed_capital_pct_NAV=desc([frac(r,r['pool_confirmed'][0])for r in rows]),confirmed_share_of_live_inventory_pct=desc([D(str(r['pool_confirmed'][0]))/D(r['inventory'])*100 for r in rows if D(r['inventory'])>0])),
 distributions_nonflat=dict(gross_pct_NAV=desc([frac(r,r['inventory'])for r in rows if D(r['inventory'])>0]),nominal_pct_NAV=desc([frac(r,risk(r))for r in rows if D(r['inventory'])>0])),
 gross_max_close=fields(max(rows,key=lambda r:frac(r,r['inventory']))),nominal_max_close=fields(max(rows,key=lambda r:frac(r,risk(r)))),
 observed_over3pct_nominal_closes=sum(risk(r)>D('.03')*D(r['nav'])for r in rows),observed_over60pct_confirmed_closes=sum(D(str(r['pool_confirmed'][0]))>D('.6')*D(r['nav'])for r in rows),
 maximum_close_resource_capital_minus_inventory=str(max(abs(D(str(r['pool_probe'][0]))+D(str(r['pool_confirmed'][0]))-D(r['inventory']))for r in rows)),
 shared_loss_start=initial['shared_loss'],shared_loss_end=rows[-1]['shared_loss'],shared_loss_increase=str(D(str(rows[-1]['shared_loss']))-D(str(initial['shared_loss']))),
 actual_buys=303,actual_sells=len(sells),role_pool_counts=[dict(role=k[0],pool=k[1],count=v)for k,v in collections.Counter((r['role'],r['pool'])for r in post_j).items()],
 new_gross_buy=str(sum((D(r['gross_cny'])for r in by),D(0))),new_buy_fees=str(sum((D(r['fees_cny'])for r in by),D(0))),sell_fees=str(sum((D(r['fees_cny'])for r in sells),D(0))),all_trade_fees=str(sum((D(r['fees_cny'])for r in tr),D(0))),
 entry_action_role_pool_counts=[dict(action=k[0],role=k[1],pool=k[2],count=v)for k,v in collections.Counter((r['action'],r['role'],r['pool_at_fill'])for r in new).items()],
 existing_initial_risk_population_reused=pop,
 full_saved_CLOSEs=[fields(r)for r in rows])
(O/'POST60_SAVED_RESOURCE_FACTS.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
(O/'POST60_SOURCE_BINDING.json').write_text(json.dumps(dict(sources={k:dict(path=str(p),sha256=sha(p))for k,p in paths.items()},script_sha256=sha(__file__),output_sha256=sha(O/'POST60_SAVED_RESOURCE_FACTS.json'),new_accounts=0,new_backtests=0),ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items()if k not in ('full_saved_CLOSEs','existing_initial_risk_population_reused')},ensure_ascii=False,indent=2))
