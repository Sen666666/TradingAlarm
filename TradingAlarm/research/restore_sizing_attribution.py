"""Fixed original cohorts and paid-fee addback; neither is a counterfactual backtest."""
import json
from pathlib import Path
import pandas as pd
from episode_capital_tail_audit import attach_cash
OUT=Path('results/broad-shared-short-restore')
old=pd.read_parquet('results/broad-shared-first-cross/episodes.parquet');old=old[old.case.eq('group_gate_cap-base')]
rows=[]
for model,root in [('original','broad-shared-first-cross'),('latched_half','broad-shared-short-half'),('restoring','broad-shared-short-restore')]:
 p=Path('results')/root;r=next(x for x in json.loads((p/'summary.json').read_text()) if x['case']=='group_gate_cap' and x['scenario']=='base');e=pd.read_parquet(p/'episodes.parquet');e=e[e.case.eq('group_gate_cap-base')];j=old.merge(e,on=['symbol','signal_date'],suffixes=('_old','_new'),validate='one_to_one');assert len(j)==len(old)==len(e)
 t=j.return_on_purchase_cash_old.ge(.3)
 rows.append(dict(model=model,episodes=len(e),orders=r['orders'],net_return=r['total_return'],paid_fees_fraction=r['fees']/1e6,paid_fee_addback=r['total_return']+r['fees']/1e6,original_tail_pnl=float(j.loc[t,'pnl_new'].sum()/1e6),original_ordinary_pnl=float(j.loc[~t,'pnl_new'].sum()/1e6)))
(OUT/'fixed-cohorts-and-fees.json').write_text(json.dumps(rows,indent=2));print(pd.DataFrame(rows).to_string(index=False))
p=Path('results/strength-short-restore');rows=[]
for r in json.loads((p/'results.json').read_text()):
 if r['group']!='hk7':continue
 case=r['case'];e=pd.DataFrame(attach_cash(json.loads((p/f'{case}-episodes.json').read_text()),json.loads((p/f'{case}-orders.json').read_text())));assert abs(e.pnl.sum()/1e6-r['total_return'])<1e-9;t=e.return_on_buy_cash.ge(.3);rows.append(dict(case=case,tail30=int(t.sum()),tail_contribution=float(e.loc[t,'pnl'].sum()/1e6),ordinary_contribution=float(e.loc[~t,'pnl'].sum()/1e6)))
(p/'capital-tail-summary.json').write_text(json.dumps(rows,indent=2))
