"""Concise saved-ledger report and audit bindings. No financial events."""
from pathlib import Path
from decimal import Decimal as D
from collections import Counter
import json
import month_runtime as M
P=M.HERE;O=P/'short_window_analysis'
def read(p):return M.read(p)
def money(n):return f'{D(n):,.2f}'
def pct(n):return f'{D(n)*100:.2f}%'
def main():
 M.guard();rr=read(O/'RESULTS.json')['rows'];dd=read(O/'DAILY.json');ll=read(O/'ALL_LAYERS.json');ee=read(O/'EVENTS.json');v=read(O/'VERIFICATION.json')
 names=read(P/'inputs/2022/metadata.json');cat=Path('/Users/bytedance/Documents/Codex/2026-11-01/task/market-permission-price-only-20261101/industry-coverage/run-v1/NODE_CATALOGUE.json');sectors={r['sector']:r['name'] for r in read(cat) if r.get('sector')}
 rows=['授权短窗连续结果（研究模拟；未改经济规则）',
 '四个原账户从各自Jan7/Jul4已核收盘接续，2022只到Jan12、2025只到Jul9。没有重置、旧日期重跑、Jan13配股或Jul10事件。原601916角色回转、中药失败、全部样本保留。',
 '', '累计口径：各自原起点100万元；2022 Jan4–12、2025 Jul1–9，各7个交易日。已实现=实际卖出净款−对应原买款及分摊买费；未实现=剩余库存估值−剩余含买费成本。股息/零股核销另列。',
 'arm | NAV | return | realized | unrealized | fee | gross two-sided turnover | exposure']
 for r in rr:
  q=r['pnl'];rows.append(' | '.join([r['arm'],money(r['NAV']),pct(r['cumulative_return']),money(q['realized_actual_sales_net_buy_and_sell_fees']),money(q['unrealized_mark_minus_remaining_net_buy_cost']),money(r['fees']),money(r['two_sided_gross_turnover']),pct(r['exposure'])]))
 rows+=['所有四账股息收入/应收/到账、零股核销均0；不表示以后无需处理权息。未平层贡献包括已卖部分，不能当成未实现：']
 for r in rr:
  q=r['pnl'];rows.append(f"{r['arm']}: closed positive {money(q['closed_layer_positive'])}, closed negative {money(q['closed_layer_negative'])}; open-layer contribution {money(q['open_layer_contribution'])}=partial realized {money(q['open_layer_realized_partials'])}+unrealized {money(q['unrealized_mark_minus_remaining_net_buy_cost'])}+open dividends {money(q['open_layer_dividends'])}.")
 rows+=['', '实际链条与代价：',
 '1. Jan7中药新买→Jan7收盘支持失败/CP1退出请求→Jan10开盘真实卖出：C10五股45.14万毛买款，含费已实现-11,415.35；C20两股19.14万，已实现-7,248.89。天士力C10仍获利304.89，不能把所有退出叫个股失败。',
 '   旧因果包已独审：Jan6合法，存在已知急跌反弹但并无规则失效被忽略。T+1/周末不能把Jan7收盘请求冒称Jan7实卖。',
 '   中药Jan10 repair_restored（未成熟），Jan11新price_advance后成熟；Jan12白云山重新获S/confirmed：C10 200股、C20 1200股，截止未实现-107.06/-620.66。没有禁重入或抹去原亏损。',
 '2. Jan10必要退出释放现金后，Jan11两档实际新买68.38万/62.90万；20%只限制健康旧仓机会性减持，不限制独立退出款/空闲现金投放。Jan11净值又下跌21,030.25/20,627.37，并非限速就全程小试。',
 '3. 601916两档均保留：Jul2 mobile/S100→Jul4筹资卖100，已实现+1.42；同开盘core/T500→Jul9仍持500、未实现+83.98；Jul7另加mobile/T500→Jul9筹资卖出、含费-8.03。core/mobile保护、池、费用和责任分别记，不能合并净量当等价。',
 '4. 2022截至Jan12 C20较C10财富多3,742.49、少双边换手414,201.40、少费用338.39；这是完整账户净差，不把少买五股当全部因果。其Jan12中药权重23.02%反而高于C10的17.30%。',
 '5. 2025首次实际限速分歧在Jul9：前收盘计划New316,009/198,284；实际健康旧仓毛卖313,131.36/196,754.57，实际毛买91,186.57/39,148.56。C20保留更多三七互娱，也少加世纪华通。',
 '   世纪华通累计贡献C20少1,890.72（主要剩余估值）；三七互娱多2,565.98；平安电工少710.84。全股票贡献差精确汇总为C20少28.71。它既减少迁移成本，又延迟新资金；不据此判C20胜。',
 '   20%限制按原决策批次计划毛市值，不是实际成交金额硬上限；价差可使实际毛卖偏离。部分卖出的保留仓贡献不可全算浮盈。',
 '', '逐日资本响应（买/卖为当天真实成交毛额；行业为当日收盘真实权重）：']
 for arm,days in dd.items():
  for d in days:
   top=d['industry'][0];rows.append(f"{arm} {d['day']}: expo {pct(d['exposure'])}, buy {money(d['buy_gross'])}, sell {money(d['sell_gross'])}, top {sectors.get(top['sector'],top['sector'])} {pct(top['weight'])}; close New {money(d['planned_New'])}, Carry {money(d['planned_Carry'])}.")
 rows+=['注意New/Carry为该收盘下一批许可，非已成交/结算资金；不可与当天卖额混同。', '', '实际首参与/追加/重入及退出：']
 for r in rr:
  arm=r['arm'];cc=Counter(z['entry_class'] for z in ll[arm]);rows.append(f"{arm}: actual buy-fill layers {r['all_layers']}, distinct funded stocks {r['actual_funded_stocks']}, first/add/reentry {cc['first']}/{cc['add']}/{cc['reentry']}; buy-fill/sell-fill receipts {r['buy_fill_receipts']}/{r['sell_fill_receipts']}; same-buy-day exit-request layers {r['same_buy_day_exit_requested_layers']}（请求非实卖）; terminal native buys/exits {r['active_native_buys']}/{r['active_native_exits']}, next-open intents {r['pending_intents']}.")
 rows+=['role/core-mobile与pool/probe-confirmed的完整买款、已实现、未实现、闭合正负见RESULTS与ALL_LAYERS；同股加仓按实际买入前全股数量，真正归零再买才算reentry。全样本保留，deterministic worst/best3仅作后视解释，不用于选择。',
 '', '技术与审计：',f"40状态×7会计差均0（280条断言，不是280独立样本）；库存股数桥、原始流水＋库存权益桥、四终态完整恢复一致。旧包254个文件按原件或明确归档副本校验一致。分析无金融事件。",
 '库存估值仍取同一原生as-of mark，不冒称第二套独立价格源。',
 f"新金融执行用同一run_month.py；四臂runner wall {sum(r['runner_seconds'] for r in rr):.3f}s（含状态保存与读取），分析复核另计。"]
 for r in rr:
  start='2022-01-07' if r['arm'].startswith('2022') else '2025-07-04';ev=[e for e in ee[r['arm']] if e['day']>start];tt={phase:sum(e['seconds'] for e in ev if e['phase']==phase) for phase in ('ACTION','OPEN','CLOSE')};rows.append(f"{r['arm']}: start {r['actual_start']}, end {r['actual_completed']}, wall {r['runner_seconds']:.3f}s, event(save+native) ACTION/OPEN/CLOSE {tt['ACTION']:.3f}/{tt['OPEN']:.3f}/{tt['CLOSE']:.3f}s.")
 rows+=['本次没有性能改代码；该计时含前后checkpoint/I/O，不能伪装纯投影耗时。',
 '当前止于授权截止，无工程失败；Jan13配股仍为后续显式接线门，未因当前没持仓跳过。后续仍有一般零股/G备用子集/部分mandatory升级等既有未支持分支，遇到须原子停。',
 '仍继承当前snapshot非PIT、日线OHLC/volume执行代理、未知分红支付不再投/权息代理限制；这7日结果不证明长期有效或实盘可执行。',
 '', '结论边界：支持“限速确实改变实际迁移节奏，必要退出与再参与仍运行”；否定“C20等于所有新股小仓、总换手很小或必然更好”；未知长期肥尾捕获/累计假启动损耗取舍。后续仅在审查后接续既有账户，不据本短窗临时调规则。']
 (O/'REPORT.txt').write_text('\n'.join(rows)+'\n')
 M.E.IO.write_json(O/'CONTINUATION_CHECKPOINTS.json',[{k:r[k] for k in ('arm','cursor','checkpoint','checkpoint_sha256','active_native_buys','active_native_exits','pending_intents')} for r in rr])
 M.E.IO.write_json(O/'BINDINGS.json',dict(policy_input_identity_sha256=M.P.sha(P/'POLICY_INPUT_IDENTITY.json'),source_runtime_sha256=M.P.sha(P/'month_runtime.py'),entry_sha256=M.P.sha(P/'run_month.py'),execution_grant_path=str(P/'grants/002_short_window.json'),execution_grant_sha256=M.P.sha(P/'grants/002_short_window.json'),old_archive_map_sha256=M.P.sha(P/'archives/grant001/ARCHIVE_MAP.json'),old_artifact_sha256=M.P.sha(P/'archives/grant001/ARTIFACT_SHA256.json'),name_catalogue=dict(path=str(cat),sha256=M.P.sha(cat)),no_strategy_change=True,no_future_financial_events=True))
 print('REPORT_READY',len(rr),'paths',v['event_states'],'saved-states')
if __name__=='__main__':main()
