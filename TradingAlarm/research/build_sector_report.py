"""Build reviewable research evidence from retained result files."""
import os,json,html
from pathlib import Path
ROOT=Path(__file__).resolve().parent
os.environ.setdefault('MPLCONFIGDIR',str(ROOT/'.venv/plot-cache'))
os.environ.setdefault('XDG_CACHE_HOME',str(ROOT/'.venv/plot-cache'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd
OUT=ROOT/'results/sector-review';OUT.mkdir(exist_ok=True)
fig,axes=plt.subplots(2,1,figsize=(11,7),sharex=True)
for version,name,label in [('sector-v3','none-top0-passive','Diversified passive'),('sector-v4','pooled_no_buffer','Sector rotation'),('sector-v4','pooled_rank_buffer','Rank retention')]:
 p=pd.read_csv(ROOT/f'results/{version}/{name}-path.csv',index_col=0,parse_dates=True)
 axes[0].plot(p.index,p.nav,label=label);axes[1].plot(p.index,p.drawdown*100,label=label)
axes[0].set_ylabel('NAV after costs');axes[0].legend();axes[1].set_ylabel('Drawdown (%)')
for ax in axes:ax.grid(alpha=.2)
fig.tight_layout();fig.savefig(OUT/'comparison.png',dpi=150);plt.close(fig)
sections=[];ledger=[]
for version in ['sector-v1','sector-v2','sector-v3','sector-v4']:
 data=json.loads((ROOT/f'results/{version}/results.json').read_text());ledger.extend([dict(version=version,**r) for r in data])
 rows=''.join('<tr>'+''.join('<td>'+html.escape(str(v))+'</td>' for v in [r['case'],f"{r['cagr']:.2%}",f"{r['max_drawdown']:.2%}",f"{r['realized_vol']:.2%}",r['orders'],f"{r['average_cash_weight']:.1%}"] )+'</tr>' for r in data)
 sections.append(f'<h2>{version}</h2><table><thead><tr><th>版本</th><th>年化</th><th>最大回撤</th><th>实际波动率</th><th>订单</th><th>平均现金</th></tr></thead><tbody>{rows}</tbody></table>')
stress=json.loads((ROOT/'results/sector-v4/market-stress.json').read_text())
(OUT/'trial-ledger.json').write_text(json.dumps(ledger,indent=2))
body='''<h1>TradingAlarm 趋势与仓位策略：深入研究记录</h1>
<p><strong>当前结论：未找到有充分证据支持的高收益算法，不启用实盘。</strong>研究目标为组合最大回撤20%，并非保证。所有现有历史都已用于探索，不存在可重新命名为“未见测试集”的部分。</p>
<p>区间：2022-01-03 至 2026-10-16。人民币基准，初始100万元，双边每次15基点、港股另加10基点换汇成本，佣金最低值、整手及历史成交量限制。现金利息假设为零。</p>
<img src="comparison.png" alt="净值及回撤对照">
<h2>可保留的机制与应否决的结论</h2>
<ul><li>加入酒、传媒、有色、煤炭，覆盖从11只增至15只ETF；改善有限，不是完整历史可投资市场。</li><li>快信号使持仓缩短，但换手与亏损增加。平均持仓两周仅为用户提供的参考假设，未验证为作者完整策略。</li><li>长期动量、波动率调整和上涨天数都未表现出可靠增量；上涨天数仍属价格因子，不应冒称财务质量。</li><li>排名缓冲改善交易行为：入选前三后，仍符合趋势且排名在前六时允许继续持有，空位按排名补齐。</li><li>排名缓冲年化2.99%，高成本1.17%，延迟成交1.74%；仍不足以认定高收益或稳健优势。</li><li>去掉仓位情景预算使轮动年化约4.96%，被动也达到4.83%；压力回撤约32%，不能视为满足20%目标的优化。</li></ul>
<h2>研究方法与外部依据</h2>
<p><a href="https://onlinelibrary.wiley.com/doi/full/10.1111/0022-1082.00146">行业动量研究</a>提供板块排名的研究动机，并不直接证明中国ETF有效。
突破规则借鉴公开海龟规则中的通道思想；这里使用收盘确认、次日执行，没有复刻海龟完整的期货组合、加仓和风险单位系统。
<a href="https://www.aqr.com/Insights/Research/Journal-Article/Momentum-Crashes">动量崩溃研究</a>强调风险状态与反转风险；其多空策略证据不能直接套用到本研究的只做多ETF。</p>
<p>先声明小型机制对照，再保留全部结果。风险匹配通过将已实现收益按全样本波动率缩小，只作归因诊断，不能充当可交易规则。分块重采样区间同样是探索性结果，不能抵消多轮模型选择偏差。</p>
<h2>适用范围与尚未完成的证据</h2>
<p>A股测试含多个行业，港股仅3只权益ETF；港股子组合还含境内黄金/债券，因此不构成纯港股账户验证，更无法证明港股行业排名能力。当前池为事后挑选的存续ETF，缺少历史退市基金与真实时点成分。公司行为仅做必要核查，未完成逐项官方审计；券商实际费用、市场准入、结算和价差仍需验证。</p>
<p>尚未完成：更广泛港股覆盖、完整跨年份迁移验证、用户收益验收标准、真正前瞻观察。不能通过继续调参制造一个必然成功的策略。</p>'''
body+='<h2>完整行情冲击</h2><p>冲击日期 '+html.escape(stress['shock_date'])+'；权益价格永久下调30%、黄金10%、债券5%、港币汇率10%，重新计算信号和成交。日期根据已观察持仓选择，是逆境测试而非概率预测。</p>'
for r in stress['records']:body+=f"<p>{html.escape(r['case'])}：最大回撤 {r['max_drawdown']:.2%}</p>"
body+=''.join(sections)
(OUT/'report.html').write_text('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>TradingAlarm 深入研究</title><style>body{font:16px/1.7 system-ui;max-width:1120px;margin:40px auto;padding:0 24px;color:#24313d}img{width:100%}table{border-collapse:collapse;width:100%;font-size:13px}td,th{padding:8px;border-bottom:1px solid #ddd;text-align:left}h2{margin-top:36px}strong{color:#9a3412}</style>'+body+'</html>')
print(OUT/'report.html')
