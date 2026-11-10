"""Matched admission experiment audit; no fitted thresholds or performance selection."""
import json,hashlib
from pathlib import Path
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
OUT=Path('results/broad-shared-first-cross');REF=Path('results/broad-shared-slots')
def main():
 rows=json.loads((OUT/'summary.json').read_text());old=json.loads((REF/'summary.json').read_text());episodes=pd.read_parquet(OUT/'episodes.parquet');new=episodes[~episodes.case.str.startswith('control_')]
 assert new.entry_signal_age.eq(0).all()
 assert len(rows)==7
 compared=[]
 for r in rows:
  if r['case']=='control_rank':continue
  prev=next(x for x in old if all(x[k]==r[k] for k in ['case','scenario']))
  compared.append(dict(case=r['case'],scenario=r['scenario'],previous_return=prev['total_return'],first_cross_return=r['total_return'],return_difference=r['total_return']-prev['total_return'],previous_mdd=prev['max_drawdown'],first_cross_mdd=r['max_drawdown'],previous_cash=prev['average_cash_weight'],first_cross_cash=r['average_cash_weight'],year2026=r['year2026']))
 fig,axes=plt.subplots(2,2,figsize=(12,7),sharex=True)
 for col,case in enumerate(['rank','group_gate_cap']):
  for label,root in [('state admission',REF),('first-cross admission',OUT)]:
   p=pd.read_parquet(root/f'{case}-base-path.parquet');axes[0,col].plot(p.index,p.nav,label=label);axes[1,col].plot(p.index,p.cash/(p.nav*1e6)*100)
  axes[0,col].set_title(case);axes[0,col].legend();axes[0,col].set_ylabel('NAV');axes[1,col].set_ylabel('Cash %')
 for ax in axes.flat:
  ax.grid(alpha=.2);ax.xaxis.set_major_locator(mdates.MonthLocator(interval=6));ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
 fig.suptitle('Fixed score, exits and slot budgets; admission timing only\nA485 adjusted-price synthetic research, development sample')
 fig.tight_layout();fig.savefig(OUT/'comparison.png',dpi=150)
 tail=json.loads((OUT/'tail-economics.json').read_text());phases=json.loads((OUT/'2026-phases.json').read_text())
 review=dict(status='research_not_validated',comparison=compared,tail_economics=tail,phases2026=phases,validation=dict(unit_tests=11,exact_old_control=True,first_cross_episodes=len(new),all_first_orders_event_age_zero=True,input_hashes=485),limits=['Both timing and capital availability change subsequent fills; paired experiment measures full policy difference, not isolated same-trade effect.','Cash exposure differs; lower drawdown alone does not prove improved signal.','19 cache-start active states initialized from flat count as first admission; not all are independently verified fresh transitions before cache.','Adjusted fractional prices, artificial ample liquidity, selected survivors and development history.','Association groups are not historical sectors.'])
 (OUT/'review.json').write_text(json.dumps(review,ensure_ascii=False,indent=2));print(pd.DataFrame(compared).to_string(index=False))
if __name__=='__main__':main()
