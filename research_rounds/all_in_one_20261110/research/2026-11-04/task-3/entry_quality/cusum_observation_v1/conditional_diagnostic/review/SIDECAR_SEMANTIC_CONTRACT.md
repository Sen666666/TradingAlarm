仅审核两个只读sidecar口径；运行中的panel/match/core不改、不重跑。

**policy持有状态不是raw方向。** 当前native cache `cache.py:27–34`将`e0_policy`输出的`target`存为`e0_target`。实际`policy.py:99–114`在触旧floor时退出、+event时启动/抬floor；−event本身不等于关闭target。独立读取原盈新2022-01-17：event=−1、leg_direction=−1、native e0_target=1/e0_ready=1，event/native的segment均0。因此旧实现正确执行了当时policy-bit规范，却不能据它宣称raw E0方向仍向上或真正额外信息。

新增metadata应保留旧extra列，命名policy候选桥接；最终rawleg-strict额外cross还要求原event**精确同日、同segment**的leg_direction明确+1。−1、0、缺失/不可比单列，不能as-of/ffill或拿本日正收益代替leg。该rawleg是原已确认市场方向状态，不是后验极值。strict当前判据不使用未来结果；原匹配、caliper、对照、label与core不变。

**同决策日不保证同未来期限。** 每个既定匹配对保留双方t后第20个已知、同源、完成close的日期。只有原label为COMPLETE20才给H20 endpoint；欠20的最后已知日若要留应另名，不得冒端点。

至少区分：双方complete20且endpoint同日；双方complete20但endpoint不同日；任一future unknown/欠20。报告后者完整缺失原因，不能填成同日、0差或完整未决。first-hit可在欠20前已决，但这也不能伪造完整20端点。

同端点子组只从原已选匹配对筛取，不事后重配control。应报n、占全部match/双方complete的比例、连续控制残差及该子组结果。它仍是未来可见性条件子组，不能覆盖全体配对结论。相同终点也不保证中间20个观察日期网格相同，完整交易日历缺行与实际可成交时钟仍未认证。

本文尚未读取sidecar实际代码/输出，不构成其实现或统计PASS；只核语义与上述原source反例。没有新E0/I/CP/CUSUM模型、账户、参数或重新匹配运行。
