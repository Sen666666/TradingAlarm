from pathlib import Path
import json,hashlib,html
import numpy as np,pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
HERE=Path(__file__).resolve().parent;OUT=HERE/'results/v0';CHART=HERE/'charts';CHART.mkdir(exist_ok=True)
for p in ['/System/Library/Fonts/Supplemental/Arial Unicode.ttf','/System/Library/Fonts/PingFang.ttc']:
 if Path(p).exists():font_manager.fontManager.addfont(p);plt.rcParams['font.family']=font_manager.FontProperties(fname=p).get_name();break
plt.rcParams.update({'axes.unicode_minus':False,'font.size':10,'figure.facecolor':'#faf9f6','axes.facecolor':'#faf9f6','savefig.facecolor':'#faf9f6'})
bars=pd.read_parquet(HERE/'inputs/AU0-main.parquet').loc['2025-01-02':'2026-10-13'];summary=pd.read_csv(OUT/'summary.csv');checks=json.loads((OUT/'checks.json').read_text())
labels={'B1':'一买','B2':'均线辅助二买','B3':'中枢三买辅助','B3A':'笔三买辅助','B23':'二买或中枢三买','B123':'一买或二买或中枢三买','HOLD':'买入持有'}
palette={'B1':'#ad604b','B2':'#216d8c','B3':'#7e5b9e','B3A':'#67865c','B23':'#4c9eae','B123':'#bd8740','HOLD':'#a89971'}
def daily(name):return pd.read_parquet(OUT/'accounts'/name/'daily.parquet')
def trades(name):return pd.read_csv(OUT/'accounts'/name/'trades.csv')
def fills(name):return pd.read_csv(OUT/'accounts'/name/'fills.csv')
def pct(v):return '—' if pd.isna(v) else f'{100*v:.2f}%'
def table(df):return df.to_html(index=False,border=0,classes='data',escape=True)

fig,axes=plt.subplots(3,1,figsize=(16,11),sharex=True,gridspec_kw={'height_ratios':[2.4,2.3,1.6]},layout='constrained')
axes[0].plot(bars.index,bars.close,color='#a48319',lw=1.6);axes[0].set_yscale('log');axes[0].set_ylabel('AU0收盘价\n对数轴');axes[0].set_title('黄金CZSC日线买点回测：只交易2025-01-02—2026-10-13，预热从2020开始\n共同卖法M：结构破坏或新卖点；下一观察开盘执行；1倍名义敞口，扣费及滑点',loc='left')
for rule in ['B1','B2','B3','B3A','B123','HOLD']:
 name=f'{rule}_M_base' if rule!='HOLD' else 'HOLD_base';dd=daily(name);style='--' if rule=='HOLD' else '-'
 axes[1].plot(dd.index,dd.nav,color=palette[rule],label=labels[rule],ls=style,lw=1.7)
 axes[2].plot(dd.index,100*dd.drawdown,color=palette[rule],ls=style,lw=1.3)
axes[1].set_ylabel('净值，初始=1');axes[1].axhline(1,c='#888',lw=.6);axes[1].legend(ncol=3,loc='upper left');axes[2].set_ylabel('历史峰值回撤 %');axes[-1].set_xlabel('B23与B2全部路径相同，图上省去重叠线；全部为已见历史开发回测，不是实盘。')
for ax in axes:ax.grid(alpha=.15);ax.spines[['top','right']].set_visible(False)
fig.savefig(CHART/'equity-comparison.png',dpi=145);plt.close(fig)

fig,axes=plt.subplots(2,1,figsize=(16,9),sharex=True,layout='constrained')
for ax,mode,title in zip(axes,['M','S'],['M：结构破坏或新卖点退出','S：只等结构破坏退出']):
 name=f'B2_{mode}_base';dd=daily(name);ff=fills(name);ax.plot(bars.index,bars.close,c='#aa8a27',lw=1.3);ax.plot(dd.index,dd.floor,c='#6b8c68',lw=1,alpha=.7,label='当时已知结构保护点')
 for side,marker,color,label in [('buy','^','#137955','开盘买入'),('sell','v','#bf5138','开盘卖出')]:
  z=ff.loc[ff.side.eq(side)];ax.scatter(pd.to_datetime(z.date),z.price,marker=marker,c=color,s=45,label=label,zorder=4)
 rr=summary.loc[summary.id.eq(name)].iloc[0];ax.set_yscale('log');ax.set_title(f'均线辅助二买 · {title} · 收益{pct(rr.net_return)} / 最大回撤{pct(rr.max_drawdown)} / {rr.trades}次',loc='left');ax.legend(loc='upper left',ncol=3);ax.grid(alpha=.15)
axes[-1].set_xlabel('标记为实际模型成交日期，不是事后笔端点；S经历2026年大幅回吐，M也会提前退出而错过后续上涨。')
fig.savefig(CHART/'second-buy-exit-comparison.png',dpi=145);plt.close(fig)

fig,axes=plt.subplots(3,2,figsize=(17,12),sharex=True,layout='constrained')
for ax,rule in zip(axes.flat,['B1','B2','B3','B3A','B23','B123']):
 name=f'{rule}_M_base';ff=fills(name);rr=summary.loc[summary.id.eq(name)].iloc[0];ax.plot(bars.index,bars.close,c='#bba35c',lw=1)
 for side,marker,color in [('buy','^','#137955'),('sell','v','#bf5138')]:
  z=ff.loc[ff.side.eq(side)];ax.scatter(pd.to_datetime(z.date),z.price,c=color,marker=marker,s=38,zorder=3)
 ax.set_yscale('log');ax.set_title(f'{labels[rule]}：收益{pct(rr.net_return)}，回撤{pct(rr.max_drawdown)}，{rr.trades}次',loc='left');ax.grid(alpha=.15)
fig.suptitle('六组买点在同一卖法M下的真实信号执行位置：绿买、红卖',fontsize=15);fig.savefig(CHART/'all-buy-rules.png',dpi=145);plt.close(fig)

base=summary.loc[summary.scenario.eq('base')];rows=[]
for rule in ['B1','B2','B3','B3A','B23','B123']:
 m=base.loc[base.id.eq(f'{rule}_M_base')].iloc[0];s=base.loc[base.id.eq(f'{rule}_S_base')].iloc[0]
 rows.append(dict(买点规则=labels[rule],M收益=pct(m.net_return),M最大回撤=pct(m.max_drawdown),M次数=int(m.trades),M胜率=pct(m.win_rate),S收益=pct(s.net_return),S最大回撤=pct(s.max_drawdown),S次数=int(s.trades)))
main=pd.DataFrame(rows);main.to_csv(OUT/'readable-main.csv',index=False)
stress=summary.loc[summary.sell_rule.eq('M')&summary.buy_rule.ne('B23'),['buy_label','scenario','net_return','max_drawdown','trades']].copy();stress.columns=['买点','执行情景','收益','最大回撤','次数'];stress['收益']=stress['收益'].map(pct);stress['最大回撤']=stress['最大回撤'].map(pct)
monthly=[]
for _,r in summary.loc[summary.scenario.eq('base')].iterrows():
 nav=daily(r.id).nav;previous=1.
 for year,group in nav.groupby(nav.index.year):
  last=group.iloc[-1];monthly.append(dict(account=r.id,year=int(year),net_return=last/previous-1));previous=last
pd.DataFrame(monthly).to_csv(OUT/'calendar-year-returns.csv',index=False)
def trade_view(name):
 t=trades(name).copy();t=t[['entry_signal','endpoint','entry_date','entry_price','exit_date','exit_price','exit_reason','net_return']]
 t.columns=['信号确认日','笔端点日期','买入日','买入价','卖出日','卖出价','退出原因','净收益'];t['笔端点日期']=t['笔端点日期'].astype(str).str[:10]
 t['买入价']=t['买入价'].round(2);t['卖出价']=t['卖出价'].round(2);t['净收益']=t['净收益'].map(pct)
 return table(t)
details=''
for rule in ['B1','B2','B3','B3A','B23','B123']:
 for mode in ['M','S']:details+=f'<details><summary>{labels[rule]} · 卖法{mode}：全部交易</summary><div class="scroll">{trade_view(f"{rule}_{mode}_base")}</div></details>'
bh=base.loc[base.buy_rule.eq('HOLD')].iloc[0]
body=f'''<!doctype html><html lang="zh"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>黄金CZSC买点回测</title><style>
body{{font:16px/1.75 -apple-system,BlinkMacSystemFont,'PingFang SC',sans-serif;background:#faf9f6;color:#273036;margin:0}}main{{max-width:1360px;margin:38px auto;padding:0 28px}}h1{{font-size:32px}}h2{{font-size:23px;margin-top:36px}}p{{max-width:1100px}}.lead{{font-size:20px}}.cards{{display:flex;gap:16px;flex-wrap:wrap}}.card{{background:#fffdf8;border:1px solid #ded7c9;padding:16px;flex:1;min-width:210px}}.num{{font-size:30px;color:#24677e}}.note{{background:#eee9de;border-left:4px solid #aa8a43;padding:16px 22px}}img{{width:100%;height:auto}}table{{width:100%;border-collapse:collapse;font-size:14px}}th,td{{text-align:left;padding:8px 11px;border-bottom:1px solid #ded7c9}}th{{background:#eee9de}}.scroll{{overflow-x:auto}}details{{margin:18px 0}}a{{color:#216d8c}}code{{background:#eee9de;padding:2px 5px}}small{{color:#68645d}}
</style><main><h1>黄金：六组CZSC买点的收益和回撤</h1><p class="lead">相同日线、相同交易区间、相同成交和成本，分别比较买点与卖法。二买在本窗口的收益/回撤组合较好，一买参与下跌后反弹并亏损；只等结构失效会保留更多上涨，也承受更大回吐。</p><p>交易期2025-01-02—2026-10-13 · 428观察 · 2020起1212条预热不计收益 · CZSC1.0.2 · 39个固定账户 · 无参数寻优</p>
<div class="cards"><div class="card">二买＋卖法M<div class="num">+23.34% / 7.63%</div>收益 / 最大回撤；10次交易，胜率60%</div><div class="card">二买＋卖法S<div class="num">+27.29% / 24.52%</div>收益 / 最大回撤；6次交易，胜率66.67%</div><div class="card">区间买入持有<div class="num">{pct(bh.net_return)} / {pct(bh.max_drawdown)}</div>收益 / 最大回撤；不代表缠论跑赢被动</div></div>
<p class="note">这是沪金主连AU0连续价格代理的1倍名义敞口回测，做多/空仓，不加杠杆。没有逐合约换月、整数手、保证金和真实费率链，不能当作真实可成交期货账户。输入复用先前保存的2008起原始数据，无需下载；采用2020起预热与2008起预热相比，回测期每日买卖信号变化0日。</p>
<h2>主结果：同一买点，分别使用两种出口</h2><p><b>M＝结构破坏或新卖点退出；S＝仅结构破坏退出。</b>基础情景在收盘确认后下一观察开盘成交，每边费用2bp＋不利滑点0.04元/克。期初空仓，不继承预热期订单/持仓；期末预定统一收盘结算。以下为累计净收益，不是年化收益；最大回撤按日收盘净值计算，不是日内极值回撤。</p><div class="scroll">{table(main)}</div><p>被动从第一天开盘持有至最后一天收盘，收益{pct(bh.net_return)}、最大回撤{pct(bh.max_drawdown)}。B23与B2所有情景每日净值完全相同：新增三买没有带来独立新增成交，不能重复算作一份额外策略优势。</p><img src="charts/equity-comparison.png" alt="黄金价格、六组买点净值和回撤对照">
<h2>买点究竟用什么规则</h2><ol><li><b>一买B1：</b>cxt_first_buy_V221126，奇数向下笔序列末端创低，价格力度背驰，并有量力度或长度背驰。</li><li><b>均线辅助二买B2：</b>cxt_second_bs_V230320，SMA21，以五笔结构和均线关系识别。它是CZSC的明确辅助实现，不冒充完整的一买后首次回抽定义。</li><li><b>中枢三买辅助B3：</b>cxt_third_bs_V230319，SMA34，前三笔存在重叠区，向上离开后回落不回中枢，并只接受均线新高/均线底分标签。</li><li><b>笔三买辅助B3A：</b>cxt_third_buy_V230228，使用突破笔重叠及回落位置的辅助规则，延续以前对照的定义；和上一项分开，不混为同一种三买。</li><li><b>B23/B123：</b>分别取B2或B3、B1或B2或B3；持仓中不加仓。</li></ol><p>日线笔最短长度6，保留100笔，di=1。函数名和参数在运行前冻结；不是“缠论”唯一实现，也不加入事后背景/成交量过滤来改善本段成绩。<a href="https://czsc.readthedocs.io/en/latest/_modules/czsc/signals/cxt.html">CZSC官方信号说明</a>网页版本为0.9.59，实际运行固定本机1.0.2 native文件。</p>
<h2>卖出和执行规则</h2><p>初始保护点是买点首次确认时的向下笔低点；持仓时任一有效新买点可提高保护点。收盘知道当日低点已跌破保护点，才产生下一观察开盘卖单。M还接受新确认的一卖、二卖、三卖；三卖只接受均线新低/均线顶分标签。退出优先，同日不重入，不设止盈。</p><p>下一开盘已跌到保护点以下则取消买单；不能利用当天尚未发生的最低价撤销开盘成交。实际买入日严格晚于信号确认日，笔端点日期仅用于结构解释。AU最小价位0.02元/克仅用于定义2跳滑点，费用2bp是统一研究假设，非真实历史费率。<a href="https://www.shfe.com.cn/products/futures/metal/ferrousandpreciousmetal/">上期所黄金合约规格</a></p>
<h2>二买的两种退出：收益和回吐的取舍</h2><img src="charts/second-buy-exit-comparison.png" alt="二买两种出口的实际成交与保护点"><p>M在2025-12-31卖出10月底开始的一段，减少2026年回撤，也错过随后1月加速。S持续持有至2026-05-19，保留上涨但最大回撤24.52%。不能只据低回撤或某一段退出接近高点就认定一种出口全面更好。</p>
<h2>六组买点实际买在哪里</h2><img src="charts/all-buy-rules.png" alt="六组买点实际成交位置"><p>一买只产生两笔成交，均在2026年6月下跌阶段，合计−8.17%；没有捕捉2025主升。一买也不能自动避开下跌反弹。二买M共10笔、6笔盈利，但没有及时进入2025年9月和2026年1月的快速启动；更少回撤伴随明显行情遗漏。中枢三买M为+5.03%，旧笔三买辅助M为−1.08%，不同三买定义的差异不能隐藏。</p>
<h2>二买M的全部十笔交易</h2><div class="scroll">{trade_view('B2_M_base')}</div>
<h2>成本加倍与多等一天</h2><p>cost2＝费用4bp、滑点0.08；delay1＝第2个后续观察开盘执行。二买M分别为22.73%、25.73%，笔三买辅助M在延迟情景由−1.08%变为+3.81%，表明小样本结果会受具体执行日影响。延迟使部分待买结构先失效而取消，不能把本段变好解释为“多等一天必然更优”。被动delay1保留预定第一天开盘买入，未事后移动起日。</p><div class="scroll">{table(stress)}</div>
<details><summary>展开全部39个账户</summary><div class="scroll">{table(summary.assign(net_return=summary.net_return.map(pct),max_drawdown=summary.max_drawdown.map(pct),win_rate=summary.win_rate.map(pct)))}</div></details>
<h2>全部买点/卖法交易明细</h2>{details}
<h2>验证和证据边界</h2><p>主输入1640日，1212日只预热；2008全历史预热对本窗口信号差异0日。6个实际前缀截断逐日/逐事件完全一致。独立从384条成交重建39账户每日现金、数量、净值、最大回撤、费用及逐笔复利；所有源和native哈希不变。首轮核验把无笔端点的被动交易当作缠论端点检查，失败已保留，修正核验适用范围，未重跑账户或改规则。</p><p>全部是已经看过的黄金历史开发检验，1个品种、有限交易数；未证明普遍优势、样本外或实盘成绩。回测没有使用原图蓝点作为交易信号，也不证明恢复趋势动物公式。现有趋势算法保持原样，微信操作0、行情新请求0。</p><p><a href="PROTOCOL.md">完整冻结规则</a> · <a href="README.md">结果说明与复现边界</a> · <a href="results/v0/summary.csv">39账户原始汇总CSV</a> · <a href="results/v0/signal-events-period.csv">所有区间信号及真正确认日期</a> · <a href="results/v0/recognition-lags.csv">笔端点至确认的滞后</a> · <a href="results/v0/checks.json">预热/前缀检查</a> · <a href="results/v0/independent-audit.json">独立成交核账</a></p></main></html>'''
with (HERE/'index.html').open('x') as fp:fp.write(body)
record=dict(charts={str(p.relative_to(HERE)):hashlib.sha256(p.read_bytes()).hexdigest() for p in CHART.glob('*.png')},html_sha256=hashlib.sha256((HERE/'index.html').read_bytes()).hexdigest(),model_or_account_changes=0)
with (HERE/'render-manifest.json').open('x') as fp:json.dump(record,fp,ensure_ascii=False,indent=2);fp.write('\n')
print('rendered',len(record['charts']),'charts and full report')
