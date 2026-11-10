# 四条原未达暖MOBILE模拟账链与暖态半导体对照

全部来自冻结原No60 BASELINE账，**只提取原记录，0新账户、0模型运行、0新参数**。价格、费用、成交是原日线执行代理模拟记录，不能称交易所真实成交。`G1<2`取实际fill前一个原市场CLOSE，恰为原intent决策日；负值、0、1分开，不再向前shift。下文及产物变量名`cold`仅指本次描述口径“未达暖（G1<2）”，**不等于原生cold**；原生公式是`ready and (grade<=-2 or acute_down)`，西子G1=1不是原生cold。本组为两个原窗口已平仓、含未达暖MOBILE层的campaign金额极值例，非独立交易样本、非门控效果检验。

| 原完整campaign | 实际入场→全部平仓 | 所有层 | 整链净额 | 其中cold层净额 | warm/其他层净额 |
|---|---|---|---:|---:|---:|
| 西子洁能002534（strong） | 2026-06-15→06-30 | 1148、1158 | −7,124.03 | **−204.46**（1148，G1=1） | −6,919.57 |
| 思源电气002028（strong） | 2026-06-02→06-08 | 1102 | −4,459.17 | **−4,459.17**（G1=−2） | 0 |
| 润泽科技300442（strong跨年参照） | **2025-11-27**→2026-01-16 | 537 | +15,341.35 | **+15,341.35**（G1=−3） | 0 |
| 中国太保601601（2022—24账，源显示名“XD中国太”） | 2024-09-02→10-10 | 1904、1914、1931 | +7,600.88 | **+2,481.60**（1931，G1=−3） | +5,119.29 |
| 单列暖态control：金海通603061，半导体 | 2026-01-19→02-12 | 674、677、684、702，均G1=4 | +6,309.03 | **0；不是cold案例** | +6,309.03 |

上述五条campaign全部真实已平，末端未实现浮盈为0，AR为0；收益均为原买卖费后已实现交易净现金。西子的大部分亏损来自后续warm层，太保正收益也含两个warm层，不能把整链净额全算给cold。润泽是**2025新增fill、2026卖出**，只作跨年参照，不能混进2026新增cold 18层。2026新增实际MOBILE中没有cold半导体成交；这不等于全候选机会中没有cold半导体信号。暖金海通单列，不用于凑四个cold样本。选例及其余cold campaign完整候选保留在`SELECTION_FREEZE.json`、`COLD_CAMPAIGN_CANDIDATES.json`。

| cold层 | G1类别/值 | 原决策CLOSE→实际买入OPEN | 原股数/买价代理 | 退出请求CLOSE→实际卖出OPEN | 原退出理由 | “原账全历史同股曾卖MOBILE” | “同一原stock_structure曾卖MOBILE” |
|---|---|---|---|---|---|---|---|
| 西子1148 | 1 | 2026-06-12→06-15 | 100 / 20.300145 | 06-29→06-30 | CP1_add_protection | false | false |
| 思源1102 | 负 / −2 | 2026-06-01→06-02 | 100 / 214.297095 | 06-05→06-08 | I_structure_exit | **true**，旧440于2025-11-24实际卖出 | false；新root2026-05-20 |
| 润泽537 | 负 / −3 | 2025-11-26→11-27 | 500 / 48.364170 | 2026-01-15→01-16 | CP1_add_protection | false | false |
| 太保1931 | 负 / −3 | 2024-09-18→09-19 | 400 / 30.415200 | 10-09→10-10 | CP1_add_protection | **true**，旧639于2022-09-30实际卖出 | false；新root2024-08-19 |

四个cold决策均为原`I_target=1`、`i_buy=false`、`g_ready=true`、真正fresh CP receipt存在；原机会日志均保存`core_Q=false, mobile_Q=true, barriers=[]`，随后实际funded。这说明原MOBILE continuing通道确实可以在G1<2时入场，不能把原I保持等同于当日warm新买资格。**全历史同股记忆与同root记忆是不同条件**；本组太保、思源仅前者为真。这里的条件flag是对原记录的描述，没有运行新门，也没有宣称省下原层损失等于账户收益。

原源码证据：`/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/v3/joint_v3.py:214`构造`event`和`continuing`；218行对后者使用`replace(s,buy_allowed=buyable[sid])`；244行CORE依赖event资格和未持仓/epoch，245行MOBILE为`cpr and continuing[sid].q is True`。235—240行先做旧MOBILE线测试再抬线。`/Users/bytedance/Documents/ChatGPT/money/research_rounds/b5-g1-20261025/code/policies_g1.py:16`把warm买机会与持有I分离；`G1_I`的I保持不会因G1 cold本身退出，原边界仍有效。源码仅只读，未执行。

机器证据入口：`FOUR_COLD_CHAINS_AND_WARM_CONTROL.json`含五个完整campaign、11层全部原买卖、逐sell.part数量/代理价/分摊卖费/实际执行订单创建时钟、原CP/I/G1、所有原持仓CLOSE快照/保护线/pending/机会/实际funding，另附每股全原账历史成交与campaign。`ENTRY_LAYER_TABLE.json/CSV`逐层分grade及双记忆口径。原exit clock来自已审actual-sale-part执行绑定，按layer+实际fill+shares+net_cash+part reason核合，未强配最早同reason但取消的pilot。`SOURCE_MANIFEST.json`绑定原账、缓存、冻结helper及两段源码SHA；`VALIDATION.json`记录11层/5campaign金额、数量与时钟核合。无未来收益进入任一信号字段；终局结果只用于选取和描述案例。
