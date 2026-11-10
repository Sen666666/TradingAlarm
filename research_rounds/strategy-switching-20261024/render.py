from pathlib import Path
import json,math
import pandas as pd,numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm
from matplotlib.font_manager import FontProperties
R=Path(__file__).resolve().parent;O=R/'results/v0';(R/'charts').mkdir(exist_ok=True)
font=FontProperties(fname='/System/Library/Fonts/Supplemental/Arial Unicode.ttf')
s=pd.read_csv(O/'summary.csv');cases=json.loads((R/'cases.json').read_text());pols=['E0','E2','R','RC','RF','G','F','C2','HOLD']
colors={'E0':'#334155','E2':'#e87825','R':'#008974','RC':'#8357be','RF':'#bd5e91','G':'#bd3a40','F':'#4f8faa','C2':'#8a8324','HOLD':'#a8a8a8'}
main=['E0','E2','R','RC','G'];data={'cases':cases,'policies':pols,'colors':colors,'summary':json.loads(s.to_json(orient='records')),'paths':{}}
for c in cases:
 data['paths'][c['id']]={}
 for sc in ['base','cost2','delay1']:
  paths={};dates=None
  for p in pols:
   l=pd.read_parquet(O/'accounts'/f"{c['id']}__{p}__{sc}"/'ledger.parquet')
   dates=[str(x.date()) for x in l.index];paths[p]={'nav':l.nav.round(7).tolist(),'drawdown':l.drawdown.round(7).tolist()}
  data['paths'][c['id']][sc]={'dates':dates,'policies':paths}
 fig,axs=plt.subplots(2,1,figsize=(12,6.5),sharex=True,gridspec_kw={'height_ratios':[2,1]})
 for p in main:
  l=pd.read_parquet(O/'accounts'/f"{c['id']}__{p}__base"/'ledger.parquet');x=s[(s.case==c['id'])&(s.policy==p)&(s.scenario=='base')].iloc[0]
  axs[0].plot(l.index,l.nav,label=f"{p}: {x.net_return:+.1%} / DD {x.max_drawdown:.1%}",lw=1.25,color=colors[p]);axs[1].plot(l.index,100*l.drawdown,lw=1,color=colors[p])
 axs[0].axhline(1,color='gray',ls=':',lw=.6);axs[0].set_title(c['name']+' '+c['start']+'—'+c['end']+' | 净值及回撤（基础成本）',fontproperties=font)
 axs[0].legend(ncol=2,fontsize=8);axs[0].set_ylabel('NAV, initial=1');axs[1].set_ylabel('Drawdown %')
 for ax in axs:ax.grid(alpha=.16)
 fig.tight_layout();fig.savefig(R/'charts'/f"{c['id']}.png",dpi=135);plt.close(fig)
fixed=s[(s.role=='fixed_scenario')&(s.scenario=='base')];ids=[c['id'] for c in cases if c['role']=='fixed_scenario'];mat=fixed.pivot(index='case',columns='policy',values='net_return').loc[ids,main];dd=fixed.pivot(index='case',columns='policy',values='max_drawdown').loc[ids,main]
fig,ax=plt.subplots(figsize=(11,8.6));ax.imshow(mat.to_numpy()*100,cmap='RdYlGn',norm=TwoSlopeNorm(vmin=-40,vcenter=0,vmax=165),aspect='auto')
ax.set_xticks(range(len(main)),['E0 原算法','E2 敏感退出','R 结构重建才重入','RC 加缠论二买重入','G 慢方向切退出'],fontproperties=font,fontsize=9)
ax.set_yticks(range(len(ids)),[c['name']+' '+c['type']+' '+c['start'][:4] for c in cases if c['role']=='fixed_scenario'],fontproperties=font,fontsize=9)
for i in range(len(ids)):
 for j in range(len(main)):ax.text(j,i,f'{mat.iloc[i,j]:+.2%}\nDD {dd.iloc[i,j]:.2%}',ha='center',va='center',fontsize=9)
ax.set_title('固定11场景：净收益 / 最大回撤\n全部扣成本，所有算法统一规则，案例重叠且均为开发历史',fontproperties=font,fontsize=13,pad=12)
fig.tight_layout();fig.savefig(R/'charts/fixed-comparison.png',dpi=140);plt.close(fig)
(R/'report-data.json').write_text(json.dumps(data,ensure_ascii=False,separators=(',',':'),allow_nan=False))
print('rendered',len(cases),'charts; data bytes',(R/'report-data.json').stat().st_size)
