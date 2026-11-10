"""Real-price accounting case study, NOT a trading strategy or broker delivery verification."""
import json
from pathlib import Path
import pandas as pd
from in_kind_ledger import InKindLedger
ROOT=Path(__file__).resolve().parent;OUT=ROOT/'results/hk-in-kind-case';OUT.mkdir(exist_ok=True)
def prices(code):
 d=json.loads((ROOT/f'data/hk-stock-raw/hk{code}.json').read_text())
 return pd.Series({r[0]:float(r[2]) for r in d['rows']}).sort_index()
def main():
 parent=prices('00700');child=prices('09618');l=InKindLedger();l.accrue('JD2022','HK09618','2022-01-20',420,1,21)
 rows=[];dates=parent.loc['2022-01-20':'2022-03-25'].index
 for dt in dates:
  if dt not in child:raise ValueError('missing recipient mark')
  value=l.value(dt,{'HK09618':(dt,float(child[dt]),dt,1.)})
  rows.append(dict(date=dt,parent_value=420*float(parent[dt]),recipient_close=float(child[dt]),receivable_value=value['total'],combined_value=420*float(parent[dt])+value['total'],cash_from_distribution=value['spendable_cash']))
 frame=pd.DataFrame(rows);frame.to_csv(OUT/'jd-receivable-values.csv',index=False)
 before=l.value('2022-03-25',{'HK09618':('2022-03-25',float(child['2022-03-25']),'2022-03-25',1.)})
 l.deliver('JD2022','2022-03-25','2022-03-25') # Scenario only, issuer dispatch is not broker settlement confirmation.
 after=l.value('2022-03-25',{'HK09618':('2022-03-25',float(child['2022-03-25']),'2022-03-25',1.)})
 assert before['total']==after['total'] and after['spendable_cash']==0
 report=dict(kind='Fixed-holding accounting illustration,no strategy signals',parent_shares=420,recipient_shares=20,rows=len(frame),first_receivable_value=float(frame.receivable_value.iloc[0]),last_receivable_value=float(frame.receivable_value.iloc[-1]),claim_mark_change=float(frame.receivable_value.iloc[-1]-frame.receivable_value.iloc[0]),transfer_value_difference=after['total']-before['total'],premature_spendable_cash_avoided=True,currency='HKD',source='https://static.www.tencent.com/uploads/2023/04/06/214dce4c5312264800b20cfab64861ba.pdf',limitations=['Dispatch-date transfer is explicit scenario,not broker confirmation','Integer ratio case excludes unresolved fractional entitlements','Raw prices not independently vendor-crosschecked','This is a narrow accounting case,not a market backtest or fullTencentledger'])
 (OUT/'summary.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
if __name__=='__main__':main()
