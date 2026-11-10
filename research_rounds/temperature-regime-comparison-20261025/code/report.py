import os,html,json
os.environ.setdefault('MPLCONFIGDIR','/private/tmp/temp-regimes-mpl')
import numpy as np,pandas as pd
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
from common import *
from analyze import clean
FONT=FontProperties(fname='/System/Library/Fonts/Supplemental/Arial Unicode.ttf')
ORDER=['E0','R','F','T_ORIG','L3']+TEMP_POLICIES+['HOLD']
SHORT={'bear_semi22':'半导体熊22','bear_jd23':'京东熊23','strong_semi21':'半导体偏强21','strong_clp23':'中电偏强23','weak_csi21':'沪深300偏弱21','weak_hktech23':'恒科偏弱23','neutral_semi23':'半导体中震23','neutral_hl22':'恒隆中震22','low_gold21':'黄金低振21','semi_ytd26':'半导体2026','bull_semi25_26h1':'半导体牛25—26'}
def main():
 out=HERE/'report';out.mkdir(exist_ok=False);cases=read(HERE/'cases.json');f=pd.read_csv(HERE/'results/v0/summary.csv');aggregate=read(HERE/'analysis/aggregate.json')
 for role,label in [('fixed_scenario','fixed'),('continuous_check','continuous')]:
  cs=[x for x in cases if x['role']==role];base=f.loc[f.scenario.eq('base')&f.role.eq(role)];vals=base.pivot(index='policy',columns='case',values='net_return').reindex(index=ORDER,columns=[x['id'] for x in cs])*100;dd=base.pivot(index='policy',columns='case',values='max_drawdown').reindex(index=ORDER,columns=vals.columns)*100
  fig,ax=plt.subplots(figsize=(max(13,len(cs)*1.35),11));im=ax.imshow(vals,cmap='RdYlGn',vmin=-60,vmax=60,aspect='auto')
  for i in range(len(ORDER)):
   for j in range(len(cs)):
    row=base.loc[base.policy.eq(ORDER[i])&base.case.eq(cs[j]['id'])].iloc[0];text=f'{vals.iloc[i,j]:+.1f}\n({dd.iloc[i,j]:.1f})'+ (' *' if row.trades==0 else '')
    ax.text(j,i,text,ha='center',va='center',fontsize=7,color='#142332')
  ax.set_xticks(range(len(cs)),[SHORT.get(x['id'],x['name']) for x in cs],fontproperties=FONT,fontsize=9,rotation=30,ha='right');ax.set_yticks(range(len(ORDER)),[p+' '+name(p) for p in ORDER],fontproperties=FONT,fontsize=8)
  ax.set_title('基础情景：净收益%（括号为最大回撤%）｜* 为零交易\n完整矩阵，不按场景拼接赢家；色阶截于±60%，数字保留实际值',fontproperties=FONT,fontsize=12);fig.colorbar(im,ax=ax,fraction=.025,pad=.02);fig.tight_layout();fig.savefig(out/(label+'-matrix.png'),dpi=130);plt.close(fig)
 # Full curve comparison for representative positive and negative mechanisms.
 choices=['bull_semi25_26h1','semi_ytd26','continuous_USHJ518880','continuous_HK03033'];ps=['E0','R','F','T_ORIG','L3','E34_X6','C4_X6','C5_X6']
 colors=['#2f68b0','#168873','#7d858f','#ba7b35','#9b62af','#c1aa32','#d95555','#293c55'];fig,axs=plt.subplots(2,2,figsize=(16,10))
 for ax,cid in zip(axs.ravel(),choices):
  c=next(x for x in cases if x['id']==cid)
  for p,col in zip(ps,colors):
   root=HERE/'results/v0' if p in NEW_POLICIES else OLD/'results/v0';l=pd.read_parquet(root/'accounts'/('__'.join([cid,p,'base']))/'ledger.parquet');ax.plot(l.index,l.nav*100,color=col,lw=1,label=p)
  ax.set_title(c['name']+' '+c['start']+'—'+c['end']+' 净值（初始100万元）',fontproperties=FONT,fontsize=10);ax.grid(alpha=.2);ax.legend(fontsize=8,ncol=4)
 fig.tight_layout();fig.savefig(out/'key-curves.png',dpi=125);plt.close(fig)
 payload=dict(cases=cases,policy_order=ORDER,policy_names={p:name(p) for p in ORDER},labels=LABELS,summary=f.to_dict('records'),aggregate=aggregate,grade_events=read(HERE/'analysis/grade-events.json'),plots={})
 for c in cases:
  d=pd.read_parquet(HERE/'inputs'/(c['symbol']+'.parquet')).loc[c['start']:c['end']];temp=pd.read_parquet(HERE/'contexts'/c['symbol']/'temperature.parquet').loc[d.index];x=dict(dates=[str(dt.date()) for dt in d.index],price=d.close.tolist(),grade=(temp.level+1).tolist(),floor=temp.floor.tolist(),models={})
  for p in ORDER:
   root=HERE/'results/v0' if p in NEW_POLICIES else OLD/'results/v0';path=root/'accounts'/('__'.join([c['id'],p,'base']));l=pd.read_parquet(path/'ledger.parquet');t=pd.read_csv(path/'trades.csv')
   x['models'][p]=dict(nav=l.nav.round(7).tolist(),drawdown=l.drawdown.round(7).tolist(),held=l.held.tolist(),trades=t.to_dict('records'))
  payload['plots'][c['id']]=x
 (out/'data.json').write_text(json.dumps(clean(payload),ensure_ascii=False,separators=(',',':'),allow_nan=False))
 template=(HERE/'code/report_template.html').read_text();(out/'index.html').write_text(template)
 (HERE/'index.html').write_text('<!doctype html><meta charset="utf-8"><meta http-equiv="refresh" content="0;url=report/"><a href="report/">查看报告</a>')
 write(out/'manifest.json',dict(recorded_at=now(),source_summary=ref(HERE/'results/v0/summary.csv'),plot_rounding_digits=7,exact_results_in_parquet_and_csv=True,policies=18,new_accounts=756,reused_old=216))
 print({'report':str(out/'index.html'),'data_bytes':(out/'data.json').stat().st_size},flush=True)
if __name__=='__main__':main()
