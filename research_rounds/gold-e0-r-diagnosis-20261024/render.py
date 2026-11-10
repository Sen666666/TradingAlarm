from pathlib import Path
import json,html
import pandas as pd,numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
font_manager.fontManager.addfont('/System/Library/Fonts/Supplemental/Arial Unicode.ttf');plt.rcParams['font.family']='Arial Unicode MS';plt.rcParams['axes.unicode_minus']=False
R=Path(__file__).resolve().parent;P=R.parent/'strategy-switching-20261024';O=R/'results/v0';G='continuous_USHJ518880';src=pd.read_csv(P/'results/v0/summary.csv');blend=pd.read_csv(O/'blend-summary.csv');cash=pd.read_csv(O/'cash-reference-summary.csv');pair=pd.read_csv(R/'evidence/paired-cycles.csv');ignored=pd.read_csv(R/'evidence/ignored-up-events.csv');years=pd.read_csv(O/'gold-continuous-years.csv');attr=pd.read_csv(O/'gold-pnl-attribution.csv');base=src[(src.case==G)&(src.scenario=='base')].set_index('policy')
fig,axs=plt.subplots(2,1,figsize=(14,7.8),sharex=True,gridspec_kw={'height_ratios':[2,1]});lines={}
for p,color in [('E0','#225c91'),('R','#e27a23')]:lines[p]=(pd.read_parquet(P/'results/v0/accounts'/f'{G}__{p}__base/ledger.parquet'),color)
lines['各半独立分仓']=(pd.read_parquet(O/'blend-ledgers'/f'{G}__base.parquet'),'#218574');lines['半数E0＋半数现金']=(pd.read_parquet(O/'gold-half-E0-cash__base.parquet'),'#8674aa')
for name,(l,color) in lines.items():
 axs[0].plot(l.index,l.nav,color=color,lw=1.45,label=name+f' 收益{l.nav.iloc[-1]-1:+.2%} / 回撤{-l.drawdown.min():.2%}');axs[1].plot(l.index,100*l.drawdown,color=color,lw=1)
axs[0].set_title('直接分仓的代价：黄金中，R并未优于保留现金\n初始资金等分，独立运行、不互相补钱、不每日再平衡；全部复用原有成交和成本',fontsize=14,pad=12);axs[0].set_ylabel('净值（起始=1）');axs[0].legend(fontsize=10,ncol=2,loc='upper left');axs[0].axhline(1,color='gray',ls=':',lw=.7);axs[1].set_ylabel('最大历史峰值以来回撤 %')
for ax in axs:ax.grid(alpha=.15)
fig.tight_layout();fig.savefig(R/'charts/direct-blend.png',dpi=145);plt.close(fig)
# Tables reuse exact frozen account fields, prices and executed dates.
def pct(v,sign=False):return f'{v*100:+.2f}%' if sign else f'{v*100:.2f}%'
def tbl(frame):return frame.to_html(index=False,border=0,escape=True,classes='data')
main=pd.DataFrame([{'方案':p,'净收益':pct(base.loc[p,'net_return'],True),'最大回撤':pct(base.loc[p,'max_drawdown']),'交易数':int(base.loc[p,'trades']),'有暴露时间':pct(base.loc[p,'exposure_fraction'])} for p in ['E0','R','HOLD']])
fuse=pd.DataFrame([{'方案':'E0','净收益':pct(base.loc['E0','net_return'],True),'最大回撤':pct(base.loc['E0','max_drawdown'])},{'方案':'R','净收益':pct(base.loc['R','net_return'],True),'最大回撤':pct(base.loc['R','max_drawdown'])},{'方案':'50% E0＋50% R','净收益':pct(blend.query('case==@G and scenario=="base"').iloc[0].net_return,True),'最大回撤':pct(blend.query('case==@G and scenario=="base"').iloc[0].max_drawdown)},{'方案':'50% E0＋50%现金（减仓基准）','净收益':pct(cash.query('scenario=="base"').iloc[0].net_return,True),'最大回撤':pct(cash.query('scenario=="base"').iloc[0].max_drawdown)}])
key=pair[pair.entry.isin(['2022-07-27','2023-10-16','2024-08-20','2026-03-25'])].copy();key=key[['entry','E0_exit','E0_return','R_exit','R_return','waiting_to_next_entry_calendar_days']];key.columns=['共同买入日','E0卖出日','E0该笔净收益','R卖出日','R该笔净收益','R到下次入场等待自然日']
for c in ['E0该笔净收益','R该笔净收益']:key[c]=key[c].map(lambda x:pct(x,True))
key['R到下次入场等待自然日']=key['R到下次入场等待自然日'].astype(int)
allpairs=pair[['entry','E0_exit','E0_return','R_exit','R_return','signal_atr_pct','signal_q','log_gap_share']].copy();allpairs.columns=['共同入场','E0退出','E0净收益','R退出','R净收益','R退出信号前14日波幅%','信号日相对量','对数终值差贡献']
for c in ['E0净收益','R净收益','对数终值差贡献']:allpairs[c]=allpairs[c].map(lambda x:pct(x,True))
for c in ['R退出信号前14日波幅%','信号日相对量']:allpairs[c]=allpairs[c].map(lambda x:f'{x:.3f}')
ignoredkey=ignored[ignored.original_entry=='2024-08-20'][['recognized','pivot_date','close','q','prior_floor','updated_floor','R_target','E0_new_entry']].copy();ignoredkey.columns=['实际确认日','被确认低点日期','当日收盘','当日相对量','旧支持','新支持','R资格','E0是否新入场'];ignoredkey['当日相对量']=ignoredkey['当日相对量'].round(3)
annual=years.pivot(index='year',columns='policy',values='net_return').reset_index();annual.columns=['年份','E0连续账户年度变化','R连续账户年度变化']
for c in annual.columns[1:]:annual[c]=annual[c].map(lambda x:pct(x,True))
allfusion=blend[blend.scenario=='base'][['case','name','start','end','net_return','max_drawdown']].copy();allfusion.columns=['场景ID','标的','开始','结束','各半净收益','各半最大回撤']
for c in ['各半净收益','各半最大回撤']:allfusion[c]=allfusion[c].map(lambda x:pct(x,True) if c=='各半净收益' else pct(x))
# Exact facts that the prose uses.
checks=json.loads((R/'input-checks.json').read_text());grossgap=float(attr.set_index('policy').loc['E0','price_pnl']-attr.set_index('policy').loc['R','price_pnl']);costgap=float(attr.set_index('policy').loc['E0',['fees','slippage']].sum()-attr.set_index('policy').loc['R',['fees','slippage']].sum())
assert abs(grossgap-costgap-(base.loc['E0','net_return']-base.loc['R','net_return']))<1e-12
(R/'conclusions.json').write_text(json.dumps({'gold_E0':base.loc['E0'].to_dict(),'gold_R':base.loc['R'].to_dict(),'paired_entries_identical':14,'R_all_exit_reasons':'atr2','gross_price_pnl_gap':grossgap,'cost_gap_E0_minus_R':costgap,'net_profit_gap':float(base.loc['E0','net_return']-base.loc['R','net_return']),'key_2024_reentry_evidence_ignored':ignoredkey.to_dict('records'),'signal_rule_changes':0,'new_signal_accounts':0,'fixed_blend_paths':54,'additional_cash_reference_paths':3,'R_optimization':'fresh higher-trough PV up event while E0 remains valid; design only, not implemented or backtested'},ensure_ascii=False,indent=2,default=str))
body='''<header><div class="eyebrow">TRADINGALARM / 2026-10-24 / E0 × R</div><h1>为什么同样买入黄金，E0赚83%，R却亏16%？</h1><p class="lead">主要差距来自 <b>2倍短期波幅早退＋原结构结束才可重入</b> 的组合。R在长趋势中反复过早离场，又拒绝原结构内部已经出现的新推进证据。</p><span class="badge">14次同日同价入场 · 原算法不改 · 新信号账户0 · 54条固定分仓推导＋3条减仓基准</span></header>
<section><h2>先看这几年黄金ETF走势与实际参与</h2><p>518880，实际2021-01-04—2026-10-16，1400个观察；严格沿用原回测区间。本数据全部价格与原始价相同、复权系数为1。它是黄金ETF，不能当成沪金主连或国际金价。蓝点为E0算法卖出，橙叉为R卖出，三角为相同买入；空心方块是预设末日清算。</p><a href="charts/gold-overview.png"><img src="charts/gold-overview.png" alt="黄金ETF走势、量、两算法暴露与净值"></a>MAIN_TABLE<p class="muted">被动对照也一并保留：本样本E0弱于被动持有，且回撤更大；E0优于R不等于E0已是最优黄金策略。暴露含开盘卖出日。E0共13笔自然退出＋1笔行政清算，R14笔全部自然退出。</p></section>
<section><h2>差距集中在三段持续上行，R并没有买得更差</h2><p>两者全部14次买入同日同价、无跳空取消；R的14次卖出全部由额外波幅条件触发，且全部早于E0。这不是数据源不同，也不是R多交了交易费。E0参与1273天，R仅197天（90.93%对14.07%）。</p>KEY_TABLE<p>最关键的2024-08-20这笔，E0持到2025-10-23，净交易收益62.59%；R于2024-09-05以−0.72%退出，直到2025-11-11才有下一次入场，等待432个自然日。2022—2023和2023—2024又重复了类似错失。</p><p>此前差异也会复利放大：2024年8月同次入场之前，E0资金已为初始的1.291倍，R为0.950倍。按配对交易的对数复利差归因，这一笔解释总差距的63.67%；这不是把单笔收益率直接相加。</p><p>独立按成交重建，E0累计费用＋滑点为初始资金3.72%，R为2.61%；E0反而付得更多。净利润差98.76个百分点主要是价格参与和复利路径，成本差抵消了其中约1.11个百分点。</p></section>
<section><h2>放大2024年：风险退出，被当成了长时间禁入</h2><a href="charts/early-exit-2024.png"><img src="charts/early-exit-2024.png" alt="2024年提前退出和更高低点确认"></a><ol><li>9月4日，收盘5.463，小幅低于R保护线5.473；E0的结构支持仍为5.327。前14日相对真实波幅约0.588%，两倍约1.176%。这是较近的波动边界，触发不等于原上升结构失效。</li><li>当日成交量为常态0.683倍。R新增退出仅使用价格波幅，未要求放量破坏或收复失败；成交量参与的是原E0事件和资格。</li><li>10月11日，E0新向上量价事件确认10月9日低点5.640，支持由5.327抬到5.640；识别日相对量1.356。R仍然空仓，因为E0一直有效，原程序的“新入场”标志为0。</li><li>此后同一结构内多次确认更高低点，R也继续忽略。这里“没有原结构重建”与“没有新的量价推进证据”是两回事。</li></ol><details><summary>同一长结构内，R未用于恢复的真实向上事件</summary>IGNORED_TABLE</details><p class="muted">前14日波幅是代码中的滞后相对真实波幅算术均值，并非Wilder平滑ATR；保护线还包含只升不降的记忆，收盘触发、下一开盘成交。ATR类量度描述波动，不能单独证明趋势反转。<a href="https://www.fidelity.com/learning-center/trading-investing/technical-analysis/technical-indicator-guide/atr">Fidelity原始指标说明</a>用于解释这个概念，具体数值来自本地代码。</p></section>
<section><h2>R的有效反例：2026年确实减少了下跌参与</h2><a href="charts/decline-2026.png"><img src="charts/decline-2026.png" alt="2026年R早退有效的反例"></a><p>同为2026-03-25入场，R于04-27退出获1.44%，E0于06-11结构退出亏11.92%。4月24日R信号的相对量仅0.579，比2024年9月的0.683还低。所以不能简单改成“缩量就不卖”。缩量下行也可能继续；量必须结合结构与后续响应。</p><p>E0的长结构允许给趋势留空间，也会让保护点离现价较远；R较快降低暴露，但可能将整理误判为需要离场。两者的优点和代价在同一资产上都存在。</p></section>
<section><h2>直接融合：固定各半能够折中，但黄金中没有证明增益</h2><p>只推导一个对称方案：初始一半资金运行E0、一半运行R，两袖各自复利，不转钱、不每日再平衡。总净值是原两条净值的各半之和；最大回撤重新按日计算。没有搜索配比，没有新增信号回测。</p>FUSION_TABLE<a href="charts/direct-blend.png"><img src="charts/direct-blend.png" alt="各半融合及等资金减仓基准"></a><p><b>这段黄金里，保留现金比配置R更好：</b>半数E0＋半数现金收益更高、回撤更低。因此“融合后比E0回撤小”并不足以证明R有正贡献。现金参考是融合结果后为区分单纯减仓而追加的明确基准，另记3条路径，不伪称事前已预设。</p><p>在其他已固定场景，各半方案同样有取舍：半导体牛市134.25%/回撤14.13%，今年完整区间39.90%/26.73%。它既没有保住E0的全部牛市收益，也没有取得R今年全部优势。黄金组合最终E0资金占比自然漂至68.46%，不能称每天保持50%股票仓位。</p><details><summary>全部18场景基础成本的固定融合结果</summary>ALL_FUSION</details><p class="muted">54条派生路径覆盖原18窗×3执行情景，3360笔缩放成交独立重放；0个新信号账户。所有历史已看过，只作开发诊断。统一费用、分数份额、流动性和港股执行代理限制继承原研究，不是实盘可执行收益。</p></section>
<section><h2>更值得研究的融合点：保留长结构，允许新证据恢复</h2><p><b>优先提出一个有限问题：保持R的2倍波幅退出不变，只修改重入资格。</b>影子E0仍有效时，如退出之后形成了新的低点，并被新的原量价向上事件确认，且该低点高于退出时记录的结构支持，就允许下一可成交开盘重新参与；原结构失效时仍按原规则处理。</p><p>2024年10月11日已观察到这种证据（10月9日低点5.640，高于旧支持5.327）。它复用E0现有事件，不需要先破坏长趋势，也不要求突破永久历史高点。此时可以产生恢复候选，但并不保证之后能一直持有；原2波幅退出仍可能再次触发。</p><p>这只是设计假说，<b>尚未实现、尚未回测</b>。它比R的整段禁入宽松，也比不加区分地接受所有反弹严格；是否真能区别两者必须由共同反例检验。先固定同一规则，重点同时检查黄金持续推进、半导体牛市恢复、今年半导体亏损重入和熊市，不为黄金单独调宽保护线。</p><p>对E0，保留结构存续和持续跟踪新量价证据的能力；对R，保留风险撤出的能力，但把“本次持仓退出”与“整个市场趋势失效”分开。直接分仓目前只是风险取舍，不升为默认；结构内恢复是更有证据的下一研究问题。</p></section>
<section><h2>证据与完整逐笔</h2><details><summary>14笔同入场对照</summary>ALL_PAIRS<p class="muted">最后一笔E0是预设期末清算；对数贡献可为负（R更好），正贡献合计可超过100%（被负贡献抵消），不可当作简单收益百分点。</p></details><details><summary>连续账户各年度变化</summary>ANNUAL<p class="muted">年度不重置，不额外年末清算；最后2026年10月16日按原协议行政清算。</p></details><p><a href="PROTOCOL.md">事前限定</a> · <a href="README.md">完整说明</a> · <a href="evidence/paired-cycles.csv">14笔配对CSV</a> · <a href="results/v0/blend-summary.csv">54条分仓汇总</a> · <a href="results/v0/cash-reference-summary.csv">3条减仓参考</a> · <a href="results/v0/audit.json">核账</a> · <a href="freeze.json">冻结</a> · <a href="cash-reference-protocol.json">补充对照记录</a> · <a href="http://127.0.0.1:8778/">原完整切换实验</a></p></section><footer>本轮只作E0/R归因、固定分仓推导及优化设计；旧算法、旧486账户、所有失败不变，无下载、微信、实盘或自动追加研究。</footer>'''
for a,b in [('MAIN_TABLE',tbl(main)),('KEY_TABLE',tbl(key)),('IGNORED_TABLE',tbl(ignoredkey)),('FUSION_TABLE',tbl(fuse)),('ALL_FUSION',tbl(allfusion)),('ALL_PAIRS',tbl(allpairs)),('ANNUAL',tbl(annual))]:body=body.replace(a,b)
css='''*{box-sizing:border-box}body{margin:0;background:#f2f5f8;color:#24384a;font:16px/1.85 -apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif}main{max-width:1400px;margin:auto;padding:30px}header{padding:10px 0 20px}h1{font-size:32px;line-height:1.4;margin:10px 0 18px}h2{font-size:23px;line-height:1.5;margin:0 0 18px}p{margin:12px 0}section{padding:28px;background:white;border:1px solid #dbe4ec;border-radius:12px;margin:20px 0}.lead{font-size:20px;max-width:1100px}.eyebrow{font-size:12px;letter-spacing:1px;color:#6a7e8e}.badge{background:#e3f2ed;color:#166653;font-size:13px;border-radius:20px;padding:7px 13px;display:inline-block}img{width:100%;height:auto;display:block;margin:14px auto}a{color:#086d9b}table{font-size:14px;border-collapse:collapse;width:100%;margin:20px 0;white-space:nowrap;display:block;overflow:auto}th,td{padding:10px 15px;border-bottom:1px solid #e4e9ef;text-align:right}th:first-child,td:first-child{text-align:left}th{background:#f1f5f8;color:#4a6579}.muted{font-size:13px;color:#6b7b88}summary{cursor:pointer;font-weight:600}details{padding:12px 0}footer{font-size:13px;color:#7a8995;padding:20px 0}li{margin:12px 0}@media(max-width:800px){main{padding:12px}section{padding:18px}h1{font-size:26px}h2{font-size:20px}.lead{font-size:18px}}'''
(R/'index.html').write_text('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>黄金E0/R｜退出、等待与融合</title><style>'+css+'</style><main>'+body+'</main></html>')
# Markdown uses the established local research-report format.
text='''# 黄金ETF E0/R专项归因（2026-10-24）

[交互图文报告](http://127.0.0.1:8779/)｜[事前协议](PROTOCOL.md)｜[原切换实验](../strategy-switching-20261024/README.md)

**主因已明确：R的短期波幅退出与“原结构完全结束才可重新入场”的长周期等待相叠加。** 这段黄金的14次买入日期/成交价全部相同，R的14次卖出全部由额外2波幅条件触发，全部早于E0。E0暴露1273天，R197天。原算法和原486账户保持不变。

![黄金2021—2026走势、参与和净值](charts/gold-overview.png)

实际窗口2021-01-04—2026-10-16，1400观察；518880黄金ETF，不是沪金主连。本数据OHLCV与原始字段完全一致，复权系数均1，无补数。E0净收益83.15%、回撤34.79%；R−15.61%/16.59%；被动119.06%/30.52%。E0也没有跑赢被动，不能由优于R就证明E0最优。

## 配对交易与复利

关键三段：2022-07-27入场，E0至2023-04-04净获16.16%，R于2022-09-01仅获1.90%；2023-10-16入场，E0至2024-08-07获18.25%，R于2023-11-09仅1.03%；2024-08-20入场，E0至2025-10-23获62.59%，R于2024-09-05亏0.72%，之后432自然日才再参与。

2024年8月入场前E0本金已为初始1.291倍、R0.950倍，遗漏会继续复利放大。各笔收益不能简单相加；配对因子乘积与账户终值完全相同，对数差可加，2024关键笔解释总对数终值差63.67%。前三段合计100.89%，其他正/负贡献抵消，不能把它解读成简单利润份额。

两者净利润差98.76个百分点。按逐日原始成交价格损益分解，E0价格损益86.87%初始资金、费用滑点3.72%；R价格损益−12.99%、费用滑点2.61%。费用差约1.11个百分点反而不利E0，差距来自价格参与和复利，并非R手续费更多。

## 2024关键日与忽略的新证据

![提前退出及原结构继续确认](charts/early-exit-2024.png)

9月4日收盘5.463低于R线5.473，但高于E0结构支持5.327。前14日相对真实波幅均值0.588%，2倍约1.176%；新增波幅退出是价格型风险规则，并没有要求放量破坏。当日量比0.683不证明后面必涨，也不足以把“触及短期波幅边界”直接叫大趋势失效。

10月11日，新原量价事件确认10月9日低点5.640，支持5.327→5.640，当日相对量1.356；因为E0仍有效，其entered标志为0，R继续禁止参与。之后同结构内一系列更高低点也被忽略。[原事件表](evidence/ignored-up-events.csv)保留识别日和低点发生日，不倒填低点当天入场。

这里的时间尺度不一致是关键：较快条件足以退出，恢复却要求较慢的大结构先被破坏。已确认的新推进没有进入R的恢复机制。

## 同一资产的R有效反例

![2026下跌R的优势](charts/decline-2026.png)

2026-03-25同入，R04-27获1.44%，E006-11亏11.92%。R04-24信号相对量0.579，比2024早退还低，因此“低量不卖”不是可直接采纳的修正。也不能为了保住2024—2025利润就取消风险退出。R的优势在部分下跌段成立，代价是可能错过趋势中整理后的推进。

## 唯一固定融合及必要减仓对照

冻结一个初始50%E0＋50%R，独立资金、各自复利、不互转、不每日再平衡；对原18窗×3执行情景机械推导54条路径，新增信号账户0。结果之后增加黄金的50%E0＋50%现金固定风险参考，3条路径；补充动机/时间/代码单列于[cash-reference-protocol.json](cash-reference-protocol.json)，没有改原协议或偷偷搜索新比例。

黄金基础结果：

| 方案 | 净收益 | 最大回撤 |
|---|---:|---:|
| E0 | +83.15% | 34.79% |
| R | −15.61% | 16.59% |
| 各半E0/R | +33.77% | 27.91% |
| 半数E0、半数现金 | +41.58% | 25.47% |

![直接融合与减仓参考](charts/direct-blend.png)

黄金中现金参考收益更高、回撤更低，R没有提供正的组合增量。因此不把“融合后回撤下降”当优化成功。其他场景亦只提供取舍：半导体牛市各半134.25%/14.13%，今年完整区间39.90%/26.73%。完整54行全部保存，不挑有利场景。

## 优化与进一步融合的可证伪设计

优先仅研究一个更具体的恢复问题，**本轮未实现、未回测新规则**：保持R现有2波幅退出与原入场不变，提前退出后记录当时的结构支持；E0仍有效期间，如果退出之后形成了新的低点，并由新的原量价向上事件确认，且这个低点高于记录支持，则允许下一可成交开盘恢复。原结构失效时仍按原规则处理。

2024-10-11提供了这种候选证据，但不能假定后来一直持有或不再触发2波幅退出。该条件复用真正进入事件确认的成交量，不是再加一个量标签；不要求永久历史新高，不靠事后牛市标签，不等整个长结构先死亡。

E0的优化空间在策略层对风险与恢复的表达，而非因黄金正常回吐一味收紧结构；R的优化空间在恢复资格，不能把一次持仓退出当作市场结构不再值得跟踪。直接分仓可以作为固定风险取舍对照，但本段黄金不支持将R资金袖默认加入。

将来若明确恢复实施，先冻结这一个恢复规则，其他都不变；同时检验黄金连续趋势、半导体牛市、今年半导体弱反弹和熊市，特别看累计普通损耗与大赢家参与，不为黄金调ATR倍数或仓位比例。本轮到分析、固定分仓和设计为止，不自动续跑新信号账户。

## 证据和核账

[14笔配对](evidence/paired-cycles.csv)、[日价格损益/费用归因](results/v0/gold-pnl-attribution.csv)、[连续年度变化](results/v0/gold-continuous-years.csv)、[54条分仓](results/v0/blend-summary.csv)、[3条现金参考](results/v0/cash-reference-summary.csv)、[独立核账](results/v0/audit.json)。3360笔缩放成交重建净值/现金/份额，最大误差2.97e-14；原471冻结文件及前轮261源未变。组合回撤按合成日净值重算，不取两回撤均值；无新的组合胜率包装。

手续费/滑点、分数份额和流动性代理继承原研究，非实盘已认证。历史已看过，不称样本外；54条分仓和3条参考是新增经济诊断，与原486账户分开计数。旧算法、旧失败保留；无行情下载、微信/凭据访问、实盘、远端发布。

ATR类量度描述波动而非方向：[Fidelity官方指标说明](https://www.fidelity.com/learning-center/trading-investing/technical-analysis/technical-indicator-guide/atr)。本代码使用滞后相对真实波幅的14日算术均值，并非Wilder平滑ATR，具体数值以冻结代码为准。公开理论不替代本地经济证据。
'''
(R/'README.md').write_text(text);print('report rendered; no signal rule implemented')
