from pathlib import Path
from decimal import Decimal as D
from collections import Counter
import json,statistics,hashlib
O=Path(__file__).parent;load=lambda n:json.loads((O/(n+'.json')).read_text());rs=load('LOT_DIAGNOSTICS');ss=load('COHORT_SUMMARY');qa=load('QA');fm=lambda x:f'{D(str(x)):,.2f}' if x is not None else '无';get=lambda sid,day:next(r for r in rs if r['sid']==sid and r['seed_day']==day)
lines=['# 固定入场 CP 失效诊断：实际路径，不是新账户策略','',
'## 1. 结论','',
'存在语义上的交接缺口：V11 的有效入场 CP 在 SEED 成交后只留作审计身份，不成为 active.cp、confirmed_history 或 SEED 的真实保护线。但本段实际资料不支持把它解释为晚期反复假主线的主要漏损原因。',
'',
'319 笔真实 CP 通路 MATURE SEED 中，262 笔入场 CP 高于入场 I；只有 17 笔在原 SEED 尚在时首次破该固定 CP。12 笔原规则已在同一最早可执行 OPEN 退出，仅 5 笔存在更早离场的时间差。5 笔中 1 笔剩余 SEED 卖款更高、3 笔更低、1 笔同价。金额合计 −1,324.59 元，只是固定原路径、固定实际剩余 SEED 的净卖款差，不是 NAV 改进或策略收益。',
'',
'晚期实际新 SEED（OPEN > 2024-11-06）161 笔，128 负、33 正，原全轮净 −47,415.32 元。只有 5 笔在 SEED 尚在时破固定 entryCP，5 笔全部与原退出重合，剩余 SEED 卖款差为 0。另 123 个负轮在原持仓内没有先破这条 entryCP，原净合计 −58,257.35 元。不能将旧 I 距离大直接等同于本固定 entryCP 可以更早止损。',
'',
'因此本研究只识别了一个真实但很窄的保护交接缺口，未识别到足以解释晚期损耗的时间窗口。未实施 M12 或任何新退出规则；是否另行研究由父任务决定。',
'',
'## 2. 固定样本与方法','',
'- 唯一样本：已通过账务和真实 CP 语义独立核验的 execution_fix_v2/once_20250120；93 日，2024-09-02 至 2025-01-20。按 STRICT_ENTRY_SEMANTICS.actual_seed_routes 中 route=CP 取 319 笔，而不是见 entry_evidence_id 就纳入。其余 178 笔 F 通路及 836 笔 EVENT/RESIDUAL 旁路不混入。',
'- 只绑定成交时 CONSUMED.final_slot 的原 evidence ID、receipt_day、floor 和 source lineage。receipt 不早于原 signal，且成交 OPEN 已有效。之后新 receipt、ADD 消费、旧 CP 失效均不撤销这个固定诊断对象。绝不找更老低 CP，不用事后高点或未来 receipt 替换。',
'- 从入场当天 CLOSE 起，按 OPEN → CLOSE 扫描 P_adj ≤ 固定 entryCP 的首次有效观察。OPEN 已知事实只取上一 CLOSE 的 I/stock/sector/M 状态；CLOSE 使用当日已知状态。未用盘中 low 触发。',
'- max(原实际 I_t, 固定 entryCP) 只作预定义结构敏感性参考。逐时点文件同时列原真实 I、固定 entryCP、两者 max 及各自首次触线。这不是原策略保护线，未把它接入账户。原 I 会沿原实际路径抬升，不冻结为初始 I。',
'- CLOSE 破坏只能 next OPEN；OPEN 破坏按本 OPEN、T+1 与原已准入执行边界处理。成交参考 raw OPEN × 0.9995，并计原 dated fee，绝不按 CP floor 成交。原模型只有有限的已核日线执行假设，不是实盘成交保证。',
'- 已平轮/未平轮分别输出；未平按 Jan20 原 mark，不自动平仓。原实际成交、逐 lot 分配、已知股息和资本表净利独立交叉核对。没有策略导入、Data 初始化、history 回放、资金再分配或联网。',
'',
'## 3. 完整样本统计','',
'|固定实际 OPEN 样本|笔数|原全轮净|SEED 尚在时首次破 CP|可比原退出更早|剩余 SEED 净卖款差|',
'|---|---:|---:|---:|---:|---:|']
for s in ss[:6]:lines.append(f"|{s['cohort']}|{s['rounds']}|{fm(s['actual_round_pnl'])}|{s['breached_while_seed_held']}|{s['original_continues_after_diagnostic_exit']}|{fm(s['remaining_seed_delta_sum'])}|")
lines+=['',
'全窗 306 个原已平轮、13 个原未平轮。319 笔首次 entryCP 观察结果为：17 笔持有 SEED 时破坏、179 笔原全轮已退出后才破坏、118 笔已验证至 Jan20 未破、5 笔原全轮退出后遇缺行/未准入公司行动，后续保持未知。179 笔中不存在“SEED 已迁出但 ADD 仍在”时才破 CP 的隐藏类别。',
'',
'17 笔中 16 笔破 CP 时仍在原 I 之上，但仅 2 笔 I、stock、sector 同时为真（华秦科技、香江控股）。其余多数原 sectorfalse 已锁定退出，或 sector unknown，不是“原全部证据持续成立直到很晚才卖”。晚期 5 笔破 CP 时原行业均已 false。',
'',
'全窗入场 OPEN 至 CP 的价格距离中位 9.34%，至 I 中位 13.06%；晚期分别 10.39% 和 13.54%。这些仅是分布描述，不是新增阈值。固定入场 CP 比 I 高，不保证足够靠近当前买价，也不保证早于原行业退出。',
'',
'全部 17 笔最早参考执行的 CP floor 至实际 OPEN 不利价差合计 3,903.30 元，晚期 5 笔合计 425.05 元。它是参考线与执行价间的跳空/穿越损失，不是可避免损失；CLOSE 到 next OPEN 的价差另列。滑点、手续费独立于该跳空数。',
'',
'## 4. 所有五个真正更早的退出窗口','',
'|股票与实际 SEED|首次固定 CP 破坏|参考卖出 OPEN|原 SEED 最后卖出|剩余股数|净卖款差|原 SEED 净 / 原全轮净|',
'|---|---|---|---|---:|---:|---:|']
for r in rs:
 if r.get('entry_CP_failure_then_original_continues'):
  b=r['first_entry_CP_breach'];e=r['diagnostic_exit_OPEN'];lines.append(f"|{r['name']} {r['sid']} / {r['seed_day']}|{b['day']} {b['phase']} 原价 {b['raw']}|{e['day']} 原价 {e['raw']}|{r['seed_actual_last_exit']}|{r['diagnostic_exit_seed_remaining_qty']}|{fm(r['remaining_seed_proceeds_delta'])}|{fm(r['actual_seed_net_allocated_fees_and_dividend'])} / {fm(r['actual_round_pnl'])}|")
lines+=['',
'**中无人机 688297.SH，10/24 SEED 200 股。** 入场 CP 原价 51.18860、I 36.26，入场 OPEN 55。10/29 OPEN 50 首次破 CP、仍高于 I；已知 I=1、stock=1、sector=-1，本轮含退出费用的已知净为 −1,026.84。诊断可在本 OPEN 按 49.975（含 slip）成交，CP floor 到 OPEN 已损失 237.72 元，不能按 51.18860 卖。原 10/30 OPEN 48.68 才卖，净亏 −1,290.56。净卖款仅多 263.72 元。之后至 Jan20 的最高已验证 OPEN/CLOSE 比诊断 OPEN 高 13%，这是原退出后的反弹，不是本轮可得收益。',
'',
'**华秦科技 688281.SH，10/10 SEED 200 股。** CP 原价 98.56236、I 65.96，入场 OPEN 107；当日 CLOSE 94.73 首破，I/stock/sector 都为真，本轮已知净 −2,496.23。只能 10/11 OPEN 91.98 卖，CLOSE→OPEN 再跌 2.75，CP floor→OPEN 价差为 1,316.47 元。原 10/14 OPEN 恰为同一 91.98，虽早一交易间隔，净卖款无改善，原净 −3,045.64。',
'',
'**香江控股 600162.SH，11/4 SEED 3,600 股，是必须分层看的回升反例。** 固定 CP 原价约 1.93573、I 1.56，当日 CLOSE 1.90 破坏时三状态都真，已知净 −741.54。诊断只能 11/5 OPEN 1.86 卖；原路径随后回升，11/8 另外实际 ADD 11,700 股，原 SEED 到 11/11 按原价 2.20 迁出，SEED 自身净 +337.31。提前卖这 3,600 股反而少 1,222.70 元。原全轮最终 −3,225.07 主要还包含后续 ADD，不能把全轮亏损都当成 entryCP 提前卖 SEED 可以避免的收益。11/5 至原全轮结束的最高已验证 OPEN/CLOSE 反弹 28.49%。不据此证明早卖后 ADD 必然消失或资金能再赚钱。',
'',
'## 5. 晚期失败：完整五笔与更大亏损反证','',
'|股票|实际 SEED|固定 CP 首破|最早可执行 / 原 SEED 卖出|原全轮净|原 SEED 净|净卖款差|',
'|---|---|---|---|---:|---:|---:|']
for r in rs:
 if r['seed_day']>'2024-11-06' and r['status']=='BREACHED_WHILE_SEED_HELD':
  b=r['first_entry_CP_breach'];lines.append(f"|{r['name']} {r['sid']}|{r['seed_day']}|{b['day']} {b['phase']}|{r['diagnostic_exit_OPEN']['day']} / {r['seed_actual_last_exit']}|{fm(r['actual_round_pnl'])}|{fm(r['actual_seed_net_allocated_fees_and_dividend'])}|{fm(r['remaining_seed_proceeds_delta'])}|")
lines+=['',
'长白山 603099.SH 的 12/17 SEED 200 股以原 OPEN 60 买，入场 CP 原价 50.06037，I 38.80。12/17 收盘行业已经 false，12/18 OPEN 49.14 才首破 CP，原退出也就在该 OPEN。所谓把保护线从 I 提到 entryCP，无法在这一实际路径上消除 −2,199.22 元亏损；CP 到 OPEN 已有 184.07 元价差。',
'',
'博实股份 002698.SZ 的 12/5 轮原全轮 −5,984.40、SEED 仅 −1,008.09；12/12 曾 ADD 1,400 股，等到 1/6 CLOSE 首破固定入场 CP 时 ADD 已先退，只余 SEED 500 股。1/7 OPEN 与原 sectorfalse 退出完全重合。浪潮信息 000977.SZ 同样包含 ADD，原全轮 −4,201.27，SEED −1,414.07，11/18 CLOSE 破 CP、11/19 原规则同 OPEN 退出。不能把这些全轮亏损算成固定 entryCP 的可救金额。',
'',
'更大的反证是中瓷电子 003031.SZ：11/11 买、11/28 原全轮退出，原净 −4,163.21，固定入场 CP 到 1/7 OPEN 才破。道氏技术 300409.SZ 的 11/8 轮原净 −3,635.87，而 SEED 自身 +446.74，固定 CP 到 1/3 才破。埃斯顿 002747.SZ 的 12/5 轮 −3,286.65，12/20 已退出，CP 也是 1/3 才破。这些亏损不是入场证据已破却继续持有的结果。',
'',
'## 6. 924 与十月光伏：不只挑亏损','',
'9/24 实际 CP 通路只有 5 笔（不能拿原 M7 的 28 笔或全部实际 MATURE 代替）：新华保险、601319、600895、国元证券、深深房A，原全轮合计 +12,406.55，全部原持仓内未破固定 entryCP。整个 9/23–9/30 实际 OPEN 窗 CP 通路 38 笔也没有任何持仓内先破 entryCP。这里没有可以如实命名的“固定 entryCP 误卖赢家”，必须报告零，不能为了正反平衡虚构。',
'',
'10/24 光伏 CP 通路 23 笔（7 正、16 负），原全轮合计 +40,817.94；10/23–10/29 扩窗 28 笔（9 正、19 负），原净 +50,241.22。只有通裕重工、阳光电源两笔在 SEED 尚在时破固定 entryCP，提前卖款反而合计少 365.61 元。',
'',
'- 通裕重工：10/29 CLOSE 2.80 破 CP，10/30 OPEN 2.77 才可卖，原 10/31 OPEN 2.86，少 206.78。至原退出反弹 3.25%，至 Jan20 的最高已验证 OPEN/CLOSE 反弹 17.33%。',
'- 阳光电源：10/30 OPEN 90 破 CP 原价 90.35401（仍高于 I 86.56），原 10/31 OPEN 91.59，提前卖少 158.83。至原退出反弹 1.77%，至 Jan20 反弹最高 4.58%。两笔都是原亏损轮中的回升反例，不伪称赢家。',
'- 聚和材料 688503.SH（10/24，原全轮 +30,223.18）、电气风电 688660.SH（10/24，+18,463.45）、钧达股份 002865.SZ（10/24，+8,715.91）、协鑫集成 002506.SZ（10/24，+8,027.54）、禾望电气 603063.SH（10/28，+8,509.35）均未破本次固定 entryCP；它们的 actual ADD、SEED 迁出和全轮终点均完整保留在逐lot文件。不能推断改成追踪新 CP 后仍不误卖，因为那是另一个没有做的假设。',
'',
'## 7. 金额口径、未知与边界','',
'- 净卖款差 = 最早参考 OPEN 的实际剩余 SEED 股数 × 含 slip 价格 − 该笔独立卖出费，再减原同一剩余 SEED 后续真实卖款/期末 mark/之后股息。原多 lot 合单费用按实际卖出数量比例归属；独立参考卖出用其自身最低费用。全轮 PnL、SEED PnL、ADD 记录分列。',
'- 17 个有剩余 SEED 的可比事件中，3 轮有过 ADD，0 笔在参考时点前已有部分 SEED 迁出。其他原机会的 partial donor 全量记录在 actual_seed_sales，不能将已卖股数当作仍可提前卖；原全股数同尺度价差字段另明确标为纯价格参考。',
'- MFE 与反弹采用已验证 OPEN/CLOSE，不用日内 HIGH/LOW 声称可成交。MFE 从入场 raw OPEN 开始，包含入场点；回升统计分别止于原全轮实际退出与 Jan20/源边界。最高点只用于事后描述，不参与任何触发。',
'- 8 个固定证据后续路径遇到 source stop：7 个未准入公司行动、1 个缺行，全部发生在原 SEED 已完全退出之后，故原持仓期没有未知区间。8 个中 3 个已有更早已核首次 CP 破坏，另 5 个仅能说截至 source stop 未破，不能说直到 Jan20 都没破。详见 QA.source_stops。',
'- 不新增公司行动，不跨 Jan20。000728 仅使用原已封存 source/parquet 和既有事件，没有查询任何新源或 403 相关来源。原 non-PIT 与净80股息/费用研究代理限制保持，不能升级为实盘认证。',
'',
'## 8. 验证与文件索引','',
f"QA={qa['result']}。校验本次读取的 {qa['source_files_read']} 个来源文件哈希、全部原输出 seal；319 个 CP 实际订单；{qa['observation_rows']} 个已验证 OPEN/CLOSE 观察；逐lot真实卖出分配及每个持仓 CLOSE 原全轮净利与 CAPITAL_LOTS.round_net 逐条一致。",'',
'- LOT_DIAGNOSTICS.json/.csv：319 笔完整身份、入场 I/CP 距离、首次破坏、知识时点、原状态/净利、原 SEED/ADD/退出、可执行 OPEN、滑费、跳空、剩余股数与回升。',
'- OBSERVED_PRICE_AND_ORIGINAL_I_PATH.json/.csv：31,995 个原源观察，真实 I 与固定 entryCP/max 参考逐点并列。',
'- ACTUAL_ORDER_PATHS.json/.csv：全部相关原真实订单，不制造反事实订单。',
'- COHORT_SUMMARY.json/.csv：全窗、晚期、924、924扩窗、光伏10/24与扩窗，并列已平/未平。',
'- SECTOR_SUMMARY.json/.csv：全行业完整分布。',
'- QA.json、SOURCE_HASHES.json、OUTPUT_SEAL.json：审计范围与边界。',
'- diagnose_saved_path.py：可复核的离线描述脚本，不导入或调用策略。',
'',
'结论限于原实际持仓路径上的固定入场证据，不检验再分配收益、之后是否仍能 ADD、替代退出改变后能否再买或新账户 NAV。禁止将 −1,324.59 元或 +263.72 元等数写成账户增益，也不能据此证明所有更敏感退出均无效。']
(O/'READOUT.md').write_text('\n'.join(lines)+'\n')
# Compact selected-case file includes all early exits, all late touched, startup entire cohort and positive PV references.
selected=[r for r in rs if r.get('entry_CP_failure_then_original_continues') or r['seed_day']>'2024-11-06' and r['status']=='BREACHED_WHILE_SEED_HELD' or r['seed_day']=='2024-09-24' or r['sector51']=='光伏风电设备' and '2024-10-23'<=r['seed_day']<='2024-10-29' and D(r['actual_round_pnl'])>4000]
(O/'REPRESENTATIVE_CASES.json').write_text(json.dumps(selected,ensure_ascii=False,indent=2)+'\n')
# Re-read every actually used source after writing report; unchanged original files is a delivery gate.
for p,h in load('SOURCE_HASHES').items():assert hashlib.sha256(Path(p).read_bytes()).hexdigest()==h,('SOURCE_CHANGED_DURING_DIAGNOSTIC',p)
seal={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in O.iterdir() if p.is_file() and p.name!='OUTPUT_SEAL.json'}
(O/'OUTPUT_SEAL.json').write_text(json.dumps(seal,ensure_ascii=False,indent=2)+'\n')
print('READOUT_AND_REPRESENTATIVE_CASES_WRITTEN',len(selected),'SEALED_FILES',len(seal))
