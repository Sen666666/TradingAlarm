from pathlib import Path
import pandas as pd, json,hashlib
O=Path(__file__).resolve().parent;R=O.parent
s=pd.read_csv(O/'FULL_NET_SUMMARY.csv');z=pd.read_csv(O/'ALL_REGISTERED_ROUNDS_ATTRIBUTED.csv')
def fnum(x):return f'{x:,.2f}'
def table(frame,cols):
 text='| '+' | '.join(cols)+' |\n| '+' | '.join(['---']*len(cols))+' |\n'
 for _,r in frame.iterrows():
  cells=[]
  for c in cols:
   v=r[c]
   if pd.isna(v):v=''
   elif isinstance(v,(float,)) and c not in ['year']:v=fnum(v)
   cells.append(str(v))
  text+='| '+' | '.join(cells)+' |\n'
 return text
lines=['# 原 A_UNION_B：I 内许可次数与完整费后回合归因',
'',
'## 主结论',
'',
'1. **没有“同一已知 I 内平仓后重复买入”的原 AB 回合：两年均为 0。** 原保存账的全部完整退出都是 I_STRUCTURE_EXIT。同股票后续初仓实际存在（2022 1445 次，2024 198 次），但 I epoch 已变。重复 i_buy 是信号前史，不是订单次数。',
'2. **重复 i_buy 日关联的回合并不比首次许可日更差。** 2022 覆盖完整回合胜率首次 29.78%、重复 31.87%；2024 为 42.86%、44.09%。这不构成消费者因果比较：原 AB 消费 A/B birth，不直接消费 i_buy；一半左右登记当日根本不是 i_buy，已独立 OTHER。',
'3. **I 内收盘新高也不能消除失败。** 重复 i_buy 且刷新全 I 收盘高水位的覆盖完整回合，2022 仍有 671 个亏损、净 −72,328.30 元；2024 有 268 个亏损、净 +909,647.78 元。只作冻结后的关联分组，不估算删单效果、不建议新门槛。',
'',
'## 覆盖与财务边界',
'',
'- 主账仅原 AB 精确回归：2022 全年 births，2024 年 9–12 月 births。各回合沿原账完整后续，不按年末截断；最后退出分别 2023-11-23 与 2025-10-27。不是账户收益，不是实盘成交。',
'- 保留全部 19,795 条 A/B 决策、4,086 条登记、4,072 次已保存条件代理初仓、9,923 条动作。1614 股全部源状态历史读取，所有查询日期有原 facts；不是 common-stock 或成功股票幸存集。',
'- 2022 登记 2732、初仓 2725、原闭合 2627，其中财务可用 2616（774 胜/1842 亏/0 零）、执行 UNKNOWN 103、另闭合财务 UNKNOWN 11、未买 7。未买中 5 个执行 UNKNOWN 与 2 个 NOFILL，不能把二者相加为互斥口径。',
'- 2024 登记 1354、初仓 1347、原闭合 1320，其中财务可用 1312（501 胜/811 亏/0 零）、执行 UNKNOWN 27、另闭合财务 UNKNOWN 8、未买 7（均 NOFILL）。',
'- 财务完整覆盖按每轮原持有区间的 FINANCIAL_COVERAGE，而非 END_STATES；2022/2024 的非普通已核权益回合为 417/141，普通无行动证据回合为 2199/1171，分别保留。UNKNOWN 不进入胜负/尾部；其原始已有金额仍保留用于总额核对。',
'- “非普通”在本报告明确指 VERIFIED_ACTIONS_SCENARIO，即该持有区间存在已核对权益事项，不表示该股性质异常；原保存账的 NET80 情景并非实际税后回款认证。',
'',
'## I 许可主分组',
'',
'W>0、L<0、zero=0，均用原 full net_pnl，含原 ADD、费用和已认可 NET80 权益。赔率=平均盈利/绝对平均亏损。≥30% 为原 full net_return_on_buy_cash；>3R 使用**原初仓实际计划风险 entry_risk**，不是名义 3000 元预算，也不是总加仓风险。',
'']
q=s[s.dimension.eq('i_group')].copy();q['win_pct']=q.win_rate*100
lines.append(table(q,['year','i_group','registered','usable_closed','W','L','zero','win_pct','mean_win_cny','mean_loss_cny','payoff_mean_win_over_abs_loss','net_sum_cny','tail_ge30_count','tail_gt3_initial_R_count']))
lines += ['',
'两年全体财务可用闭合净额分别 −651,087.03 与 +1,462,350.68 元；≥30% 尾 105/109 个，>3R 尾 118/143 个。精确值以 CSV 为准。',
'',
'## CP 同日重合分组',
'',
'CP_FIRST_IN_I / CP_REPEAT_IN_I 是当前 AB birth 当天存在 CP receipt 时，在完整已知 I 内的 receipt 序号。不是 CP 自己的 consumer 经济结果，也不将 NO_CP_TODAY 当首次。',
'']
cq=s[s.dimension.eq('cp_group')].copy();cq['win_pct']=cq.win_rate*100
lines.append(table(cq,['year','cp_group','registered','usable_closed','W','L','win_pct','net_sum_cny','tail_ge30_count','tail_gt3_initial_R_count']))
lines += ['',
'## 市场历史定义与 UNKNOWN',
'',
'- 先从 STOCK_MANIFEST 对应 facts、raw signal lineage、CP1 的完整前史读取，按原 common calendar 复现 native i_epoch。ordinal 从 I 出生累计，绝不从 2022/2024 交易窗清零。',
'- 严格已知出生要求同来源连续确切观察中 I=0→1；缺失观察或来源切换后 lineage 不明的活动段独立 UNKNOWN，不能把左截断第一条信号算首次。',
'- 原 DAILY_OVERLAP 仅覆盖 2022、2024Q4、2026H1 窗口，不能单独提供完整许可序号。19795个决策点的原 epoch / i_buy / I_target / E0_target / lineage / CP receipt 与源重建逐项相等，差异 0。',
'- 登记中 I lineage UNKNOWN 为 13/9，全部理由 MISSING_OR_CHANGED_LINEAGE；其市场分类单列，不因财务闭合就装成已知首次或重复。',
'- prior_i_buy_known_count 是信号之前的许可数；i_buy_known_ordinal 仅在当天确为 i_buy 且前史已知时存在。OTHER 没有硬贴序号。raw observed count 保留，不能当已知序号。',
'- HWM 为原 close 严格大于同 I 内过去最大 close，FIRST_I_DAY 独立。没有等待天数、倍数或择优门槛。',
'',
'## 可复算文件与核对',
'',
'- PROTOCOL.json：读金额前冻结的规则。FEATURE_SEAL.json：金额归因前的状态特征封存。',
'- SIGNAL_STATE_PRELABEL.csv / ALL_AB_DECISIONS_PRELABEL.csv：全部19795个信号的完整前史分类及未选决策。',
'- ALL_REGISTERED_ROUNDS_ATTRIBUTED.csv：4086条登记逐轮完整数据、初仓动作、I/CP/HWM、所有原金额及财务状态。',
'- FULL_NET_SUMMARY.csv：主分组、CP、HWM、事件类型、财务路径、实际参与和交叉分组；PRIOR_I_BUY_EXACT_COUNT_SUMMARY.csv：原始次数不分箱。',
'- ALL_AB_DECISIONS_WITH_OUTCOME_CLASS.csv / ALL_DECISION_FUNNEL_COUNTS.csv：全部未买/未选原因，不局限已买者。',
'- ALL_ACTUAL_ACTIONS_RECONCILED.csv / ROUND_ACTION_CASH_RECONCILIATION.csv：独立动作算术复算；数量、所有费用、买入现金、已支付/应收权益与完整净额逐轮差异全部为0。',
'- UNKNOWN_AND_NO_BUY_ROUNDS.csv / FULL_FINANCIAL_PATH_COVERAGE.csv：全路径 UNKNOWN 与未买；COMPLETE_FULL_TAILS.csv：全部固定尾部明细。',
'- SAME_I_REENTRY_AFTER_FULL_EXIT.csv：有表头、0行，不代表没有跨 I 正常再入。',
'- SOURCE_HISTORY_COVERAGE.csv / I_EPOCH_BIRTHS_PRELABEL.csv：原史起点与I出生清单；SOURCE_HASHES.json / QA.json / FINAL_OUTPUT_HASHES.json：来源及金额守恒。',
'',
'2022正确完整报告是 baseline_regression_2022/postprocess_completion/CORE_AND_FULL_ROUNDS.csv（4651ca…），顶层同名文件是初次后处理失败遗留。2024使用顶层完整报告。两者已分别与最原报告按 A_UNION_B 精确逐值核对。',
'',
'技术恢复：audit_saved.py 完成并封存前史后，在未买回合的 NaN 持仓数量核对处停止；audit_saved_postprocess.py 保留原特征封存，按无买动作为零库存继续。不是参数/样本更换。reproduce_all.py 已包含同一技术修复，可用 --output-dir 指向本目录下尚不存在的子目录完整重算；不可覆盖既有结果。',
'',
'没有导入消费者，没有生成反事实回合，没有重跑经济，没有使用 PRICE joint 数据。原历史源和静态股票池 NON-PIT，财务和执行 UNKNOWN 非随机；这些描述不证明任何新规则有效。',
]
# Exact report-value regression against original source, not rerunning original report scripts.
verification=[]
for year,root,sub in [(2022,'relative_priority_equity_run_2022_v1','postprocess_completion'),(2024,'cash_equity_baseline_2024_v1','')]:
 base=R/'independent_channel_joint_economic_v1'/f'baseline_regression_{year}'
 actual=base/sub/'CORE_AND_FULL_ROUNDS.csv'
 original=R/'m3_stock_birth_during_sector_v1'/root/'report/CORE_AND_FULL_ROUNDS.csv'
 a=pd.read_csv(actual,float_precision='round_trip',low_memory=False);b=pd.read_csv(original,float_precision='round_trip',low_memory=False);b=b[b.arm.eq('A_UNION_B')].reset_index(drop=True)
 pd.testing.assert_frame_equal(a,b,check_exact=True)
 verification.append(dict(year=year,rows=len(a),columns=len(a.columns),original_report=str(original),original_sha256=hashlib.sha256(original.read_bytes()).hexdigest(),baseline_report=str(actual),baseline_sha256=hashlib.sha256(actual.read_bytes()).hexdigest(),exact_all_columns=True))
(O/'ORIGINAL_REPORT_EXACT_QA.json').write_text(json.dumps(verification,ensure_ascii=False,indent=2)+'\n')
# Correct display amounts from exact CSV rather than hand-copied rounded text.
allq=s[s.dimension.eq('ALL')].set_index('year')
txt='\n'.join(lines).replace('−651,087.03 与 +1,462,350.68',f"{allq.loc[2022,'net_sum_cny']:,.2f} 与 +{allq.loc[2024,'net_sum_cny']:,.2f}")
(O/'READOUT.md').write_text(txt+'\n')
(O/'FINAL_OUTPUT_HASHES.json').write_text(json.dumps({p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in O.iterdir() if p.is_file() and p.name!='FINAL_OUTPUT_HASHES.json'},ensure_ascii=False,indent=2)+'\n')
print('DONE_FINAL',len(verification),len(txt))
