# 当前新前沿以上成交量占比下界：唯一固定机制预检
状态：先冻结定义与19固定点，后读取所需当日量价。历史盈亏已知，不是盲样本外。只检验信号，不运行经济消费者，不计算删单收益。

## 新的可计算对象与唯一许可
取原PRICE当日新receipt。出生票的比较边界 J_t=原冻结U；续票 J_t=max(C_j, root_birth<=j<t)。这是本票之前已经可见的价格前沿，不是入场成本、旧amount基准B、事后峰或当日High。
日内未知成交分布P支持在真实raw L/H内。日成交股数V=raw_volume>0、金额A为CNY，真实均价q=A/V；原native坐标同时用factor转换。所有计算统一raw坐标：J=J_t/factor_t。
先沿旧dual-frontier的误差约定 eps=0.5/V+1e-8（元），要求q在[L-eps,H+eps]。为严格保证，使用q_minus=max(L,q-eps)、q_plus=min(H,q+eps)，不以截断均价点值冒充精确真值。
未知成交股数占比 p=Pr(P>J) 的可认证下界：
- L>J：LB=1；
- H<=J：LB=0；
- L<=J<H：LB=max(0,(q_minus-J)/(H-J))。
相应上界诊断：H<=J时0；L>J时1；L<J<H时min(1,(q_plus-L)/(J-L))；L=J<H时1（q_plus=L的退化点为0）。
唯一候选许可 = 原可用PRICE新receipt AND LB>1/2。1/2是“可保证超过半数成交股数”的语义门槛，不按年份优化。所有个股同式。LB<=1/2不代表多数没有在边界上方，只代表日线统计不足以保证。
推导：E[P] <= J*(1-p)+H*p，因此p >= (q-J)/(H-J)。这不识别主动买盘、净流入、筹码/持仓成本、日内先后、盘口或可成交性。

## 时钟、状态与角色
只用t收盘已知raw H/L/A/V及截至t-1的原前沿；known_at=t CLOSE，最早消费者为立即next-common OPEN。当前量价一次性使用，不积累余额，无持续true锁，不从旧CONFIRMED借证。
不改原PRICE root、receipt、S及E0接管，不改原行业四事实、AB优先、PVR、名额、金额、退出或经济路径。
首探及退出后再入同一新票规则，不禁止止损重入，不设置次数/根龄/年份/行情长度门。候选只研究新的初始目标许可；券商订单重试沿原parent/ACK/未决状态，不把市场信号当ACK，也不以新LB重开已消费receipt。ADD仍是原职责，本次不提出ADD修改；不能把首探失败后转给ADD救活该候选。
新增只是每张票的J/LB/UB/known reason，不创立额外长寿状态。
UNKNOWN：缺票/非新receipt分别NOT_RECEIPT；价格root或source lineage不明、共同日缺失、source_kind/path/segment或adjustment_factor跨比较区间变化、raw与native不匹配、量额单位不明、非observed/不eligible/synthetic、V/A非正或均价不在合法范围时UNKNOWN，不补0，不跨未知接旧锚。当前H=L且同价>J可以合法LB=1，但不等于次日可成交。

## 新旧差别与证伪
G/I读平滑收益及原S21/S63事件；CP/PRICE-Q只累积新close前沿与活动量信用，均不形成当日成交位置的最坏分布界。
旧dual-frontier已使用q及min(logC,logq)累计前沿，本候选继承q定义，绝不称首次引入均价；差别为同日H约束下的份额界、逐票原价前沿及无跨日信用。固定C/q/J而改变H可改变本许可，原min(logC,logq)不会改变。
旧acceptance A按历史cohort的H/L、amount、指数年龄重新估值，本候选只使用当前bar的第一矩和支持域，无历史cohort/半衰/净额。
CMF是CLV*V/总V，以C在H/L内的位置归属股数，不使用真实均价。不能据输入不同宣称经济独立性。
目标假说仅是：在当日新价格前沿处，已成交价格分布的保守位置证据能否区别“旧信用许可当前边界”。不声称已证两窗损失原因，不把历史组别亏损当此门有效。
固定点包括2022正反例、2024正反例、海能达9/25与江丰12/15/17及2026点。若固定早启动被挡，或与旧式原样同义，停止晋升；不降低半数门槛、不换边界、不改窗口，不改为ADD/软排序挽救。仍完成既定19点的事实展示，不能扩池。
