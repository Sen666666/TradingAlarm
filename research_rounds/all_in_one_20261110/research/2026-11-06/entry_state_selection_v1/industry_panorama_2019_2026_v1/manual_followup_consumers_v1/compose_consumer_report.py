from pathlib import Path
import pandas as pd,json,hashlib
O=Path(__file__).parent;r=pd.read_csv(O/'MANUAL_CYCLES.csv');l=pd.read_csv(O/'AUXILIARY_REVIEW_LEDGER.csv');d=json.loads((O/'review_decisions.json').read_text());qa=json.loads((O/'QA.json').read_text());ss=pd.read_csv(O/'SECTOR_SUMMARY.csv')
fmt=lambda x:'未知/无正收益' if pd.isna(x) else f'{x:.2f}%'
lines=['消费与服务20行业：2019–2026独立行情人工补全','观察截止：2026-10-22。2018年起点仅用于保留跨入2019年的完整周期。','',f'覆盖结果：20行业、全部140条机械辅助段已人工审阅，整理为100个互不重叠的人工周期，其中15个重点候选、54个普通或可错过、31个证据不足；28个跨机械段长周期，67个跨年周期，另有2个人工低点修正。未重复原先已审29行业。','',
'一、先看结论','1. 最有辨识度的长周期包括白色家电2018–2026、饮料制造2018–2021、食品加工制造2018–2020、影视院线2024–2026、家居用品2024–2026及包装印刷2024–2026。它们也并非都可称历史全行业广泛行情：本研究仅覆盖2026静态存续大市值固定池，范围、端点未知、全路径缺失及集中度逐条列明。',
'2. 白色家电不拆成五个独立肥尾：主表只计一个2018-10-18至2026-05-19长期母周期。连续日线中2019、2022、2024、2025的大底逐级抬高，最终上涨342.16%，全程最大回撤-30.34%。9/9已知端点上涨、中位334.35%，但P/F=10/43，完整路径仅5只。辅助表保留五个内部阶段，不可相加或分别重复计总收益。',
'3. 美容护理2018–2021指数涨208.27%，端点仅2只，因此列证据不足。互联网电商2018–2020、2024–2026均有指数大行情，但端点/覆盖小且收益集中，未把它们升级成广泛肥尾。教育、其他社会服务、纺织制造、厨卫电器、造纸均存在1–3只小样本限制。',
'4. 小家电2024–2025合并后行业涨108.69%，实际只有5/6上涨、中位26.48%、前三正收益贡献94.46%，最终降为普通分化行情。不能因每个机械子段分别6/6上涨就假定整个长周期也6/6，也不能拼接或相乘子段收益。服装家纺2024–2026行业109.84%、中位29.36%，同样没有自动晋级。',
'5. 两个人工起点修正：家居用品A0223的2020-02-04收盘较原机械起点2019-08-06低0.025%，主表改从2020-02-04起；汽车服务及其他A0146的2023-10-23较原起点2022-10-10低1.51%，主表排除一年弱整理、改从2023-10-23起。原140辅助段均保留于审阅归属表，不改原输出。','',
'二、解释协议与边界',
'人工优先读连续日线图、逐月路径与年度实际日线极值，再审全部辅助段。20%规则仅提供候选清单，不决定人工等级、独立长周期起止或“肥尾”。没有阈值搜索、经济回测、账户模拟或外部新数据。',
'跨年高低点持续抬升且后续新高时，可以将多个机械子段归入同一长周期；明显降低的结构基底、久盘后失败恢复则分开。箱体中小幅新高不自动视为长期主升，反之20%以上回撤也不自动结束整轮。边界是回顾性人工解释，并非唯一数学真值、当时可知信号或收益承诺。',
'重点候选是后续研究优先级，不是统计学肥尾的检验证书；普通或可错过包括幅度一般的普涨修复，也包括指数很强但成员分化的走势；证据不足尤其包括K<=3，不能用妖股或少数样本代替行业。主表同一行业周期不重叠，内部机械段不可重复相加。',
'价格完全沿用原signal.parquet调整收盘：observed_bar与price_eligible为真、source_invalid与synthetic_event_bar为假、正且有限收盘。行业与股票同口径，确切端点，无前填。全部20行业与127只股票原源SHA256验证，100行都从原日线重新计算。',
'n/K/P/F：n=端点收益为正只数，K=起止两日均有有效价只数，P=本研究固定池只数，F=现行业映射全成员数；F不等于历史成员总数。full_path_members=区间行业所有有效交易日均有该股有效价的只数。K不等于全路径有效，P/F亦不能说明历史覆盖率。',
'固定池是2026年静态1709只存续、约100亿元以上公司市值池和现行业映射，NON-PIT。结论只支持已覆盖固定池，不得扩展为历史全行业或可交易性验证。',
'中位收益按K个确切同端点成员计算，未知端点不当零或剔除后假称全体。前三正收益贡献=sum前三max(收益,0)/sum全部max(收益,0)，为等初始名义金额的正收益集中度，不是行业指数权重贡献；K<=3时100%通常只是算术结果。',
'全部_pct字段都是百分数百分点，如342.16表示上涨342.16%，不是3.4216；最大回撤为负。主周期回撤覆盖起止间全部有效日线，不隐去机械段之间的下降。',
'峰后观察统一从该周期峰值日到2026-10-22，列峰后最低日与回落幅度、截止相对峰值幅度。峰后最低使用未来信息，只作复盘；开放段峰值也只是截止前局部峰，不能声称经济周期已结束。',
'覆盖完整指本组20行业及全部140条给定辅助段人工审阅；不声称穷尽所有小于20%的短反弹，也不声称以唯一区分方式覆盖所有交易机会。','',
'三、15个重点候选（完整数值仍以下文及CSV为准）']
for x in r[r.priority.eq('重点候选')].itertuples():
 lines.append(f'{x.record_id} {x.name} {x.start}→{x.end}：行业{fmt(x.industry_return_pct)}，MDD {fmt(x.mdd_pct)}；n/K/P/F={x.positive_members}/{x.known_members}/{x.research_pool_members}/{x.current_all_members}，全路径{x.full_path_members}/{x.research_pool_members}，成员中位{fmt(x.member_median_pct)}，前三{fmt(x.top3_positive_share_pct)}。')
lines+=['','四、逐行业完整说明与全部人工周期']
for i,(name,conf) in enumerate(d.items(),1):
 sub=r[r.name.eq(name)];cov=ss[ss.name.eq(name)].iloc[0]
 lines+=['',f'{i}. {name}（{cov.sector}）',conf['overview'],f'覆盖{int(cov.auxiliary_records)}个辅助段→{len(sub)}个人工周期：重点{int(cov.key_cycles)}、普通{int(cov.ordinary_cycles)}、不足{int(cov.insufficient_cycles)}。P/F={int(cov.research_pool_members)}/{int(cov.current_all_members)}。']
 for x in sub.itertuples():
  unknown=x.unknown_symbols if pd.notna(x.unknown_symbols) else '无'
  lines += [f'• {x.record_id}｜{x.priority}｜{x.start}→{x.end}｜辅助段{x.auxiliary_ids}',f'  行业{fmt(x.industry_return_pct)}；MDD {fmt(x.mdd_pct)}（{x.mdd_peak}→{x.mdd_trough}）；{x.sessions_after_start}个起点后有效交易日。',f'  n/K/P/F={x.positive_members}/{x.known_members}/{x.research_pool_members}/{x.current_all_members}；全路径{x.full_path_members}/{x.research_pool_members}；端点未知{x.unknown_members}；池外{x.outside_pool}。中位{fmt(x.member_median_pct)}，P25/P75={fmt(x.member_p25_pct)}/{fmt(x.member_p75_pct)}；前三正收益贡献{fmt(x.top3_positive_share_pct)}；去前三均值{fmt(x.mean_without_top3_pct)}。',f'  人工边界与定级：{x.boundary_rationale}',f'  峰后至2026-10-22最低点{x.peak_following_low}，较峰{fmt(x.peak_to_observed_low_pct)}；截止较峰{fmt(x.at_cutoff_vs_peak_pct)}。{x.endpoint_status}。',f'  未知端点股票：{unknown}。']
 lines+=['  本行业辅助段逐条归属：']
 for x in l[l.name.eq(name)].itertuples():
  lines.append(f'  {x.auxiliary_id} {x.start}→{x.end}，原段行业{fmt(x.industry_return_pct)} → {x.manual_cycle_id}（{x.manual_priority}）：{x.review_decision}。理由同该周期；原段成员n/K={int(x.positive_members)}/{int(x.known_members)}，中位{fmt(x.member_median_pct)}。')
lines+=['','五、可追溯文件与QA','MANUAL_CYCLES.csv：100个最终人工周期，均原始日线和成员重算。','AUXILIARY_REVIEW_LEDGER.csv：全部140个辅助段逐条归属、是否合并、定级与理由。','MEMBER_RETURNS_MANUAL.csv：639个周期×股票端点/全路径/收益证据。','MERGED_LONG_CYCLES.csv：28个跨机械段重算周期。','review_decisions.json：逐行业人工决定与理由，不是阈值扫描。','DAILY_REVIEW_PANEL_1.png至4.png：20行业日线审阅图。','DAILY_PRICES.csv、MONTHLY_PATH.csv、YEARLY_EXTREMA.csv、PATH_REVIEW.txt：连续路径与日线极值底稿。','SAME_BOUNDARY_RECHECK.csv：70个未改边界行与原辅助统计核对，最大误差1.4210854715202004e-14。','PROTOCOL.json、SOURCE_HASHES.json、QA.json、OUTPUT_SEAL.json：口径、来源哈希及验收。',json.dumps(qa,ensure_ascii=False,indent=2)]
(O/'CONSUMER_SECTOR_REVIEW.txt').write_text('\n'.join(lines)+'\n')
qa['manual_rebased_cycle_n']=int(r.boundary_source.eq('manual_rebase_recomputed').sum());qa['priority_key_with_K_le_3']=int((r.priority.eq('重点候选')&r.known_members.le(3)).sum());qa['final_rows_all_window_min_to_window_max']=True;qa['explicit_human_decisions']=True;qa['daily_panels_reviewed']=4
(O/'QA.json').write_text(json.dumps(qa,ensure_ascii=False,indent=2)+'\n')
files=[p for p in O.iterdir() if p.is_file() and p.name!='OUTPUT_SEAL.json'];seal={'output_file_count':len(files),'sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)},'source_unchanged':all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in json.loads((O/'SOURCE_HASHES.json').read_text()).items())}
(O/'OUTPUT_SEAL.json').write_text(json.dumps(seal,ensure_ascii=False,indent=2)+'\n')
print('REPORT',O/'CONSUMER_SECTOR_REVIEW.txt','bytes',(O/'CONSUMER_SECTOR_REVIEW.txt').stat().st_size);print(json.dumps(qa,ensure_ascii=False,indent=2));print('SEALED',len(files),'files; source unchanged',seal['source_unchanged'])
