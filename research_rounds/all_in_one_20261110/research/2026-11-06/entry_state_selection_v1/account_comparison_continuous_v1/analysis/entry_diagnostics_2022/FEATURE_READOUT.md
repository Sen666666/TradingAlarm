# 2022 PVR 首次开仓特征诊断

范围：原120万元账户2022年内完成的692个股票0→0回合，562亏、130赢。闭合回合净损益−372009.36元，包含后来加减仓及费用/股息，不等于账户全年−359093.74元。年末未闭回合未纳入，故存在闭合条件选择，不可推广为全体入口无偏估计。没有新账户、改规则、阈值搜索或参数网格。

## 校验与时间

ENTRY_FEATURES.csv 692行，唯一键(account,sid,round_id)与STOCK_ROUNDS_2022.csv原id完全一致。首买是回合layer_ids中最早实际buy。entry_quarter为首次执行北京时间季度；signal_quarter独立保留。H1得分、四段raw加总、原PVR缓存、决策PVR_score均692/692一致。trade.pvr实际保存H1，绝未作为真正PVR。

特征截至signal_at。execution_*及first_buy_actual_pool/attempt为执行事件属性，不能冒充signal已知；pool来自real_buy_fill日志，绝不取年末迁移后的pool。行业stage、financial_level单列，后者658条来自不晚于signal的native stage日志、34条来自未变的账户初始warm状态。first_role=MOBILE指本回合从零持仓开始的首买角色，不是已有持仓加仓。

## 冻结公式

H1：h≤252，b_j=min(63j,h)，raw=Σ(.4,.2,.2,.2)_j×(C[t-b_(j-1)]/C[t-b_j]−1)，重合边界贡献0，结果round12；至少6观测、同段、同h横截面至少20参考。score=100×(严格更小raw数+0.5×相等数)/有效参考数。股票与行业分别横截面。四段回报、权重贡献及实际近/远lag均保留。

PVR：有效正close和amount、真实观测且非synthetic，失效/segment改变重置。r=ΔlnC；s=max(1e−8,1.4826×此前63个|r|中位数)；Aref=此前21个成交额中位数；u=tanh(r/s)，b=tanh(ln(A/Aref))；e=u×(1+0.5|u|b)；E为最近21个e按0.9衰减、越新越重的归一加权；score=50+50tanh(2E)。本次象限以signal当日r与ln(A/Aref)符号定义，不是成交量，也不是昨日成交额。

阻力：signal以前严格20根同segment、有效真实观测的调整后high最大值；同时保留close最大值。距离=C_signal/该值−1。均价延伸=C_signal/前20根平均close−1。另以原冻结CP1.s缓存标准化log(C_signal/均价)和log(C_signal/最高high)，原值与分母同时留存。这只是位置描述，不将20日阻力虚构成未来收益目标。

首层floor保持原调整价格域；signal raw floor=floor/factor_signal，execution raw floor=floor/factor_execution；风险距离分别1−raw_floor/C_signal_raw、1−raw_floor/O_execution。原raw开盘变化与factor统一开盘变化并存，后者也仅执行时已知。I年龄为同segment连续i_target=True段，自首日起到signal有效观测数−1，无未来信息。

## 描述结果

- 首CORE229回合30赢，13.10%，净−107504.42；首MOBILE463/100赢，21.60%，净−264504.94。全部MOBILE为新鲜CP1；CORE119同日也有CP1、110无。CORE全probe池；MOBILE confirmed池432、probe31。信号日692均I_target=True。
- 当日上涨且成交额高于前21日中位数677回合127赢(18.76%)，净−362240.66；上涨低于中位数15回合3赢(20%)，净−9768.71。无下跌象限，样本没有支持公平四象限比较。
- 高于严格前20high411回合73赢(17.76%)净−248591.61；未高于281/57赢(20.28%)净−123417.76。
- Q1首MOBILE：189/27赢净−199357.98；其中高于20high89/6赢(6.74%)净−121372.25，未高于100/21赢(21%)净−77985.73。但Q2同角色高于组70/22赢(31.43%)，未高于28/7赢(25%)，方向反转，不能据此直接禁突破。
- Q1首MOBILE亏/赢组均值：H1最近一段19.84%/8.09%，20日均价延伸10.72%/6.22%，I年龄23.38/7.59有效日，signal floor距离7.87%/6.07%。Q3/Q4这些关系不全部保留，不宣称稳定预测力。
- Q1首MOBILE行业expanded113回合14赢净−144607.97；Q2同组61/23赢净+15318.07。市场/季度混合是重大混淆，industry expanded不是稳定亏损判据。

所有组均给样本数、赢数、胜率与净金额；金额还受回合后续层数/规模影响，不能单归因首买特征。固定未来1709池、开盘O±5bp因果代理不保证可成交、公司行动条款预先已知假设均继承原回放。未来路径表仅事后诊断，不能回流排序。没有统计显著性或样本外策略结论。

## 文件

build_entry_features.py；ENTRY_FEATURES.csv；CATEGORICAL_QUARTER_DIAGNOSTICS.csv；NUMERIC_QUARTER_OUTCOME_DIAGNOSTICS.csv；ROLE_QUARTER_OUTCOME_NUMERICS.csv；ROLE_QUARTER_CATEGORICAL.csv；VALIDATION.json(输入SHA)；OUTPUT_SHA256.json。
