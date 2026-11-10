"""Standard standalone scientific figure; every frozen perturbation retained."""
from pathlib import Path
import argparse,hashlib,json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

HERE=Path(__file__).resolve().parent;F=HERE.parent
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def main():
 p=argparse.ArgumentParser();p.add_argument('--results',type=Path,default=HERE/'results_v1');a=p.parse_args();v=read(a.results/'VALIDATION.json')
 assert v['status']=='PASS_ALL_FROZEN_ROBUSTNESS_PATHS' and v['completed_new_paths']==12 and not v['waiting']
 matrix=read(a.results/'FIXED_PERIOD_PERFORMANCE.json');by={(x['arm'],x['window'],x['period']):x for x in matrix};fr=read(F/'ROBUSTNESS_FREEZE.json')
 labels=['JOINT']+[x['label'] for x in fr['parameter_variants']];xt=['R20 / E20']+[f"R{s['R']} / E{s['EMA']}" for s in fr['parameter_variants']];colors=['#202020']+['#4d83b2']*4
 fig,axes=plt.subplots(3,2,figsize=(16,12));fig.suptitle('Frozen JOINT robustness: single-factor perturbations and full-account cost stress',fontsize=16)
 cost={x['window']:x for x in read(a.results/'COST_SENSITIVITY.json')}
 for col,(win,full,title) in enumerate([('2022_2024','full_2022_2024','Continuous 2022-2024'),('strong','strong','Jul 2025-Jun 2026')]):
  base=by['BASELINE',win,full];rr=[by[x,win,full] for x in labels]
  for row,(field,mult,ylabel) in enumerate([('NAV_end',.0001,'Ending NAV (CNY 10,000)'),('period_rebased_max_DD',100,'Maximum drawdown (%)')]):
   ax=axes[row,col];vals=[float(x[field])*mult for x in rr];ax.bar(np.arange(5),vals,color=colors,width=.65)
   baseval=float(base[field])*mult;ax.axhline(baseval,color='#777777',linestyle='--',linewidth=1.3,label='Original BASE')
   ax.set_xticks(np.arange(5),xt,rotation=18,ha='right');ax.set_ylabel(ylabel);ax.set_title(title if row==0 else 'Original20 in black; all four perturbations in frozen order')
   ax.set_ylim(0,max(max(vals),baseval)*1.2);ax.grid(axis='y',alpha=.22);ax.set_axisbelow(True);ax.legend(fontsize=9,loc='upper left')
   for i,x in enumerate(vals):ax.annotate(f'{x:.2f}',(i,x),ha='center',va='bottom',xytext=(0,3),textcoords='offset points',fontsize=9)
  ax=axes[2,col];c=cost[win];vals=[float(c['normal_JOINT_advantage'])*.0001,float(c['cost150_JOINT_advantage'])*.0001]
  ax.bar([0,1],vals,color=['#202020','#4d83b2'],width=.5);ax.axhline(0,color='#777777',linewidth=1);ax.set_xticks([0,1],['Original costs','Fees + adverse slip x1.5'])
  ax.set_title('JOINT minus matched BASE ending NAV');ax.set_ylabel('Advantage (CNY 10,000)');ax.grid(axis='y',alpha=.22);ax.set_axisbelow(True)
  for i,x in enumerate(vals):ax.annotate(f'{x:+.2f}',(i,x),ha='center',va='bottom' if x>=0 else 'top',xytext=(0,3 if x>=0 else -3),textcoords='offset points',fontsize=10)
  lo=min(0,min(vals));hi=max(0,max(vals));pad=max(1,(hi-lo)*.25);ax.set_ylim(lo-pad,hi+pad)
 fig.text(.5,.012,'Consumed historical development sample. No parameter selection. All paths start with CNY1m per independent window.\nCost stress preserves endogenous sizing, cash, ACT and fills; advantage change is not a static fee-only attribution.',ha='center',fontsize=10)
 fig.tight_layout(rect=(0,.055,1,.97));target=a.results/'ROBUSTNESS_SENSITIVITY.png';pdf=a.results/'ROBUSTNESS_SENSITIVITY.pdf';assert not target.exists() and not pdf.exists()
 fig.savefig(target,dpi=160);fig.savefig(pdf);plt.close(fig)
 manifest={'status':'COMPLETE_FROZEN_ALL_VARIANTS_FIGURE','sources':{str(p.resolve()):sha(p) for p in [Path(__file__),F/'ROBUSTNESS_FREEZE.json',a.results/'VALIDATION.json',a.results/'FIXED_PERIOD_PERFORMANCE.json',a.results/'COST_SENSITIVITY.json']},'outputs':{str(p.resolve()):sha(p) for p in [target,pdf]},'no_highlight_or_rank_of_winner':True,'order':'original20, then four frozen one-factor variants; all perturbations identical color','new_accounts':0}
 out=a.results/'FIGURE_PROVENANCE.json';assert not out.exists();out.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n');print(target)
if __name__=='__main__':main()
