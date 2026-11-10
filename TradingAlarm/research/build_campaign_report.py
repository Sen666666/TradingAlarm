import json,html
from pathlib import Path
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'results/sector-review';OUT.mkdir(exist_ok=True)
body='''<h1>账户级肥尾目标：持仓模型研究</h1><p>更新：2026-10-18。目标为一轮大行情中整个账户收益超过80%，并保留20%最大回撤研究目标；两者尚未被同时验证。</p>
<p><strong>结论：没有合格的高收益算法。低回撤来自较低实际投入，不能单独视作成功。</strong></p>
<p>模型以真实股份与现金运行：0.5%账户计划风险首次入场，初始4ATR止损；价格有利移动2个入场ATR后才能加仓，最多三层。无固定止盈。对比每日跟随高点上移的ATR退出与初始保护加两次收盘跌破200日均线退出。所有信号滞后执行，计入分红、拆分、汇率、手续费、最低佣金、整手和成交量约束。</p>
<p>风险翻倍情景明确将首次计划风险从0.5%提高到1%、总止损距离预算从4%提高到8%，属于提高风险的诊断，不是同风险超额收益。计划止损不保证成交价格，账户回撤仍可能超过20%。</p>
<p>重要修复：早期实现会在回撤10%之后完全禁止开仓、却只有达到16%才进入恢复流程，形成现金锁死。已修复并完整重跑；无效结果保留于campaign-v1/pre-fix-entry-lock。</p>
<p>现有组合前29组主要对照最好252交易日收益约34.32%，事后最低点到后续高点约45.51%。这些是事后统计，不能当作预先能识别的行情周期。</p>
'''
ledger=[]
for version in ['campaign-v1','campaign-v2','campaign-v3']:
 rows=json.loads((ROOT/f'results/{version}/results.json').read_text());ledger.extend([dict(version=version,**r) for r in rows])
 body+=f'<h2>{version}</h2><table><tr><th>方案</th><th>年化</th><th>最大回撤</th><th>最好252交易日</th><th>平均现金</th><th>订单数</th></tr>'
 for r in rows:
  body+='<tr>'+''.join('<td>'+html.escape(str(v))+'</td>' for v in [r['case'],f"{r['cagr']:.2%}",f"{r['max_drawdown']:.2%}",f"{r['best252_return']:.2%}",f"{r['average_cash_weight']:.1%}",r['orders']])+'</tr>'
 body+='</table>'
body+='''<h2>港股扩展与局限</h2><p>新增02845电动车及电池和03110恒生高股息，香港上市权益ETF从3只增至5只；全部来源池17只，其中本持仓模型只交易15只权益ETF。上市地点不等于资产经济敞口；02845与A股新能源有重叠。03110按发行人记录修正2018年9月每份分红1.51港元，采用100份保守交易单位，兼容已核实的历史100份与现行50份。</p>
<p>仍是事后挑选的存续ETF池，不是全市场历史股票池；港股行业覆盖有限。所有数据已被观察，现有结果都属于探索。已结束持仓的分红收益归因使用除息日汇率估值，而总账户净值使用真实支付日参考汇率与换汇费用；归因不是完整的已实现盈亏对账。</p>
<h2>下一步门槛</h2><p>不能用重复调参强行制造80%。需明确是否扩展到个股；若扩展，必须采用历史可投资股票池、公司行为、停牌与涨跌停数据，并加入实际交易摩擦。无论是否扩展，都需要预先定义行情周期、保存所有尝试、验证跨阶段迁移，并做前瞻观察。</p>'''
(OUT/'campaign-trials.json').write_text(json.dumps(ledger,indent=2))
(OUT/'campaign-report.html').write_text('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>账户级肥尾策略研究</title><style>body{font:16px/1.7 system-ui;max-width:1100px;margin:40px auto;padding:0 24px;color:#24313d}table{border-collapse:collapse;width:100%;font-size:14px}th,td{padding:8px;text-align:left;border-bottom:1px solid #ddd}strong{color:#9a3412}</style>'+body+'</html>')
print(OUT/'campaign-report.html')
