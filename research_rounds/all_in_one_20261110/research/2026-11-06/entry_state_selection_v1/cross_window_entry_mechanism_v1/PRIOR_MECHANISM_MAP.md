# 初仓量价机制排重

本文件只解释本轮与既有研究的关系，不把旧未修复权益数字移作新基线结论。查阅范围为本项目及 /Users/bytedance/Documents/ChatGPT/money/research_rounds 和2026-10-29/11-04本地研究。未发现等价实现不等于数学原创。

## 已覆盖，不重新运行

1. **FAST/E0/G/PVR、行业attempt、跨I根支持底**：fast_q1_signal_mechanism_v1 已核原公式、消费/重置、未知及启动边界。独立后续原fresh来源拆分表明弱Q1各路皆弱；同日冲量可同时贡献E0、G2、PVR，不能把三项合格当三份独立信息。原尺度反向候选连续量未能区分寒武纪失败与银之杰早CP，不能换名字继续。
2. **单日信用集中度**：breadth_single_day_dependency_v1 的 Q=E−max(0,w_k e) 已停；pvr_contribution、FIP、刚进入/持续M3配对也已有。不再用扣大阳日、提高G或等待连续日作新发现。
3. **普通参与和留存**：selection_entry_diagnosis_v1/market_participation_flow_audit_v1 使用 B20、5日新进入/退出、端点留存及正收益集中度，不能解释PVR跨年翻转。pvr_sector_breadth_round_interaction_v1 的PVR×B20交互也没有稳定增益。
4. **行业金额份额与扩散**：sector_cp1_diffusion_audit_v1 的 LDP=exp(tanh(Zrel20))×(1+B_t)/(1+B_t−5)×exp(tanh(log(share5/median_prior21_share))) 已有固定日期机制研究。均值PVR、广度×金额份额不是新共同冲击信号。
5. **上下腿单位成交额响应**：retest_impact_diagnostic_v1 的 Z=(U·Vtest−D·Vup)/(U·Vtest+D·Vup) 已停；累计金额把时长混入“承接”。volume_return_kernel_v1 已用成熟历史回归y=a+b r+c r log(A/Aref)，未提供稳定增量。不要换成“每元上涨/下跌冲击”重跑。
6. **推进/波动效率**：range_efficiency_increment_v1、CP timing quality 的CE、双前沿、保护迁移、下行损伤、回撤占用均有前例。Σr/Σ|r|、Σr/sqrtΣr²或换分母不是本轮新机制。
7. **波动重置**：pv-retained-impact-20261020/results/code/trend_shock_scale.py 包含先前剧烈段RMS；trend_quiet_scale.py 使用反向收益RMS。旧PVS-B3/B4还禁止只因旧冲击滚出/分母下降制造恢复。
8. **单资产冲击留存**：pv-retained-impact-20261020 用 e_i(t)=sign(r_i)min(|r_i|,max(0,sign(r_i)(p_t−p_i−1)))，重复穿越会复活旧证据而停。pv-strength-three-axis-20261025 已实现固定episode锚、异常量冲击区间、部分结清且不复活，只晋升描述、不晋升选股。其起点R=1和长期陈旧债务的反例仍有效。
9. **事后成熟失败广度**：trend-failure-breadth-20261027 在原I候选后5日发布失败，滚21日逐股/行业/市场汇总，未可靠提前预警。不能把共同cohort说成首次研究失败参与度。

## 本轮只保留一个很窄的诊断差异

固定同一原行业E0出生时点及当时正价推进成员，冻结原e权重，逐共同交易日记录该批原始价格位移被保留多少；不随强股加入/弱股退出滚动更新成员，不叠加多条重叠腿，回吐后不复活。目标是观察“今天看见的广度是否还是原始参与群体的价格推进”，不是证明启动能成功。

这仍不是一个完整的新共同量价冲击模型：anchor来自原行业E0，不是从跨股联合创新创建；e>0按价格符号选成员，成交额仅改变权重。故必须保留等权/u权重控制和非参与成员同期价格推进；若结论与纯价格相同，不能宣称量能增量。

公共行业分数不能直接做同业选股。排除目标股只是避免自我贡献；等权时 R_{−i}−R_{−j}=(h_j−h_i)/(N−1)，若直接排序LOO会机械逆排自身留存。出生当日全体R=1也没有持续性信息。任何可执行消费者还须明确新增权限、等待代价、UNKNOWN、原fast/AB各自权限及名额影响，目前没有这种授权或已验证公式。

本轮限定固定25例的小诊断，不跑更广评分、不训练、不重排、不接账户。历史案例已反复见过，不是盲法/OOS；只要固定反例不能支持其新增解释，就停止，不能改锚、调衰减、换窗口或挑阈值挽救。
