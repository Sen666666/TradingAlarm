"""Only saved continuous books; Q2 and whole-period clocks are kept separate."""
from pathlib import Path
from decimal import Decimal as D
import json,gzip,sys
O=Path(__file__).resolve().parent
sys.path.insert(0,str(O.parent/'execution-pressure-preflight-20261031'));from initialization_guard import IO
def rows(p):
 with gzip.open(p,'rt') as f:return [json.loads(x) for x in f]
def obj(p):
 with gzip.open(p,'rt') as f:return json.load(f)
def dd(v):
 peak=v[0];worst=D(0)
 for x in v:peak=max(peak,x);worst=max(worst,1-x/peak)
 return worst*100
def mean(x):return sum(x,D(0))/len(x)
out=[]
for ref in ('B3','B_diag'):
 p=O/'runs'/ref
 if not (p/'DONE.json').exists():continue
 a=obj(p/'pair/B.json.gz');daily=rows(p/'pair/daily.jsonl.gz');assert all(x['account']=='B' for x in daily)
 assert len({x['at'][:10] for x in daily})==len(daily)
 start=next(x for x in daily if x['at'][:10]=='2026-03-31');q=[x for x in daily if '2026-04-01'<=x['at'][:10]<='2026-06-30'];assert len(q)==60
 nav0=D(start['nav']);nav1=D(a['ending_NAV']);ex=[D(x['inventory'])/D(x['nav'])*100 for x in q];cash=[D(x['available'])/D(x['nav'])*100 for x in q];confirmed=[D(str(x['pool_confirmed'][0]))/D(x['nav'])*100 for x in q];probe=[D(str(x['pool_probe'][0]))/D(x['nav'])*100 for x in q]
 tr=[t for t in a['trades'] if t['at'][:10]>='2026-04-01'];cost=sum((D(t['fees_cny']) for t in tr),D(0));phases=[x for x in a['audit'] if x['kind']=='risk_checkpoint' and x['at'][:10]>='2026-04-01' and x.get('event') is not None]
 month=[]
 for m in ('2026-04','2026-05','2026-06'):
  r=[x for x in q if x['at'].startswith(m)];tx=[x for x in tr if x['at'].startswith(m)]
  month.append(dict(month=m,mean_exposure_pct=str(mean([D(x['inventory'])/D(x['nav'])*100 for x in r])),end_exposure_pct=str(D(r[-1]['inventory'])/D(r[-1]['nav'])*100),mean_cash_available_pct=str(mean([D(x['available'])/D(x['nav'])*100 for x in r])),mean_confirmed_committed_pct=str(mean([D(str(x['pool_confirmed'][0]))/D(x['nav'])*100 for x in r])),new_buy_cash=str(sum((D(x['gross_cny'])+D(x['fees_cny']) for x in tx if x['side']=='buy'),D(0))),buy_fill_records=sum(x['side']=='buy' for x in tx),sell_fill_records=sum(x['side']=='sell' for x in tx),paused_closes=sum(not x['on'] for x in r)))
 check=rows(p/'pair/balances.jsonl.gz');assert all(D(x['independent_NAV_difference'])==0 and D(x['maximum_stock_quantity_difference'])==0 for x in check)
 result=dict(reference=ref,Q2_start_NAV=str(nav0),Q2_end_NAV=str(nav1),Q2_net_change=str(nav1-nav0),Q2_return_pct=str((nav1/nav0-1)*100),Q2_local_DD_pct=str(dd([nav0]+[D(x['nav']) for x in q])),cumulative_return_pct=str((nav1/D(1000000)-1)*100),cumulative_DD_pct=str(dd([D(1000000)]+[D(x['nav']) for x in daily])),Q2_mean_exposure_pct=str(mean(ex)),Q2_peak_exposure_pct=str(max(ex)),Q2_mean_cash_available_pct=str(mean(cash)),Q2_end_cash_available=str(a['ending_cash']),Q2_mean_confirmed_committed_pct=str(mean(confirmed)),Q2_peak_confirmed_committed_pct=str(max(confirmed)),Q2_mean_probe_committed_pct=str(mean(probe)),Q2_fees=str(cost),Q2_buy_fills=sum(x['side']=='buy' for x in tr),Q2_sell_fills=sum(x['side']=='sell' for x in tr),Q2_ACT_paused_closes=sum(not x['on'] for x in q),ACT_transitions=phases,monthly=month,independent_NAV_and_stock_gaps_zero=True,account_days=len(check),period_vs_cumulative_not_rebased=True)
 IO.write_json(p/'QUICK_RESULT.json',result);out.append(result)
 print(ref,'Q2 return/DD',result['Q2_return_pct'],result['Q2_local_DD_pct'],'cumulative',result['cumulative_return_pct'],result['cumulative_DD_pct'],flush=True)
IO.write_json(O/'QUICK_RESULTS.json',out)
