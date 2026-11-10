"""Supplement existing aggregation with price-index and saved native scope checks."""
from pathlib import Path
from decimal import Decimal as D
from collections import Counter
from datetime import datetime, timezone
import csv, gzip, hashlib, json

O=Path(__file__).resolve().parent
T=O.parent
Z=D(0)
SOURCES={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def bind(p):
    p=Path(p);SOURCES[str(p.relative_to(T))]=sha(p);return p
def read(p):return json.loads(bind(p).read_text())
def rows(p):return list(csv.DictReader(bind(p).open()))
def save(n,v):
    p=O/n;assert not p.exists();p.write_text(json.dumps(v,indent=2,ensure_ascii=False,default=str)+'\n')
def write(n,items):
    p=O/n;assert not p.exists()
    with p.open('w')as f:
        w=csv.DictWriter(f,fieldnames=list(items[0]));w.writeheader();w.writerows(items)
def dd(start,seq):
    peak,m=start,Z
    for v in seq:peak=max(peak,v);m=max(m,1-v/peak)
    return m*100

old=rows(T/'benchmark_2022_2023/inputs/HS300_daily.csv')
new=rows(T/'benchmark_2022_2023/continuation2024/inputs/HS300_2024_daily.csv')
assert old[-1]['date']=='2023-12-29' and len(new)==242
allrows=old+new
points={r['date']:D(r['close'])for r in allrows}
index_boundaries=[dict(date=d,index_close=points[d],reference_only=True)
    for d in ['2023-12-29','2024-09-23','2024-10-08','2024-12-31']]
intervals=[('pre924','2024-01-02','2024-09-23'),('924_to_Oct8','2024-09-24','2024-10-08'),
    ('post_Oct8','2024-10-09','2024-12-31'),('year2024','2024-01-02','2024-12-31')]
index_phases=[]
for name,lo,hi in intervals:
    ids=[i for i,r in enumerate(allrows)if lo<=r['date']<=hi]
    start=D(allrows[ids[0]-1]['close']);end=points[hi]
    index_phases.append(dict(phase=name,start=lo,end=hi,closes=len(ids),starting_index_close=start,
        ending_index_close=end,price_return_pct=(end/start-1)*100,
        local_close_DD_pct=dd(start,[D(allrows[i]['close'])for i in ids]),
        reference_only=True,fees='NOT_APPLICABLE_NONTRADABLE_PRICE_INDEX',
        includes_dividend_total_return=False))
write('HS300_REFERENCE_BOUNDARIES.csv',index_boundaries)
write('HS300_REFERENCE_PHASES.csv',index_phases)

stock_scope={}
for label,folder,bookname in [
    ('No60','capacity_cost_guard_v1/runs/long-v1/arms/B/pair','B'),
    ('D_GROSS10','market_gross_admission_native_v1/full-long-v1/pair','D_GROSS10')]:
    f=bind(T/folder/(bookname+'.json.gz'))
    with gzip.open(f,'rt')as r:book=json.load(r)
    allkinds=Counter(e['kind']for e in book['audit'])
    def eventday(e):return str(e.get('at')or e.get('receipt',{}).get('at')or e.get('receivable',{}).get('ex_at')or '')[:10]
    events=[e for e in book['audit']if eventday(e).startswith('2024')]
    kinds=Counter(e['kind']for e in events)
    dp=bind(T/folder/'daily.jsonl.gz')
    with gzip.open(dp,'rt')as r:daily=[json.loads(line)for line in r]
    y=[r for r in daily if str(r['at']).startswith('2024')]
    assert len(y)==242
    boundaries=[]
    for day in ['2023-12-29','2024-09-23','2024-10-08','2024-12-31']:
        d=next(r for r in daily if str(r['at']).startswith(day))
        near=sum((D(d[k])for k in ['available','order_reserved','sale_receivable','dividend_receivable','inventory']),Z)
        assert abs(near-D(d['nav']))<D('.000001')
        boundaries.append(dict(date=day,available_CNY=d['available'],order_reserved_CNY=d['order_reserved'],
            sale_receivable_CNY=d['sale_receivable'],dividend_receivable_CNY=d['dividend_receivable'],
            inventory_CNY=d['inventory'],NAV_CNY=d['nav']))
    recognized=sum((D(e['receivable']['net_local'])for e in events if e['kind']=='dividend_accrual'),Z)
    assert not any('deposit'in k or 'withdraw'in k or 'external_flow'in k for k in allkinds)
    stock_scope[label]=dict(actual_2024_event_kind_counts=dict(kinds),all_event_kind_counts=dict(allkinds),
        recognized_2024_dividend_CNY=recognized,boundaries=boundaries,
        no_external_cash_flow='No deposit/withdrawal/external-flow event in saved full book. Earlier independent daily replay starts at original1m and accounts for fills/fees, quantity adjustment and dividend recognition without external cash addition.',
        dividend_payment_scope='No dividend_payment event kind; native accrued receivable is part of NAV, not available cash or independently certified dividend payment.',
        corporate_action_scope='Native share/cash/basis transitions were audited; external issuer entitlement economics, cash-in-lieu and exchange fills are not certified.')
save('STOCK_EXTERNAL_FLOW_AND_AR_SCOPE.json',stock_scope)
for n in ['market_gross_admission_full_ledger_review_v1/FINAL_TWO_WINDOW_FINANCE_PVR_ATOMIC_REVIEW.json',
    'independent_review/trend_confirmation_full_ledger_v1/FULL_TWO_WINDOWS_FINANCE_PVR_CA_AUDIT.json',
    'independent_review/capacity_cost_guard_v1/FULL_TWO_WINDOWS_INDEPENDENT_AUDIT.json',
    'independent_review/trend_confirmation_full_ledger_v1/generic_saved_finance_reader.py']:
    bind(T/n)
save('SCOPE_AND_INDEX_SOURCE_BINDING.json',dict(recorded_UTC=datetime.now(timezone.utc).isoformat(),
    script_SHA256=sha(__file__),source_SHA256=SOURCES,new_accounts_or_backtests=0))
print(json.dumps(dict(index_boundaries=index_boundaries,index_phases=index_phases,
    stock_2024_dividends={k:v['recognized_2024_dividend_CNY']for k,v in stock_scope.items()}),default=str))
