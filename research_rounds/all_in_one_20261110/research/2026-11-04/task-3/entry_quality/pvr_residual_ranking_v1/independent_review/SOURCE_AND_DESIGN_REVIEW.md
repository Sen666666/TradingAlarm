# 原排序接口与残差组合：有界独审

本件只读源码与冻结稿，未运行账户、退出、指标或候选策略。源码/保存输出审计通过不等于新排序有效。

## 原接口

No60的`native_adapter.py:27–33`保留`N.Runner.planning`与`J.Runner.opening`。`joint_v3.py:214–220`先计算S0资格，按当日`sd[sid].rank.read(clock)`降序、sid破同分排全股H1次序；242–258行经过CORE/mobile角色、ACT/待退/待买屏障、报价/保护线与正cap后形成pending。不是对全1709股票直接排序后都可买，也不是仅已成交者。

`native_rank.py:115–120`在原planning完成后调用47–74行`priority_plan`：同股CORE/mobile合并为一个股票slot；原PVR按`-round(score,12)`降序，tie保H1先序，缺分股票留原H1槽；再使用原数字rank键（可有全市场空隙）。原PVR是跨行业pending股票替位，未调用通用S0行业轮转。OPEN仍按同股CORE优先，reserve成功即done，实际fill在所有资金决定之后。原trade.pvr/H1 score别名也不能代替真实PVR排序值。

原PVR `experiment.py:24–42` /逐字抽取`original_score_function.py`：`r=log(C).diff`；s为此前63绝对r中位×1.4826；amount背景为此前21中位；`u=tanh(r/s)`、`b=tanh(log(amount/background))`、`e=u*(1+.5*abs(u)*b)`；E为最近21项e、0.9衰减的有限加权和；`score=50+50*tanh(2E)`。它不是无限EWMA，也不是成功率。无效或来源变化切block重准备。实际运行读取冻结score缓存，不现场重算该函数。

H1通过`current_pool_bridge.py:331–347`读取当日h1矩阵并构造Rank；`Rank.read`核同session/known时钟并round12。原`sector_stock_admission.rs_score:163–175`定义4×63观察RS，不能将其名称与本候选的RS20混称。此次没有重算H1矩阵或逐股票核其值。

## 不能从残差定义推出的结论

当p、q无ties且同n分位时，两者均值为1/2且方差相同，内点OLS的b就是Spearman相关；约束后b=max(0,rho)。q=p时残差应全tie、残差分位为1/2，而不是制造唯一名次。

原残差与p样本协方差为0只对无约束内点OLS成立；负相关时b被截0，不成立。残差再rank也不保此正交性。近乎同序、仅两名邻位交换时，未交换者有`epsilon=(1-b)*(p-1/2)`，再rank可能把这个很小的p相关项重新铺满0..1。0.3权重会把微小剩余差异变为完整排序贡献。因此本组合是一个先验排序变换，不能叫已剥离PVR后的独立信息。

原PVR与RS20、距旧高和两段低点均来自价格路径。重新组合可能有用，但不是外生新增数据；0.5/0.3/0.2及n>=10都属预先假设，不是经济推导。n>=10不保证有效十个独立观察、p方差或残差稳定。PAVA仅作预先固定的形状敏感度，不能据结果改选主模型。

若同一day/sector股票使用同一20观察起止日，减同一行业回报不会改变RS20的截面名次；此时q就是个股20回报名次，不含额外行业共振。各股起点不同必须按各自stock anchor取行业精确同日端点，UNKNOWN不近邻补值，并报告起点/自然日跨度差异。

两段五观察低点改善是滚动收盘路径形状，不是已确认higher-low事件；旧低滚出窗口也可改善。prior20高必须排当日。各输入沿原同source/block、完成CLOSE，不能用日后pivot或峰。

## 当前冻结合同的可执行边界

冻结稿已采用全部四输入同完整组、n>=10、零p方差UNKNOWN；约束OLS闭式、平均tie分位、残差round12；结构先各自分位、等权后再分位。缺值不填0，不为凑10扩大候选池。当前组合只在**同业原PVR占据的槽位集合**内排列，未知和小组保原PVR位置，跨行业slot pattern不变。这是较原PVR接口新增的局部替位合同，不能暗改为全局按S比较行业内分位。

`original_H1_rank`/`original_PVR_priority_rank`是可有空隙的native数字键；`original_*_slot`是pending ordinal；行业rank又是行业子集名次。不能把三者互换。当前hypothetical pending slot仅观察位置，不是已连接的实际资金rank键。

全池为旧账户路径产生的pending，排序改变后的新账户候选集合和资金竞争均未知。静态位移、原赢家PNL只能并列诊断，不可叫收益反事实。行业归属/股票池非PIT，固定历史案例不称新样本外。

## 本轮静审发现与修正

已指出默认pandas JSON读数可能重现既有1ULP PVR失败；父线程已改stdlib json精确读取。低点导出列L与主脚本low_improvement接口不一致，已显式rename。早先我误认为PRIMARY有sector而提出sector_x/y冲突，亲读实际PRIMARY schema后已撤回；该PRIMARY没有sector，行业列来自原feature表，不能把撤回意见算作源码缺陷。

其余percentile、非负OLS、带ties聚合权重的PAVA及同业槽位替位静读未见致命冲突。非有限相关系数应作为无信息/UNKNOWN诊断，不能解释为0相关。保存结果审计另给收据，本文不冒称全池重算。
