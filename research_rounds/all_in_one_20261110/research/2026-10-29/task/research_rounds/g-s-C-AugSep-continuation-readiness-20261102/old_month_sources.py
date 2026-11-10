"""Cashflows + saved positions + original as-of marks, no account progression."""
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict
import json,gzip,pandas as pd
P=Path(__file__).resolve().parent;W=P.parent
B=Path('/Users/bytedance/Documents/Codex/2026-11-01/task/market-permission-price-only-20261101/g-s-minimal-input-readiness/STOCK_INPUT_INVENTORY.json')
inv={r['symbol']:r['refs'] for r in json.loads(B.read_text())};names=json.loads((W/'g-s-C-month-continuation-20261102/inputs/2025_26/metadata.json').read_text());frames={};Z=D(0)
def rows(p):
 with gzip.open(p,'rt') as f:return [json.loads(x) for x in f]
def price(sid,d):
 if sid not in frames:
  q=pd.read_parquet(inv[sid]['raw_bars']);q['trade_date']=pd.to_datetime(q['trade_date']);frames[sid]=q.sort_values('trade_date')
 q=frames[sid];v=q[q.trade_date<=pd.Timestamp(d)].iloc[-1]['close'];assert pd.notna(v) and v>0;return D(str(v))
def main():
 out={}
 for pol,root in [('SC',W/'q2-normal-continuation-20261031/runs/B_diag/pair'),('PVR_SLOT1',W/'pvr-slot1-native-readiness-20261101/runs/2025_26/pair')]:
  daily=rows(root/'daily.jsonl.gz')
  with gzip.open(root/'B.json.gz','rt') as f:book=json.load(f)
  prev={};months=[]
  for month in ['2025-07','2025-08','2025-09']:
   end=[r for r in daily if r['at'].startswith(month)][-1];d=end['at'][:10];cash=defaultdict(lambda:Z);div=defaultdict(lambda:Z);buy=defaultdict(lambda:Z)
   for t in book['trades']:
    if t['at'][:10]>d:continue
    s=t['security_id'];cash[s]+=(D(t['gross_cny']) if t['side']=='sell' else -D(t['gross_cny']))-D(t['fees_cny'])
    if t['side']=='buy' and t['at'].startswith(month):buy[s]+=D(t['gross_cny'])
   for a in book['audit']:
    if a['kind']=='dividend_accrual' and a['receivable']['ex_at'][:10]<=d:
     z=a['receivable'];assert z['currency']=='CNY';div[z['security_id']]+=D(z['net_local'])
   val={s:D(q)*price(s,d) for s,q in end['positions'].items() if q};assert abs(sum(val.values(),Z)-D(end['inventory']))<D('1e-7'),'saved original mark inventory bridge'
   net={s:cash[s]+div[s]+val.get(s,Z) for s in cash.keys()|div.keys()|val.keys()};assert abs(sum(net.values(),Z)-(D(end['nav'])-D(1000000)))<D('1e-7'),'stock contribution NAV bridge'
   delta={s:net.get(s,Z)-prev.get(s,Z) for s in net.keys()|prev.keys()};rank=sorted(delta,key=lambda s:-delta[s]);months.append(dict(month=month,day=d,NAV=end['nav'],top_positive=[dict(sid=s,name=names[s]['name'],sector=names[s]['sector'],month_contribution=delta[s],month_actual_buy=buy[s]) for s in rank[:5]],top_negative=[dict(sid=s,name=names[s]['name'],sector=names[s]['sector'],month_contribution=delta[s],month_actual_buy=buy[s]) for s in reversed(rank[-5:])],all_stock_contribution_delta=delta,source='saved original trades/dividend accrual/current positions plus original unadjusted as-of close; no future final-layer labels'));prev=net
  out[pol]=months
 (P/'OLD_MONTHLY_SOURCES.json').write_text(json.dumps(out,ensure_ascii=False,indent=2,default=str)+'\n')
 for p,ms in out.items():
  for m in ms:print(p,m['month'],[(q['name'],str(q['month_contribution'])) for q in m['top_positive'][:3]])
if __name__=='__main__':main()
