from pathlib import Path
import json,html
import numpy as np,pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
R=Path(__file__).resolve().parent;O=R/'results/v0';C=R/'charts'
font_manager.fontManager.addfont('/System/Library/Fonts/Supplemental/Arial Unicode.ttf');plt.rcParams.update({'font.family':'Arial Unicode MS','axes.unicode_minus':False,'font.size':10,'figure.facecolor':'#faf9f6','axes.facecolor':'#faf9f6','savefig.facecolor':'#faf9f6'})
s=pd.read_csv(O/'summary.csv');d=pd.read_parquet(R/'inputs/USHJ512480.parquet').loc['2025-01-02':'2026-06-30'];ddates=pd.read_csv(O/'drawdown-and-boundaries.csv');labels={'E0':'原算法：结构退出','E2':'结构＋2倍波幅退出','E3':'结构＋3倍波幅退出','ED':'结构＋向下量价事件','HOLD':'区间买入持有'};colors={'E0':'#176b78','E2':'#d57235','E3':'#8b66a5','ED':'#bd4453','HOLD':'#969184'};pol=['E0','E2','E3','ED']
def pct(v):return '—' if pd.isna(v) else f'{100*v:.2f}%'
def ledger(key):return pd.read_parquet(O/'accounts'/key/'ledger.parquet')
def trade(key):return pd.read_csv(O/'accounts'/key/'trades.csv')
def fills(key):return pd.read_csv(O/'accounts'/key/'fills.csv')
def table(df):return '<div class="scroll">'+df.to_html(index=False,border=0,escape=True)+'</div>'
def result_table(z,scenario=False):
 cols=(['scenario'] if scenario else [])+['policy','net_return','max_drawdown','trades','win_rate','natural_win_rate','exposure_fraction'];v=z[cols].copy();v.policy=v.policy.map(labels)
 for col in ['net_return','max_drawdown','win_rate','natural_win_rate','exposure_fraction']:v[col]=v[col].map(pct)
 return table(v.rename(columns={'scenario':'情景','policy':'算法/退出','net_return':'累计净收益','max_drawdown':'最大回撤','trades':'交易笔数','win_rate':'胜率(含期末)','natural_win_rate':'自然退出胜率','exposure_fraction':'参与观察比例'}))
def clean(axes):
 for ax in np.array(axes).flat:ax.grid(alpha=.15);ax.spines[['right','top']].set_visible(False)
# Overall price and actual account curves.
fig,axes=plt.subplots(3,1,figsize=(16,11),sharex=True,layout='constrained',gridspec_kw={'height_ratios':[1.5,2,1.2]})
axes[0].plot(d.index,d.close,c='#9b8450',lw=1.4);axes[0].set_yscale('log');axes[0].set_ylabel('ETF权息价格代理\n对数轴')
for p in pol+['HOLD']:
 k=f'P_{p}_base' if p!='HOLD' else 'H_HOLD_base';l=ledger(k);style='--' if p=='HOLD' else '-';axes[1].plot(l.index,l.nav,c=colors[p],label=labels[p],ls=style,lw=1.7);axes[2].plot(l.index,100*l.drawdown,c=colors[p],ls=style,lw=1.3)
axes[1].legend(ncol=3,fontsize=9);axes[1].set_ylabel('扣费净值，初始1');axes[2].set_ylabel('峰值以来回撤 %');axes[2].set_xlabel('2025-01-02—2026-06-30；359交易观察，1350条前史仅预热；末日预定结算，不是策略自行卖出')
fig.suptitle('半导体ETF512480：同开仓逻辑、不同退出规则，允许按原规则重入\n基础费用/滑点；下一观察开盘执行；不使用2026年7月以后行情');clean(axes);fig.savefig(C/'comparison.png',dpi=145);plt.close(fig)
# Actual fills for every policy including losers.
fig,axes=plt.subplots(4,1,figsize=(16,14),sharex=True,layout='constrained')
for ax,p in zip(axes,pol):
 z=s.loc[s.key.eq(f'P_{p}_base')].iloc[0];f=fills(z.key);st=pd.read_parquet(R/'prepared'/f'{p}.parquet');ax.plot(d.index,d.close,c='#a59054',lw=1.1,label='收盘');ax.plot(st.index,st.exit_line.where(st.target.astype(bool)),c=colors[p],lw=.9,alpha=.7,label='当时保护线')
 for side,marker,col in [('buy','^','#208563'),('sell','v','#c15345')]:
  q=f.loc[f.side==side];ax.scatter(pd.to_datetime(q.date),q.price,marker=marker,c=col,s=40,zorder=4,label='实际买入' if side=='buy' else '实际卖出(含期末)')
 ax.set_yscale('log');ax.set_title(f'{labels[p]}：收益{pct(z.net_return)} / 回撤{pct(z.max_drawdown)} / {int(z.trades)}笔',loc='left');ax.legend(fontsize=8,ncol=4)
axes[-1].set_xlabel('首日承接2024末已有效结构；末日仍持仓的组统一收盘结算。价格点为实际模型成交，不是事后极值。');clean(axes);fig.savefig(C/'transactions.png',dpi=135);plt.close(fig)
# Matched actual entry diagnostic.
fig,axes=plt.subplots(2,2,figsize=(16,9),sharex=True,layout='constrained')
for j,mode in enumerate(['P','M']):
 for p in pol:
  key=f'{mode}_{p}_base' if not(mode=='M' and p=='E0') else 'P_E0_base';l=ledger(key);axes[0,j].plot(l.index,l.nav,c=colors[p],label=labels[p]);axes[1,j].plot(l.index,100*l.drawdown,c=colors[p])
 axes[0,j].set_title('P：退出后可按原规则重入' if mode=='P' else 'M：严格锁定原算法7次买入，不在原周期内重入');axes[0,j].legend(fontsize=9);axes[0,j].set_ylabel('扣费净值');axes[1,j].set_ylabel('回撤 %')
clean(axes);fig.suptitle('早退出的风险改善，是否被重新入场消耗？');fig.savefig(C/'matched-comparison.png',dpi=140);plt.close(fig)
# Descriptive continuous-account calendar splits, without annual resetting.
years=[]
for row in s.loc[(s.scenario=='base')&s['mode'].isin(['P','H'])].to_dict('records'):
 prior=1.
 for year,g in ledger(row['key']).groupby(lambda x:x.year):
  years.append({'算法':labels[row['policy']],'期间':str(year)+'全年' if year==2025 else '2026上半年','连续账户该段收益':g.nav.iloc[-1]/prior-1});prior=g.nav.iloc[-1]
year=pd.DataFrame(years);year.to_csv(O/'calendar-period-returns.csv',index=False);year['连续账户该段收益']=year['连续账户该段收益'].map(pct)
# Complete trades with terminal separate; no deleting failures.
tradedetails=''
for p in pol:
 t=trade(f'P_{p}_base');v=t[['entry_date','exit_date','net_return','net_pnl','exit_reason','terminal']].copy();v.net_return=v.net_return.map(pct);v.net_pnl=v.net_pnl.map(lambda x:f'{100*x:+.2f}个百分点');v=v.rename(columns={'entry_date':'买入日','exit_date':'卖出/结算日','net_return':'该笔净收益','net_pnl':'初始账户贡献','exit_reason':'原因','terminal':'是否期末结算'})
 tradedetails+=f'<details><summary>{labels[p]}：全部{len(t)}笔交易</summary>{table(v)}</details>'
base=s.loc[(s.scenario=='base')&s['mode'].eq('P')];matched=s.loc[(s.scenario=='base')&s['mode'].eq('M')];hold=s.loc[(s.scenario=='base')&s['mode'].eq('H')];stress=s.loc[s['mode'].eq('P')];mdates=ddates.loc[ddates.key.isin(base.key),['key','dd_peak','dd_trough','max_drawdown']].copy();mdates.max_drawdown=mdates.max_drawdown.map(pct)
contrib=base[['policy','tail_trades','tail_pnl','ordinary_pnl','fees','slippage']].copy();contrib.policy=contrib.policy.map(labels)
for col in ['tail_pnl','ordinary_pnl','fees','slippage']:contrib[col]=contrib[col].map(lambda v:f'{100*v:+.2f}个百分点')
contrib=contrib.rename(columns={'policy':'算法','tail_trades':'≥30%交易笔数(含期末)','tail_pnl':'尾部交易账户贡献','ordinary_pnl':'其他交易账户贡献','fees':'手续费/初始资金','slippage':'滑点/初始资金'})
body=f'''<!doctype html><html lang="zh"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>半导体牛市：原退出与敏感退出</title><style>
body{{margin:0;background:#faf9f6;color:#27353a;font:16px/1.8 -apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif}}main{{max-width:1380px;margin:36px auto;padding:0 24px}}h1{{font-size:34px;line-height:1.4}}h2{{margin-top:38px;font-size:24px}}.lead{{font-size:21px;max-width:1150px}}.note{{background:#eee8da;padding:18px 22px;border-left:4px solid #a98a45}}.cards{{display:flex;gap:14px;flex-wrap:wrap}}.card{{flex:1;min-width:220px;padding:18px;background:white;border:1px solid #ded8c8}}.big{{font-size:30px;color:#176b78}}img{{width:100%;height:auto}}table{{width:100%;border-collapse:collapse;font-size:14px}}th,td{{padding:9px 11px;text-align:left;border-bottom:1px solid #ddd6c7;white-space:nowrap}}th{{background:#eee8da}}.scroll{{overflow-x:auto}}details{{margin:16px 0;padding:12px;border:1px solid #ddd6c7}}summary{{cursor:pointer;font-weight:600}}a{{color:#176b78}}.small{{font-size:14px;color:#606b70}}
</style><main><h1>半导体大牛市：原算法更能保留趋势</h1><p class="lead">2025年初至2026年6月末，原结构退出的收益、胜率和基础情景回撤均优于三种敏感退出。卖早确实有几笔收益改善，但长趋势被切短、再次入场的损失和复利底数下降，代价更大。</p><p>固定半导体ETF512480 · 2025-01-02—2026-06-30 · 359交易观察 · 1350条前史预热 · 24账户一次运行 · 旧规则字节不变</p>
<div class="cards"><div class="card">原算法 E0<div class="big">+162.01% / 16.59%</div>累计净收益 / 最大回撤<br>7笔，胜率71.43%</div><div class="card">敏感退出 E2<div class="big">+105.15% / 19.27%</div>累计净收益 / 最大回撤<br>13笔，胜率53.85%</div><div class="card">区间买入持有<div class="big">+199.00% / 19.90%</div>原算法仍少赚36.99个百分点<br>本轮未证明战胜被动持有</div></div>
<p class="note">这是用户指定的大牛市窗口中的机制诊断，不能认定算法事先知道半导体是牛市。标的是上一轮同一半导体ETF代理，不是半导体个股组合；输入复用既有因果权息价格。6月30日预定收盘结算，最后一笔并非算法发出的卖出信号。未使用7月以后行情、未调参、未改变原算法或访问外部账号。</p>
<h2>1. 设计与公平比较</h2><p>保持相同原量价开仓：上行事件确认和高量下跌跨日收复。E0只有结构floor破坏退出；E2/E3另加2/3倍历史相对真实波幅跟踪退出；ED另加原量价向下事件退出。它们是退出机制对照，不能称趋势动物原公式。</p><p>均为1倍做多/现金，开仓投入当时净值，不每日再平衡。收盘得信号，下一观察开盘成交；每边手续费5bp＋不利滑点5bp。成本翻倍、额外延迟一观察另外报告。2024末已有有效E0结构，因此四组统一于2025首日开盘承接；没有带入此前利润。</p><p>先看原始量价和信号轨迹、再冻结、最后运行账户。E0与原实现逐日相同；四政策信号与上一轮相同日期逐日相同；全部24账户在6月29日以前与上一轮完全相同，差别仅为本轮6月30日提前结束并结算。</p>
<h2>2. 主结果：允许按原规则重新入场</h2>{result_table(base)}{result_table(hold)}<p class="small">累计净收益不是年化；回撤按每日收盘净值，含费用与滑点，不代表盘中最坏损失。胜率包括期末结算，另列只算自然退出的胜率。参与比例按持有过的交易观察计，卖出日也计入。</p><img src="charts/comparison.png">
<h2>3. 差距在哪里：完整长趋势与再次试错</h2><p><b>2025年4月至11月：</b>四组都在4月10日同次买入。E0持续到11月13日，获利39.40%；E2在5月16日离场仅0.79%，E3/ED在5月19日离场仅0.88%。E2之后6月26日才重新买入，再经历9月和10月换手；不能只把后续盈利加起来就当作补回整段行情，期间现金、亏损和复利底数都发生变化。</p><p><b>早卖也有成功：</b>2025年12月9日同次入场，E0到2026年3月4日获利7.54%；E2在2月3日获利15.00%，ED在1月30日获利17.58%，确实避开部分回落。但自主循环的敏感组2月26日又买回，至3月4日亏损8.12%，吃掉部分改善。</p><p><b>2026年4月至6月：</b>E0在4月9日买、6月9日卖，获利35.09%；E2在6月2日卖，获利35.02%，本次提前离场没有明显增加收益，6月5日买回反而再亏4.93%。ED在6月1日卖出获利42.02%，确有更好卖点，仍经历同一次买回损失。</p><p><b>6月最后加速段：</b>四组均在6月16日买入，至6月30日结算同获34.06%。虽然单笔比例相同，E0此前保留的资金更多，此笔对初始账户贡献66.57个百分点，E2为52.12个百分点。这是复利基数差异；不能把贡献数字当成该笔涨幅，也不能把期末结算解释为算法卖在行情末端。</p><img src="charts/transactions.png">{tradedetails}
<h2>4. 同批买入，只改变退出：风险改善确实存在，但有收益代价</h2>{result_table(pd.concat([base.loc[base.policy=='E0'],matched]))}<p>锁定原算法全部7次实际买入、每个原周期不重入，E2回撤降至12.91%，但收益也降至106.48%；胜率仍为71.43%。开放原规则重入后，E2收益105.15%、回撤19.27%。因此这段行情里，敏感退出本身可减少持有风险，但重新入场把这项优势消耗掉了。不能把M当成另一套可自主运行选股策略，也不能只比较早卖后的现金净值。</p><img src="charts/matched-comparison.png"><details><summary>三种敏感出口 × 三情景：同批逐笔配对CSV</summary><p><a href="results/v0/matched-legs.csv">查看全部63组配对</a>；同次实际入场，卖出不晚于E0，无事后强行撤销原买单。</p></details>
<h2>5. 不是仅靠成本：普通交易改善，尾部贡献下降</h2>{table(contrib)}<p>原算法三笔≥30%交易贡献156.10个百分点，其余交易净贡献5.92个百分点；E2分别93.88和11.27个百分点。敏感方案改善了部分普通交易，却损伤了长赢家及其后续复利。30%只是统一事后归因边界，所有普通亏损均包含，没有到30%止盈。两组均含末日期末交易，它的共同34.06%并非已验证自然退出。</p><p>原算法手续费＋滑点合计约初始资金2.00个百分点，E2约3.15个百分点；这并不足以解释56.87个百分点的最终收益差距，核心还是持仓路径。上述摩擦是相同实际成交数量下的账面支出，不是假设零成本、重新计算仓位后的独立账户。</p><details><summary>2025与2026上半年：连续账户分段收益，不重置本金</summary>{table(year)}<p>ED在2026上半年连续账户收益87.71%，略高于E0的86.97%；但2025赚得更少，全窗口仍落后。不能声称每个自然阶段原算法都最好。</p></details><details><summary>各组最大回撤的峰值与谷值日期</summary>{table(mdates)}</details>
<h2>6. 费用和延迟压力下，收益排序是否改变</h2>{result_table(stress,scenario=True)}<p>成本翻倍后，E0收益158.37%、回撤16.76%；E2收益99.88%、回撤19.43%。多延迟一观察，E0收益184.20%、回撤15.03%，E2为124.68%、19.79%。E0在三种情景均取得四组最高累计收益和胜率。延迟情景ED回撤13.63%低于E0，说明“原退出风险总更低”也不能一概而论。</p>
<h2>7. 结论与上一轮如何衔接</h2><p><b>在这段明确的半导体大趋势中，保留当前结构退出比普遍收紧更合适。</b>强趋势中的短期向下波动不必然意味着结构已破坏；更多退出没有稳定降低自主循环风险，反而切碎了长持有。不过原算法162.01%仍低于同期间被动199.00%，没有证明其在已知大牛市中创造超额收益。</p><p>上一轮半导体同一账户延续到2026年10月13日，E0收益77.58%、回撤32.29%；本轮到6月末为162.01%、16.59%。这不是改参数后的提升，而是窗口排除了后续走弱，且前缀完全相同。它说明原算法适合保留强趋势的证据增加了，也说明本轮不能回答怎样可靠判断牛市结束，更不能掩盖随后承受的大回撤。</p><p>本轮是单ETF、已知牛市开发案例；没有验证全行业个股、板块→个股选择、未来胜率、真实整手成交或更复杂资金账户。保留旧算法，24账户完成即收口，不增加倍数、缩放日期或继续寻参。</p>
<h2>8. 审计、数据和原始证据</h2><p>47冻结文件未变；12精确真实前缀、4上一轮信号恒等、24上一轮账户前缀恒等通过。398条成交独立重放24账户，现金/数量/净值与逐笔复利核账，最大净值差2.67e-15；9个同批入场账户通过。没有外部行情下载或微信操作。</p><p><a href="PROTOCOL.md">事前协议</a> · <a href="freeze.json">冻结与哈希</a> · <a href="inputs.json">数据口径</a> · <a href="results/v0/summary.csv">24账户总表CSV</a> · <a href="results/v0/audit.json">独立核账</a> · <a href="results/v0/prior-account-prefix-checks.csv">与上一轮前缀恒等</a> · <a href="charts/raw.png">原始量价</a> · <a href="charts/signals.png">收盘信号轨迹</a></p></main></html>'''
(R/'index.html').write_text(body)
print('Rendered report and three comparison figures')
