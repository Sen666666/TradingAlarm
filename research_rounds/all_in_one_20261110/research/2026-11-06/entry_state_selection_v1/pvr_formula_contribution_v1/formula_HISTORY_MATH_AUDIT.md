# 原PVR公式溯源、数学性质与排重审查
2026-11-08。只读既有代码/研究，另做原函数内存合成核验；无新病例计算、参数网格、账户或原文件修改。本文不批准候选，不宣称预测效果。

路径缩写：
R=/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1
D=/Users/bytedance/Documents/Codex/2026-11-04/task-3/entry_quality
M=/Users/bytedance/Documents/ChatGPT/money

## 精确原式及来源
权威代码M/research_rounds/pvr-act-comparison-20261027/code/experiment.py:24–42；原函数抽取副本在/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/pvr-current-v3-information-capital-20261101/original_score_function.py。本次AST定位抽取与副本逐字相同，SHA256=9328109bada26c53b04cf0f3e84d719917cb528ff8608b3e9faa5d1c55ba8cb2。
最初合同M/research_rounds/pv-rank-q1-20261027/FORMULA.json。

r=log(C)-log(Cprev)；
s=max(1e-8,1.4826 median(此前63个|r|))；
Aref=median(此前21个A)；
u=tanh(r/s)，b=tanh(log(A/Aref))；
m=1+0.5|u|b，e=m*u；
w_k=.9^k/Σ_(j=0..20).9^j，E=Σ_(k=0..20)w_k e_(t-k)；
S=50+50tanh(2E)。

s不是中心化MAD或标准差。A是真实CNY成交额，不是股数、换手率、资金净流入；不作价格复权。当日价额完整值只在收盘后已知。

## 原时钟、预热、缺失与复权
有效行要求close/amount正且有限；可选price_eligible/observed_bar/is_observed_bar须为真（NA按假），source_invalid/synthetic_event_bar须为假（NA按真）。无效行或segment_id改变使全预热重启；原函数无segment_id时默认0。首e在第65个有效收盘，首S在第85个（零基64/84），未知不填50。
原score不读交易日历。输入中不存在的日期不推进、不自动重置；出现invalid占位行则重置。“确认停牌不推进、未知缺口重置”需要上游正确标记，不能说score独立核实所有缺口。
原E是21个贡献，但每个e另有63收益/21金额前史，S最远原始价格支持可到t−84，不等于只读最近21根全部数据。

M/research_rounds/current-pool-20261022/code/current_pool_bridge.py:145–220显示因果signal坐标：theoretical_ex_price以ex_price=(previous−cash)/split、factor*=previous/ex_price更新；OHLC统一乘当时factor，volume另按share_units调整，amount原样保留；合成公司行动行不是实际观察。239–258以声明segment断开来源。原score不因factor变化本身重置。存储price_adjustment字符串不是再次复权许可。
这是计算规则核对，不证明公司行动条款发布时点、供应商历史版本、ST/停牌、实际开盘成交已PIT认证。

## 三组可证明性质
### 1. 幅度/单位不辨识与路径压缩
全前缀变成C_j的新值=k*C_j^a，a>0，且s固定底板均未触发，则r与s同乘a，全部u/e/E/S相同。绝对涨幅相差很大的比例相似路径可以同分。金额全乘正数也不变。价格镜像k/C令r/e/E反号，S镜像为100−S。
单日tanh在有限实数上严格单调，并非任意不同q数学上同值；它压缩跨日相对冲击，浮点大q才会精确饱和。真正多对一是省略尺度、合并u/b以及21维贡献压到一个E。0.9权重仍包含部分顺序，不能说完全不读顺序。
既有D/pvr_information_v1/math_review/READOUT.txt已经有这些性质和6对同PVR异路径见证，不是本轮新发现。外层tanh仅单调映射，改显示斜率不改变精确排序。

### 2. 金额调制保留日收益方向
a=A/Aref时b=(a²−1)/(a²+1)，m在0.5到1.5之间，所以sign(e)=sign(r)。
放量增强正日和负日；缩量削弱正日也削弱负日；r=0时量再大也无e。金额增量e−u=.5u|u|b，不能解释为真实买卖方向。
固定s/b时de/du=1+|u|b>0。|e|、|E|<1.5，S约在(0.2473,99.7527)，外层没有逼近double的0/100饱和。不能把亏损原因简单归为最终分数显示饱和。

### 3. 负项封顶、旧信用与滚出边界
w0=.11228624771875692，w20=.013651386354174415。
近5/10项占45.9823413%/73.1344540%；半衰6.57881348观察；平均年龄6.41988798；有效权重样本量15.25216295。
E_t=.9E_(t-1)+w0*e_t−w0*.9^21*e_(t-21)，最后系数=.012286247718756974。
旧负项滚出可抬分，不需要价格收复；日负项封顶，单次急跌可被旧正贡献覆盖。原式没有每段已回吐涨幅的独立偿还账。但忘记旧坏日也保留重入弹性，不是单向缺陷。
原函数合成：长期+.005 log/日、恒额，u=.5879261383，S=91.30696192；仅末日−.10 log，u≈−1、E=.40962387054、S=83.73301135。这个见证不是固定22点的失败解释。病例worker已报告固定22点最近1/3/5日净e全部正，因此不得将“已发生近期净破坏被掩盖”强写成它们的共同原因。

## 已试研究地图：不能换名
1. 尺度移到聚合外/趋势与噪声分离：M/research_rounds/pv-strength-20261025/CONCLUSION.md的B1用潜在level/drift/temporary，S=100tanh(√21*mu/sigma)。急跌仍近满分、启动先归暂时冲击，未晋升。pv-strength-b3-20261025两窗OLS/RMS受大冲击抬分母掩盖阴跌；pv-strength-b4-20261025已用原单位EMA5/21推进与冻结前沿，改善部分语义但旧大涨后的平滑/结构滞后仍在。
2. 当前负日去饱和：R/entry_current_downside_unsaturation_v1/READOUT.md，Q=E+w0*m[min(r/s,0)−min(tanh(r/s),0)]。仅移出2022目标3条、2024目标6条，同时丢益生/中国软件/兆威等赢家，覆盖不足且无界，停止。
3. 历史保留价差：M/research_rounds/pv-retained-impact-20261020/code/trend_retained_impact.py及M/docs/RESEARCH_ROUND_2026_10_20_RETAINED_IMPACT.md。63窗/21半衰/量sqrt，每条r按当前仍保留部分计分；同价域重走复活旧贡献，固定同端点1/3/6次穿越分2.0220/2.5432/3.1212，轨迹阶段否决。
4. 正负位移完全抵消：M/docs/RESEARCH_ROUND_2026_10_20_COMPETING_STATE.md已经推导代数和退化为窗口端点log位移，剩余同号，正量权不改方向。随后level jump/observation shock竞争及drift-break模型已试；后者更快但普通损耗大，旧ETF/HK净+2.75%/−30.62%，未晋升。与本A股账户合同不同，不拼结果。
5. 跨锚有符号信用：R/selection_entry_diagnosis_v1/cp1_signal_mechanism_v1/soft_cp1_quality_v1；R/rsi_pvr_credit_fusion_v1/READOUT.md。U/D=RMA21(m*r正/负)，Q=100U/(U+D)替PVR已测；PVR域20日年度差−.188/+.025/+.584/−.036/−.480pp、MAE均差。再以Q折减正E也未支持晋升。
6. 原贡献保留/承接：D/pvr_contribution_attribution_v1/run_attribution.py及FINAL_RESULT.json已有E_price、E_amt_retained、E_path_retained、kappa、E_support=E−A_up(1−P5)、首破豁免。support的60日原I事件等权差−.1333pp，早大根2370→2249；等5日误伤早启动，首破豁免也恢复失败。
7. 记忆重组：D/pvr_dual_memory_v1/READOUT.md，快5个e用.8、慢6–63共58个e均值、分位.3/.7。CONT三期20日均值低原PVR；强期FAST损尾，旧失败反弹进入慢窗仍可高分。不是改半衰就有新机制。
8. 量价响应核：R/volume_return_kernel_v1/DECISION.json，旧I起点冻结504窗/至少252已成熟样本，fit y=a+b*r+c*r*V，e=tanh((b+cV)r/s)。51430 known/53121机会；5/20/60日差−.1369/−.3139/−.6641pp，大根715→655，停止。“放量可反转”已被直接测试。
9. 原股数替金额、OBV、CMF：R/pvr_raw_share_ablation_v1仅19/14185换槽；OBV折减仅46/1749已知闭MOBILE受影响、14赢家；CMF只换27槽，60日正差去最佳日变负。CMF以REPORT_AUDITED.md的封存和2026共同分母修正为准，不能说2026根本零替换。
10. H/L：R/range_efficiency_increment_v1，Qrange=D/ΣTR=Qclose*Σ|ΔC|/ΣTR，无稳定增量，保留43条原PVR未知被重排的合同缺口；R/dmi_boundary_migration_v1，E*=E+.25d*max(E,0)，49/14185换槽，未晋升；R/common_boundary_translation_preflight_v1，median(ΔlogH,ΔlogL,0)固定18可计算点全通过、亏赢不分，不复用。
11. 价格区域：M/research_rounds/pv-price-region-20261020/code/trend_price_region.py是两相邻21窗、量sqrt加权25/50/75分位迁移除63 RMS√21，旧ETF/HK净−2.78%/−3.60%、跳启滞后等而否决。后续RESEARCH_REGION_PATH_AUDIT发现并列价格排列伪效应，原量增益解释不能照搬。
12. 回撤/损伤：R/entry_drawdown_occupancy_mechanism_v1的Q=1−平均回撤/总路程会奖励额外往返分母，合成否决；R/lifecycle_ordered_damage_v1和普通下行波动高度重叠，年AUC .463/.507/.533/.472/.510，无稳定选择增量。
13. 二阶/效率近邻：D/pvr_information_v1/math_review/FUSION_HYPOTHESIS.md已有L+=(Σw e+)²/Σ(w e+)²折减正E、会压强首脉冲/快V；旧η=Σwe/Σw|e|及KAMA/ER/63路径效率已有。R/selection_entry_diagnosis_v1/cp1_signal_mechanism_v1/cp_timing_quality_v1/candidate_test/REPORT.md的CE=min(CP D,K)/√Σ形成期滞后21均方预算已全机会测，部分弱市改善而2025/26及IMPROVING变差，偏好一日跳涨。以上不是下面加权均值/均方根的恒等式。

## 备选一：独立日内方向量项，建议不冻结
父提案e_body=u_cc+.5*u_oc*|u_oc|*b，u_oc=tanh(log(C/O)/s)。
它有界、无gap或b=0时还原原式，但经济假设已属旧时段归属：
R/intraday_overnight_attribution_v1已测e*=k[m*d+m_prev*n]，n=gap，d=body，k=tanh(r/s)/r（r=0取1/s），53121机会换637槽，20/60日−.0703/−.0693pp、大根715→711；预热出现−183989无界问题。
CP六例m_body=1+.5*tanh(d/s)*b、Σfresh*m_body也已试，六例全通过；见R/selection_entry_diagnosis_v1/cp1_signal_mechanism_v1/first_signal_ohlc_mechanism_v1/REPORT.md:93。其anatomy报告高开收阴旧首仓26.83%对其他25.65%，弱市31.37%对23.44%，不支持先验一律判坏。
新式非等价且无界问题确实消失，但出现原式没有的收盘非单调：固定gap/s=4、b=−.8，body/s由.5涨.6，新e却.9143323040→.8844290466。缩量正body的负调整可盖过饱和cc主项。缩量阴body反而正调整。父任务已决定不将其冻结，不在看病例后改b/阈值救活。

## 备选二：未见等价实测的加权均值/均方根，尚未批准
固定原a_j=w_j*m_j>0：
G=Σa_j r_j / sqrt[(Σa_j)(Σa_j r_j²)]；零能量时定义G=0；
score=50+50tanh(2G)。
纯数学/历史审查，不读取固定病例的新G，不测试新名单。

检索R、D及M/research_rounds、M/docs的weighted Sharpe、RMS、信噪、coherence、energy、相干、均值/均方与代码sqrt/sum近邻，未找到同式PVR消费者。命中多为账户Sharpe绩效、η/L+、B1/B3、CE、peer Zrel20，均非等价。此为限定检索结果，不证明所有旧聊天不存在。

p_j=a_j/Σa，μ=Σpr，σ²=Σp(r−μ)²，则G=μ/sqrt(μ²+σ²)=SR/sqrt(1+SR²)，SR=μ/σ。是加权Sharpe的有界单调变换，不是新理论、不是未来收益预测。Cauchy保证|G|≤1。价格/量单位不变，原s底板不活跃的全前缀C^a伸缩也不变。只有一根非零r时G=sign(r)*sqrt(p_j)，不是可以任意大；负向大冲击在加总前不再被每日tanh截平，但m仍保留旧tanh。

与Qclose/RSI的L1分母不同：两条全正路径的Qclose/RSI均最大，而G随幅度分散变化；与L+不同：它用raw r及a加权r²而非(w e+)²，且负项直接入分子；与B3不同：不是OLS位移/滞后RMS；与CE不同：不是CP形成锚、前沿信用或历史预测方差预算。

必须先接受的经济代价：
- 它惩罚正向突增和负向突增，不是只修复下跌。b=0、m=1，前20日r=ε，末日从ε升到10ε，G由1降到.5776101873371753，score98.2013790038→90.9738053846，尽管最后价格更强。任意极小等幅单边微涨均给G=1。
- 固定正权下，令其余B=Σa r、C=Σa r²、当前权a、A=Σa，则对当前x的导数为a(C−Bx)/[sqrt(A)*(C+a*x²)^(3/2)]。B>0且x>C/B时更强正日反而降分。原m随当前r变化并不消除此问题，因为b=0已给完整合法反例。
- 它仍是平滑度/方向一致性偏好，可能压924跳启、科技加速、肥尾初段；一根首脉冲仍能得到正分（p=w0时G=.3350914020、score79.2550），不是硬门，却无法保证资金排序保留。
- 高分不包含绝对盈利空间，全部21项微小正r可比大涨更高；旧负日滚出仍会升分；右侧重入没有固定冷却但负能量留窗可能压早V。
- 平价窗定义0是显式约定；σ=0但非零常数收益则G=±1，不应作为未知。
- 是否符合任务想要的经济语义由父任务裁决。若要求强正推进不能因为自身更大而降分，该式不满足；不再提供第三个变体。

## 验证与交付边界
原函数内存QA：AST副本字节相同、首e64/score84；C变73*(C/100)^3且金额19倍最大S差2.13e−13；镜像误差2.84e−13；70号行amount缺失后79个剩余收盘仍不就绪。合成不验证价格限制/交易资格或未来预测。
文件只记录溯源和数学，不重新消费case输出结果，不改源、经济、冻结产物。相关路径均可定位；不能称完成全历史未见样本外验证。
