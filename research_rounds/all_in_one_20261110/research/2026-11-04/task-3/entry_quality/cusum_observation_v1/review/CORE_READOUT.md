有界核心 gate：固定五源观测/原源数学核同；`cusum_v2.py` source-pending guard静审闭合，可供预定纯观测母体使用。不是后续shared匹配/forward20代码审查，不是策略、账户或经济有效性PASS。

真实调用链已亲读：`joint_v3.py:216–218` watch key为 `(bool(row.i_target), int(row.segment_id))`，任一变化都增epoch，包含1→0；`native_rank.py:116–118`先调用J.planning。`Facts.row:24–26`是as-of最近行，不能当每日新事实。`policies_g1.py:12–24`按source重置、invalid时target可NaN，active按旧floor/shadow先退出；29–34的i_buy可重复，不等于新I周期。CUSUM因此用精确同日、同源已知0/1来定义active周期，不直接复制bool(NaN)、CP epoch、CORE消费或stock_structure。

原helper/driver已完整静读。63尺度在当前r入队前计算，启动close不纳r；vol历史不因I或CP重新准备，只有source/显式无效断暖。I1→0那根仍可计算旧D，但active warning为False。unknown/低尺度从当日起poison，先前已知值不回删；同一cycle不恢复D0。D≥3是level，cross/first-cross另列，不能把持续level每天都当独立预警。

独审12600个已存source观察，7855个known值的启动/单步约束及206个unknown不恢复核同；原native-I身份与源SHA核同。三个首次触发的r和prior63绝对收益median由原price独立计算：

| 原CP参考锚 | 首active cross | D_before→D | 单日无记忆值 | 当时旧CP |
|---|---|---|---:|---|
| 盈新2022-01-07 | 2022-01-18 | 1.773261→4.431723 | 2.658463 | C3.735647>旧P3.712053；原CP次观察1/19退出 |
| 海2024-09-20 | 2024-11-04 | 2.279091→4.489155 | 2.210064 | C已低于旧P，同日CP退出 |
| 银2024-09-12及失败锚10/9 | 2024-10-10 | 0→7.041030 | 7.041030 | 当日大跌单步足够，旧CP同日已破 |

前两例需要记忆才越3，但这不等于增量信息：盈新原E0 down在1/17已出现；海、银与原E0 down同日。银的两CP锚共用同一真实I周期，不能重复当成两个独立预警；更不能拿9/12先行锚替代10/9真实失败层。旧P为给定CP锚的条件影子线，非新订单或所有No60实仓线。

发现并修复的唯一source-start缺陷：v1在已观察新source、无效C但同源I1形成LEFT_CENSORED未知cycle后，pending-source可在下一I1有效行再次D0。v2仅将source-special-start限定为`source_confirmation_pending and cycle is None`。亲读一行diff；五源postinitial source_changed、source-special-start、left-censor和低s场景均为0，改分支不可达，旧五源输出不受影响；没有重跑五源或合成边界。v2主SHA为`dc51546262739da5db9e7ae50c26c42e10162a2b108608d34e119f100a37583c`。这些未出现的分支只静审，不称真实运行已验证。

数学界限：D是负向价格CUSUM，不是现金损耗或风险预算。固定s、最后归零后未再归零时，参考的是CUSUM最后零点C，而非必为普通峰；变s时是逐期标准化和。平价亦每观察减.25，所以等待能消警；慢跌每次−r/s≤.25可不触发。h3不是3σ概率界，MAD/漂移固定先验没有工业误警保证。

母体的最小辨识要求：先选既存代表CP层，再判当前是否已退出，不能换年轻层绕退出；已触旧P/I和同期退出单列。以当时known oldP距离/持有年龄/尺度/已知回撤控制后再看关联；当前已知回撤和当日负r强烈内生于D。原无记忆单日量`max(0,−r/s−.25)`可作无新参数的代数拆分。固定粗箱只描述，不把箱残差宣称新增信息；紧匹配须先于未来标签完整性筛选、保留无匹配和标签未知。匹配caliper与未来20/q90属于父冻结后续诊断，本gate未审其实现。

全市场日历缺行仍未验证，当前是可比源观察钟。当前五源gate无剩余阻碍；未启动任何账户、订单、数量、收益或参数搜索。此前phase保护一次291的实现/输出未由本审复核，不能与此gate混记。
