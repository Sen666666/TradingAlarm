"""Static scientific figures and local report, no economic simulation."""
from pathlib import Path
import json,html,shutil
import numpy as np
import pandas as pd
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
from prepare import HERE,NEW,OLD,EXAMPLES,FONT,read,write,sha,now
from calculate import Study

def main():
 out=HERE/'report';out.mkdir(exist_ok=False);figdir=out/'figures';figdir.mkdir();downloads=out/'downloads';downloads.mkdir()
 s=Study();rows=read(HERE/'results/examples.json');curves=pd.DataFrame(read(HERE/'results/curves.json'));milestones=read(HERE/'results/milestones.json');trunc=read(HERE/'results/artificial-truncations.json')
 summary=read(HERE/'results/summary.json');allrows=read(HERE/'results/latest-all.json')
 for group,label in [(NEW,'new'),(OLD,'old')]:
  fig,axes=plt.subplots(len(group),2,figsize=(13,3*len(group)),squeeze=False)
  for k,sid in enumerate(group):
   j=s.symbols.index(sid);f=curves[curves.symbol==sid];ds=pd.to_datetime(f.date)
   ix=s.dates.get_indexer(ds);p=s.arrays['close'][ix,j];valid=np.flatnonzero(np.isfinite(p));p=p/p[valid[0]]*100
   axes[k,0].plot(ds,p,color='#315d97',lw=1.1);axes[k,0].set_title(sid+' '+s.facts[sid]['name']+' 因果复权价格（首个绘图日=100）',fontproperties=FONT)
   axes[k,1].plot(ds,f.score,color='#ad791c',label='RS-H1',lw=1.2)
   if group==OLD:axes[k,1].plot(ds,f.old_percentile,color='#718096',label='Old RS percentile',ls='--',lw=.8)
   else:
    pts=[x for x in milestones if x['symbol']==sid and x['milestone_symbol']==sid]
    axes[k,1].scatter(pd.to_datetime([x['date'] for x in pts]),[x['score'] for x in pts],s=18,color='#315d97',zorder=3)
   ready=np.flatnonzero(s.arrays['e0_ready'][:,j]==1)
   if len(ready) and group==NEW:
    d=s.dates[ready[0]]
    for ax in axes[k]:ax.axvline(d,color='#718096',ls=':',lw=.8)
    axes[k,0].text(d,.95,' 原E0预热完成',transform=axes[k,0].get_xaxis_transform(),fontsize=8,fontproperties=FONT,va='top')
   axes[k,1].set_ylim(-2,102);axes[k,1].axhline(50,color='#bac4d0',lw=.6);axes[k,1].legend(fontsize=8,loc='best')
   axes[k,1].set_title('RS是描述性强弱，不是上涨概率或买入信号',fontproperties=FONT)
   for ax in axes[k]:ax.grid(alpha=.15);ax.tick_params(axis='x',labelrotation=20)
  fig.tight_layout();fig.savefig(figdir/(label+'-price-score.png'),dpi=125);plt.close(fig)
 fig,ax=plt.subplots(figsize=(11,5));validrows=[x for x in rows if x['score'] is not None]
 names=[x['name'] for x in validrows];pos=np.arange(len(names));ax.barh(pos,[x['score'] for x in validrows],color=['#ad791c' if x['symbol'] in NEW else '#315d97' for x in validrows])
 ax.set_yticks(pos,names,fontproperties=FONT);ax.invert_yaxis();ax.set_xlim(0,104)
 for k,x in enumerate(validrows):ax.text(x['score']+.5,k,f"{x['score']:.2f}  (h={x['h']})",va='center',fontsize=9)
 ax.set_title('2026-10-22 · 同长度参照后的RS-H1（0—100）',fontproperties=FONT);ax.grid(axis='x',alpha=.2);fig.tight_layout();fig.savefig(figdir/'snapshot.png',dpi=130);plt.close(fig)
 fig,ax=plt.subplots(figsize=(10,4.7))
 for sid in ['001309.SZ','600519.SH','300750.SZ']:
  f=[x for x in trunc if x['symbol']==sid];ax.plot([x['h'] for x in f],[x['score'] for x in f],marker='o',label=s.facts[sid]['name'])
 ax.set_xticks([5,21,63,126,252]);ax.set_ylim(0,100);ax.set_xlabel('人为仅提供的收益区间数量',fontproperties=FONT);ax.set_ylabel('同长度参照分',fontproperties=FONT)
 ax.set_title('同一只老股截短历史后：评分含义也随观察期限改变',fontproperties=FONT);ax.legend(prop=FONT);ax.grid(alpha=.2);fig.tight_layout();fig.savefig(figdir/'truncations.png',dpi=130);plt.close(fig)
 for name in ['new','old']:shutil.copy2(HERE/'raw-review'/f'{name}.png',figdir/f'raw-{name}.png')
 for p in (HERE/'results').glob('*.csv'):shutil.copy2(p,downloads/p.name)
 shutil.copy2(HERE/'PROTOCOL.md',downloads/'PROTOCOL.md');shutil.copy2(HERE/'audit/verification.json',downloads/'verification.json')
 def fmt(v):return '—' if v is None else f'{v:.2f}'
 def pct(v):return '—' if v is None else f'{v*100:+.2f}%'
 def table(data,cols):
  return '<div class="scroll"><table><thead><tr>'+''.join('<th>'+html.escape(c[0])+'</th>' for c in cols)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+html.escape(str(fn(r)))+'</td>' for _,fn in cols)+'</tr>' for r in data)+'</tbody></table></div>'
 exampletable=table(rows,[('股票',lambda r:r['name']+' '+r['symbol']),('实际收盘数',lambda r:r['observations']),('统一交易日h',lambda r:r['h']),('本窗口涨跌',lambda r:pct(r['horizon_return'])),('RS-H1',lambda r:fmt(r['score'])),('旧RS原始值',lambda r:fmt(None if r['old_rs'] is None else r['old_rs']*100)),('参照数N',lambda r:r['reference_n']),('E0',lambda r:'未知' if r['e0_ready'] is None else ('未预热' if not r['e0_ready'] else ('有效' if r['e0_up'] else '无效')))])
 milestone_table=table([x for x in milestones if x['symbol']==x['milestone_symbol']],[('股票',lambda r:r['name']),('日期',lambda r:r['date']),('收盘数',lambda r:r['observations']),('h',lambda r:r['h']),('窗口涨跌',lambda r:pct(r['horizon_return'])),('RS-H1',lambda r:fmt(r['score'])),('E0预热',lambda r:'完成' if r['e0_ready'] else '未完成')])
 unmatched=table([x for x in allrows if x['score'] is None],[('股票',lambda r:r['name']+' '+r['symbol']),('原因',lambda r:r['status']),('旧RS',lambda r:fmt(r['old_rs']))])
 text='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>RS-H1 · 新老股票强弱比较</title><style>
body{margin:0;background:#f4f6f9;color:#253247;font:15px/1.75 -apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif}main{max-width:1180px;margin:auto;padding:30px 24px 65px}h1{font-size:30px;line-height:1.4}h2{font-size:22px}.panel{background:white;border:1px solid #dfe5ee;border-radius:9px;padding:23px;margin:20px 0}.lead{font-size:19px;border-left:4px solid #315d97;padding-left:17px}.muted{color:#63748a}.tag{display:inline-block;background:#edf1f7;padding:3px 10px;border-radius:4px;margin:3px}.note{background:#f0f4f8;padding:12px 16px;border-radius:5px}.formula{font-family:ui-monospace,monospace;background:#f4f6f9;padding:15px;overflow:auto;white-space:pre-wrap}.scroll{overflow:auto}table{border-collapse:collapse;width:100%;white-space:nowrap;font-size:13px}th,td{padding:9px 12px;border-bottom:1px solid #dfe5ee;text-align:right}th:first-child,td:first-child{text-align:left}th{background:#edf2f8}img{display:block;max-width:100%;height:auto}a{color:#315d97}.links a{display:inline-block;margin:6px 16px 6px 0}summary{cursor:pointer;font-weight:600}@media(max-width:700px){main{padding:20px 13px}.panel{padding:15px}h1{font-size:25px}}
</style><main><div class="muted">TRADINGALARM · RS DESIGN · 2026-10-25</div><h1>RS-H1：给新老股票一把可解释的比较尺</h1><div><span class="tag">最低6个真实收盘</span><span class="tag">一个候选，结果后修订0</span><span class="tag">E0未改 · 无换仓 · 账户0</span></div>
<section class="panel"><p class="lead">股票历史不足一年也可以评分。新股有多少可用历史，参照股票就同样只看多少历史，再把相对位置映射到0—100。</p><p>这次解决的是“评分可用与比较口径”，没有证明收益改善。高RS不是买入信号，也不是上涨概率。量价趋势判断继续由原E0承担；RS-H1是价格排序原型。</p><p class="note">重要边界：冻结E0在本例新股第65个有效收盘才完成预热。RS第6个收盘即可用，不代表本轮可以在第6天开仓。若要参与更早阶段，须另立E0启动研究，不能在这里静默改动。</p></section>
<section class="panel"><h2>公式和最少数据</h2><p>h为从首个有效源收盘至今天的市场交易日间隔，最多252；最低6个真实有效收盘、h≥5。首日发行价跳涨不计入。四个区段仍用0.4/0.2/0.2/0.2权重。b<sub>j</sub>=min(63j,h)，只计算非空区段：</p><div class="formula">Mᵢ(t;h) = Σ wⱼ × [Pᵢ(t−bⱼ₋₁) / Pᵢ(t−bⱼ) − 1]
RS-H1ᵢ = 100 × (参照M更低的数量 + 0.5×相同数量) / 有效参照数量N</div><p>M不是跨年龄直接比较的最终分数。例如45日新股只与其他股票的45日M比较；有252日历史的老股与其他股票的252日M比较。空区段不伪造收益、不年化、不重新分配权重；所有参照和目标使用相同h，所以区段覆盖口径一致。</p><p>参照固定为上一轮当前市值合格的1709只A股，与E0状态或是否实际买入无关；同一h的源锚点缺失者单独缺席。N少于20则不评分并说明原因。20是技术下限，不是统计可靠性保证。</p><p>0—100表示在对应历史长度下的相对位置。不同长度的分数有共同描述尺度，但稳定性不相同；本版不额外压低新股分数，短历史噪声和IPO波动风险必须保留。成熟股在日线连续时的M与旧RS原始公式一致；当前市场日历和旧有效观察日计时的差异明确披露。</p></section>
<section class="panel"><h2>统一日期的本地例子：2026-10-22</h2>'''+exampletable+'''<p class="muted">旧RS原始值以百分数展示，是加权区段收益，不是分位，也不能直接与RS-H1数值相减。窗口涨跌是各自h内涨跌，时长不同，不冒充同一持有收益。</p><img src="figures/snapshot.png" alt="八只新老股票RS-H1及历史长度"><p>蘅东光原RS为空，RS-H1为97.20；杰理科技上市后走弱，只有1.09。新股身份不加分。中科仪虽E0有效，相对强弱仅40.52；有趋势状态与强势排名是两件事。</p><p class="note">德明利RS-H1为87.97，但近63日涨跌约−36.25%。高分仍含较早季度的强势，不代表最近一季度强。这里保留原四段权重的滞后代价，没有据此追加过滤器、改E0或换仓。</p></section>
<section class="panel"><h2>新股早期到后续：不是只挑涨得好的时点</h2>'''+milestone_table+'''<p>里程碑事前固定为第6/22/64/127/253个实际收盘，数据尚未走到的时点不推算。中科仪第6个收盘RS高达99.85，之后走弱，说明很早的高分不保证后续持续；第64个收盘窗口已下跌约4.29%，仍能相对领先同期较弱股票。</p><img src="figures/new-price-score.png" alt="三只新股因果复权价格与逐日RS-H1"><p class="muted">价格为冻结因果复权坐标。虚线只标记已有E0预热完成，未画任何模拟账户或新增交易。</p></section>
<section class="panel"><h2>老股截短：历史长度改变了我们回答的问题</h2><img src="figures/truncations.png" alt="同一老股在不同可见历史长度下的分数"><p>例如德明利仅给63日数据时约3.17分，给满252日后约87.97分。这个差异说明不同期限的强势不能当成同一预测结论；长度匹配解决比较单位，不能让较短数据凭空拥有长趋势信息。人为截短仅作诊断，不声称老股真变成新股。</p><details><summary>查看五只老股完整价格与新旧分位轨迹</summary><img src="figures/old-price-score.png" alt="五只老股价格和新旧相对评分"></details></section>
<section class="panel"><h2>覆盖、缺口与核验</h2><p>1709只参照池中：RS-H1可评1702只，旧RS可评1648只；新增60只旧RS未知股票，同时6只旧RS可用股票因统一日历锚点不全被暂留未知，另1只当日无新报价。净新增覆盖54，不把未知强行填分。</p>'''+unmatched+'''<p>独立公式/分位重算、原始RS连续报价身份、价格单位缩放、同路径同分、缺失候选隔离、分段边界与真实未来截断均完成，明细可下载。全部数据仍为当前存续、当前市值/行业快照的历史开发研究，存在选样偏差和既有权益代理限制；无账户验证。</p><details><summary>评分前原始量价图检</summary><img src="figures/raw-new.png" alt="新股原始量价"><img src="figures/raw-old.png" alt="老股原始量价"></details></section>
<section class="panel"><h2>来源与下一边界</h2><p><a href="https://www.oneilglobaladvisors.com/documents/FG/oneil/research/605570_OCM_Relative_Strength_Rating-OGA.pdf">O’Neil公开研究</a>允许一年以内股票用最早可得价格、少于5个交易日不评级；它没有公开本版同长度校准公式。<a href="https://www.msci.com/indexes/documents/methodology/2_MSCI_Momentum_Indexes_Methodology_20250417.pdf">MSCI 2025-04方法</a>使用6/12月动量，缺6月不纳入。RS-H1是本项目独立设计，不认领任何专有公式还原或这些研究的收益结论。</p><p>本轮到设计/示例收口；E0/R/R1保持、换仓ROT-01待后续、本次不运行买卖执行或账户回测。候选的收益价值、初始试错代价及完整选股效果尚未验证。</p><div class="links"><a href="downloads/PROTOCOL.md">完整协议</a><a href="downloads/examples.csv">示例逐项计算</a><a href="downloads/latest-all.csv">1709股评分及未知</a><a href="downloads/milestones.csv">固定早期里程碑</a><a href="downloads/artifical-truncations.csv">截短对照</a><a href="downloads/verification.json">技术核验</a></div></section><p class="muted">生成：'''+now()+''' · 单候选设计与局部机制展示，未进行账户经济验证。</p></main></html>'''
 text=text.replace('artifical-truncations','artificial-truncations')
 (out/'index.html').write_text(text)
 write(out/'provenance.json',{'recorded_at':now(),'source_summary_sha256':sha(HERE/'results/summary.json'),'protocol_sha256':sha(HERE/'PROTOCOL.md'),
  'verification_sha256':sha(HERE/'audit/verification.json'),'html_sha256':sha(out/'index.html'),'report_code_sha256':sha(__file__),'accounts_run':0})
 print({'report':str(out/'index.html'),'figures':len(list(figdir.glob('*.png'))),'accounts_run':0},flush=True)

if __name__=='__main__':main()
