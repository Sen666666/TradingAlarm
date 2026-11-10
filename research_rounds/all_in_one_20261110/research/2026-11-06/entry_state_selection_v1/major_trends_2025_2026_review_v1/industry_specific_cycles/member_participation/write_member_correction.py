import pathlib,json,math,pandas as pd,numpy as np
B=pathlib.Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1/major_trends_2025_2026_review_v1')
O=B/'industry_specific_cycles/member_participation'
W=pd.read_csv(O/'WINDOW_PARTICIPATION.csv');R=pd.read_csv(O/'RAW_VS_ADJUSTED_MEMBER_RETURNS.csv');V=pd.read_csv(O/'MEMBER_COVERAGE.csv');U=pd.read_csv(O/'ALL_MEMBER_WINDOW_RETURNS.csv')
lines=['三之二 行业广泛走强与个股暴涨分开验证','',
'修正判断标准：行业指数涨得多、几只股票暴涨、较多成员持续走强，是三个不同的事实。代表股数倍涨幅仅作个股观察，不能据此把该股票指定为策略必须买到的目标；也不能用少数个股极值证明行业普涨。',
'本次保留前节已冻结的各行业独立起止，不重新挑日期，不把各股各自的最低点和最高点拼在一起。主表比较同一个行业二次底部日与行业峰值日；另列从“收盘重返前高”开始的敏感性结果和峰后回撤。两类起点与峰值均已看过后续，仍是事后描述，不是可实现收益。',
'成员口径：2026/10/22现有行业名单与原1709研究池的交集，共246只。五行业现有清单合计404只，未覆盖158只。现有成员不等于历史成员，NON-PIT及退出、迁行业、存续选择偏差未消除，不能称历史全行业全样本。未知不按零收益或不涨处理。',
'价格口径：冻结复权收盘，原价另路核对；必须在指定起止日期有真实有效观测，不前填。两端已知不代表中途每日都有价，完整路径数量单列。所有涨幅都是价格描述，不是费后净回合收益。',
'集中度定义：各成员初始同额的正涨幅份额，最大一只或前三只的 max(r,0) 之和除以全组正涨幅之和。它不是按指数历史权重计算的贡献率；真正指数权重及贡献集中度仍待对齐。删除最高10%成员按向上取整，不重新挑选阈值，只检查结果是否被少数极端值撑起。',
'持续性定义：每个共同交易日比较该股当日与21个共同交易日前的收盘，两个端点均有效才入当日已知分母，中途缺价不被伪造；统计当日已知成员中至少一半、至少三分之二上涨的天数。仅描述是否反复出现群体推进，不是新增行业准入门，未知成员日另列。',
'']
for v in V.to_dict('records'):
 sid=v['sector'];w=W[(W.sector==sid)&(W.window=='二次底部至行业峰值')].iloc[0];rr=R[(R.sector==sid)&(R.window=='二次底部至行业峰值')];re=W[(W.sector==sid)&(W.window=='重返前高至行业峰值')].iloc[0];rawre=R[(R.sector==sid)&(R.window=='重返前高至行业峰值')]
 rawsort=rr.raw_return_pct.sort_values(ascending=False);rawtrim=rawsort.iloc[math.ceil(.1*len(rawsort)):]
 end=W[(W.sector==sid)&(W.window=='行业峰值至截止')].iloc[0]
 lines += [v['name'],
 f"覆盖：研究池{v['research_pool_n']}/{v['current_master_n']}只现有成员（{v['coverage_pct']:.2f}%），池外{v['outside_research_pool_n']}只未算。主周期两端已知{int(w.known_endpoint_n)}/{int(w.pool_n)}，两端UNKNOWN {int(w.unknown_endpoint_n)}；中途每个共同交易日都有效的{int(w.full_path_valid_n)}只。",
 f"同日起止 {w.start} → {w.end}：行业指数{w.industry_return_pct:+.2f}%。已知成员{int(w.positive_n)}/{int(w.known_endpoint_n)}上涨（{w.positive_pct_known:.2f}%），涨≥50%有{int(w.over50_n)}只，涨≥100%有{int(w.over100_n)}只。复权涨幅25/50/75分位为{w.p25_pct:+.2f}% / {w.median_pct:+.2f}% / {w.p75_pct:+.2f}%；未复权中位{rr.raw_return_pct.median():+.2f}%，原价上涨{int((rr.raw_return_pct>0).sum())}/{len(rr)}。",
 f"集中度：最高一只占等初始权正涨幅{w.top1_positive_gain_share_pct:.2f}%，前三只{w.top3_positive_gain_share_pct:.2f}%。删除涨幅最高10%（{int(w.top10pct_n)}只）后，其余复权平均仍{w.exclude_top10pct_mean_pct:+.2f}%、中位{w.exclude_top10pct_median_pct:+.2f}%；按未复权涨幅独立排序并剔除最高10%后，其余平均{rawtrim.mean():+.2f}%。这支持样本上涨并非只靠最高几只，但不等于真实加权指数贡献已核。",
 f"持续性：该段{int(w.sessions_after_start)}个后续收盘中，21日涨幅为正的成员占已知成员至少一半有{int(w.breadth21_majority_days)}天，至少三分之二有{int(w.breadth21_two_thirds_days)}天，后者最长连续{int(w.breadth21_two_thirds_longest_sessions)}个交易日；每日21日上涨占比的中位{w.breadth21_median_pct:.2f}%。未必全程普涨，期间UNKNOWN成员日合计{int(w.breadth21_unknown_member_days)}。",
 f"改从重返前高日 {re.start} 开始至同一行业峰值：{int(re.positive_n)}/{int(re.known_endpoint_n)}上涨，复权中位{re.median_pct:+.2f}%，未复权中位{rawre.raw_return_pct.median():+.2f}%。这避免只报最低点起算，但不是实时入场检验。",
 f"峰后 {end.start} → {end.end}：行业{end.industry_return_pct:+.2f}%，已知成员仅{int(end.positive_n)}/{int(end.known_endpoint_n)}上涨，中位{end.median_pct:+.2f}%。上涨广泛性不能永久外推到峰后。",
 '']
lines += ['分段参与明细（与前节50个行业子阶段逐一对应；黄金现货不是股票成员群，不作成员广度）']
for sid in V.sector:
 g=W[(W.sector==sid)&W.window.str.startswith('阶段')]
 lines.append(g.iloc[0]['name'])
 for x in g.to_dict('records'):
  lines.append(f"  {x['start']} → {x['end']}：{x['window']}；已知{int(x['known_endpoint_n'])}/{int(x['pool_n'])}，上涨{int(x['positive_n'])}，成员中位{x['median_pct']:+.2f}%；21日上涨成员过半{int(x['breadth21_majority_days'])}/{int(x['sessions_after_start'])}天。")
lines += ['',
'原价与复权交叉核验',
'本次另从原始Tushare历史文件和THS原始日线文件读取，而非只重算复权结果：两种固定起点、五行业的862个有效价格端点逐点一致，误差0；234处换源接缝，新源的前一日原价与旧源、当日原价与冻结数据均一致，误差0。五个行业在二次底部至观察截止全序列中的峰值日期重新计算，5/5与表一致，行业close与raw_close完全一致。',
'246只股票的 close=raw_close×adjustment_factor 数值关系最大差约1.82×10⁻¹²。未复权中位仍很高，因此未发现本次数倍中位数主要由换源断裂或复权重复造成。这是原始文件与冻结文件的一致性检查，不是独立交易所认证，也不是逐笔公司行动的PIT审计；复权不能被称为真实已兑付总回报。',
'主周期30只两端未知：29只的冻结序列首个有效日晚于周期起点，不能为其回填更早价格或据此断言具体上市日；另1只在行业峰值日没有有效价格。各阶段的已知分母随实际缺价而变化，未把这些股票补成零收益。',
'',
'证据分级与仍待对齐',
'1. 已支持：在现有固定研究成员的可比样本内，五条主线的上涨都不只发生在少数暴涨股；多段推进与大范围回撤都能在成员分布中看到。',
'2. 待对齐：真实历史行业全量成员及迁入迁出，未覆盖的158只现有成员，历史指数权重和指数涨幅由哪些成员贡献。通信设备仅覆盖现有行业43/93只，尤其不能把样本41/41上涨说成全行业100%上涨；其他行业也不得把已知分母写成全行业分母。',
'3. 贵金属虽覆盖当前14/14只，仍是当前行业分类，不能抹去历史成分偏差。招金黄金等个股从低基数起算可能占较高正涨幅份额，但剔除极端股后其余仍明显上涨；这不自动把个股的特殊重估目标加入策略。',
'4. 这些行业级证据可以支持继续检查策略对群体行情的参与，不规定必须捕获源杰科技、某只重组股或任何事后妖股。第六节所有数倍个股均降为独立观察，不作为行业“必须捕获”验收清单。',
'5. 没有因本补充改动策略、跑新账户、改变原账结束日或将未来峰值送回当时开仓信号。对未复核的其他85行业，成员广泛性仍未审，不沿用本五行业结论。',
'']
text='\n'.join(lines)
(O/'五行业成员参与度补充.txt').write_text(text,encoding='utf-8')
report=B/'2025至2026重大行情与原账户参与复核.txt';old=report.read_text()
assert '三之二 行业广泛走强与个股暴涨分开验证' not in old
(O/'REPORT_BEFORE_MEMBER_CORRECTION.txt').write_text(old,encoding='utf-8')
s=old.replace('四 半导体与黄金三种标的分开列示',text+'\n四 半导体与黄金三种标的分开列示',1)
s=s.replace('修订：年度和半年表仅作背景；第三部分已改为逐板块独立周期，人工覆盖五个行业与黄金现货。','修订：年度表仅作背景；第三部分含五个行业独立周期与成员参与度。个股数倍涨幅仅观察，不作为必须捕获目标。')
s=s.replace('主观验收：核心肥尾应看整个跨年主升及反复恢复，不要求精确买最低卖最高。','主观验收：行业肥尾评价需同时看跨年主升、成员广泛参与和反复恢复，不能只凭指数或少数个股极值。不要求精确买最低卖最高。')
s=s.replace('六 固定代表股及实际参与','六 个股独立观察与实际参与（不作必须捕获清单）')
s=s.replace('只作机制病例，不能替代行业全部成员胜率。','只作个股观察，不能替代行业成员广泛性或全部成员胜率，也不因事后数倍上涨就要求策略必须买到。')
s=s.replace('一 主要发现\n','一 主要发现\n先区分行业与个股：五行业已补成员分布、分段持续性和等初始权涨幅集中度，支持固定研究样本内广泛上涨；真实历史全量成员与指数权重仍待对齐，不能把样本普涨说成历史全行业普涨。代表股仅观察。\n',1)
report.write_text(s,encoding='utf-8')
assert '三之二 行业广泛走强与个股暴涨分开验证' in report.read_text()
assert s.count('三之二 行业广泛走强与个股暴涨分开验证')==1
print('updated report bytes',report.stat().st_size,'supplement',len(text.encode()))
print('raw trim',[(k,float(g.raw_return_pct.sort_values(ascending=False).iloc[math.ceil(.1*len(g)):].mean())) for k,g in R[R.window=='二次底部至行业峰值'].groupby('industry')])
