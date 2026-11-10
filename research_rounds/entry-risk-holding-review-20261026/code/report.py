from pathlib import Path
import html
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image, ImageOps, ImageDraw

HERE=Path(__file__).resolve().parents[1]
out=HERE/'report';out.mkdir(exist_ok=False)
f=pd.read_csv(HERE/'results-v1/decision-overlap.csv').set_index('group').loc[['SEMI','COMM','DRUG','BANK']]
x=np.arange(4);w=.35
fig,ax=plt.subplots(1,3,figsize=(16,5.2))
for a in ax:a.set_xticks(x, ['Semi','Comm','Drug','Bank']);a.grid(axis='y',alpha=.18);a.set_axisbelow(True)
ax[0].bar(x-w/2,100*f.near_n/f.closed,w,label='Closed trades',color='#7394ad')
ax[0].bar(x+w/2,100*f.near_tails/f.tails,w,label='Tail trades',color='#cf9b44')
ax[0].set_title('Entry support distance < 5%');ax[0].set_ylabel('Share of original I trades (%)');ax[0].set_ylim(0,100);ax[0].legend()
for i,(_,r) in enumerate(f.iterrows()):ax[0].text(i+w/2,100*r.near_tails/r.tails+2,f'{int(r.near_tails)}/{int(r.tails)}',ha='center',fontsize=9)
ax[1].bar(x-w/2,100*f.stress_n/f.closed,w,label='Closed trades',color='#7394ad')
ax[1].bar(x+w/2,100*f.stress_tails/f.tails,w,label='Tail trades',color='#cf9b44')
ax[1].set_title('After >= 4 losses among prior 5 exits');ax[1].set_ylabel('Share of original I trades (%)');ax[1].set_ylim(0,100);ax[1].legend()
for i,(_,r) in enumerate(f.iterrows()):ax[1].text(i+w/2,100*r.stress_tails/r.tails+2,f'{int(r.stress_tails)}/{int(r.tails)}',ha='center',fontsize=9)
ax[2].bar(x-w/2,100*f.risk_median,w,label='Median',color='#7394ad')
ax[2].bar(x+w/2,100*f.risk_p90,w,label='P90',color='#cf9b44')
ax[2].set_title('Initial price risk to known support');ax[2].set_ylabel('% of decision NAV');ax[2].legend()
fig.suptitle('Existing I paths: narrow distance and loss feedback also overlap with winners',fontsize=14)
fig.text(.5,.015,'721 closed I trades, 72 tails. Descriptive overlap and entry risk only; no new strategy returns. Bank has only one tail.',ha='center',fontsize=9)
fig.tight_layout(rect=[0,.045,1,.93]);fig.savefig(out/'overview.png',dpi=150);plt.close(fig)
sheet=Image.new('RGB',(1560,1680),'white')
for row,g in enumerate(['BANK','COMM','DRUG','SEMI']):
    for col,k in enumerate(['near','far']):
        im=Image.open(HERE/'charts-overlay'/f'{g}_{k}.png');im.thumbnail((780,420));sheet.paste(im,(col*780,row*420))
sheet.save(out/'overlay-contact.png')
def table(p):return pd.read_csv(p).to_html(index=False,border=0,classes='data')
body='''<!doctype html><html lang="zh"><meta charset="utf-8"><title>入场风险与趋势持有深入复查</title><style>body{max-width:1500px;margin:35px auto;padding:0 25px;font:16px/1.65 system-ui;color:#263746}h1,h2{line-height:1.3}img{max-width:100%;height:auto}table{border-collapse:collapse;font-size:13px}th,td{padding:7px 10px;border-bottom:1px solid #ddd;text-align:right}.scroll{overflow:auto}a{color:#245d8b}.note{background:#f3f6f8;padding:18px}</style><h1>入场风险与趋势持有：深入复查</h1><p class="note">3646个真实周期、11670资格事件、4895个来源安全E0段。新经济账户0。当前存续/分类快照的已见开发历史；下方分组与集合重叠不是新策略回测。</p><p>窄支持不作为统一好买点；连亏后硬暂停不采用。保留结构持有，唯一设计候选I-RB1只研究首次金额风险合同，尚未实现或运行。</p><p><a href="../CONCLUSION.md">完整结论</a> · <a href="../CANDIDATE_I_RB1.md">I-RB1设计</a> · <a href="../verification-v1/receipt.json">独立核验</a></p><img src="overview.png"><h2>原I闭合交易中的重叠与风险</h2><div class="scroll">'''
body+=table(HERE/'results-v1/decision-overlap.csv')
body+='</div><h2>原始量价图与未改E0支持</h2><p>按当时支持距离分位选例，未按后续收益选例。虚线右侧为随后已发生的开发历史。</p>'
for g in ['BANK','COMM','DRUG','SEMI']:
    body+='<h2>'+g+'</h2>'
    for k in ['near','far']:body+=f'<p><a href="../charts-raw/{g}_{k}.png">原始量价</a></p><img src="../charts-overlay/{g}_{k}.png">'
body+='</html>'
(out/'index.html').write_text(body)
print(str(out/'index.html'))
