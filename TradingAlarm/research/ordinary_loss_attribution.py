"""Exact paid-fee and execution-gap attribution on fixed realized episode cohorts."""
import json,hashlib
from pathlib import Path
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'results/ordinary-loss-attribution'
def main():
 OUT.mkdir(exist_ok=True);source=ROOT/'results/sector-ranking-random-controls';episodes=pd.read_parquet(source/'episodes.parquet');manifest=json.loads((ROOT/'data/ths-refresh-20261018/validated-input-balanced-second500.json').read_text());prices={};hashes={}
 for r in manifest['records']:
  p=ROOT/'data/ths-refresh-20261018'/f"{r['ths_symbol']}-signal.parquet";h=hashlib.sha256(p.read_bytes()).hexdigest();assert h==r['signal_sha256'];hashes[str(p)]=h;prices[r['symbol']]=pd.read_parquet(p).signal_close
 details=[];checks=[]
 for case,g in episodes.groupby('case'):
  orders=json.loads((source/f'{case}-orders.json').read_text());f=g.copy().reset_index(drop=True)
  for col in ['paid_fees','buy_gap','sell_gap','signal_price_pnl','matched_units']:f[col]=0.
  for o in orders:
   owners=f.index[(f.symbol==o['symbol'])&(f.entry_date<=o['date'])&(f.exit_date.isna()|(f.exit_date>=o['date']))];assert len(owners)==1
   i=owners[0];u=o['units'];c=float(prices[o['symbol']].loc[pd.Timestamp(o['signal_date'])]);f.loc[i,'paid_fees']+=o['fee'];f.loc[i,'signal_price_pnl']-=u*c;f.loc[i,'matched_units']+=u;f.loc[i,'buy_gap' if u>0 else 'sell_gap']-=u*(o['raw_open']-c)
  for i,e in f.iterrows():
   if e.status!='closed':f.loc[i,'signal_price_pnl']+=e.units*float(prices[e.symbol].loc[:'2026-10-16'].iloc[-1])
  np.testing.assert_allclose(f.matched_units,f.units,rtol=0,atol=1e-7)
  error=float((f.signal_price_pnl+f.buy_gap+f.sell_gap-f.paid_fees-f.pnl).abs().max());assert error<1e-6
  assert abs(f.paid_fees.sum()-sum(o['fee'] for o in orders))<1e-6
  f['cohort']=np.where(f.return_on_purchase_cash.ge(.3),'tail30','ordinary');f['paid_fee_addback']=f.pnl+f.paid_fees
  details.append(f);checks.append(dict(case=case,orders=len(orders),max_episode_error=error))
 d=pd.concat(details,ignore_index=True);d.to_parquet(OUT/'episodes.parquet',index=False)
 s=d.groupby(['case','cohort']).agg(episodes=('symbol','size'),net=('pnl','sum'),paid_fees=('paid_fees','sum'),paid_fee_addback=('paid_fee_addback','sum'),signal_price_pnl=('signal_price_pnl','sum'),buy_gap=('buy_gap','sum'),sell_gap=('sell_gap','sum')).reset_index()
 for col in ['net','paid_fees','paid_fee_addback','signal_price_pnl','buy_gap','sell_gap']:s[col]/=1e6
 s.to_csv(OUT/'account-contributions.csv',index=False)
 ordinary=s[s.cohort.eq('ordinary')];report={'status':'fixed_cohort_accounting_diagnostic','accounts':len(checks),'episodes':len(d),'checks':checks,'ordinary_positive_after_paid_fee_addback':int(ordinary.paid_fee_addback.gt(0).sum()),'ordinary_net_range':[float(ordinary.net.min()),float(ordinary.net.max())],'ordinary_fee_addback_range':[float(ordinary.paid_fee_addback.min()),float(ordinary.paid_fee_addback.max())],'rank':s[s.case.eq('rank-base')].to_dict('records'),'input_hashes':hashes,'limits':['Original net return30% cohort fixed; fee addback never reclassifies winners.','Paid fee addback is accounting, not rerun zero-cost NAV: position sizes and future capital remain actual.','Signal-close prices are untradeable counterfactual marks; buy/sell gaps include waiting and price changes, not solely market-impact slippage.','Adjusted-price fractional execution ignores actual corporate cash/lot/liquidity/price-limit details.','All selected survivor development history, no independent validation.']}
 (OUT/'review.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(ordinary.to_string(index=False));print('errors',max(x['max_episode_error'] for x in checks))
if __name__=='__main__':main()
