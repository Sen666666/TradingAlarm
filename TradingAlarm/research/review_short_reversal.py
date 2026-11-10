"""Frozen short-direction exit experiment: full accounts, matched episodes and transfers."""
import json,hashlib
from pathlib import Path
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
OUT=Path('results/broad-shared-short-exit');OLD=Path('results/broad-shared-first-cross');TRANSFER=Path('results/strength-short-reversal')
def main(half=False,restore=False):
 if restore:half=True
 OUT=Path('results/broad-shared-short-restore' if restore else 'results/broad-shared-short-half' if half else 'results/broad-shared-short-exit')
 TRANSFER=Path('results/strength-short-restore' if restore else 'results/strength-short-half' if half else 'results/strength-short-reversal')
 model_name='short_restore_pairwise_volume' if restore else 'short_half_pairwise_volume' if half else 'short_reversal_pairwise_volume'
 old=pd.read_parquet(OLD/'episodes.parquet');new=pd.read_parquet(OUT/'episodes.parquet');comparisons=[];matched_tables=[]
 for sc in ['base','cost2','delay1']:
  case='group_gate_cap-'+sc;a=old[old.case.eq(case)].copy();b=new[new.case.eq(case)].copy();keys=['symbol','signal_date'];assert not a.duplicated(keys).any() and not b.duplicated(keys).any()
  joined=a.merge(b,on=keys,how='outer',suffixes=('_old','_new'),indicator=True,validate='one_to_one');matched=joined[joined._merge.eq('both')];onlyold=joined[joined._merge.eq('left_only')];onlynew=joined[joined._merge.eq('right_only')]
  matched_effect=float((matched.pnl_new-matched.pnl_old).sum()/1e6);old_effect=float(-onlyold.pnl_old.sum()/1e6);new_effect=float(onlynew.pnl_new.sum()/1e6)
  delta=(b.pnl.sum()-a.pnl.sum())/1e6;assert abs(matched_effect+old_effect+new_effect-delta)<1e-10
  tails=matched[matched.return_on_purchase_cash_old.ge(.3)]
  comparisons.append(dict(scenario=sc,matched=len(matched),old_only=len(onlyold),new_only=len(onlynew),paired_mean_return_change=float((matched.return_on_purchase_cash_new-matched.return_on_purchase_cash_old).mean()),matched_account_pnl_difference=matched_effect,removed_old_contribution=old_effect,newly_admitted_contribution=new_effect,total_return_difference=float(delta),original_tail_matched=len(tails),original_tail_still_tail=int(tails.return_on_purchase_cash_new.ge(.3).sum())))
  joined['scenario']=sc;matched_tables.append(joined)
 pd.concat(matched_tables,ignore_index=True).to_parquet(OUT/'matched-episodes.parquet',index=False)
 transfer=json.loads((TRANSFER/'results.json').read_text());fig,axes=plt.subplots(3,1,figsize=(11,9))
 for label,root in [('original',OLD)]+([('latched half',Path('results/broad-shared-short-half'))] if restore else [])+[('restoring target' if restore else 'half target' if half else 'short reversal',OUT)]:
  p=pd.read_parquet(root/'group_gate_cap-base-path.parquet');axes[0].plot(p.index,p.nav,label=label)
 for i,group in enumerate(['etf17','hk7'],1):
  for model in ['pairwise_volume']+(['short_half_pairwise_volume'] if restore else [])+[model_name]:
   p=pd.read_parquet(TRANSFER/f'{group}-{model}-daily-base-path.parquet');axes[i].plot(p.index,p.nav,label=model)
 for ax,label in zip(axes,['A485 group capped first-cross','ETF17 equal capital','HK7 equal capital']):
  ax.set_title(label);ax.set_ylabel('NAV');ax.legend();ax.grid(alpha=.2);ax.xaxis.set_major_locator(mdates.YearLocator());ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
 fig.suptitle('Frozen five-bar direction response | reused development samples')
 fig.tight_layout();fig.savefig(OUT/'comparison.png',dpi=150)
 review=dict(status='pending_review' if half else 'rejected_not_adopted',a_matched_accounting=comparisons,transfer_results=transfer,conclusion='Half-target experiment requires evaluation of tail retention and ordinary losses.' if half else 'A485 loses money under all three scenarios. Faster exit reduces tail contribution and releases slots for more losing campaigns. ETF worsens; HK small base improvement does not survive cost2 economically. No universal benefit.',limits=['Matched PNL difference includes position-size and execution path changes; not a causal exit-only PNL estimate.','New-only episodes arise from changed capital/slot availability; original thresholds unchanged.','A485 adjusted synthetic execution, not actual corporate-action/limit/liquidity validation.','ETF17/HK7 raw share ledgers validated but selected surviving pools and reused development data.'])
 (OUT/'review.json').write_text(json.dumps(review,indent=2));print(pd.DataFrame(comparisons).to_string(index=False))
 print(pd.DataFrame(transfer)[['group','strategy','scenario','total_return','max_drawdown']].to_string(index=False))
if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--half',action='store_true');p.add_argument('--restore',action='store_true');a=p.parse_args();main(a.half,a.restore)
