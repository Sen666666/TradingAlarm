"""Saved NAV/resource/quantity/price snapshots only, no account/model methods."""
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict,Counter
import json,gzip,hashlib,pandas as pd
O=Path(__file__).resolve().parent;ROOT=O.parents[1];BASE=ROOT/'new_price_trend_v1/funding/runs/long_OFF/pair';Z=D(0);sources={}
def bind(p):
 p=Path(p);sources[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();return p
def read(p):return json.loads(bind(p).read_text())
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
def load(p,lines=False):
 with gzip.open(bind(p),'rt')as f:return list(map(json.loads,f))if lines else json.load(f)
b=load(BASE/'B.json.gz');all_daily=load(BASE/'daily.jsonl.gz',True);daily=[r for r in all_daily if r['at'][:4]in ['2022','2023']];meta={r['sid']:r for r in read(ROOT/'core_confirmed_v1/analysis/long_OFF_STOCKS.json')};m={r['symbol']:r for r in read('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')};prices={}
for sid in {s for r in daily for s in r['positions']}:
 f=pd.read_parquet(bind(m[sid]['refs']['facts']),columns=['raw_close']);prices[sid]=f['raw_close'].to_dict()
out=[];missing=[];prevnav=D(1000000);peak=D(1000000)
for r in daily:
 day=r['at'][:10];nav=D(r['nav']);peak=max(peak,nav);ts=pd.Timestamp(day);stocks=[]
 for sid,q in r['positions'].items():
  price=prices[sid].get(ts)
  if price is None:
   ks=[x for x in prices[sid]if x<=ts];price=prices[sid][max(ks)]if ks else None
   missing.append({'sid':sid,'day':day,'used_latest_prior_fact_raw':price is not None})
  if price is None:continue
  value=D(str(price))*D(q);stocks.append({'sid':sid,'name':meta.get(sid,{}).get('name'),'industry':meta.get(sid,{}).get('industry'),'shares':q,'value':value})
 sector=defaultdict(lambda:Z)
 for x in stocks:sector[x['industry']]+=x['value']
 inv=sum((x['value']for x in stocks),Z);residual=inv-D(r['inventory']);lc=Counter(l['sid']for l in r['layers']);stockmax=max(stocks,key=lambda x:x['value'],default=None);sectormax=max(sector.items(),key=lambda x:x[1],default=(None,Z));risk=D(str(r['pool_probe'][1]))+D(str(r['pool_confirmed'][1]))
 out.append({'day':day,'year':int(day[:4]),'NAV':nav,'daily_NAV_change':nav-prevnav,'unreset_initial_peak_drawdown_pct':100*(peak-nav)/peak,'ACT_on':r['on'],'inventory':D(r['inventory']),'inventory_pct_NAV':100*D(r['inventory'])/nav,'facts_inventory_residual':residual,'stocks':len(r['positions']),'layers':len(r['layers']),'max_concurrent_layers_same_stock':max(lc.values(),default=0),'stocks_with_multiple_layers':sum(n>1 for n in lc.values()),'largest_stock':stockmax,'largest_stock_pct_NAV':100*stockmax['value']/nav if stockmax else Z,'largest_industry':sectormax[0],'largest_industry_inventory':sectormax[1],'largest_industry_pct_NAV':100*sectormax[1]/nav,'saved_line_distance_risk':risk,'saved_line_distance_risk_pct_NAV':100*risk/nav,'pending_sell_stocks':len(r['pending_sells']),'industry_inventory':dict(sector)});prevnav=nav
summary={}
for year in [2022,2023]:
 rr=[r for r in out if r['year']==year];valid=[r for r in rr if abs(r['facts_inventory_residual'])<D('.000001')];acct=[a for a in b['audit']if a['kind']=='risk_checkpoint'and a['at'][:4]==str(year)];nonempty=[a for a in acct if a.get('event')]
 summary[str(year)]={'saved_CLOSEs':len(rr),'exact_price_inventory_CLOSEs':len(valid),'nonzero_inventory_residual_CLOSEs':[{'day':r['day'],'residual':r['facts_inventory_residual']}for r in rr if abs(r['facts_inventory_residual'])>=D('.000001')],'mean_inventory_pct_NAV':sum((r['inventory_pct_NAV']for r in rr),Z)/D(len(rr)),'maximum_inventory_pct_NAV':max(rr,key=lambda r:r['inventory_pct_NAV']),'maximum_concurrent_layers_same_stock':max(rr,key=lambda r:r['max_concurrent_layers_same_stock']),'maximum_saved_line_distance_risk_pct_NAV':max(rr,key=lambda r:r['saved_line_distance_risk_pct_NAV']),'largest_exact_industry_concentration':max(valid,key=lambda r:r['largest_industry_pct_NAV']),'largest_exact_single_stock_concentration':max(valid,key=lambda r:r['largest_stock_pct_NAV']),'worst_5_CLOSE_NAV_changes':sorted(rr,key=lambda r:r['daily_NAV_change'])[:5],'ACT_events':nonempty,'risk_checkpoint_last':acct[-1]}
save('ALL2022_2023_DAILY_CONCENTRATION_AND_RESOURCES.json',out);save('CONCENTRATION_AND_ACT_SUMMARY.json',summary);save('CONCENTRATION_SOURCE_SHA256.json',sources);save('FACT_PRICE_MISSING_CLOSE_ROWS.json',missing)
for year,r in summary.items():
 print(year,json.dumps({'closes':r['saved_CLOSEs'],'exact':r['exact_price_inventory_CLOSEs'],'nonzero':r['nonzero_inventory_residual_CLOSEs'],'mean_exposure':r['mean_inventory_pct_NAV'],'max_same_stock_layers':r['maximum_concurrent_layers_same_stock']['max_concurrent_layers_same_stock'],'max_single_stock':[(k,r['largest_exact_single_stock_concentration'][k])for k in ['day','largest_stock_pct_NAV','largest_stock']],'max_industry':[(k,r['largest_exact_industry_concentration'][k])for k in ['day','largest_industry_pct_NAV','largest_industry']],'risk_last':r['risk_checkpoint_last'],'events':r['ACT_events']},ensure_ascii=False,default=str))
