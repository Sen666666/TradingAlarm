"""Static scientific figures and a local research index; no remote resources."""
from common_m1 import *
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
from html import escape
FONT=FontProperties(fname='/System/Library/Fonts/Supplemental/Arial Unicode.ttf')
LABEL={'acute_down':'急跌冲击','fast_up':'短周期强推进','slow_up':'长周期强推进','modest_up':'同向温和','long_weak_short_strong':'长弱短强','long_strong_short_weak':'长强短弱','aligned_down':'同向下降','mixed':'混合','unknown_long':'长证据不足','invalid_observation':'缺失'}
COL={'acute_down':'#bb3449','fast_up':'#b96d36','slow_up':'#638339','modest_up':'#c2b07e','long_weak_short_strong':'#9d85b4','long_strong_short_weak':'#6d98ad','aligned_down':'#435f85','mixed':'#b0bac4','unknown_long':'#ddd','invalid_observation':'#ddd'}
def plot(z,case,path):
 a=z.loc[case['start']:case['end']].copy();a=a.loc[a.close.notna()]
 fig,axs=plt.subplots(6,1,figsize=(14,12),sharex=True,gridspec_kw={'height_ratios':[3,0.8,1.3,1.5,1.3,0.8]})
 axs[0].plot(a.index,a.close,color='#223543',lw=1);axs[0].set_yscale('log');axs[0].set_ylabel('price (log)')
 axs[0].scatter(a.index,a.close,c=[COL[x] for x in a.profile],s=7,alpha=.65)
 title=NAMES[case['symbol']]+'｜'+case['title']+'：旧G1/IX不改，B5-M1只增加推进描述'
 axs[0].set_title(title,fontproperties=FONT,loc='left',fontsize=12)
 vol=a.volume/a.volume.shift().rolling(21).median();axs[1].bar(a.index,vol,width=1,color='#8c9da4');axs[1].set_ylabel('V / prev21')
 axs[2].step(a.index,a.score,where='post',color='#9f613e',lw=.7,label='original G1');axs[2].set_ylim(-85,110);axs[2].legend(loc='upper left',fontsize=8)
 axs[3].plot(a.index,a.short_score,color='#cb743b',lw=.7,label='short: EW5 / EW21');axs[3].plot(a.index,a.long_score,color='#267f87',lw=1,label='long: EW63 / EW126');axs[3].axhline(0,color='gray',lw=.6);axs[3].set_ylim(-105,105);axs[3].legend(loc='upper left',fontsize=8,ncol=2)
 axs[4].plot(a.index,a.mu21*1e4,color='#cb743b',lw=.7,label='EW21 net log return (bp/day)');axs[4].plot(a.index,a.mu126*1e4,color='#267f87',lw=1,label='EW126 net log return (bp/day)');axs[4].axhline(0,color='gray',lw=.6);axs[4].legend(loc='upper left',fontsize=8,ncol=2)
 col='e0_target';e0=a[col].astype(float) if col in a else a.e0_target
 axs[5].step(a.index,e0*.7,where='post',color='#88916b',lw=.8,label='original E0 qualified')
 if 'ix_target' in a:axs[5].step(a.index,a.ix_target*.7+1,where='post',color='#3c698e',lw=.8,label='original IX qualified')
 axs[5].set_ylim(-.1,1.9);axs[5].legend(loc='upper left',fontsize=8,ncol=2)
 crash=a.acute_down.fillna(False).astype(bool)
 axs[0].scatter(a.index[crash],a.loc[crash,'close'],c='#c82440',marker='x',s=18,label='original volume-price acute down')
 for ax in axs:ax.grid(alpha=.15)
 fig.text(.04,.008,'F/L不是新温度、买卖信号或收益概率。长强短弱可能是整理也可能是初跌；长弱短强可能是反弹也可能是新启动。',fontproperties=FONT,fontsize=9)
 fig.tight_layout(rect=(0,.025,1,1));fig.savefig(path,dpi=115);plt.close(fig)

def main():
 verify();out=HERE/'report';out.mkdir(exist_ok=False);(out/'figures').mkdir()
 cases=[]
 for sid in NAMES:cases.append(dict(id=sid+'_full',symbol=sid,start='2021-01-01' if sid not in ['688256.SH','300308.SZ','300502.SZ'] else '2023-01-01',end='2026-10-23',title='连续历史'))
 manifest=read(ROOT/'research_rounds/pv-strength-b3-20261025/figures/real-manifest.json')['plots']
 for x in manifest:cases.append(dict(id='fixed_'+x['id'],symbol=x['asset'],start=x['start'],end=x['end'],title='原固定量价窗口 '+x['id']))
 for c in cases:plot(pd.read_parquet(HERE/'analysis/series'/f"{c['symbol']}.parquet"),c,out/'figures'/f"{c['id']}.png")
 # Exact same requested gold windows, diagnostics only, not additional fit.
 gold=pd.read_parquet(HERE/'analysis/series/AU0.parquet');stats=[]
 for name,start,end in [('gold_flat25','2025-05-01','2025-09-01'),('gold_down26','2026-03-01','2026-07-31')]:
  a=gold.loc[start:end];stats.append(dict(window=name,start=start,end=end,rows=len(a),grade_changes=int(a.grade.diff().ne(0).iloc[1:].sum()),short_score_daily_change_median=a.short_score.diff().abs().median(),long_score_daily_change_median=a.long_score.diff().abs().median(),short_score_min=a.short_score.min(),short_score_max=a.short_score.max(),long_score_min=a.long_score.min(),long_score_max=a.long_score.max(),acute_days=int(a.acute_down.fillna(False).sum()),profiles=a.profile.value_counts().to_dict()))
 write(out/'gold-window-diagnostics.json',stats);write(out/'figure-manifest.json',cases)
 labels=pd.read_csv(HERE/'analysis/label-summary.csv');h=pd.read_csv(HERE/'handoff/summary.csv');diag=read(HERE/'analysis/series-diagnostics.json')
 recent=labels.query("scope=='recent' and field=='profile' and horizon==63").copy()
 for c in ['mean','median','p10','p90','positive','stock_year_mean']:recent[c]=recent[c].map(lambda x:f'{x*100:.2f}%')
 recent['group']=recent.group.map(LABEL);h=h.query("scope=='recent'").copy()
 for c in ['mean63','median63','positive63','stock_year_mean63']:h[c]=h[c].map(lambda x:f'{x*100:.2f}%')
 options=''.join(f'<option value="{escape(c["id"])}">{escape(NAMES[c["symbol"]]+" / "+c["title"])}</option>' for c in cases)
 text='''<!doctype html><meta charset="utf-8"><title>多尺度推进与资源交接诊断</title><style>body{font-family:system-ui,-apple-system,sans-serif;background:#f4f6f6;color:#263841;margin:0}main{max-width:1200px;margin:auto;padding:30px 24px}h1{font-size:29px}h2{font-size:22px}p{line-height:1.8}.box{background:white;border:1px solid #dae1e2;padding:20px;border-radius:9px;margin:18px 0}select{padding:10px;width:100%;font-size:16px}img{width:100%;margin-top:15px}table{border-collapse:collapse;font-size:13px;width:100%}td,th{border:1px solid #dce2e3;padding:7px;text-align:right}th:first-child,td:first-child{text-align:left}.scroll{overflow:auto}.muted{color:#64747c}</style><main><h1>短期快涨与长期慢涨：现在究竟算进了什么</h1><p>本轮增加 B5-M1 多尺度证据面板，并检查全部 IX-S0 候选在自然退出后的资源接续空间。旧 E0 / B4 / B5 / G1 / IX 和原账户全部保留。本轮新增资金账户 <b>0</b>，行情下载 <b>0</b>。</p><div class="box"><b>先看结论</b><p>当前 G1 只有 EW5 / EW21 推进，S63 是量价结构方向。长期慢涨并非完全没算：只要双结构向上且 EW21 正，原分已经可以是75；但它没有单独展示慢速贡献。M1补上 EW63 / EW126，并把反向冲击留在独立栏，避免旧涨势抵消新急跌。F/L仍是波动归一化证据，绝对推进速度另看日基点。</p><p>不把“加入长期”自动当成改善。长期通道在顶部之后仍能保持正数，不能直接用于继续持有；新启动早期也可能面对旧长期负数，不能一律禁买。它为政策消融提供依据，当前不生成新温度。</p></div><div class="box"><h2>同一批标的与固定窗口</h2><select id="case">OPTIONS</select><img id="fig" src="figures/AU0_full.png" alt="量价、原G1、短长推进和E0对照"><p class="muted">资格轨迹不是资金持仓。价格为各自已冻结的研究输入；沪金连续合约与黄金ETF分别显示。</p></div><div class="box"><h2>全A原IX事件：后续63交易日价格标签</h2><p>1709只股票、原481305个事件；下表为2023年以后。均值、中位、股年等权分别列出。是重叠的未来价格诊断，含事后信息，不能当作可成交策略收益或独立样本。</p><div class="scroll">LABELTABLE</div></div><div class="box"><h2>自然退出资源交接：原路径容量上限</h2><p>只移除昨晚已锁定退出、原账户次日确已完成的持仓。保留其余持仓与买单，再按昨晚原RS排序竞争。lot_aware另要求最小单位金额不超过昨晚15%NAV。没有假造可用现金、手续费或新成交，不能汇总为收益。</p><div class="scroll">HANDOFFTABLE</div></div><div class="box"><h2>本轮范围与下一步</h2><p>自然交接先作为单独执行政策冻结与比较，主动换仓另组；强度方面保留快/慢/结构/冲击四类可追溯输出，先验证政策取舍，不以三只事后大赢家为例外名单。不同时重写排序、退出和仓位。</p><a href="../CONCLUSION.md">完整分析</a> · <a href="../PROTOCOL.md">冻结公式与协议</a></div></main><script>const s=document.getElementById('case'),im=document.getElementById('fig');s.addEventListener('change',()=>im.src='figures/'+s.value+'.png');</script>'''
 text=text.replace('OPTIONS',options).replace('LABELTABLE',recent.to_html(index=False,border=0)).replace('HANDOFFTABLE',h.to_html(index=False,border=0))
 (out/'index.html').write_text(text)
 write(out/'build.json',dict(recorded_at=now(),figures=len(cases),remote_assets=0,accounts=0,report_type='descriptive research, no economic returns'))
 print(dict(figures=len(cases)),flush=True)
if __name__=='__main__':main()
