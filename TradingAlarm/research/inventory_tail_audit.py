"""Audit ordinary/tail accounting of minimal-screen survivors without choosing a winner."""
import json,hashlib
from pathlib import Path
import pandas as pd
from episode_capital_tail_audit import attach_cash
OUT=Path('results/trend-model-inventory')
def main():
 models=json.loads((OUT/'model-summary.json').read_text());lookup={r['strategy']:r for r in models};aliases=json.loads((OUT/'equivalent-observed-paths.json').read_text());rows=[];checks=[]
 for names in aliases:
  if not lookup[names[0]]['both_conditions']:continue
  selected=None
  for name in names:
   c=next(x for x in lookup[name]['base_case_sources'] if x['group']=='hk7');root=Path(c['source']).parent;p=root/(c['case']+'-episodes.json')
   if p.exists():selected=(name,c,root,p);break
  if selected is None:raise ValueError(('Missing HK episode report',names))
  name,c,root,p=selected;orders=root/(c['case']+'-orders.json');path=root/(c['case']+'-path.parquet');e=pd.DataFrame(attach_cash(json.loads(p.read_text()),json.loads(orders.read_text())));nav=pd.read_parquet(path);error=abs(e.pnl.sum()/1e6-(nav.nav.iloc[-1]-1));assert error<1e-9
  tail=e.return_on_buy_cash.ge(.3);loss=e.pnl.lt(0);wins=e.pnl.ge(0)&~tail
  rows.append(dict(strategy=name,equivalent_observed_versions=names,episodes=len(e),tail30=int(tail.sum()),tail_contribution=float(e.loc[tail,'pnl'].sum()/1e6),ordinary_wins=float(e.loc[wins,'pnl'].sum()/1e6),ordinary_losses=float(e.loc[loss,'pnl'].sum()/1e6),ordinary_net=float(e.loc[~tail,'pnl'].sum()/1e6),net=float(e.pnl.sum()/1e6),ordinary_win_loss_coverage=float(e.loc[wins,'pnl'].sum()/-e.loc[loss,'pnl'].sum())))
  checks.append(dict(strategy=name,error=error,hashes={str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in [p,orders,path]}))
 (OUT/'screened-hk-tail-economics.json').write_text(json.dumps(rows,indent=2));(OUT/'screened-hk-tail-validation.json').write_text(json.dumps(dict(checks=checks,limits=['HK7 base only; remaining scenarios and ETF ordinary/tail structure not established by this report.','Return uses cumulative purchase cash; marked claims are included where present.','Minimal screen and tail audit use inspected development data, not independent model selection validation.','Equivalent observed paths do not establish that two formulas are universally identical.']),indent=2));print(pd.DataFrame(rows).drop(columns='equivalent_observed_versions').to_string(index=False))
if __name__=='__main__':main()
