"""Build the final research report and machine-readable rule/audit bundle."""
import hashlib
import html
import json
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'results/portfolio-v3'
LABELS={'frozen_trend_guard':'趋势＋仓位＋情景预算','trend_without_guard':'取消15%/20%保护（保留情景预算）',
        'passive_same_allocation':'无趋势过滤，保留情景预算','passive_without_budget':'无趋势过滤，无情景预算',
        'high_cost':'提高交易和换汇费用','delay_one_session':'额外延迟1个交易日','cost_and_delay':'高费用＋额外延迟2日','small_capital':'10万元账户',
        'recomputed_market_shock':'注入市场冲击并重算交易','shock_high_cost_delayed':'市场冲击＋高费用＋延迟成交'}

def table(records):
    df=pd.DataFrame(records)[['case','cagr','max_drawdown','realized_vol','average_cash_weight']]
    df['case']=df['case'].map(lambda s:LABELS.get(s,s))
    for c in df.columns[1:]:df[c]=df[c].map(lambda n:f'{n:.2%}')
    df.columns=['场景','年化收益','最大回撤','实际年化波动','平均现金比例']
    return df.to_html(index=False,escape=True,border=0)

def main():
    result=json.loads((OUT/'portfolio-results.json').read_text())
    diagnostic=json.loads((OUT/'diagnostics.json').read_text())
    protocol=json.loads((ROOT/'portfolio-protocol.json').read_text())
    protocol['source_hashes']={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in
                              ['portfolio_engine.py','portfolio_data.py','run_portfolio.py','portfolio_diagnostics.py']}
    protocol['validation_tests']=29
    protocol['decision']='Freeze v3 for paper evaluation. Do not claim proven alpha, a guaranteed25% drawdown ceiling, or production execution readiness.'
    protocol['changes_after_v2']='Risk-budget derivation only; then corrected zero-volume placeholder execution. Trend/vol/correlation windows unchanged.'
    (OUT/'protocol.json').write_text(json.dumps(protocol,ensure_ascii=False,indent=2))
    (ROOT/'portfolio-protocol.json').write_text(json.dumps(protocol,ensure_ascii=False,indent=2))
    r=result['records'][0]; s=result['stress']; control=diagnostic['controls']['ex_post_risk_matched_passive']
    interval=diagnostic['controls']['paired_mean_difference_diagnostic']['block_bootstrap_95pct_interval']
    rules=[
      ('投资池','境内：510300沪深300、512480半导体、512010医药、512660军工、512800银行、515030新能源车、518880黄金、511010国债。香港上市：02800盈富、02820中国生物科技、03033恒生科技。港股上市地点不代表仅持有香港公司；不使用杠杆、反向ETF或个股。'),
      ('信号数据','用拆分与分红处理后的总回报收盘序列计算信号，真实原始价格执行。每个标的先积累200个本地交易日；组合风险计算另需60个共同交易日。只用已结束交易日数据。'),
      ('入场','连续两日收盘高于200日简单均线，且最新63日收益大于零，进入可持有状态。每周第一个共同交易日按此前收盘状态配置；不预测反转，不抄底。'),
      ('退出','连续两日收盘低于200日均线，下一可成交开盘退出，不等周度调仓。未满两日不因单日下跌退出。'),
      ('趋势温度','冷＝未进入可持有状态；热＝可持有且63日收益为正；温＝仍可持有但63日收益非正。温度只是现有状态的展示，不再拟合七档阈值，不用相对排名强迫买入下跌资产。'),
      ('基础仓位','对可持有ETF按过去60个共同交易日、人民币口径收益的波动率倒数分配；年化波动率下限5%，避免低波动债券无限放大权重。先归一化，再执行下面各项上限；被削减的权重留作现金，不重新分配。'),
      ('集中度','单只ETF目标上限20%，股票ETF合计70%，香港上市ETF合计30%。黄金、国债同样受单只20%限制。目标上限在调仓时执行，期间市值可能漂移。'),
      ('行业重叠','预设科技、医疗、工业、金融、消费材料及其他风险组，每组保守暴露上界35%。宽基与跨行业恒生科技ETF按全部权重计入每组；A股医药和香港生物科技合并计入医疗；新能源车同时计入相关组。若任一组越界，同比缩减所有股票仓位。这是保守上界，不是假装掌握历史成分股。'),
      ('相关性','过去60个共同交易日相关系数≥0.75的ETF连接成组；每个连通组目标权重≤35%。组合协方差采用50%样本矩阵＋50%对角矩阵；预计年化波动率超过12%时同比降仓，不向上加杠杆。'),
      ('剩余亏损空间','E为上一交易日组合净资产，H为全程历史最高净资产。压力预算B＝0.8×max(0,1−0.75H/E)。对候选仓位计算L＝30%×人民币股票权重＋37%×港币股票权重＋10%×黄金权重＋5%×国债权重。若L>B，将全部ETF仓位乘B/L。每天检查实际收盘持仓，越界则下一可成交开盘减仓；风险减仓不新增持股。'),
      ('回撤保护','风险观察期内回撤15%后减半，恢复该期高点才解除；20%后退出。完全空仓满20个共同交易日，再到周度配置日才可重启观察期。全程H从不重置，剩余亏损空间仍按全程高点计算；若实际全程回撤已达25%，预算归零，必须人工复核后才能启动新版本。'),
      ('下单顺序','每日处理拆分、应收分红与到账，再依次执行风险退出、信号退出和周度配置；先卖后买，不透支。境内100份一手；02800为500份，02820为50份，03033为200份。单日成交不超过此前20日平均成交份额的1%；不足则分批，零成交量日不假设成交。真实应用优先使用可控制价格的订单，不能保证开盘价成交。'),
      ('成本与现金','本研究基础费用单边15基点，港股另计10基点换汇；最低费用假设境内5元、港股18港元，须替换为真实券商费用。现金收益记零，港币用延迟可获得的参考汇率计价，分红到账前不能使用。两地资金须提前备妥；真实转账、结算与价差仍需落地验证。')]
    body='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>ETF趋势组合：规则与研究结论</title><style>body{font:16px/1.75 system-ui,sans-serif;max-width:1100px;margin:36px auto;padding:0 24px;color:#223340;background:#fbfcfd}section{background:white;border:1px solid #dfe5ea;border-radius:10px;padding:24px;margin:24px 0}h1,h2,h3{line-height:1.4}table{border-collapse:collapse;width:100%;font-size:14px;white-space:nowrap}td,th{padding:9px;border-bottom:1px solid #e5e9ed;text-align:right}td:first-child,th:first-child{text-align:left}.scroll{overflow:auto}.warning{background:#fff4dd;border-left:5px solid #b88022;padding:18px}img{width:100%;height:auto}.muted{color:#526574}a{color:#176280}code{overflow-wrap:anywhere}</style><h1>A股／港股ETF：趋势＋仓位管理规则 v3</h1><p class="muted">2026-10-17研究冻结 · 回测截至2026-10-16 · 人民币记账 · 目标最大回撤25%，不是保证</p>'''
    body+=f'<p class="warning"><strong>结论：可以作为冻结规则的模拟运行候选，不足以证明值得直接实盘。</strong>本样本年化收益{r["cagr"]:.2%}，最大回撤{r["max_drawdown"]:.2%}；收益较低，且对少数上涨日依赖明显。与相同实际风险的被动组合相比优势很小。研究结果不支持继续为提高收益反复调参。严重回撤后，剩余亏损空间约束可能使仓位长期很低、错过反弹；压力净值图显示了这一代价。</p>'
    body+='<section><h2>方法依据与迭代纪律</h2><p>参考长期均线／时间序列动量、海龟式纪律与波动率仓位管理的研究方法，但本规则是这些思想的具体组合，不能借大师名声视作已验证。趋势条件在本轮保持200日均线、63日动量不变。v1缺少行业与执行细节；v2补齐后复合跳空回撤26.34%，超过目标；v3仅按25%风险目标推导剩余亏损空间约束。随后修复了零成交量占位行情仍可成交的问题，保留了修正记录。</p><p>全部历史已被观察，均属探索性研究；保留所有版本和不利结果，不将复用数据重新命名为样本外。港股科技和生物科技按覆盖缺口加入，非按回测优胜挑选。</p></section>'
    body+='<section><h2>明确执行规则</h2>'+''.join(f'<h3>{i+1}. {html.escape(title)}</h3><p>{html.escape(text)}</p>' for i,(title,text) in enumerate(rules))+'</section>'
    body+='<section><h2>回测与对照</h2><p>2022-01-03至2026-10-16，基础账户100万元；最后一行为10万元账户。收益含表列费用和模型中的分红，不含个人税务或现金利息。</p><div class="scroll">'+table(result['records'])+'</div><img src="portfolio-overview.png" alt="组合净值、回撤及现金仓位图">'
    body+=f'<p>事后把无情景预算被动组合缩至同样的实际波动率：年化收益{control["cagr"]:.2%}，最大回撤{control["max_drawdown"]:.2%}。这只是归因对照，缩放比例使用了全期数据，不能作为事前交易规则。配对20日块重采样得到的年化日均收益差95%区间为[{interval[0]:.2%}, {interval[1]:.2%}]；它仍受到模型选择影响，不构成可靠超额收益证据。</p></section>'
    body+='<section><h2>压力测试：通过了什么，没有证明什么</h2>'
    body+=f'<p>对每个历史收盘持仓施加人民币股票−30%、港股股票−30%并叠加港币−10%、黄金−10%、国债−5%的冲击，最坏相对历史高点回撤{s["worst_gap_from_prior_peak"]:.2%}。再选择脆弱持仓后的下一共同交易日，将冲击写入原始价格与汇率，重新计算所有信号、仓位、分批成交与保护机制：</p><div class="scroll">'+table(diagnostic['market_path_stresses'])+'</div><img src="portfolio-stress.png" alt="重新计算信号后的市场冲击回撤图">'
    body+=f'<p>移除收益最高的10个交易日后，累计收益为{s["remove_best_10_days"]["total_return"]:.2%}。1000次已实现策略收益的20日块重采样中，有{s["bootstrap"]["fraction_drawdown_beyond_25pct"]:.1%}的样本超过25%回撤；这个比例不是未来超限概率，因为该检验没有在每条重采样市场路径上重算策略。不能隐去这些不利证据，也不能把25%宣传成止损保证。</p><p>基础历史路径没有触发15%/20%保护，所以取消该保护的历史结果相同。保护逻辑由合成冲击与核算测试验证，不应把未发生的保护效果计作历史收益。</p></section>'
    body+='<section><h2>行业约束与执行核验</h2>'
    body+=f'<p>已逐项核验{diagnostic["decision_constraints_verified"]}次配置决策的单只、股票合计、港股、相关组、行业上界和信号时间约束。期间价格漂移后，最高行业保守上界约{max(diagnostic["realized_industry_upper_bound_maxima"].values()):.2%}；35%是目标权重上限，不是每个时刻的市值硬上限。29项测试覆盖未来数据隔离、分红到账、拆分、整手与现金约束、部分成交、零成交量、情景预算和高点重置规则。</p><p>数据边界：当前存续ETF样本存在选择偏差；部分公司行动来自供应商表，关键拆分已核对公告，但未做完整审计。恒生科技上市首日开盘异常保留在原文件，位于回测执行期之外，信号不使用该开盘价。研究没有完整还原历史盘口、涨跌停队列、两地转账结算或每个投资者的市场准入。</p></section>'
    body+='<section><h2>从研究到实际使用</h2><p>建议先用这套冻结规则做模拟账户，并记录每次信号、目标仓位、预期与实际成交差异。短期模拟只验证数据和执行，不能证明未来盈利。除数据错误、基金投资范围变化或风险约束失效外，不因几个月收益落后改参数；任何修改另建版本，保留旧版对照。</p><p>实盘前必须核实券商准入、真实费用、两地资金与汇兑安排，以及全部公司行动。这个报告完成的是明确规则、历史验证和风险评估，不是生产系统或收益承诺。</p></section>'
    body+='<section><h2>来源与复现</h2><p><a href="https://w4.stern.nyu.edu/facdir/lpederse/papers/TimeSeriesMomentum.pdf">时间序列动量原论文</a> · <a href="https://www.tradingblox.com/originalturtles/originalturtlerules.pdf">原始海龟规则</a> · <a href="https://mebfaber.com/wp-content/uploads/2016/05/SSRN-id962461.pdf">Faber长期趋势配置研究</a> · <a href="https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf">回测过拟合研究</a>。这些研究支持方法审查，不验证本组合的收益。</p><p><a href="protocol.json">完整冻结协议</a> · <a href="portfolio-results.json">全部结果</a> · <a href="diagnostics.json">归因与市场路径压力</a> · <a href="portfolio-frozen_trend_guard-path.csv">每日净值及权重</a> · <a href="portfolio-frozen_trend_guard-orders.json">模拟交易</a> · <a href="portfolio-data-audit.json">公司行动清单</a> · <a href="validation-correction.json">成交校正记录</a></p><p>项目根目录运行：<code>python3 TradingAlarm/research/run_portfolio.py</code>，然后 <code>python3 TradingAlarm/research/portfolio_diagnostics.py</code>。图表：<code>TradingAlarm/research/.venv/bin/python TradingAlarm/research/plot_portfolio.py</code>；报告：<code>python3 TradingAlarm/research/finalize_portfolio_report.py</code>。</p></section></html>'
    (OUT/'strategy-report.html').write_text(body)
    (OUT/'rules.json').write_text(json.dumps(dict(version=protocol['version'],rules=[dict(title=t,rule=v) for t,v in rules],decision=protocol['decision']),ensure_ascii=False,indent=2))
    print(OUT/'strategy-report.html')

if __name__=='__main__':main()
