"""Report every frozen random control; never adopt an ex-post winning seed."""
import json,hashlib
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from broad_shared_slot_report import main as episode_report
OUT=Path('results/sector-ranking-random-controls')
def main():
 protocol=json.loads((OUT/'protocol.json').read_text());names=['rank']+['random_'+str(s) for s in protocol['seeds']]
 rows=[json.loads((OUT/(n+'-base-metrics.json')).read_text()) for n in names]
 assert len(rows)==21 and len({r['case'] for r in rows})==21
 (OUT/'summary.json').write_text(json.dumps(rows,indent=2));episode_report(OUT.name)
 f=pd.DataFrame(rows);rank=f.iloc[0];random=f.iloc[1:];tails=pd.DataFrame(json.loads((OUT/'tail-economics.json').read_text()));t= tails[tails.case.ne('rank-base')]
 review={'status':'development_only_no_strategy_adopted','accounts':len(f),'exact_rank_control':True,'rank_return':float(rank.total_return),'random_return_median':float(random.total_return.median()),'random_return_min':float(random.total_return.min()),'random_return_max':float(random.total_return.max()),'random_accounts_beating_rank':int(random.total_return.gt(rank.total_return).sum()),'rank_fraction_random_below':float(random.total_return.lt(rank.total_return).mean()),'max_ledger_error':float(f.ledger_error.max()),'random_ordinary_positive':int(t.ordinary_account_contribution.gt(0).sum()),'limits':protocol['limits']+['Percentile is descriptive conditional on frozen seeds and observed market history; not a p-value or independent future evidence.','Random priority is fixed per symbol, so this compares static randomized selection priorities, not fresh daily lotteries.','Ledger accounting reconciles synthetic adjusted fractional execution; does not certify real trading feasibility.'],'source_hashes':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path('sector_ranking_random_controls.py'),Path('sector_admission_audit.py'),Path(__file__),OUT/'protocol.json']}}
 (OUT/'review.json').write_text(json.dumps(review,ensure_ascii=False,indent=2)+'\n')
 fig,axes=plt.subplots(1,3,figsize=(13,4))
 for ax,col,label in zip(axes,['total_return','max_drawdown','year2026'],['Full return','Max drawdown','2026 return']):
  ax.scatter(np.arange(1,21),100*random[col],color='steelblue');ax.axhline(100*rank[col],color='darkorange',label='Strength rank');ax.set_xlabel('Pre-fixed seed index');ax.set_ylabel(label+' (%)');ax.grid(alpha=.2)
 axes[0].legend();fig.tight_layout();fig.savefig(OUT/'random-controls.png',dpi=150);plt.close(fig)
 print(json.dumps(review,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
