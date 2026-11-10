"""Exactly one fixed independent-sleeve allocation, using immutable ledgers.
No signal generation, backtest-engine call, parameter search or rebalancing.
"""
from pathlib import Path
import math,json,hashlib
import pandas as pd,numpy as np
R=Path(__file__).resolve().parent;P=R.parent/'strategy-switching-20261024';A=P/'results/v0/accounts';O=R/'results/v0'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def replay(index,close,records,cash0=1.):
 grouped={}
 for x in records:grouped.setdefault(x['date'],[]).append(x)
 cash=cash0;qty=0.;rows=[]
 for dt in index:
  for x in grouped.get(str(dt.date()),[]):
   sign=1 if x['side']=='buy' else -1;qty+=sign*x['quantity'];cash-=sign*x['quantity']*x['price']+x['fee']
  assert cash>-1e-11 and qty>-1e-11
  rows.append((cash,qty,cash+qty*close.loc[dt]))
 return np.array(rows)
def main():
 fr=json.loads((R/'freeze.json').read_text())
 for name,h in fr['sha256'].items():assert sha(R/name)==h,name
 O.mkdir(parents=True,exist_ok=False);(O/'blend-ledgers').mkdir();summary=[];maxerr=0.;fills_replayed=0
 src=pd.read_csv(P/'results/v0/summary.csv')
 for (case,sc),z in src.groupby(['case','scenario'],sort=False):
  states={};records=[];fees=slips=0.
  for p in ['E0','R']:
   key=f'{case}__{p}__{sc}';states[p]=pd.read_parquet(A/key/'ledger.parquet');f=pd.read_csv(A/key/'fills.csv')
   for x in f.to_dict('records'):
    x['sleeve']=p
    for col in ['quantity','fee','slippage']:x[col]*=.5
    records.append(x)
   fees+=.5*f.fee.sum();slips+=.5*f.slippage.sum();fills_replayed+=len(f)
  e,r=states['E0'],states['R'];assert e.index.equals(r.index);np.testing.assert_array_equal(e.close,r.close)
  out=pd.DataFrame(index=e.index)
  for col in ['cash','quantity','nav']:out[col]=.5*e[col]+.5*r[col]
  out['close']=e.close;out['drawdown']=out.nav/np.maximum.accumulate(np.r_[1.,out.nav.to_numpy()])[1:]-1;out['market_exposure']=out.quantity*out.close/out.nav
  independent=replay(out.index,out.close,records);err=np.max(np.abs(independent-out[['cash','quantity','nav']].to_numpy()));maxerr=max(maxerr,float(err));np.testing.assert_allclose(independent,out[['cash','quantity','nav']],rtol=1e-10,atol=1e-11)
  np.testing.assert_allclose(out.nav,out.cash+out.quantity*out.close,rtol=1e-12,atol=1e-12)
  final=.5*z.set_index('policy').loc['E0','net_return']+.5*z.set_index('policy').loc['R','net_return'];np.testing.assert_allclose(out.nav.iloc[-1]-1,final,atol=1e-12)
  out.to_parquet(O/'blend-ledgers'/f'{case}__{sc}.parquet');row=z.iloc[0];tail=.5*(z.set_index('policy').loc['E0','tail_pnl']+z.set_index('policy').loc['R','tail_pnl']);ordinary=.5*(z.set_index('policy').loc['E0','ordinary_pnl']+z.set_index('policy').loc['R','ordinary_pnl'])
  summary.append(dict(case=case,scenario=sc,role=row.role,name=row['name'],symbol=row.symbol,type=row['type'],start=row.start,end=row.end,net_return=float(out.nav.iloc[-1]-1),max_drawdown=float(-out.drawdown.min()),mean_market_exposure=float(out.market_exposure.mean()),fees=fees,slippage=slips,tail_pnl=tail,ordinary_pnl=ordinary,initial_E0_weight=.5,initial_R_weight=.5,final_E0_weight=float(.5*e.nav.iloc[-1]/out.nav.iloc[-1]),new_signal_accounts=0))
 assert len(summary)==54;pd.DataFrame(summary).to_csv(O/'blend-summary.csv',index=False)
 # Gold daily economic attribution, independently from fills, no backtest call.
 gold='continuous_USHJ518880';attrib=[];annual=[]
 for p in ['E0','R']:
  l=pd.read_parquet(A/f'{gold}__{p}__base/ledger.parquet');f=pd.read_csv(A/f'{gold}__{p}__base/fills.csv');grouped={k:g.to_dict('records') for k,g in f.groupby('date',sort=False)};prevqty=0.;prevclose=float(l.close.iloc[0]);dayrows=[]
  for dt,row in l.iterrows():
   price=prevqty*(row.close-prevclose);fee=slip=0.
   for fill in grouped.get(str(dt.date()),[]):
    price+=(1 if fill['side']=='buy' else -1)*fill['quantity']*(row.close-fill['raw_price']);fee+=fill['fee'];slip+=fill['slippage']
   dayrows.append(dict(date=dt,policy=p,price_pnl=price,fees=fee,slippage=slip));prevqty=row.quantity;prevclose=row.close
  daily=pd.DataFrame(dayrows).set_index('date');reconstructed=1+(daily.price_pnl-daily.fees-daily.slippage).cumsum();np.testing.assert_allclose(reconstructed,l.nav,atol=1e-11,rtol=1e-11)
  daily.to_csv(O/f'gold-{p}-daily-pnl.csv');attrib.append(dict(policy=p,price_pnl=float(daily.price_pnl.sum()),fees=float(daily.fees.sum()),slippage=float(daily.slippage.sum()),net_profit=float(l.nav.iloc[-1]-1)))
  previous=1.
  for year,g in l.groupby(l.index.year):
   annual.append(dict(year=int(year),policy=p,opening_nav=previous,ending_nav=float(g.nav.iloc[-1]),net_return=float(g.nav.iloc[-1]/previous-1),account_reset=False,year_end_liquidation=False));previous=float(g.nav.iloc[-1])
 pd.DataFrame(attrib).to_csv(O/'gold-pnl-attribution.csv',index=False);pd.DataFrame(annual).to_csv(O/'gold-continuous-years.csv',index=False)
 for name,h in fr['sha256'].items():assert sha(R/name)==h,name
 audit=dict(passed=True,derived_blend_paths=54,new_signal_accounts=0,original_signal_algorithms_changed=0,weight_choices_evaluated=1,weight_search_performed=False,weights={'E0':.5,'R':.5},daily_rebalanced=False,scaled_fills_independently_replayed=fills_replayed,max_cash_quantity_nav_error=maxerr,gold_price_pnl_cost_reconstruction=True,original_frozen_files_verified=len(fr['sha256']))
 (O/'audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2));print(json.dumps(audit,ensure_ascii=False,indent=2))
 print(pd.DataFrame(summary).query("case=='continuous_USHJ518880'").to_string(index=False));print(pd.DataFrame(attrib).to_string(index=False))
if __name__=='__main__':main()
