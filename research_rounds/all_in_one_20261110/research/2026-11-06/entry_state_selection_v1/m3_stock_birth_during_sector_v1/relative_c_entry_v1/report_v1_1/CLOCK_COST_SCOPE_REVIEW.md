# 时钟、成本与作用域审查

C规则和数值时钟未改动。x_t=log(股票调整收盘/官方行业调整收盘)，epsilon_t=x_t-x_(t-1)；严格极点e冻结delta_e²=(5/63) sum(epsilon_(e-63)..epsilon_(e-1))²，极点自身新回报不进入其冻结尺度。使用原70位Decimal/区间数值保护；无法确定极点顺序或阈值跨越时UNKNOWN，不引入经济epsilon。区间只覆盖最终binary64表示舍入，不消除供应商上游或复权修订。

4595共同日完整相对时钟预热，1088日原M预移位，1085执行共同日。1627股票、495412窗内市场日，旧20445个AB状态和所有检查到的原close字段精确；2242 broad receipts的PVR原分与known逐条精确。连续Iepoch从完整facts/source重建，所有旧AB日epoch、relative事件/known精确，不把稀疏旧表当连续全日状态。

成本直接AST提取原finite/true/false/lineage/flags/getmeta/fee/size/checkclose/load/DayFrame函数。初仓含费预算24000，计划floor风险含双边费用<=3000，NAV参考1200000；dated lot与dated fees、双向5bp不利滑点不变。容量=至signal close原始正成交量最近20观察均值的1%，不是20个完整日或当天实盘可执行流动性。next common OPEN按同预算/风险/容量重新算量，不能把close手数当固定单。OPEN<=保护价/0手为明确NOFILL；来源/factor/dated-rule不明为UNKNOWN。不能声称历史涨跌停/停牌/排队或真实成交可知。

当日AB原PVR先分2槽，C只分剩余，再观察next OPEN代理；两次2024 NOFILL未替补。影子C获槽160/238/6，已知OPEN代理160/236/6，不是ABC实际交易数。重复同股影子获槽14/18/0次可能在真实C第一次成交后消失；首次成交也会改未来AB资格和持仓。

潜在后续AB冲突必须区分C-AB配对与独立AB事件：详见LATER_AB_CONFLICT_DENOMINATORS.csv。它只显示如果C更早入场可能阻断的同I后续AB，不宣称已经阻断，不能作为收益归因。

每窗起始标记为空，必须该窗原AB合法且纯排名落选才能造标。因此每窗AB股票域对限定C是闭合的；并集外82株无法形成必要条件。仍是静态NON-PIT研究，非新全池、非共享账户、非完整策略。

固定2022目标20例仅国机重装有合格C，6月7日发邀、6月8日条件OPEN代理；不能继承旧回合收益。秦川机床7月21日虽有persistent新UP，但6月27日资格已于7月15日UNKNOWN清掉。其余18例没有目标间隔内符合原I的persistent收据；原始fresh时钟原因详见TARGET_2022_CLOCK_REASONS.csv，避免把“无C日期”误说成“完全没有任何新UP”。2024既定11例均无已知OPEN影子C，明细完整保留。

修订记录：原预检第6片因无事件股票空DataFrame缺列失败，保留原代码/FREEZE/日志，仅追加preflight_v1_1并补6，另7片复用。修复逐字符验证只改空表schema及对应seal引用。首版汇总因示例字典重复window键失败，其部分文件保留；最终report_v1_1修复展示，并将目标时间窗日期映射扩展至全部候选以免漏原因分母。冻结规则、名单、C资格、PVR配额与nextOPEN不变。

经济ABC尚未授权、未运行。28项补充检查是marker实现及邀请/配额规格检查，不冒充未来ABC集成验收。独审最终意见另行提供。
