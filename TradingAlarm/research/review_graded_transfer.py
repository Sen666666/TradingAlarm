"""Review unchanged graded-state transfer; existing ETF/HK evidence kept separate."""
import json,hashlib
from pathlib import Path
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
OUT=Path('results/broad-shared-graded');BASE=Path('results/broad-shared-first-cross')
def main(linear=False):
 OUT=Path('results/broad-shared-linear' if linear else 'results/broad-shared-graded')
 a=json.loads((OUT/'summary.json').read_text());b=json.loads((BASE/'summary.json').read_text());comparison=[]
 for r in a:
  if r['case']!='group_gate_cap':continue
  old=next(v for v in b if v['case']==r['case'] and v['scenario']==r['scenario']);comparison.append(dict(scenario=r['scenario'],old_return=old['total_return'],new_return=r['total_return'],old_mdd=old['max_drawdown'],new_mdd=r['max_drawdown'],old_cash=old['average_cash_weight'],new_cash=r['average_cash_weight'],year2026=r['year2026']))
 episodes=pd.read_parquet(OUT/'episodes.parquet');old=pd.read_parquet(BASE/'episodes.parquet');matched=[]
 for sc in ['base','cost2','delay1']:
  case='group_gate_cap-'+sc;new=episodes[episodes.case.eq(case)];prior=old[old.case.eq(case)];j=prior.merge(new,on=['symbol','signal_date'],how='outer',suffixes=('_old','_new'),indicator=True,validate='one_to_one');both=j[j._merge.eq('both')];oldonly=j[j._merge.eq('left_only')];newonly=j[j._merge.eq('right_only')]
  effects=[float((both.pnl_new-both.pnl_old).sum()/1e6),float(-oldonly.pnl_old.sum()/1e6),float(newonly.pnl_new.sum()/1e6)];assert abs(sum(effects)-(new.pnl.sum()-prior.pnl.sum())/1e6)<1e-10
  matched.append(dict(scenario=sc,matched=len(both),old_only=len(oldonly),new_only=len(newonly),matched_pnl_difference=effects[0],removed_old_contribution=effects[1],new_contribution=effects[2]))
 fig,axes=plt.subplots(3,1,figsize=(11,9),sharex=True)
 for label,root in [('original binary',BASE),('linear volume score' if linear else 'graded existing state',OUT)]:
  p=pd.read_parquet(root/'group_gate_cap-base-path.parquet');axes[0].plot(p.index,p.nav,label=label);axes[1].plot(p.index,p.drawdown*100);axes[2].plot(p.index,p.cash/(p.nav*1e6)*100)
 for ax,title in zip(axes,['NAV','Drawdown %','Cash %']):
  ax.set_ylabel(title);ax.grid(alpha=.2);ax.xaxis.set_major_locator(mdates.MonthLocator(interval=6));ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'));ax.axvline(pd.Timestamp('2026-06-01'),color='grey',linestyle=':')
 axes[0].legend();fig.suptitle(('Linear-volume' if linear else 'Graded-state')+' A485 transfer | nine slots, group gate/cap\nSynthetic adjusted-price development account, not certified execution')
 fig.tight_layout();fig.savefig(OUT/'comparison.png',dpi=150)
 review=dict(status='pending_review',comparison=comparison,matched_accounting=matched,tail_economics=json.loads((OUT/'tail-economics.json').read_text()),phases2026=json.loads((OUT/'2026-phases.json').read_text()),limits=['Full-history state initialized before2024; trading uses same flat-before-cache boundary as baseline. Graded initial positive state may be half; linear state is binary.','Changed exits and slot duration change later admissions; accounting decomposition is not a causal same-trade exit estimate.','A485 selected survivors, synthetic adjusted units, no complete liquidity/limit/corporate-action/tax certification.','Existing ETF/HK results have different pools and allocation; cannot be averaged with this A portfolio as independent evidence.','All inspected years are development; no future robustness claim.'])
 (OUT/'review.json').write_text(json.dumps(review,indent=2));print(pd.DataFrame(comparison).to_string(index=False));print(pd.DataFrame(matched).to_string(index=False))
if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--linear',action='store_true');main(p.parse_args().linear)
