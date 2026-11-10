from pathlib import Path
import json,hashlib,datetime
import pandas as pd
O=Path(__file__).resolve().parent;R=O.parent
W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(n,d):
 with (O/n).open('x') as f:json.dump(d,f,ensure_ascii=False,indent=2);f.write('\n')
x=pd.read_csv(O/'POINT_FEATURES.csv');q=json.loads((O/'SUMMARY.json').read_text());src=R/'pvr_formula_contribution_v1/case_FIXED_CASES_WITH_CONTEXT.csv';ctx=pd.read_csv(src);keys=pd.DataFrame(json.loads((O/'FIXED_CASES.json').read_text()),columns=['sid','day','case_source'])[['sid','day']]
cols=['sid','day','old_price_status','old_price_net','close_size_check','open_size_check','historical_fill','context_class'];z=keys.merge(ctx[cols],on=['sid','day'],how='left',validate='one_to_one');z['scope']='Previously seen conditional PRICE case context, NOT current ACT actual order/position/outcome';assert len(z)==22;z.to_csv(O/'EXISTING_CASE_CONTEXT_REUSED.csv',index=False)
old_attention=W/'market-mainline-measurement-20261031/rank-comparison/FINAL_REPORT.txt'
save('READOUT_REFERENCE_HASHES.json',{str(src):sha(src),str(old_attention):sha(old_attention),str(Path(__file__)):sha(__file__)})
lines=['# 同业异常成交额扣除：固定22点机制检验','',
'## 裁决','',
'完成唯一冻结公式的固定22点计算与既定工程检查，停在机制层，不晋升、不扩样、不调peer覆盖阈值、不换消费者挽救。22点均为已看过的开发病例，不是新胜率样本；本轮没有新增未来标签、排名、选择、订单或账户。',
'','本式确实改变原PVR的个股量额信用，而非仅对最终分数做共同缩放；但没有给同方/南网、华电/海能达提供预期固定病例区分，同时降低江丰四个既定时点的信用。它还会减轻负收益日借记，使部分分数上升。不能据此宣称净流、行业因果剥离、准入改善、收益改善或实际买错/错过。',
'','## 冻结与不等价排重','',
'PROTOCOL、FIXED_CASES、原ACT映射及449个同业源hash先于新分值封存。22股日、19股、13行业不增删。原ACT使用的1709/90由 run_act_only → continuous_inputs.inputs → adapter.context → load_bundle(input-manifest) → selection.lines 取 sector_id；和ACT fixed_ids/sectors及原metadata逐项一致。只读取这13行业的449股历史以构造22点的21日贡献，没有计算全候选新分数。',
'','DEDUPLICATION.json逐一记录实际代码/公式，不仅用关键词判新：',
'- 原PVR贡献分解：b=tanh(个股当日额/自身前21额中位数的log)，没有同行参照。此前body核是 e_new=tanh(r/s+0.5*b*tanh(log(C/O)/s))，界为±1，本次不沿用其压缩论证。',
'- volume_return_kernel：个股成熟样本拟合冻结b、c，让(b+cV)作用于收益；明确不同行业pooling。本次不拟合收益响应、不改u。',
'- raw-share：用自身原始股数替换金额；dual-frontier：用均价与价格联合前沿改CP回执；均非同业量额扣除。',
'- 63β/21残差：先用63个行业/个股收益拟合β，再取21个收益残差；CH3为月度36月拟合、11月残差均值/标准差；peer_downside取同行下跌日的个股减同行收益。这些都改价格比较，不在原b中扣量额共振。',
'- sector_cp1_diffusion/LDP：同行业总CNY额占全1709可用总额，近5均份额对此前21中位份额，经exp(tanh(log ratio))再和价格残差/广度组合。其分母是全市场活动份额，而非每只同行自己的前21基准。',
'- market-mainline attention：固定26日交集的个股全市场额份额，近5中位/前21中位后再行业中位。它也对共同市场额倍增不敏感，但输出行业关注排序，不是本次leave-one-out逐日h及个股PVR日项。',
'','在上述持久化代码范围内未发现严格同式，故执行此唯一小样本。不能把相近旧式统称失败：attention既有同股票候选预算窗内机会覆盖1260，超过R21/H1上界1229/1192；但首锚436未全面优于价格上界487/511。那是2025Q3–2026Q2已消费样本的价格机会代理，非同版I、资金或交易账户；可保留线索，不能转授本式有效性。见DEDUP_EVIDENCE_ADDENDUM.md。',
'','## 唯一公式及真正含义','',
'原u=tanh(r/s)、63观察尺度、原Aref=前21有效额中位数、原观察/invalid/segment重置时钟完全不动。v=log(A/Aref)；h为原静态行业剔除自身后当日可用同行v的中位数；b*=tanh(v−h)；e*=u(1+0.5|u|b*)。原21观察、0.9权及外层50+50tanh(2E)不变。',
'','单日差为0.5u|u|[tanh(v−h)−tanh(v)]。当h>0，上涨项减弱，下跌项也减弱而更接近0；并非单向惩罚放量上涨。h<0方向相反。日项与u同号，仍受原±1.5界约束；价平不凭空制造日证据。',
'','所有成员异常v相同则b*=0；在可用成员不变的代数控制下，所有成员当日额共同×k令各v同加log(k)，v−h完全抵消。固定货币单位在当日额和全部参照额共同变换也抵消。这些是不变性，不证明h是行业因果成分、买方需求或净流。实际原始额/股数/价格的合法性仍单独检查，不能把单改原始额的合成数当真实行情。',
'','## 覆盖、UNKNOWN与时点','',
'同行可用必须有原时钟内当日及前21有效观察；额的原基准不改。另做严格22来源审计：真实/eligible标志、OHLC/raw一致、shares/CNY、额/股数落raw价格区间，source_kind/path/segment一致，正且不变的adjustment_factor/volume_factor。数据缺失或边界不补零。该恒定factor条件是本轮保守证据约束，不等于原复权过程有错。',
'','每行明确同行总数、可用数/比例、名单与缺失原因。全行业仅一股或无可用peer为UNKNOWN；本固定样本没有这种情况。中位数只代表available-peer条件参考，不是完整行业；本轮未自造数据或事后加最低覆盖阈值。',
'',f'本轮{q["unique_peer_date_rows"]}个唯一member-day参考中，{q["peer_unique_available"]}可用、{q["peer_unique_missing"]}不可用：2484无当日观察、627 adjustment_factor跨界、162原block不足22、19同时adjustment/volume factor跨界。缺失/IPO/来源状态会改变参考集合，不能被“median稳健”一词抹去。',
'','最少同行数是共创草坪6/9；最低覆盖是寒武纪2022-03-04所用窗口59/125=47.2%。因此尤其不能声称该处已稳健估出完整行业量额：过半固定peer不可用，未知群体可以改变完整行业中位数。available-peer中位数可机械计算，完整行业代表性未获证明。其余各点最小覆盖见表。',
'','原分严格85共同日审计18点通过，力鼎光电、永和股份、福莱新材、歌尔股份4点因adjustment_factor变化保留UNKNOWN。原时钟机械分仍可复现，新机械值也列出，但score_peer_supported为空，不把4点大降分混作严格效果。peer_supported只表示冻结计算/来源条件满足，不表示有预测力。',
'','同日h在该日收盘后才可知，最终t分数最早下一独立交易时点可用。原池/行业来自后定静态snapshot，包含未来成员/存活者选择，全部NON-PIT。物理prefix测试不证明当年的数据发布、成员或复权版本可得。',
'','## 全部固定点','',
'表中N为21个贡献日的最少可用peer/固定总peer；百分比为最小覆盖。UNKNOWN行的新值仅机械演示。',
'','| 股票 | 信号日 | 原分 | 新机械分 | 差 | 来源状态 | 最少peer | 最小覆盖 |','|---|---|---:|---:|---:|---|---:|---:|']
for row in x.itertuples(index=False):lines.append(f'| {row.name} {row.sid} | {row.day} | {row.score_original:.3f} | {row.score_peer_mechanical:.3f} | {row.score_delta:+.3f} | {"条件可计算" if row.peer_supported else "UNKNOWN"} | {row.peer_min}/{row.peer_total} | {row.peer_fraction_min:.1%} |')
lines+=['','## 重点读数与代价','',
'- 同方2022-01-04：82.016→81.724；南网2022-05-12：82.000→81.194。新式没有给这两个历史固定病例提供预期区分。两者不在同日同业同槽，不存在此表证明同方抢走南网名额的含义。',
'- 华电2024-10-28：88.228→86.717；海能达2024-09-25：83.661→81.627。新式仍使前者的跨日期分数更高，但不能将跨日数值顺序称真实错误买单或资金机会损失。',
'- 寒武纪2022-03-04：66.322→68.352。上升日对E的差−0.000587，下跌日对E的差+0.023671，主要来自负日借记减弱，不是新增上涨证据。旧已看上下文是条件PRICE完整回合亏损−5528.79；historical_fill=UNKNOWN_NOT_SIMULATED，OPEN仅条件可行非fill。没有在本轮接当前ACT真实订单，不能称ACT实际买入的反例胜负。',
'- 江丰2025-12-15、12-17、2026-01-05、01-15分别−1.330、−0.938、−2.200、−2.509分；1/5由65.115降62.915，E量额项由0.067595降0.043715；1/15由91.771降89.261，E量额项由0.152855降0.079388。这是可能减少早期排序信用的机制代价，非实际漏买。四点无精确原PRICE回合，且1/15旧条件病例为Q0，不能包装成四个赢家或新胜率。',
'- 同日2026-01-15的江丰/珂玛/金海通都降分；这里不能单凭降幅判收益、入选或资金变化。',
'','原case上下文已在特征封存后逐键复用到EXISTING_CASE_CONTEXT_REUSED.csv，没有新增未来结果。其条件PRICE合同与当前ACT账户不同，当前ACT实际买入/未买入状态不由此表认证。',
'','## QA与停止边界','',
f'- 22个原分及逐日u/b/e/E/score与既有分解最大差{q["original_daily_max_error"]:.3g}；original_pvr和原score函数同输入逐元素完全一致。',
f'- 22个时点均将每个用到的成员源物理截在t，另把t后close/amount污染，合计{q["member_day_prefix_checks"]} member-day对照完全一致；源hash前后未变。',
'- 固定单位、同异常v、共同当日倍额抵消、leave-one-out、自身符号/±1.5、无同行UNKNOWN、invalid/source/segment/factor边界均通过合成检查；详见SYNTHETIC_QA、PREFIX_FUTURE_QA。',
'- 输出22点、462逐日贡献、27048逐贡献peer审计行；无账户、全候选新分、排名、调参、新标签或选择改变。',
'','本轮结果仅证明冻结公式可在上述条件数据上计算及它怎样改变已有日证据，未提供值得晋升的固定病例区分。停止，不改变peer覆盖阈值来救结果。若未来另行批准消费者，也只可能更改原pending顺序；当前原账户没有TopK，CORE/MOBILE同股耦合，排序影响取决于真实竞争及资金路径，不能搬旧TopK消费者结论过来。',
'','## 文件','',
'- POINT_FEATURES.csv：22点，机械值/严格支持值分列。',
'- DAILY_CONTRIBUTIONS.csv：462个日项，u/v/h/b/e与E贡献、coverage。',
'- PEER_COVERAGE_EVERY_CONTRIBUTION.csv / PEER_UNIQUE_SOURCE_AUDIT.csv：逐peer来源、支持起止与UNKNOWN原因。',
'- ORIGINAL_REPRODUCTION.csv、PREFIX_FUTURE_QA.csv、SYNTHETIC_QA.json、SOURCE_HASHES_AFTER.json：复现及工程证据。',
'- PROTOCOL.json / FREEZE_SEAL.json / COMPUTATION_SOURCE_FREEZE.json：计算前冻结。',
'- DEDUPLICATION.json / DEDUP_EVIDENCE_ADDENDUM.md：限定排重、旧线索证据等级。',
'- EXISTING_CASE_CONTEXT_REUSED.csv：旧条件病例上下文，不冒充ACT实际成交。','']
(O/'READOUT.md').write_text('\n'.join(lines))
(O/'DEDUP_EVIDENCE_ADDENDUM.md').write_text('''# 旧attention证据等级补充

此为阅读已有报告的补充，不改冻结公式或病例。DEDUPLICATION.json仅判严格同式与否，没有宣称所有相近旧式负结果。

原market-mainline attention在共同P资格、共同已知mask、每日相同候选股票数预算99738股日下，窗内后续价格机会覆盖1260，大于R21/H1整行业超预算上界1229/1192。它存在应保留的排序线索。首锚436并非全面优于R21/H1上界487/511，且完整行业预算是阶梯上下界，不是完全相同资金风险。样本是2025Q3–2026Q2已消费历史，价格机会代理、删失与同版原生I接口限制均保留；不是交易账户、PIT或独立有效性。

本次是原固定行业逐股自身基准异常额v的leave-one-out当日中位数h，从原PVR的b输入中扣除。旧attention是全市场成交额份额的5/21时间比再行业中位并在行业层排序，时间、分母、输出/消费者均不同。共同放量不变性的重合不使二者代数等价，也不把旧attention的正线索转给本次新核。

来源：/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/market-mainline-measurement-20261031/rank-comparison/FINAL_REPORT.txt

本轮裁决仍停在22点机制层。所有新分差不是新胜率、交易收益或买单。
''')
save('COMPLETION.json',dict(status='COMPLETE_FIXED22_MECHANISM_STOP_NO_PROMOTION',completed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),case_n=22,stock_n=19,strict_computational_supported=18,lineage_UNKNOWN=4,all_original_sources_unchanged=True,no_new_outcomes=True,account_runs=0,ranking_runs=0,consumer_changes=0,parameter_searches=0))
save('FINAL_OUTPUT_SHA256.json',{p.name:sha(p) for p in O.iterdir() if p.is_file()});print('READOUT_COMPLETE')
