# 独立实现复核：固定22点结构预检

## 裁决
PASS_WITH_SCOPE_LIMITS。未发现会改变本轮结论的公式、窗口或合并错误。18个已知点全部结构通过，4个点UNKNOWN；这些结果不支持升级为入场过滤器。没有新增模型、收益拟合、病例重跑或经济运行。

## 已独立核验
- SOURCE_HASHES.json所列28项源hash、OUTPUT_HASHES.json所列原10项产物hash及STRUCTURE_SEAL.json中的结构表hash全部相等。
- CASE_STRUCTURE_PRELABEL.csv与FIXED_CASES_WITH_CONTEXT.csv的全部结构列逐字符串相等，22点/19股；PREFIX_QA.json覆盖同22键，全部保存为exact。
- 代码run_fixed_cases.py:46–66的84日窗为t−83..t。最后63收益为r[t−62..t]；尺度为此前63收益r[t−63..t−1]的1.4826×median|r−median(r)|，排除当前收益。它是信号时统一冻结的一份尺度，不是每天分别计算的尺度。最早量权使用t−83..t−63的21股数观察，窗口足够。
- 22窗均恰84共同日期；共同日历4677日单调唯一，19源索引单调唯一。没有跳过缺日再拼样本。
- 四UNKNOWN源行各有两个adjustment_factor值，其他source_kind/source_path/segment_id/volume_factor各一值，无缺close。变化日期：605020于2022-06-07，605118于2022-06-02，002241于2024-08-23，605488于2024-06-19。严格排除是冻结的保守覆盖选择，不能解释为差股或亏损。
- run_fixed_cases.py:33–42与已审积分式一致：无变点正/负各1/4，20个断点的四符号组合各1/(8×20)。分段竞争包含匹配的后负零假设，无额外BIC重复处罚。
- original_scipy.txt与当前程序差异仅为两个特殊函数替代及其合成断言。独立100位Decimal参考测试中，logPhi在[-40,20]所测点最大绝对log误差6.06e−14，−100为2.11e−13，−10000为2.04e−9；后者相对约−50000010的log值属于双精度量级。logsumexp极小同值测试误差0。未安装依赖。
- overlap中固定键精确命中20行/20唯一键，无重复冲突被drop_duplicates隐藏。另两行江丰2025-12-15/17仅由FIXED_DAILY补市场状态，不含成交认证。

## 结果口径
- 15个old_price_net都精确匹配原PRICE完整条件回合，其中11个added=True，故包含首探及ADD等整局现金流，不是初始层单独净额。源joint_engine.py:186–198卖出core+add，:219–226将ADD写入同局cash/spent/fees。
- 这15局均actual_fill=NOT_PROVIDED、historical_tradability=UNKNOWN，是条件OPEN全成交代理，不是现实成交证据。
- 江丰、301611、603061在2026-01-15的open_size_check均为NOT_REACHED_CLOSE_NOT_FEASIBLE，historical_fill均UNKNOWN_NOT_SIMULATED，且无本表精确原PRICE回合结局。不能称结构保留了真实入场。
- structure_pass只表示piC+piR>piN，不含原合法PRICE、名额、整手、资金、收盘及次OPEN资格。市场背景是事后合入的同时点描述，不参与结构计算。
- 15个旧结局中4个结构UNKNOWN原样保留；11个known旧结局含5负6正，全部结构通过。只能说该固定域未产生新增否决，不能推断胜率或收益改善。

## 明确未审
本次只查代码、封存产物、源hash和部分原始行；没有重新执行run_fixed_cases.py，没有独立复算22点posterior，没有独立重新运行完整prefix。已核的prefix是保存记录、键覆盖及源码时钟，不是第二套全前缀复现。没有认证上游源生成PIT、现实可成交、全池覆盖、完整财务账或经济改善。固定历史已消费，结构先seal后join标签的代码顺序不构成盲测证明。

通用数值函数未全域认证；logsumexp不处理全负无穷输入，极端量比可能使tanh浮点饱和并触发严格范围assert。当前固定输出未出现此问题，不构成本轮阻断理由；如未来扩域，须在扩域前单独处理，不能据此重新跑本轮病例。
