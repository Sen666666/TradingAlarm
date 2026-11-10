"""Bounded independent benchmark CSV slice arithmetic, no replay or valuation."""
import csv,json,hashlib
from pathlib import Path
from decimal import Decimal as D
T=Path(__file__).resolve().parent.parent;O=Path(__file__).resolve().parent;Z=D(0);EPS=D('.000001')
def rows(p):
 with open(p) as f:return list(csv.DictReader(f))
def near(a,b,l):assert abs(D(a)-D(b))<EPS,(l,a,b)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
bounds=rows(T/'resume_inventory_2024_v2/BENCHMARK_2024_BOUNDARIES.csv');phases=rows(T/'resume_inventory_2024_v2/BENCHMARK_2024_PHASES.csv')
result={'status':'PASS_BOUNDED_SAVED_BENCHMARK_SLICE_ARITHMETIC','scope':'Independent raw saved CSV NAV/cash/shares/inventory/AR/fees four anchors and three phases+year own denominators/MDD/actual saved fill counts/fee sums; no new FIFO/valuation/price/CA/execution verification. execution_verified=false is retained. No claim of exact fee or risk equivalence with No60/D.','arms':{},'source_sha256':{}}
for arm in ['BUY_HOLD','MA63_90']:
 dp=T/'benchmark_2022_2023/continuation2024/daily_2022_2024'/(arm+'.csv');fp=T/'benchmark_2022_2023/continuation2024/logs_2022_2024'/(arm+'_fills.json');raw=rows(dp);fills=json.load(open(fp));ix={r['date']:i for i,r in enumerate(raw)}
 for r in [x for x in bounds if x['arm']==arm]:
  old=raw[ix[r['date']]]
  for a,b in [('NAV_CNY','NAV'),('cash_CNY','cash'),('shares','shares'),('inventory_mark_CNY','market_value'),('dividend_receivable_CNY','dividend_receivable'),('cumulative_fee_CNY','cumulative_fee')]:near(r[a],old[b],(arm,r['date'],a))
  near(r['close_exposure_pct'],D(old['market_value'])/D(old['NAV'])*100,(arm,r['date'],'gross'))
 totals=[]
 for r in [x for x in phases if x['arm']==arm]:
  a=ix[r['start']];b=ix[r['end']];ds=raw[a:b+1];s=D(raw[a-1]['NAV']);e=D(raw[b]['NAV']);peak=s;mdd=Z
  for x in ds:peak=max(peak,D(x['NAV']));mdd=max(mdd,(1-D(x['NAV'])/peak)*100)
  for label,new in [('own_start_NAV_CNY',s),('own_end_NAV_CNY',e),('wealth_change_CNY',e-s),('own_return_pct',(e/s-1)*100),('local_close_DD_pct',mdd),('fee_CNY',sum((D(x['fee']) for x in ds),Z)),('dividend_recognized_CNY',sum((D(x['dividend_accrued']) for x in ds),Z)),('dividend_paid_CNY',sum((D(x['dividend_paid']) for x in ds),Z))]:near(r[label],new,(arm,r['phase'],label))
  tx=[x for x in fills if r['start']<=x['day']<=r['end']]
  assert len(ds)==int(r['closes']) and int(r['actual_buy_fills'])==sum(x['side']=='buy' for x in tx) and int(r['actual_sell_fills'])==sum(x['side']=='sell' for x in tx)
  totals.append(e-s)
 near(sum(totals[:3],Z),totals[3],(arm,'three phase telescope'))
 result['arms'][arm]={'four_points_newly_checked':4,'phase_rows_newly_checked':4,'actual_2024_fills':sum(x['day'].startswith('2024') for x in fills),'execution_verified':False}
 for p in [dp,fp]:result['source_sha256'][str(p)]=sha(p)
for p in [T/'resume_inventory_2024_v2/BENCHMARK_2024_BOUNDARIES.csv',T/'resume_inventory_2024_v2/BENCHMARK_2024_PHASES.csv']:result['source_sha256'][str(p)]=sha(p)
result['checker_sha256']=sha(__file__)
(O/'BENCHMARK_SLICE_REVIEW.json').write_text(json.dumps(result,indent=2))
print(result['status'],result['arms'])
