"""Standalone BASE/ETA NAV, drawdown and actual-fee figure; completed only."""
from pathlib import Path
import argparse,hashlib,json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd
HERE=Path(__file__).resolve().parent
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--results',type=Path,default=HERE/'results_v1');a=p.parse_args();v=read(a.results/'VALIDATION.json');assert v['status']=='PASS_READ_ONLY_ETA4_PATH36_PERIOD20_STAGE_COMPARISON' and v['full_paths']==4
 rows=read(a.results/'FIXED18_PERIODS_TWO_CONFIGURATIONS.json');assert len(rows)==36;by={(x['arm'],x['window'],x['period']):x for x in rows};fig,axes=plt.subplots(3,2,figsize=(15,11));files=[a.results/'VALIDATION.json',a.results/'FIXED18_PERIODS_TWO_CONFIGURATIONS.json',Path(__file__)]
 for col,(win,full,title) in enumerate([('2022_2024','full_2022_2024','Continuous 2022-2024'),('strong','strong','Jul 2025-Jun 2026')]):
  fees=[]
  for arm,color in [('BASELINE','#222222'),('ETA','#397eb8')]:
   path=a.results/f'{arm}_{win}_DAILY_WEALTH_SPLIT.json';files.append(path);d=read(path);days=pd.to_datetime([x['day'] for x in d]);label='BASE' if arm=='BASELINE' else 'Raw eta priority'
   axes[0,col].plot(days,[float(x['NAV'])/10000 for x in d],label=label,color=color,linewidth=1.6)
   axes[1,col].plot(days,[-100*float(x['drawdown_from_full_path_peak']) for x in d],label=label,color=color,linewidth=1.4)
   fees.append(float(by[arm,win,full]['fees']))
  axes[0,col].set_title(title);axes[0,col].set_ylabel('NAV (CNY 10,000)');axes[0,col].legend()
  axes[1,col].set_ylabel('Running-peak drawdown (%)')
  for ax in axes[:2,col]:ax.grid(alpha=.23);ax.tick_params(axis='x',rotation=22)
  ax=axes[2,col];ax.bar([0,1],[x/10000 for x in fees],color=['#222222','#397eb8'],width=.55);ax.set_xticks([0,1],['BASE','ETA']);ax.set_ylabel('Actual explicit fees (CNY 10,000)');ax.set_title('Native filled-trade fees; embedded slippage separate');ax.grid(axis='y',alpha=.23);ax.set_axisbelow(True)
  for j,x in enumerate(fees):ax.annotate(f'{x/10000:.3f}',(j,x/10000),ha='center',va='bottom',xytext=(0,3),textcoords='offset points')
 fig.suptitle('One frozen priority-source substitution: original BASE versus raw eta',fontsize=16)
 fig.text(.5,.013,'Separate CNY1m starting account per window. Consumed historical development; current membership and native execution proxies.\nEligibility, budgets, holding and ACT rules unchanged; funding/CORE/ACT paths can change endogenously. No parameter selection.',ha='center',fontsize=9)
 fig.tight_layout(rect=(0,.055,1,.965));png=a.results/'ETA_NAV_DD_FEES.png';pdf=a.results/'ETA_NAV_DD_FEES.pdf';assert not png.exists() and not pdf.exists();fig.savefig(png,dpi=160);fig.savefig(pdf);plt.close(fig)
 p=a.results/'FIGURE_PROVENANCE.json';assert not p.exists();p.write_text(json.dumps(dict(status='COMPLETED_FIXED_BASE_ETA_FIGURE',source_sha256={str(q.resolve()):sha(q) for q in files},outputs={str(q.resolve()):sha(q) for q in [png,pdf]},new_accounts=0),ensure_ascii=False,indent=2)+'\n');print(png)
if __name__=='__main__':main()
