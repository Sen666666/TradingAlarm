"""Fixed-rule attribution, not a new strategy or parameter-selection exercise."""
import json
import pandas as pd
from hk_stock_account_pilot import ROOT,load,run
from hk_stock_rule_transfer import targets_for
from audit_hsbc_dividends import RECORDS
OUT=ROOT/'results/hk-hsbc-return-attribution'
def summarize_path(path):
 years=[]
 for year,g in path.groupby(path.index.year):
  previous=path.nav.shift(1).fillna(1).loc[g.index[0]]
  years.append(dict(year=int(year),start=str(g.index[0].date()),end=str(g.index[-1].date()),return_fraction=float(g.nav.iloc[-1]/previous-1),pnl_hkd=float((g.nav.iloc[-1]-previous)*1e6),partial=bool(year in [path.index[0].year,path.index[-1].year])))
 assert abs(sum(y['pnl_hkd'] for y in years)-(path.nav.iloc[-1]-1)*1e6)<1e-6
 # Account intervals from first entry through day before next entry, including any dividends received while flat.
 starts=path.index[(path.parent_shares>0)&(path.parent_shares.shift(1,fill_value=0)==0)].tolist()
 intervals=[]
 for i,start in enumerate(starts):
  end=path.index[path.index.get_loc(starts[i+1])-1] if i+1<len(starts) else path.index[-1]
  g=path.loc[start:end];prior=path.nav.shift(1).fillna(1).loc[start]
  intervals.append(dict(start=str(start.date()),end=str(end.date()),holding_sessions=int((g.parent_shares>0).sum()),pnl_hkd=float((g.nav.iloc[-1]-prior)*1e6),return_fraction=float(g.nav.iloc[-1]/prior-1),open_position_at_end=bool(g.parent_shares.iloc[-1]>0),note='Account interval including flat days and receivables; not isolated stock trade PnL'))
 assert abs(sum(x['pnl_hkd'] for x in intervals)-(path.nav.iloc[-1]-1)*1e6)<1e-6
 rolling=path.nav.pct_change(252);end=rolling.idxmax();start=path.index[path.index.get_loc(end)-252]
 return dict(years=years,entry_intervals=intervals,best252=dict(start=str(start.date()),end=str(end.date()),return_fraction=float(rolling.loc[end])),largest_year_profit_share=float(max(y['pnl_hkd'] for y in years)/sum(y['pnl_hkd'] for y in years)),largest_entry_interval_profit_share=float(max(x['pnl_hkd'] for x in intervals)/sum(x['pnl_hkd'] for x in intervals)))
def main():
 OUT.mkdir(exist_ok=True)
 protocol=dict(start='2022-03-07',rules=['buy_hold','sma200'],cases=[dict(signal_lag=1,cost_bps=20),dict(signal_lag=2,cost_bps=40)],order_increment=400,status='Descriptive decomposition of previously viewed single surviving asset; no new holdout or strategy selection',dividends='Issuer fixed HKD after fixing date, USD receivable earlier',limitations=['No verified full price-source history','Calendar-year and entry-interval decomposition are descriptive, not predefined market episodes','Cash dividend servicing fees/taxes investor-specific and unmodeled'])
 (OUT/'protocol.json').write_text(json.dumps(protocol,indent=2))
 raw,events=load('00005');official=[]
 for line in RECORDS.splitlines():
  ex,pay,usd,hkd,fix=line.split();official.append(dict(ex=pd.Timestamp(ex),pay=pd.Timestamp(pay),amount=float(usd),currency='USD',settlement=dict(fixing=fix,hkd_per_share=float(hkd))))
 f=json.loads((ROOT/'data/hk-stock-pilot/usd-hkd.json').read_text());assert f['base']=='USD'
 src=pd.Series({pd.Timestamp(d)+pd.Timedelta(days=1):v['HKD'] for d,v in f['rates'].items()}).sort_index();fx=src.reindex(src.index.union(raw.index)).ffill().reindex(raw.index);targets=targets_for(raw,events,fx);results=[]
 for rule in protocol['rules']:
  for case in protocol['cases']:
   m,p,o=run({'00005':raw},{'00005':official},fx,targets[rule],primary='00005',start=protocol['start'],order_increment=400,**case)
   a=summarize_path(p);r=dict(rule=rule,**case,metrics=m,attribution=a);results.append(r)
   p.to_csv(OUT/f"{rule}-lag{case['signal_lag']}-cost{case['cost_bps']}.csv")
   print(rule,case,'CAGR/DD/best252',m['cagr'],m['max_drawdown'],m['best252']);print(pd.DataFrame(a['years'])[['year','return_fraction','pnl_hkd']].to_string(index=False));print('Best window',a['best252']);print('Entry intervals',len(a['entry_intervals']),'largest year profit share',a['largest_year_profit_share'])
 (OUT/'results.json').write_text(json.dumps(results,indent=2))
if __name__=='__main__':main()
