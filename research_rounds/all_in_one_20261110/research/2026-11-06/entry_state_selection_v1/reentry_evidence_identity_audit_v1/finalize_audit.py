"""Final read-only consistency checks and documentation for the saved-event audit."""
from pathlib import Path
from collections import Counter
import csv,json,hashlib
O=Path(__file__).resolve().parent
R=O.parent
J=R/'independent_channel_joint_economic_v1'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def rows(n):return list(csv.DictReader((O/n).open()))
def dump(n,x):
 with (O/n).open('x') as f:json.dump(x,f,ensure_ascii=False,indent=2);f.write('\n')
events=rows('ALL_ACTUAL_BUY_EVENTS.csv')
re=rows('PRICE_REENTRY_EVENTS.csv')
counts={}
for y in ('2022','2024'):
 z=[r for r in re if r['year']==y]
 conf=Counter()
 for r in z:
  c=json.loads(r['market_confirmed_at'])['day'] if r['market_confirmed_at'] else None
  conf['UNCONFIRMED_AT_ENTRY' if not c else 'AFTER_PREVIOUS_EXIT' if c>r['prev_full_exit_day'] else 'SAME_DAY_CLOSE_AFTER_OPEN' if c==r['prev_full_exit_day'] else 'BEFORE_PREVIOUS_EXIT']+=1
 assert not conf['BEFORE_PREVIOUS_EXIT']
 counts[y]=dict(
  confirmation_clock=dict(conf),
  receipt_type=dict(Counter('ROOT_BIRTH' if json.loads(r['price_root'])[2]==r['signal_day'] else 'STRICT_NEW_FRONTIER_AFTER_BIRTH' for r in z)),
  I_epoch_by_immediate_transition={tr:dict(Counter(r['I_epoch_vs_previous_buy'] for r in events if r['year']==y and r['transition']==tr)) for tr in ('PRICE->PRICE','AB->PRICE','PRICE->AB','AB->AB')})
same_i=[r for r in events if r['I_epoch_vs_previous_buy']=='SAME']
with (O/'SAME_I_EPOCH_DISTINCT_EVENTS.csv').open('x',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(events[0]));w.writeheader();w.writerows(same_i)
dump('CLOCK_AND_TRANSITION_SUMMARY.json',counts)
contracts=[
 Path('/Users/bytedance/Documents/Codex/2026-11-04/task-3/entry_quality/e0_i_structure_redesign_v1/V5_EXECUTION_CONTRACT.md'),
 Path('/Users/bytedance/Documents/Codex/2026-11-04/task-3/entry_quality/e0_i_structure_redesign_v1/V5_INHERITANCE_CONTRACT.md'),
 R/'epoch_v3/rolling_prebreak_v31/check_epoch_semantics.py',
 Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/continuous-protection-lines-20261028/code/model.py'),
 R/'selection_entry_diagnosis_v1/cp1_signal_mechanism_v1/READOUT.md',
 Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-local-entry-reentry-20261026/RULES.md')]
ch={str(p):sha(p) for p in contracts}
dump('CONTRACT_SOURCE_HASHES.json',ch)
report="""# 全量重入身份审计：旧 PRICE 根重复发初仓未被证实

## 结论及边界

在保存的 2022、2024 两个研究窗口内，“一次旧 PRICE 根确认重复授权多个新初仓”不存在于全量实际 buy_core 事件。完整 root=(sid,source_identity,root_birth)、receipt=(root,signal_day)、probe parent 的跨实际初仓复用均为 0。不是仅在共同股票样本中得到此结果，后来 UNKNOWN 的股票和未闭合回合也已纳入。

这里“实际”严格指原保存账中发生的条件全填代理 buy_core/sell_all，不是券商真实订单、ACK 或 fill。两个窗口分别从执行 FLAT 开始，彼此不是连续账户；窗口首 BUY 不能被称为退出后的重入，也不能证明窗前从未持有同一旧根。2022 UNKNOWN 与 2024 独立初始化之间不能推断责任释放。跨窗同一 canonical 身份的重复检查仅为附带身份检查，不是连续执行检验。

未运行经济回测、consumer、参数搜索、过滤后或反事实收益。未改策略、授权、原账及任何既存输入。没有提出新的“修复公式”，因为待修复的 PRICE 旧根复用前提已被实际全量事件反证。

## 1. 全量账与真正全卖

|窗口|登记|实际 BUY|AB / PRICE BUY|真正 sell_all|sell_add（不算空仓）|
|---|---:|---:|---:|---:|---:|
|2022|4127|4102|1707 / 2395|3677|233|
|2024|1950|1934|736 / 1198|1826|159|

已按每个 round 的原 action 行序独立累加数量；每笔 sell_all 前量等于卖量、卖后为 0，每笔 sell_add 后仍有仓。下一实际 BUY 的前一实际回合均已真正 sell_all。尾部 2023/2025 退出直接取原保存账，未重跑。

|立即前一实际 BUY → 当前 BUY|2022|2024|
|---|---:|---:|
|PRICE → PRICE|861|141|
|AB → PRICE|550|74|
|PRICE → AB|621|131|
|AB → AB|614|84|
|窗口首 BUY|1456|1504|

“repeat PRICE”指此前任何回合曾实际 PRICE BUY，可能夹有 AB，不等于“立即前轮 PRICE→PRICE”。该数为 1102 / 150。2022 其中 1098 次换 I epoch、4 次不换；2024 全部换 I epoch。4 次相同旧 I epoch 的 PRICE 重入也全部是新价格 root，不是旧价格根复用。

另有 2022 的 4 次 PRICE→AB 未换旧 I epoch（002465 8/9、300130 7/20、600008 8/23、601512 7/28 信号）；它们用退出后新的 A/B event_id，信号时没有 active PRICE root。此为跨 owner 合同差别，不能把“PRICE 没复用”扩写成“所有 owner 都强制新 I epoch”。是否另外限制这些新 AB 事件属于另一个策略问题，本审计未证明其为重复授权漏洞。完整 8 例见 SAME_I_EPOCH_DISTINCT_EVENTS.csv。

## 2. PRICE 重入的价格根、receipt 与确认时钟

|前面已有任一 owner 实际 BUY 的 PRICE 入场|2022|2024|
|---|---:|---:|
|总数|1411|215|
|新 root 出生日在前次 sell_all 日期后|1408|215|
|同日，但 OPEN 退出后 CLOSE 新根|3|0|
|root 出生早于前次全卖|0|0|
|新根生日即信号|1174|193|
|新根出生后，后续严格新 frontier 信号|237|22|
|信号时 CONFIRMED|1186|164|
|信号时 PROBE / PROBE_AMOUNT_UNKNOWN|219 / 6|50 / 1|

所有已 CONFIRMED 重入的确认钟也在前次退出之后（2022 的 3 例为同日 CLOSE）。没有一例借用退出前的旧 PRICE 确认钟重新开初仓。尚未 CONFIRMED 的 225 / 51 例是合同本来允许的价格 probe，不能悄悄改成“先再次量价 CONFIRMED 才准首探”。

两窗的窗口首 PRICE BUY 为 984 / 983，其中 root 早于窗口起点 286 / 162；这些是窗内首次参与，不是“上轮退出后旧根复活”。

独立可核验指来源、身份、形成时间和消费可查，不表示这些价格/量价观察在统计学上独立。新 root 的 formation 窗口仍可能含退出前已知价格，CONFIRMED 也可在根生日因已知形成区间直接成立；本审计未把“所有量价都必须发生在退出后”偷加为现有约束。

## 3. 三笔同日根：不能只比日期

保存的 PRICE 顺序号是 OPEN target=20、proxy fill=30、terminal=40、CLOSE receipt=100。不是实际券商时刻。

- 002428 云南锗业：旧根 2021-11-24，2022-01-25 CLOSE 100 永久退役；1/26 OPEN terminal 40 全卖；1/26 CLOSE 100 出生并确认新根、新 receipt；1/27 OPEN 20 固定新 Q=1900，30/40 全填及完成。旧 I epoch 69 → 71。
- 688105 诺唯赞：旧根 2022-11-04，11/28 CLOSE 100 退役；11/29 OPEN terminal 40 全卖；11/29 CLOSE 100 新生并确认；11/30 OPEN 20 固定 Q=219，30/40 全填及完成。旧 I epoch 11 → 13。
- 688630 芯碁微装：前轮是 5/12 的 B_STOCK_BIRTH_DURING_SECTOR 授权，6/23 OPEN 原 sell_all；6/23 CLOSE 新生并确认 PRICE root；6/24 OPEN 固定 Q=259 并全填。旧 I epoch 7 → 9。AB 退出只有原 OPEN action，不伪造 PRICE book 或券商 ACK。

完整 event_id、root/source、receipt、前后原账、orders/events 见 CASE_CLOCKS_COMPLETE.json。

## 4. 消费、UNKNOWN、q0 与同信号优先级

- 全部 3593 个实际 PRICE probe 的 root、receipt、parent 唯一；target 事前登记一次，Q 与本轮实际 proxy F 一致。卖出不把旧 parent 变成新 parent。
- UNKNOWN 共 445 / 113，其中已经 BUY 的 425 / 108；PRICE UNKNOWN 为 353 / 86，其中已 BUY 的 340 / 83。逐一检查之后的新登记及实际 BUY，均为 0。已有 PRICE book 最终仍 unknown 且 owner_locked；未买 UNKNOWN 无执行 book 也未释放成可买。FROZEN_RESPONSIBILITIES 的 book 是冻结调用前快照，最终状态以 EXECUTION_BOOKS 为准。
- PRICE q0 是 3 / 9 个 PRECHECK_Q0_NO_SUBMIT，均无 parent、无订单、无 BUY，不是“submitted zero fill”。其中 1 / 3 后来以同 root 新 receipt 首次实际成功：300953 2022-05-20 信号 q0 后 6/2 新证、6/6 买；300474 2024-09-30 q0 后 10/18 新证；688213 10/18 q0 后 11/7 新证；688116 11/11 q0 后 11/20 新证。不是同 root 两次已买。
- 全部原始 PRICE 信号共 37456 条逐条与同日 AB_DECISION/OFFER/实际账对照。合法 AB 优先抑制 PRICE 为 309 / 408；没有同日双初仓、没有 legal AB 被 PRICE 反抢。被选中的 AB 后来没买有 3 / 1 例（600621、603259、600282、688778），均未回退消费旧 PRICE 票。详细见 SAME_SIGNAL_AB_PRICE_CONTROLS.csv。
- 本数据只有 conditional full-fill proxy；没有真实 submitted-zero、partial、cancel ACK 或 latefill 证据。不能用 q0/no-submit 冒充真实重试验证。

## 5. 正反例保留，不计算新收益

以下“正/负”仅复述原账结果，不计算过滤收益，也不暗示新证必然有利：

- 永和 605020：2022-07-11 前轮全卖，7/15 新 root、新确认、新 receipt，7/18 新 Q=600 买，原回合为正。
- 巨轮 002031：2022-02-25 前轮 AB 全卖，6/13 新 PRICE root，6/14 Q=12600 买，原回合为正；8/12 全卖后，12/14 又是另一新 root，12/15 Q=8100 买，原回合亦为正。
- 2024 杭钢 600126：11/25 前轮全卖，12/11 新生 root 尚为 PROBE，12/12 Q=4700 买，2025-03-25 全卖，原回合为正。要求初探先 CONFIRMED 是新增限制，会改变这个真实路径；不是修复旧根复用。
- 2024 银轮 002126：11/27 全卖，12/25 新 root/新确认，12/26 Q=1200 买，2025-03-03 全卖，原回合为正。
- 力鼎 605118：2022-08-15 前轮 AB 全卖，8/22 新 root/新确认、新 I epoch，8/23 Q=1400 买，8/29 全卖，原回合为负。新证、身份无复用仍可能失败。

因此不禁洗出后再追高，本来已是 PRICE 的行为；再次写“退出后新证”并不能据此称作新的实质机制或已证亏损修复。

## 6. 与现有合同的必要区别（只读现源）

1. PRICE 市场根：independent_channel_probe_preflight_v1/core.py:18–38 先旧 S 失效并永久清根，仅严格新 Close frontier 发 receipt；40–61 以 C>prior20High 建新 root，确认使用冻结量价 credit。joint_engine.py:120–142 把 receipt CLOSE100 绑定次 OPEN；181–200 全卖并释放执行状态；250–254 旧根退役。
2. PRICE 执行：execution_book.py:242–258 拒绝旧/已消费/非严格新 frontier 票，并要求解锁/完成之后新证；301–325 一 root 一 probe parent，固定 Q；330–348 补余量仍是同 parent。joint_engine.py:285–382 决策前 OPEN、持仓 CLOSE、再选新信号，合法 AB 优先。全量实际事件检查与这些合同一致，不靠源码推断替代证据。
3. V5：V5_EXECUTION_CONTRACT.md:9–26 已分清 UP slot、固定 Q/F、真实正 fill 单调消费和未知责任；101 明确“同 parent 续余量”不重套当日 fresh CP；111–115 及 V5_INHERITANCE_CONTRACT.md:44–61 才要求新 ADD 的 CP 晚于完成/必要退出解锁且有当前健康认证层。V5 的 UP/structure identity 不等于 PRICE root。当前 PRICE submit_remaining 比 V5 同 parent 续单多要求 unlock 后新 receipt，但本历史无真实 partial/zero，无法从本账评估差异。不能声称 V5 已原样要求每个续单都等新 CP，也不能声称固定 Q/F 与禁止旧票复活是新发明。
4. E3.1：epoch_v3/rolling_prebreak_v31/check_epoch_semantics.py:24–27 原 I_entered 建 I 根；46–51 首突破才冻结基准；60–62 后续日价格再推进且净 signed amount>0 才确认。35–55 有新底、收复、回撤再起子事件。它不是 PRICE 无 I 门的 root/receipt，更不是已完成的订单消费协议。把“再推进确认”改名不能成为新机制。
5. 原 CP1：continuous-protection-lines-20261028/code/model.py:30–38 来源/I有效性及 SEEK 重锚；40–49 严格新 frontier 才累计 credit、发新 receipt，然后重锚。该市场 receipt_consumed 不是账户 fill 消费。另一个明确已否决的 CP 观察基准提案见 selection_entry_diagnosis_v1/cp1_signal_mechanism_v1/READOUT.md:43–52：合法空仓首 fresh CP 定基准，下一张新 CP 先评估旧基准再重置、旧票不复活。此处不将它冒充无法唯一定位的“shadow 首合法τ”源，也不复活被否决提案。
6. LER 的原 RULES.md 已有退出完成后新局部 receipt 可再入，不固定禁重试。它依赖 E0、3观察休整和昨日 high 等另一套形成条件，不能说与 PRICE 完全相同，也未在本轮重跑或扩展。

## 7. 文件、复核与运行边界

- audit_saved.py：只读保存账/市场 parquet 的事件审计，禁止导入 consumer，输出只写本新研究目录；同名输出用 x 模式防覆盖。
- ALL_ACTUAL_BUY_EVENTS.csv：6036 个完整初仓事件，含四类 owner 转移、前全卖、市场/执行身份与时钟。
- ALL_ACTUAL_ACTION_SEQUENCE.csv：14258 个原 action 的数量流水，单列 sell_add 与真全卖。
- PRICE_REENTRY_EVENTS.csv：全部 1626 个 PRICE 重入，包括后来 UNKNOWN。
- UNKNOWN_LOCK_ASSERTIONS.csv：558 个逐一锁责任检查。
- Q0_FRESH_RECEIPT_FIRST_USE.csv：12 个无提交 q0 与后续首次成功。
- SAME_SIGNAL_AB_PRICE_CONTROLS.csv：37456 个 PRICE 信号的同日对照。
- CASES.csv / CASE_CLOCKS_COMPLETE.json：要求的正反例和三笔同日根完整原证据。
- SUMMARY.json / CLOCK_AND_TRANSITION_SUMMARY.json：分母、时钟、I epoch 等计数。
- SOURCE_HASHES.json / CONTRACT_SOURCE_HASHES.json / OUTPUT_HASHES.json / FINAL_AUDIT_SEAL.json：输入、合同、输出 hash 及终验。

原 FINAL_RUN_SEAL 的 35 项文件/9 份生产源码均重验一致；本轮经济 runs=0、consumer imports=0、反事实/过滤收益=0、策略修改=0。首个审计脚本曾在输出前遇到计数 Boolean/None 的 TypeError，修正仅在本新脚本；此前没有输出及经济执行。完成后全部源再 hash 验证不变。
"""
with (O/'READOUT.md').open('x') as f:f.write(report)
# Revalidate every primary input and production seal after all analysis/documentation.
h=json.loads((O/'SOURCE_HASHES.json').read_text())
assert all(sha(p)==v for p,v in h.items())
assert all(sha(p)==v for p,v in ch.items())
checks=json.loads((O/'QA.json').read_text())
dump('FINAL_AUDIT_SEAL.json',dict(
 result='PASS_ALL_SAVED_EVENT_IDENTITIES_AND_CLOCKS',
 scope='Two independent FLAT-start research windows; no across-window execution continuity claim',
 old_PRICE_root_confirmation_authorizing_multiple_actual_initial_positions=False,
 all_actual_buys=6036,PRICE_actual_buys=3593,PRICE_reentries=1626,
 per_window_unknown_responsibility_checks=558,
 all_sources_unchanged=True,primary_source_files=len(h),contract_source_files=len(ch),
 sealed_files_verified=35,sealed_production_files_verified=9,
 actual_broker_fill_evidence='NOT_PROVIDED',
 economic_runs=0,consumer_imports=0,filtered_counterfactual_runs=0,production_changes=0,
 same_I_epoch_warning='Four PRICE->PRICE new-price-root events plus four PRICE->AB new-AB-event events in 2022; no same-I requirement asserted across all lanes',
 new_mechanism_proposed=False,readout_sha256=sha(O/'READOUT.md')))
dump('OUTPUT_HASHES.json',{p.name:sha(p) for p in sorted(O.iterdir()) if p.is_file() and p.name!='OUTPUT_HASHES.json'})
print(json.dumps(json.loads((O/'FINAL_AUDIT_SEAL.json').read_text()),ensure_ascii=False,indent=2))
print('READOUT',O/'READOUT.md')

