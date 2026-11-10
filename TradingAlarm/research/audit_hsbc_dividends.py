"""Issuer timetable audit and HKD settlement sensitivity; signals retain causal USD FX."""
import json
import pandas as pd
from hk_stock_account_pilot import ROOT,load,run
from hk_cash_annotations import parse_cash
from hk_stock_rule_transfer import targets_for
OUT=ROOT/'results/hk-hsbc-dividend-audit'
# Manual transcription of issuer timetable, accessed 2026-10-18. Ex, pay, USD, HKD, fixing.
RECORDS='''2022-03-10 2022-04-28 .18 1.411736 2022-04-19
2022-08-18 2022-09-29 .09 .706305 2022-09-20
2023-03-02 2023-04-27 .23 1.804399 2023-04-17
2023-05-11 2023-06-23 .10 .783215 2023-06-12
2023-08-10 2023-09-21 .10 .783202 2023-09-11
2023-11-09 2023-12-21 .10 .780278 2023-12-11
2024-03-07 2024-04-25 .31 2.426355 2024-04-15
2024-05-09 2024-06-21 .31 2.420133 2024-06-11
2024-08-15 2024-09-27 .10 .779073 2024-09-16
2024-11-07 2024-12-19 .10 .777313 2024-12-09
2025-03-06 2025-04-25 .36 2.791007 2025-04-14
2025-05-08 2025-06-20 .10 .783972 2025-06-09
2025-08-14 2025-09-26 .10 .777678 2025-09-15
2025-11-06 2025-12-18 .10 .777722 2025-12-08
2026-03-12 2026-04-30 .45 3.522942 2026-04-20
2026-05-14 2026-06-26 .10 .783188 2026-06-15
2026-08-13 2026-09-25 .10 .784088 2026-09-14'''
def main():
 OUT.mkdir(exist_ok=True)
 records=[dict(zip(['ex','pay','usd','hkd','fixing'],line.split())) for line in RECORDS.splitlines()]
 evidence={'source':'https://www.hsbc.com/investors/shareholder-and-dividend-information/dividend-information-and-timetable','accessed':'2026-10-18','records':records,'scope':'2022-03-07 through2026-10-16 evaluation period, not all signal warmup dividends','policy':'USD receivable marked with lagged FX until first trading date strictly after fixing; then issuer fixed HKD; payable cash only on/after paydate. Signals unchanged, never use future HKD alternative at exdate. No brokerage dividend handling fees or investor-specific taxes.'}
 (OUT/'issuer-records.json').write_text(json.dumps(evidence,indent=2))
 raw,events=load('00005');vendor=json.loads((ROOT/'data/hk-stock-raw/hk00005.json').read_text());checks=[];official=[]
 assert set(str(e['ex'].date()) for e in events if e['ex']>=pd.Timestamp('2022-03-07'))=={r['ex'] for r in records}
 for r in records:
  es=[e for e in events if str(e['ex'].date())==r['ex']]
  assert all(str(e['pay'].date())==r['pay'] and e['currency']=='USD' for e in es)
  assert abs(sum(e['amount'] for e in es)-float(r['usd']))<1e-10
  annotations=[e for row in vendor['rows'] if row[0]==r['ex'] for e in row[6:] if isinstance(e,dict) and e.get('FHcontent')]
  hkd=sum(float(c['alternatives']['HKD']) for e in annotations for c in parse_cash(e['FHcontent']))
  assert abs(hkd-float(r['hkd']))<1e-9
  official.append(dict(ex=pd.Timestamp(r['ex']),pay=pd.Timestamp(r['pay']),amount=float(r['usd']),currency='USD',settlement=dict(fixing=r['fixing'],hkd_per_share=float(r['hkd']))))
  checks.append(dict(ex=r['ex'],usd=sum(e['amount'] for e in es),hkd=hkd,status='matched_amounts_ex_pay'))
 f=json.loads((ROOT/'data/hk-stock-pilot/usd-hkd.json').read_text());assert f['base']=='USD'
 src=pd.Series({pd.Timestamp(d)+pd.Timedelta(days=1):v['HKD'] for d,v in f['rates'].items()}).sort_index();fx=src.reindex(src.index.union(raw.index)).ffill().reindex(raw.index)
 target=targets_for(raw,events,fx)['sma200'];results=[]
 for lag in [1,2]:
  for cost in [20,40]:
   m,p,o=run({'00005':raw},{'00005':official},fx,target,cost_bps=cost,primary='00005',start='2022-03-07',order_increment=400,signal_lag=lag)
   m.update(signal_lag=lag,cost_bps=cost);results.append(m);p.to_csv(OUT/f'lag{lag}-cost{cost}-path.csv')
 (OUT/'checks.json').write_text(json.dumps(checks,indent=2));(OUT/'results.json').write_text(json.dumps(results,indent=2));print('Matched issuer dates and amounts:',len(checks));print(pd.DataFrame(results)[['signal_lag','cost_bps','cagr','max_drawdown','best252']].to_string(index=False))
if __name__=='__main__':main()
