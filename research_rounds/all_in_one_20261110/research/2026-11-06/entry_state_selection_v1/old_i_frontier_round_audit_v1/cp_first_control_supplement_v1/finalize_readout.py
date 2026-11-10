from pathlib import Path
import pandas as pd,json,hashlib
O=Path(__file__).resolve().parent
p=pd.read_csv(O/'CP_POOLED_COMPLETE_METRICS.csv');m=pd.read_csv(O/'CP_SIGNAL_MONTH_COMPLETE_METRICS.csv');c=pd.read_csv(O/'EXACT_CONTROL_SUMMARY.csv');f=json.loads((O/'FIRST_CP_FUNNEL_SUMMARY.json').read_text())
def table(df,cols):
 out='| '+' | '.join(cols)+' |\n| '+' | '.join(['---']*len(cols))+' |\n'
 for _,r in df.iterrows():
  vs=[]
  for col in cols:
   v=r[col]
   if pd.isna(v):v=''
   elif isinstance(v,float):v=f'{v:,.3f}' if col not in ['year'] else str(int(v))
   vs.append(str(v))
  out+='| '+' | '.join(vs)+' |\n'
 return out
texts=['# 首 CP 同日重合：冻结后的探索性控制',
'',
'## 结论',
'',
'首 CP 的 pooled 关联值得记录，但**目前不能把它当作稳定准入机制**。2024 年首 CP 的高收益集中在 9 月，44/107 条登记集中于 9 月 26 日。相同日期和行业的严格比较中，首 CP 相对无 CP 的均净优势由 pooled +1,873.37 元变成 −184.99 元，均 R 差 −0.364，>3R 尾概率差 −18 个百分点。相对重复 CP 的严格 cell 差仍为正，但 2024 只有19个可算 cell、8个日期，9月26日占 cell 权重63.16%，无法视为稳健证据。',
'',
'这是看到 pooled 结果后才冻结的探索性补充，不是预注册盲测或 OOS。仅描述旧 AB 保存回合，不产生新策略收益。原 AB 使用 A/B birth，首 CP 只是当天可见的并行市场特征。',
'',
'## 1. 完整 pooled 指标',
'',
'财务覆盖完整 FULL 回合的 W/L、均净、赔率、完整净额与尾部均保留原费用、ADD及 NET80。R=原初仓实际计划 entry_risk，非名义3000预算，也非总加仓风险。UNKNOWN 不当作亏损或零收益。',
]
pp=p.copy();pp['win_pct']=pp.win_rate*100
texts.append(table(pp,['year','cp_group','registered','actual_buys','usable_closed','W','L','zero','win_pct','mean_net','mean_initial_R','mean_win','mean_loss','payoff','tail_ge30','tail_gt3R','execution_unknown','closed_financial_unknown','not_bought']))
texts+=['',
'无 CP 当日占全部登记：2022 2273/2732=83.20%，2024 958/1354=70.75%。CP_TRACE_OR_EPOCH_UNKNOWN 独立保留，未并入无 CP。',
'',
'终止类别与是否买入是两条轴，不能加总混用。例：2022 首 CP 194=185财务覆盖闭合+9执行UNKNOWN；未买1属于这9个UNKNOWN之一。2024首CP107=103覆盖闭合+4已知NOFILL。TERMINAL_BUCKET_BY_ACTUAL_BUY.csv 给出所有互斥终止桶×买入标记。',
'',
'## 2. 固定日期与精确日期×行业控制',
'',
'- 先按**全部登记**判定两组是否共存，不先删掉 UNKNOWN。每组至少一条财务覆盖完整回合的 cell 才能计算经济差；其余共存 cell 保留计数，不零填。',
'- 日期控制：每个有两组的信号日期中先分别算组均值，再日期等权。',
'- 日期×行业控制：原 sector 行业ID（与行业名一一对应）的精确同日 cell 内比较，再 cell 等权。没有因样本少改用月份、邻日或宽行业。',
'- 下表差均为“首 CP − 对照”。这些控制只限制日期/行业差异，未解决PVR排序、已有持仓、行业top2条件化、其他特征或UNKNOWN的非随机性，不能声称消除了选择偏差。',
]
cc=c.copy();cc['win_diff_pp']=cc.equal_weight_diff_win_rate*100;cc['tail30_diff_pp']=cc.equal_weight_diff_tail_ge30_rate*100;cc['tail3R_diff_pp']=cc.equal_weight_diff_tail_gt3R_rate*100;cc['first_coverage_pct']=cc.first_registered_coverage_fraction*100;cc['max_day_weight_pct']=cc.eligible_max_day_cell_weight_share*100
texts.append(table(cc,['year','comparator','unit','coexisting_cells','outcome_eligible_cells','eligible_dates','eligible_industries','eligible_stocks','first_coverage_pct','equal_weight_diff_mean_net','win_diff_pp','equal_weight_diff_mean_initial_R','tail30_diff_pp','tail3R_diff_pp','max_day_weight_pct']))
texts += ['',
'严格行业cell通常各组只有一条，因为原AB每天每行业最多选2条。2022首CP对重复CP仅覆盖28/194首CP登记（可算25对）；2024为21/107（可算19对）。该小子集不是全体首CP，不能用其差额替换 pooled 总额。首CP对无CP严格cell分别覆盖90/194与51/107。',
'',
'同日期控制仍允许跨行业对照，日期×行业控制则因行业top2更稀疏。MATCHED_CELL_MEMBERS.csv 明确每条回合进了哪个cell及其UNKNOWN状态，MATCHED_CELL_DETAILS.csv保留两侧分母与原均值。',
'',
'## 3. 信号月与集中度',
'',
'全部四种CP组、16个原信号月份的完整表在 CP_SIGNAL_MONTH_COMPLETE_METRICS.csv，空组也保留。首CP如下，未按结果合并或删月份。',
]
texts.append(table(m[m.cp_group.eq('CP_FIRST_IN_I')],['year','signal_month','registered','usable_closed','W','L','mean_net','mean_initial_R','tail_ge30','tail_gt3R','execution_unknown','closed_financial_unknown','not_bought']))
texts+=['',
'2024首CP的全部≥30%和>3R右尾均来自9月；10/11/12月首CP均净分别−959.59/−1225.27/−1387.58元。每月只有3/11/14条可用回合，不能反过来发明月度开关。',
'',
'各组全部登记的日期/行业/股票数与最大单日集中如下。注意date×industry cell等权下，同一日可贡献多个行业，因此还单列最大日cell权重，不把cell数当独立日期数。',
]
texts.append(table(p,['year','cp_group','n_dates','n_industries','n_stocks','max_day_registered','max_day_registered_share','max_day_dates']))
texts += ['',
'## 4. 首CP完整原决策漏斗与行业槽',
'',
'- 2022首CP原决策405条，原可行331条=选中194+未进top2 137，选择率58.61%；另持仓阻挡45、UNKNOWN阻挡9、收盘数量/风险拒绝18、PVR未知2。',
'- 2024首CP原决策332条，原可行314条=选中107+未进top2 207，选择率34.08%；另持仓阻挡12、UNKNOWN阻挡1、收盘数量/风险拒绝5。',
'- 两年所有 PASS_NOT_TOP2 首CP候选的同日行业已有2个 SELECTED_PENDING。这里只说明保存的原日内行业队列名额，不是共享账户真实持仓、资金或券商成交。',
'- 选中/未选平均原PVR分数：2022 70.48/62.41，2024 73.91/67.53；原排队序号均值1.40/6.51与1.39/11.98。这说明旧回合经济标签来自已被原排序筛选的子集，不能赋给未选首CP。',
'- 2024-09-26占全部首CP原决策219/332=65.96%，但首CP选中44/107=41.12%。单日大量同类候选及行业2名额会改变进入回合样本的构成。',
'- FIRST_CP_ALL_DECISIONS_WITH_SLOTS.csv保存全部737条首CP决策、原排名/分数、当天同行业可行候选和已选数量。未选行从未赋予PnL；FIRST_CP_FUNNEL_COUNTS.csv与FIRST_CP_FEASIBLE_SELECTED_SLOT_COUNTS.csv可复算漏斗。',
'',
'## 5. 时点、核对与可复算',
'',
'CP必须signal t当天 receipt=True且当时已知I内序号=1。序号是从完整I历史向前计数；没有用未来第一次CP回填此前birth。无CP只表示t日没有receipt，不能解释为以后永远无CP。',
'',
'PROTOCOL.json在查看本补充控制结果前冻结，并明确已看过pooled的探索性质。compare_saved.py仅读取原归因封存CSV及原DECISIONS；SOURCE_HASHES.json、QA.json、OUTPUT_HASHES.json核对全部来源未变、4086登记与19795决策守恒、互斥终止桶和独立actual-buy轴、原行业每日最多2次登记以及未选无PnL。',
'',
'无需将这项发现升级为规则。可用结论是：首CP的优势随月份、日期及行业匹配显著改变；尤其2024相对无CP不能通过严格同日同行业均净/右尾比较。目前保存账不支持宣称稳定改进。没有运行consumer、改变参数、反事实收益或新经济。',
]
(O/'READOUT.md').write_text('\n'.join(texts)+'\n')
(O/'OUTPUT_HASHES.json').write_text(json.dumps({p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in O.iterdir() if p.is_file() and p.name!='OUTPUT_HASHES.json'},ensure_ascii=False,indent=2)+'\n')
print('FINALIZED',len('\n'.join(texts)))
