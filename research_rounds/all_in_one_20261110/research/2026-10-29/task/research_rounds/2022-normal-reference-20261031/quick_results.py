"""Only saved books; report every completed2022 reference immediately."""
from pathlib import Path
from decimal import Decimal as D
import sys,json,gzip
O=Path(__file__).resolve().parent;sys.path.insert(0,str(O.parent/'execution-pressure-preflight-20261031'))
from initialization_guard import IO
Z=D(0)
def rows(p):
 with gzip.open(p,'rt') as f:return [json.loads(x) for x in f]
def obj(p):
 with gzip.open(p,'rt') as f:return json.load(f)
def dd(v):
 peak=v[0];worst=Z
 for x in v:peak=max(peak,x);worst=max(worst,1-x/peak)
 return worst*100
def avg(v):return sum(v,Z)/len(v)
def metrics(a,daily,tr,base):
 ex=[D(x['inventory'])/D(x['nav'])*100 for x in daily];cash=[D(x['available'])/D(x['nav'])*100 for x in daily]
 return dict(start_NAV=str(base),end_NAV=daily[-1]['nav'],return_pct=str((D(daily[-1]['nav'])/base-1)*100),DD_pct=str(dd([base]+[D(x['nav']) for x in daily])),mean_exposure_pct=str(avg(ex)),peak_exposure_pct=str(max(ex)),mean_available_cash_pct=str(avg(cash)),mean_confirmed_committed_pct=str(avg([D(str(x['pool_confirmed'][0]))/D(x['nav'])*100 for x in daily])),mean_probe_committed_pct=str(avg([D(str(x['pool_probe'][0]))/D(x['nav'])*100 for x in daily])),fees=str(sum((D(x['fees_cny']) for x in tr),Z)),buy_fill_records=sum(x['side']=='buy' for x in tr),sell_fill_records=sum(x['side']=='sell' for x in tr),buy_cash=str(sum((D(x['gross_cny'])+D(x['fees_cny']) for x in tr if x['side']=='buy'),Z)),paused_closes=sum(not x['on'] for x in daily),observations=len(daily))
out=[]
for ref in ['B3','B_diag']:
 p=O/'runs'/ref
 if not (p/'DONE.json').exists():continue
 a=obj(p/'pair/B.json.gz');daily=rows(p/'pair/daily.jsonl.gz');assert len(daily)==242 and len({x['at'][:10] for x in daily})==242
 audit=rows(p/'pair/balances.jsonl.gz');assert all(D(x['independent_NAV_difference'])==0 and D(str(x['maximum_stock_quantity_difference']))==0 for x in audit)
 annual=metrics(a,daily,a['trades'],D(1000000));annual['terminal_inventory']=daily[-1]['inventory'];annual['terminal_dividend_AR']=daily[-1]['dividend_receivable'];annual['terminal_cash_available']=a['ending_cash']
 quarter=[];base=D(1000000)
 for label,lo,hi in [('Q1','2022-01-01','2022-03-31'),('Q2','2022-04-01','2022-06-30'),('Q3','2022-07-01','2022-09-30'),('Q4','2022-10-01','2022-12-30')]:
  q=[r for r in daily if lo<=r['at'][:10]<=hi];tr=[x for x in a['trades'] if lo<=x['at'][:10]<=hi];quarter.append(dict(quarter=label,**metrics(a,q,tr,base)));base=D(q[-1]['nav'])
 phase=[x for x in a['audit'] if x['kind']=='risk_checkpoint' and x.get('event') is not None]
 result=dict(reference=ref,annual=annual,quarters=quarter,ACT_transitions=phase,independent_journal_NAV_and_shares_zero=True,account_days=len(audit),quarter_statistics_only_no_resets=True)
 IO.write_json(p/'QUICK_RESULT.json',result);out.append(result);print(ref,'return/DD',annual['return_pct'],annual['DD_pct'],'expo',annual['mean_exposure_pct'],'paused',annual['paused_closes'],flush=True)
IO.write_json(O/'QUICK_RESULTS.json',out)
