"""Reporting supplement only: state event order and exact entry/flat-price costs.
No re-selection, no exit strategy, no financial account. Added after fixed labels
to prevent gross price paths being mistaken for tradable round-trip wins.
"""
import sys,json,hashlib
from pathlib import Path
from decimal import Decimal as D
import pandas as pd,numpy as np
O=Path(__file__).resolve().parent;ROOT=O.parent
sys.path.insert(0,str(O))
from experiment import U,B,fee,QuantityRule,FeeComponent,FeeSchedule,version_on,market_identity_on
END='2026-05-15'
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 s=pd.read_csv(O/'EPISODE_FIRST_PROBE_RESULTS.csv')
 sm={r['symbol']:r for r in read(U/'STOCK_MANIFEST.json')};im={r['series']:r for r in read(U/'INDUSTRY_MANIFEST.json')}
 rules=read(B/'inputs-v2/market-rules.json');proxies=read(B/'inputs-v2/economic-protocol.json')['approved_proxy_ids']
 src={};rows=[]
 for r in s.to_dict('records'):
  sid=r['sid'];day=r['day'];od=r['open_day'];pp=sm[sid]['refs']['facts'];src[pp]=sha(pp);f=pd.read_parquet(pp).loc[:END]
  future=f.loc[f.index>day];off=future[~future.i_target.astype(bool)]
  ioff=str(off.index[0].date()) if len(off) else None
  ip=im[r['sector']]['refs']['state'];src[ip]=sha(ip);sf=pd.read_parquet(ip);sf=sf[sf.day.le(END)]
  end=r['E0_end'] if pd.notna(r['E0_end']) else END
  z=sf[sf.day.gt(day)&sf.day.le(end)&sf.action.eq('end_attempt')]
  attemptend=z.day.iloc[0] if len(z) else None
  q=int(r['quantity']);buy=D(str(r['price']));op=buy/D('1.0005');sell=op*D('.9995')
  ident=market_identity_on(rules,sid,od,proxies);sd=version_on(rules['fee_versions'][ident['venue']],od,proxies)['schedule'];sched=FeeSchedule(sd['schedule_id'],tuple(FeeComponent(**a) for a in sd['components']))
  par=D(str(rules['security_metadata'][sid]['par_value']));bf=fee(q,buy,sched,'buy',par);sfv=fee(q,sell,sched,'sell',par)
  # Pure same-day-quote cost example; not executable A-share same-day resale.
  cash=D(q)*buy+bf;flatcost=D(q)*(buy-sell)+bf+sfv
  rows.append(dict(**r,stock_I_first_off=ioff,industry_first_end_attempt=attemptend,entry_cash_exact=str(cash),entry_fee_fraction=float(bf/(D(q)*buy)),flat_quote_cost_cny_exact=str(flatcost),flat_quote_cost_fraction=float(flatcost/(D(q)*op)),flat_quote_note='same known raw open and dated fee schedule, 5bp each side; illustrative cost only, not a permitted same-day A-share trade',stock_I_off_before60=bool(r['complete60'] and ioff and ioff<=r['end_day60']),industry_E0_end_before60=bool(r['complete60'] and pd.notna(r['E0_end']) and r['E0_end']<=r['end_day60'])))
 e=pd.DataFrame(rows);e.to_csv(O/'EVENT_ORDER_AND_COSTS.csv',index=False)
 summary=dict(added_after_price_results_for_reporting_only=True,selection_unchanged=True,entry_fee_fraction=e.entry_fee_fraction.describe().to_dict(),flat_quote_cost_fraction=e.flat_quote_cost_fraction.describe().to_dict(),gross_min=float(e.gross.min()),gross_median=float(e.gross.median()),gross_max=float(e.gross.max()),complete60=int(e.complete60.sum()),complete60_with_prior_stock_I_off=int(e.stock_I_off_before60.sum()),complete60_with_prior_industry_E0_end=int(e.industry_E0_end_before60.sum()),big60_count=int(e.big60.sum()),big60_with_prior_stock_I_off=int(e[e.big60].stock_I_off_before60.sum()),big60_with_prior_industry_E0_end=int(e[e.big60].industry_E0_end_before60.sum()))
 (O/'EVENT_COST_SUMMARY.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
 (O/'REPORTING_SUPPLEMENT_HASHES.json').write_text(json.dumps({**src,str(Path(__file__)):sha(Path(__file__)),str(O/'SELECTION_SEAL.json'):sha(O/'SELECTION_SEAL.json')},ensure_ascii=False,indent=2)+'\n')
 print(summary)
if __name__=='__main__':main()
