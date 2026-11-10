# 当前No60：风险上限与失败记忆独审

状态：**PASS_STATIC_CURRENT_NO60_RISK_MEMORY_SOURCE_REVIEW**。只读源码、静态AST字面字符串与文件身份；未导入策略、执行组件中的exec/compile、调用模型、运行测试/账户/回测或改策略。29段逐行原文见[EVIDENCE.md](EVIDENCE.md)。

## 当前移除和保留的门

实际覆盖是A.NoConfirmed60Budget：request来自P.MOD.Contract.request，migrate来自P.MOD.Contract.migrate；route为P.ROUTES[True]。loss/resources/start/observe等仍沿J.Budget→V.Contract继承。不能把MODEL_TEMPLATE全部辅助方法或J未覆盖的原route当成当前运行路径。

1. 原request的`ar+risk>.03*budget_nav`与原route的`ar+risk>.03*nav`全账户名义到线风险门已由without-account模板移除。独立源文本核对：MODEL_TEMPLATE恰等于原V模型只删除这一行。
2. P再移除confirmed池60%资本门的三处：migrate、request、route。probe池10%资本门保留。该改写不取消行业/现金/个股/ACT门。

当前主要OPEN约束如下（省略展示中的原1e−9数值比较余量，原文完整保留）：

| 门 | 当前源码判据 |
|---|---|
| 现金及原留存 | `cap+fee <= min(a.available-.1*a.current_nav, b.cash-reserve)` |
| probe池资本 | `pc+cap <= .10*nav` |
| probe池名义风险 | `pr+risk <= .005*nav`，合计跨行业全部probe占用 |
| 行业资本 | `sc+cap <= frac*nav`；probe为.02，confirmed在level1/2分别为.10/.20 |
| 行业名义风险 | `sr+risk <= .01*nav`，包括该sector全部池、旧/新attempt与episode占用 |
| 个股资本 | `实际股数*known_open+cap <= .10*a.current_nav` |
| 新单与状态资格 | 行业active、原合法凭证/时钟、CORE epoch、未消费CP、pending/退出障碍及原数量/费用规则 |
| ACT | `ACT20_BREAK`独立episode NAV峰值回撤暂停/flat且BREAK63恢复，仍保留 |

**两个NAV时钟：** route中`nav=b.nav-pending_fees-fee`，request同量纲扣待买费及本单费。b.nav来自该OPEN的sync：原ledger当时已知mark、现金/预留和应收域，不是强行把全组合都按最终OPEN重估。现金10%留存与个股10%用`a.current_nav`，它在J222的CLOSE更新，OPEN没有重赋值。

CORE信号和OPEN仍核单笔.25%信号NAV、原保护距离和双边费用；MOBILE原信号金额仍为`min(.02*a.current_nav, .1*a.current_nav-已持股*信号raw价)`的非负部分。尚未实施的单位风险修订不属于本次现行源码。

## 计量与行业相关性

`resources`先按pool/sector筛选，再求和：live风险为`qty*max(mark-floor,0)`，待买为`qty*max(limit-floor,0)`；open/cancel_pending余量仍占资源。资本按mark/limit计，现金预留含买费，费用还影响预算分母；风险距离本身不包含跳空、压力卖费或连续无法成交责任。mark已低于floor时，该名义风险项可为0，但实股、资本和退出责任没有因此消失。

sector_by_sid为每个股票的一项行业映射。当前这些函数没有协方差、跨行业相关系数、beta或共同跳空压力项。跨行业共享现金、probe池.5%总和及ACT会耦合决策，但不能称为相关性建模；行业1%也不是全账户1%。未显式建模相关性不等于代码作过“行业统计独立”的检验。

## 金钱损耗保留，但当前不主动拒新

J16初始化`shared_loss_budget=20000, exhausted_policy='record_only'`。`shared_loss=sum(losses.values())`；losses按`(sector,原行业episode)`保存。当前native买回调记实际研究账买费；卖回调逐part记`max(0,原unit_cost-模拟卖价)*卖股数+分摊卖费`。正价差/分红没有抵减该累计值，所以它不是净亏损。

`loss`撤单与`request`返回`shared_loss_exhausted`均要求`exhausted_policy!='record_only'`。当前这两条不会因达到2万元而生效；ACT另有自己的账户状态机。**累计记录存在，不等于累计损耗主动预算已启用。** 当前这条Budget路径没有名为episode_loss的独立字段；每episode金额就是losses字典对应键。

## 结构失败记忆与重置

- `invalidate/observe(failure=True)`令行业inactive、记failed_bar并取消该episode余单；同观察的CP不能立即重启。后来行业证据须在end/confirmed_time及已消费的进展时钟上严格更新；没有新增“重夺旧高/盈利验证”条件。
- inactive后合法新行业CP建立新attempt、level回0；新行业episode重建Sector并保留旧failed_bar。旧lot/order仍留原episode/attempt、继续占资源，原池不因失败自动变probe。
- losses、consumed和stock_requests不因换行业episode/attempt、卖出或ACT恢复清空。金钱损耗按原lot归属回记。新个股CP可以有新的合法申请资格，这与重用旧CP、清掉历史损耗是不同事项。
- 同股CP退出/亏损没有直接调用行业failure；J行业failure来自行业E0无效或end_attempt。行业confirmed不能当成该股已经盈利验证。
- checkpoint保留整个account字段及budget；restore还原该保存对象，月/季度复制不是预算重置。上述保留指同一连续账户；2022–24长账与strong窗口各自fresh100万，二者不继承损耗。

## 代码接口边界

如果以后改变累计损耗的执行政策，不能只改request拒绝：当前route.allowed先找合法q，调用request后断言必须reserved，预检与执行须一致。若改变风险单位，existing resources与route/request的新单risk也须一致。这是现源码接口约束，本次没有增加任何门、参数或机制。

root READ_FIRST的第1–4、6节已薄核，无关键源码异议。第5节原六层金额、逐日损耗、行业凭证namespace和资金记录由链owner提供；本件不重新计算或为该数值部分背书。没有从源码推出损失界限、经济有效性或历史样本覆盖。
