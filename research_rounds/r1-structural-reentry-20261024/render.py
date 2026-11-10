"""Post-result presentation only. No signal generation or account engine calls."""
from pathlib import Path
import json, math
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
from matplotlib.ticker import PercentFormatter
from matplotlib.colors import TwoSlopeNorm

ROOT=Path(__file__).resolve().parent
PARENT=ROOT.parent/'strategy-switching-20261024'
INPUT=ROOT.parent/'market-regimes-exit-20261024/inputs'
OUT=ROOT/'results/v0'
CHART=ROOT/'charts'; CHART.mkdir(exist_ok=True)
SERIES=ROOT/'series'; SERIES.mkdir(exist_ok=True)
FONT=FontProperties(fname='/System/Library/Fonts/Supplemental/Arial Unicode.ttf')
plt.rcParams.update({'font.family':FONT.get_name(),'axes.unicode_minus':False,'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'axes.grid':True,'grid.alpha':.18,'figure.facecolor':'#ffffff'})
COLORS={'E0':'#2866ad','R':'#087e75','R1':'#d97732','E2':'#9569bd','HOLD':'#9a9a9a','HALF_E0':'#70869c'}
NAMES={'E0':'E0 原结构持有','R':'R 敏感退出／整段重建','R1':'R1 结构内恢复','E2':'E2 宽松重试对照','HOLD':'被动持有','HALF_E0':'初始半 E0＋半现金'}
CASES=json.loads((ROOT/'cases.json').read_text())
S=pd.read_csv(OUT/'comparison.csv')
REF=pd.read_csv(OUT/'cash-reference.csv')
T=pd.read_csv(OUT/'R1-trades-with-provenance.csv')
SCENARIOS={'base':'基础：每边费用5bp＋滑点5bp','cost2':'成本加倍：每边费用10bp＋滑点10bp','delay1':'延迟：第二个后续观察日开盘'}
def ledger(c,p,sc):
    if p=='HALF_E0':return pd.read_parquet(OUT/'cash-reference'/f'{c}__{sc}.parquet')
    path=OUT if p=='R1' else PARENT/'results/v0'
    return pd.read_parquet(path/'accounts'/f'{c}__{p}__{sc}/ledger.parquet')
def records(df):return json.loads(df.to_json(orient='records',force_ascii=False))
def pct(x):return f'{x*100:+.2f}%'
def pair(a):return f"{a.net_return*100:+.2f}% / {a.max_drawdown*100:.2f}%"
def title(c):return f"{c['name']} · {c['type']} · {c['start']}—{c['end']}"

# All paths are saved, including stressed scenarios and reference controls.
for c in CASES:
    for sc in SCENARIOS:
        paths={}; dates=None
        for p in COLORS:
            l=ledger(c['id'],p,sc)
            dates=l.index.strftime('%Y-%m-%d').tolist()
            paths[p]={'nav':l.nav.round(9).tolist(),'drawdown':l.drawdown.round(9).tolist()}
        d=pd.read_parquet(INPUT/f"{c['symbol']}.parquet").loc[dates[0]:dates[-1]]
        (SERIES/f"{c['id']}__{sc}.json").write_text(json.dumps({'dates':dates,'close':d.close.round(7).tolist(),'volume':d.volume.round(2).tolist(),'paths':paths},ensure_ascii=False,separators=(',',':')))
    d=pd.read_parquet(INPUT/f"{c['symbol']}.parquet").loc[c['start']:c['end']]
    fig,axs=plt.subplots(3,1,figsize=(13.6,8.2),sharex=True,gridspec_kw={'height_ratios':[1.05,1.2,.7]})
    axs[0].plot(d.index,d.close,color='#454b50',lw=1.2)
    axs[0].set_ylabel('研究价格')
    for p in ['E0','R','R1']:
        l=ledger(c['id'],p,'base');st=S[(S.case==c['id'])&(S.scenario=='base')&(S.policy==p)].iloc[0]
        axs[1].plot(l.index,l.nav,color=COLORS[p],lw=1.5,label=f'{p}  收益 {pct(st.net_return)} / 回撤 {st.max_drawdown*100:.2f}%')
        axs[2].plot(l.index,l.drawdown,color=COLORS[p],lw=1.1)
    axs[1].axhline(1,color='#999',lw=.7);axs[1].set_ylabel('净值（初始1）');axs[1].legend(loc='upper left',fontsize=9)
    axs[2].set_ylabel('日收盘回撤');axs[2].yaxis.set_major_formatter(PercentFormatter(1));axs[2].set_ylim(top=.02)
    fig.suptitle(title(c)+'\n基础费用；本图为完整原账户路径，期末清算另列',fontsize=12)
    fig.tight_layout(rect=[0,0,1,.94]);fig.savefig(CHART/f"{c['id']}.png",dpi=145);plt.close(fig)

# Main fixed suite matrix, full 11, without choosing only successful cases.
base=S[S.scenario=='base'];main=CASES[:11]
v=np.array([[float(base[(base.case==c['id'])&(base.policy==p)].net_return.iloc[0])*100 for p in ['E0','R','R1']] for c in main])
fig,ax=plt.subplots(figsize=(11.5,7.8));ax.imshow(v,cmap='RdYlGn',norm=TwoSlopeNorm(vmin=-40,vcenter=0,vmax=170),aspect='auto',alpha=.6)
ax.set_xticks(range(3),['E0 原结构持有','R 敏感退出／整段重建','R1 结构内恢复'])
ax.set_yticks(range(11),[f"{c['name']} · {c['type']}\n{c['start'][:4]}—{c['end']}" for c in main])
for i,c in enumerate(main):
    for j,p in enumerate(['E0','R','R1']):
        st=base[(base.case==c['id'])&(base.policy==p)].iloc[0]
        ax.text(j,i,f'{st.net_return*100:+.2f}%\n回撤 {st.max_drawdown*100:.2f}%',ha='center',va='center',fontsize=10,color='#15232b')
ax.grid(False);ax.xaxis.tick_top();ax.tick_params(length=0,pad=8);ax.set_title('固定 11 场景：净收益 / 最大回撤\n每个账户初始资金1，场景重叠，不是投资组合',pad=18,fontsize=13)
fig.tight_layout();fig.savefig(CHART/'fixed-suite.png',dpi=160);plt.close(fig)

def focus(case,a,b,name,heading,annotate=True):
    c=next(x for x in CASES if x['id']==case);d=pd.read_parquet(INPUT/f"{c['symbol']}.parquet").loc[a:b]
    fig,axs=plt.subplots(4,1,figsize=(14.3,10),sharex=True,gridspec_kw={'height_ratios':[2.2,.6,.65,1.1]})
    ax=axs[0];ax.plot(d.index,d.close,c='#40484e',lw=1.5,label='研究收盘价')
    tt=T[(T.case==case)&(T.scenario=='base')&(T.entry_date<=b)&(T.exit_date>=a)]
    for _,t in tt.iterrows():
        en=pd.Timestamp(t.entry_date);ex=pd.Timestamp(t.exit_date);restore=t.qualification=='higher_trough_reentry'
        ax.axvspan(max(en,d.index[0]),min(ex,d.index[-1]),alpha=.10,color=COLORS['R1'] if restore else '#8898a8')
        if en in d.index:
            ax.scatter(en,d.loc[en,'close'],marker='^',s=48,c=COLORS['R1'] if restore else '#788b9e',zorder=4)
        if ex in d.index:ax.scatter(ex,d.loc[ex,'close'],marker='v',s=44,c='#b84545',zorder=4)
        if restore and annotate and en in d.index:
            i=int(np.searchsorted(d.index.values,en.to_datetime64()));y=.95 if i%3==0 else (.82 if i%3==1 else .69)
            ax.annotate(f"{t.entry_date[5:]} → {t.exit_date[5:]}\n{pct(t.net_return)}",xy=(en,d.loc[en,'close']),xytext=(en,y),textcoords=('data','axes fraction'),fontsize=8,ha='center',va='top',bbox=dict(boxstyle='round,pad=.25',fc='white',ec='#ddd',alpha=.9),arrowprops=dict(arrowstyle='-',color='#b4b4b4',lw=.6))
    ax.set_ylabel('研究收盘价');ax.legend(loc='upper left',fontsize=9)
    axs[1].bar(d.index,d.volume,color='#afb8be',width=1.4);axs[1].set_ylabel('成交量')
    for j,p in enumerate(['E0','R','R1']):
        l=ledger(case,p,'base').loc[a:b]
        axs[2].fill_between(l.index,j-.35,j+.35,where=l.quantity.gt(0),color=COLORS[p],step='post',alpha=.8)
        axs[3].plot(l.index,l.nav,color=COLORS[p],lw=1.4,label=p)
    axs[2].set_yticks([0,1,2],['E0','R','R1']);axs[2].set_ylim(2.5,-.5);axs[2].grid(False);axs[2].set_ylabel('实际持仓')
    axs[3].set_ylabel('原场景账户净值');axs[3].legend(loc='upper left',ncol=3)
    fig.suptitle(heading+'\n橙色阴影＝恢复交易；灰色＝原周期入场；三角为实际成交日。净值沿用原账户，不在放大窗重置。',fontsize=12)
    fig.tight_layout(rect=[0,0,1,.94]);fig.savefig(CHART/f'{name}.png',dpi=155);plt.close(fig)

focus('continuous_USHJ518880','2024-07-15','2025-11-07','gold-cycle','黄金长趋势：恢复了参与，但连续大趋势仍被短波幅出口切成多笔')
focus('semi_ytd26','2026-01-01','2026-10-23','semi-ytd','今年半导体：新增两笔恢复都亏损，R 的风险优势被部分消耗')
focus('bull_semi25_26h1','2025-04-01','2026-06-30','semi-bull','半导体牛市：一次恢复赚18.43%，随后两次亏损抵消大部分增量')

# Save exact delayed-execution exceptions and the cancelled gold order as evidence.
exceptions={
 'factor_identity':{'unchanged_cases':53,'total_cases':54,'exception':'continuous_USHJ510300 / delay1','reason':'A recovery position was still waiting for its latched sell when the next original E0 cycle was recognized. The new buy could only be submitted after that sell; original-channel entries were one observation later than R. No forced matching or decomposition identity is claimed.',
 'entry_pairs':[{'R':'2023-05-17','R1':'2023-05-18','exit':'2023-05-25'},{'R':'2025-09-09','R1':'2025-09-10','exit':'2025-10-16'}]},
 'gold_cancel':{'recognition':'2021-06-11','cancel':'2021-06-15','action':'cancel_gap','reason':'Actual open was at or below the previously known support; the unchanged engine correctly cancelled the recovery buy. There were 30 theoretical restoration signals but only 29 actual restoration trades in this window.'},
 'review_display_note':'All18 raw PV/state sheets and four focused windows were inspected before account admission. A cosmetic focused-chart change used full-history relative-volume baselines for the first21 plotted observations; prior images remain archived, signal inputs and rules were unaffected.'}
(OUT/'execution-exceptions.json').write_text(json.dumps(exceptions,ensure_ascii=False,indent=2))

data={'cases':CASES,'scenarios':SCENARIOS,'policies':NAMES,'colors':COLORS,'summary':records(S),'reference':records(REF),'trades':records(T),'audit':json.loads((OUT/'audit.json').read_text()),'mechanism':json.loads((OUT/'mechanism.json').read_text()),'aggregate':records(pd.read_csv(OUT/'descriptive-summary.csv'))}
(ROOT/'report-data.json').write_text(json.dumps(data,ensure_ascii=False,separators=(',',':'),allow_nan=False))

def md_table(cases):
    lines=['| 场景与时间 | E0 收益 / 回撤 | R 收益 / 回撤 | R1 收益 / 回撤 | R1交易 / 自然胜率 |','|---|---:|---:|---:|---:|']
    for c in cases:
        g=base[base.case==c['id']].set_index('policy');r=g.loc['R1']
        lines.append(f"| {c['name']} · {c['type']}<br>{c['start']}—{c['end']} | {pair(g.loc['E0'])} | {pair(g.loc['R'])} | {pair(r)} | {int(r.trades)} / {r.natural_win_rate*100:.1f}% |")
    return '\n'.join(lines)

readme='''# R1：结构内恢复｜固定多场景回测

2026-10-24。完整标识 **R1-IR-20261024**。用户授权给上一轮提出的候选命名、设计并完整运行既定多场景。旧算法与所有失败结果保留。报告：[本机8780](http://127.0.0.1:8780/)。

本轮结论：**恢复通道确实补回了部分趋势，但不支持将R1晋升为R的默认升级。** 主要问题是：更高回调低点仍会出现在下跌反弹和弱震荡中；同时R原来的2波幅出口继续切碎长趋势。这里得到的是一次有限开发检验的否定/有条件结果，不是参数尚未调好的借口。

## 算法与执行

R1保留原R的首次开仓与退出，仅增加恢复资格。R的独立影子E0用于判断原结构是否还活着，策略空仓不会让影子E0停止更新。

1. **首次开仓**：与R相同，影子E0新建趋势结构；起始窗口若继承前日有效结构，按同一预设初始规则入场。
2. **卖出**：E0失效或收盘跌至更新后的结构支持，结构退出；否则收盘跌至单向2波幅保护线，敏感退出。峰值从本次入场计算，波幅为滞后14观察日的相对真实波幅算术均值。精确对数公式见[事前协议](PROTOCOL.md)，不是额外止盈规则。
3. **退出后的记忆**：只有敏感退出且E0仍有效，才记录退出信号日和当日结构支持。结构失效立即清空，保留原风险否决。
4. **恢复开仓**：其后原量价算法新确认向上事件；该事件的回调低点日须严格晚于退出信号日、早于确认日，低点须严格高于记录的支持。所有依据在确认收盘时可得，不能回填到低点买入。
5. **重新计时**：恢复后重新计算本次峰值和波幅线，记忆用一次即清除。再次退出使用新记忆。新E0周期仍可按原通道开仓，同日禁止卖出又重入。

量不是事后标签：原事件用归一化价格位移乘摆动以来量活跃度的平方根，影响是否和何时确认。局部去量消融固定E0和波幅线，仅替换恢复确认事件，18重叠窗中改变92个恢复信号日、262个状态日；这只是机制检验，没有新增价格版经济账户，不能说明量提高收益。

**条件的实际选择力需要澄清**：原E0持续有效时，“低点高于退出时支持”大多已由结构存续保证；本轮没有只因该项而被拒绝的真实等待事件。新增的有效约束主要是“退出后新低点＋新的量价确认”，不能把它包装成额外的趋势质量评分。严格晚于退出日还会排除退出当天即为低点的V形恢复；这是事前设计的取舍，结果后未放松。

收盘信号、下一观察日开盘执行；买入跳空跌破已知支持取消，卖单锁定；归一初始资金1、全额多头或现金、分数份额、无杠杆、不每日再平衡。基础每边费用5bp＋不利滑点5bp；压力分别为二者加倍、额外延迟一个观察日。末日收盘清算单列为行政清算，不是算法卖顶。现金利息0。港股未还原真实税费、手数和汇率，均为统一价格代理研究。

## 完整范围与基础结果

新增 **54个R1经济账户＝18窗×3执行情景**。读取原E0/R/E2/被动持有 **216个已审核账户**，不重跑、不改动。另有事前固定的 **54条初始半E0＋半现金机械参考路径**，没有扫分仓比例；比较表270行、含参考共324条展示路径。没有新增行情、微信或Key操作。

固定11主场景包括两熊、两偏强、两偏弱、两高振幅中性、一低振幅、今年半导体和已研究的半导体牛市；另7个2021—2026连续窗检验累计试错。半导体以512480代表板块，2026今年止10月23日，24日是周六。连续窗统一止10月16日，保持前轮口径，未补到23日。所有都是已看历史的开发检验；场景重叠，不当作独立样本或未来胜率。

下表每格为“**净收益 / 日收盘最大回撤**”，回撤包括初始资金1。自然胜率排除期末行政清算。

'''+md_table(CASES[:11])+'''

### 七个连续区间

'''+md_table(CASES[11:])+'''

## 收益变化来自哪里

**黄金：恢复不等于留住长趋势。** 2024-08-20至2025-10-23，原E0单笔净收益62.59%。原R在2024-09-05提前退出亏0.72%；R1利用10月11日当时确认、低点日为10月9日的量价事件，在10月14日实际恢复。原E0周期内共8笔、其中7次恢复，逐笔复利15.52%，最大单笔仅7.30%，没有30%尾部交易。它修复了R长时间禁入，却仍被敏感出口切碎。

2024-12-11、2025-03-14、2025-09-22的向上确认，因为低点发生在前一次退出信号当天，被“严格晚于”限制排除。尤其3月恢复缺口是可识别的代价，但本轮不能事后把这几个日期单独放行。黄金整个2021—2026连续账户从R的−15.61%改善到R1的+0.13%，回撤由16.59%升到24.86%；E0仍为+83.15%/34.79%，被动119.06%/30.52%。R1有43笔交易，费用与滑点各消耗初始资金约4.33%，零笔30%尾部交易。固定半E0＋半现金参考为41.58%/25.47%，不能只与低暴露R相比就称改善成功。

**今年半导体：两次误恢复直接解释收益下降。** R原6笔入场的日期、价格和单笔回报均未变；新增2月26日—3月4日−8.12%、9月21日—9月29日−7.50%两笔恢复。因此1.54822×(1−0.08124)×(1−0.07505)≈1.31569，净收益54.82%降为31.57%，回撤21.52%升到27.41%。即使低点高于旧支持、原结构尚未死，也不能证明不是下跌中的反弹。

**半导体牛市：补回一段，又交回大部分。** 新增2025年6月26日—9月5日恢复赚18.43%，但10月27日—11月4日亏7.04%、2026年2月26日—3月4日亏8.12%，三笔复利只给R账户增加约1.15%的净值乘数，收益106.48%→108.86%，回撤12.91%→21.98%。E0为162.01%/16.59%；期末清算的上涨交易不叫策略及时退出。

**也保留正例。** 2021半导体偏强震荡，R1为28.63%/20.47%，R为0.04%/18.15%；2023中电为13.80%/7.75%，R为−1.14%/5.72%。连续半导体R1为137.43%/31.15%，收益高于R的105.02%/29.15%和E0的108.71%/40.62%。这里新增参与有价值，但未带来相对R更低的回撤。

**普通交易损耗仍是关键。** 基础11场景R1收益高于R仅4/11、回撤降低0/11；7连续窗为3/7、0/7。11场景等权“案例均值”收益15.88%对R15.93%，平均最大回撤20.00%对15.86%；连续7窗为8.36%对13.55%、平均回撤41.74%对34.17%。这些是描述统计，不能当成可投资组合收益，也不是独立检验的胜率。连续窗尾部净贡献的案例均值约34.74%（R30.71%），普通交易净贡献却恶化到−26.38%（R−17.17%），新增尾部不足以覆盖多出来的普通损耗。尾部以单笔净收益≥30%分类，只是评价线，不是止盈线。

R1在4个固定场景（半导体2022、半导体2021、恒生科技2023、半导体2023）和宽松重试E2的基础结果完全相同，说明这套恢复规则在这些行情中未提供额外的质量区分。137笔基础恢复交易（含场景重叠）仅49笔盈利，不能把“更高低点”视为稳健买点。

## 成本和延迟

报告可切换全部54账户的成本/延迟结果，不能用最有利执行方式替换事前主结果。

| 场景与R1结果 | 基础 收益/回撤 | 成本加倍 | 额外延迟一观察日 |
|---|---:|---:|---:|
| 连续黄金 | +0.13% / 24.86% | −8.12% / 25.61% | +23.41% / 18.04% |
| 今年半导体 | +31.57% / 27.41% | +29.48% / 27.92% | +30.51% / 31.74% |
| 半导体牛市 | +108.86% / 21.98% | +104.72% / 22.29% | +130.45% / 20.94% |

黄金延迟一日反而改善很大，说明密集恢复/敏感退出的成交路径依赖，不能理解为“以后故意晚买一天就可稳定提高收益”。固定场景成本加倍时R1案例均值13.93%弱于R14.52%；连续窗R1−1.04%弱于R6.80%。没有稳定的跨场景优势。

## 审核与复现

事前54项完整重算前缀恒等、18窗禁用恢复与原R逐日恒等、8个有经济意义的边界测试通过。所有18原始量价/状态图及4重点窗在账户准入前复查。重点图前21点相对量显示改为完整历史基准是展示修复，旧4图保存，信号从未使用缩短基准。然后冻结1034个代码/输入/状态/旧对照文件，仅运行一次54账户，结果后规则修订0。

新增账户2498笔成交由原始开收盘、费用、现金、数量逐日独立重放；最大净值误差1.03e−14以内；54账户全通过。实际409笔恢复买入（含三情景及重叠窗）逐笔核对退出信号日<低点日<确认日<成交日。216旧对照逐项一致，54现金参考恒等，1034冻结源未变。

53/54组的原R交易日期/回报完全不变，R1净值可严格分解为R净值乘新增恢复交易回报乘积。唯一例外为连续沪深300的延迟情景：恢复持仓的锁定卖单跨过下一E0新周期，使2023-05-17和2025-09-09原通道买入分别推迟至18日、10日；不强行匹配。黄金2021-06-11理论恢复在15日因开盘低于已知支持取消，故30个理论恢复信号对应29笔实际恢复，不能混用信号和成交数。详见[执行例外](results/v0/execution-exceptions.json)。

证据：[冻结协议](PROTOCOL.md)、[冻结哈希](freeze.json)、[图检准入](review-before-accounts.json)、[前检](preflight.json)、[核账](results/v0/audit.json)、[全比较270行](results/v0/comparison.csv)、[新54账户汇总](results/v0/R1-summary.csv)、[逐笔恢复来源](results/v0/R1-trades-with-provenance.csv)、[配对差异](results/v0/paired-deltas.csv)、[费用/延迟逐组分解](results/v0/recovery-factor-decomposition.csv)、[案例描述统计](results/v0/descriptive-summary.csv)、[半E0/半现金参考](results/v0/cash-reference.csv)。

复现时先核哈希，不重新运行run.py覆盖账户。prepare/preflight/plot_review/freeze/run/audit构成原一次性流程；analyze.py、render.py只读取结果生成分析/展示。本专项的54新账户与旧486等历史轮次分开计数，不重置全项目停止计数。

## 裁决

保留E0作为长趋势基准、R作为较低参与的风险对照；R1作为已经测完的“允许结构内恢复”机制证据归档，**不替换默认策略**。缺口已较清楚：R的退出与恢复需要共同匹配趋势尺度，仅放开恢复无法同时避免反弹误入、密集止损和丢失长赢家。这不支持立刻继续叠加过滤器、放松低点日期或扫波幅倍数。本轮完成即收口，不自动追加模型或账户；任何后续研究需另定有限问题。没有实盘授权，也不把本轮ETF/7资产代理诊断冒充板块→个股全市场策略验证。
'''
(ROOT/'README.md').write_text(readme)
print('Rendered18 complete path images,3 focus images,1 matrix,54 series, report data and README',flush=True)
