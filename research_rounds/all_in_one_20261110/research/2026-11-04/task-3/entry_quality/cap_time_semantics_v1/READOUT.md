# S0市值门的实际时间语义

**已证实的是：原研究代码明确把当前市值作为固定名单字段，允许在历史clock下读取；这不只是本轮新分析临时加入的代理。尚未完全认证的是：两条既有No60账户当时读取的逐股市值叶文件及逐值结果。它们保存了固定1709股身份与部分源码冻结，但没有直接冻结该叶文件，也没有保存cap逐值dump。不能用本轮join补出这段旧运行证据。**

本次只读源文件、原运行记录及已有数据，另执行一次纯字段read对照；无账户、市场模型、回测、参数搜索或网络调用。

## 原码与数据来源

[current_fixed_pool.py:89](/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025/code/current_fixed_pool.py:89) 的原文为：

```python
class SelectionFact:
    """Only fixed selection fields may bypass the historical knowledge clock."""
    field: Literal['issuer_id', 'sector_id', 'company_cap_cny']
    # ...
    def read(self, clock: admission.Clock, *, for_execution: bool = False):
        # Deliberate research assumption; observed_at is retained, not backdated.
        return self.value
```

[build_security:154](/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025/code/current_fixed_pool.py:154) 把company_cap_cny装成SelectionFact；[S0 eligibility:197](/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025/code/sector_stock_admission.py:197)执行：

```python
cap = s.company_cap_cny.read(clock)
# checks中的原式
'cap_above_10bn': None if cap is None else cap > 10_000_000_000
```

门槛为严格大于100亿元。cap未知保留None；任何检查未知使q=None，即使另有已知失败项。普通Fact.read仍检查known_at、有效区间和snapshot observed_at；该例外仅在固定名单字段中明确实现。源码18—21行声明`current_pool_historical_development`、当前幸存股/市值/行业、非PIT或未见样本。

[current_pool_bridge.py:416](/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025/code/current_pool_bridge.py:416)按manifest引用及SHA载入selection，再把observed_at留在SelectionEvidence中。[build_inputs.py:23](/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/code/build_inputs.py:23)的输入为`downloads/current-cap-all/snapshot.json`原字段3541450；非正或非数转None。29—35行先保留cap>100亿元或未知，**未过门股在构造selection时就已被排除**。

实际叶文件为[selection.json](/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/inputs-v2/selection.json)，SHA256=`3b0dac60526ff042b24e3a436638d6ef5a631a52f62f0c9daeb57e644633ca99`。其日期不能混用：

|字段或证据|实际记录|含义|
|---|---|---|
|roster_asof|2026-10-22|名册标签|
|cap_observed_date|2026-10-24|本次取值日期|
|000620原响应receipt|2026-10-24 21:55:54 +08|本地收到该值|
|selection observed_at / snapshot updated_at|2026-10-24 21:56:29 +08|导出/快照观察时间|
|construction created_at|2026-10-24 22:50:11.376302 +08|输入包生成时间|
|market_timestamp_unknown|true|未获市值真实行情时戳|

不能把名册标签当观察时间，也不能把文件生成时间回填到2024。repair_classification只修行业，不改cap或上述观察时间。

纯字段调用保留2026-10-24 evidence时间：000620的16,617,237,000元在2024-09-24和2026-01-15 clock均原值返回；同值同时间的普通snapshot Fact在这两日均返回None。未知cap的000016、002731仍为None。详见[实际read证据](source_semantics/ONE_FIELD_READ_EVIDENCE.json)和[逐段原文](source_semantics/SOURCE_EXCERPTS.json)。此调用没有载入账户或完整bundle。

## 旧账户的证据边界

范围为`trend_exit_controls_v1/runs/BASELINE/2022_2024`与`strong`两条封存原账户，未扩大认证所有历史版本。

1. 两条RUN_METADATA各38项source_freeze均与现文件SHA吻合，实际保存了No60 Runner、planning、opening/route身份及固定1709股、90行业范围；两条原run的1709 fixed IDs均恰好等于当前selection中1709个已知合格ID。这是名单身份一致性，仍非市值逐值读取记录。
2. 当前传递引用可追到context→rs-h1-execution inputs-v2 manifest→selection，引用SHA吻合，指向上述2026年10月快照。
3. 但38项没有直接包含selection.json、current_fixed_pool.py、current_pool_bridge.py或input-manifest.json。两个pair/B及checkpoint未发现cap、SelectionFact、SelectionEvidence或selection路径的逐值记录。checkpoint仅以pickletools解析，未反序列化执行。

因此，可明确指出**当前原码路径存在固定未来快照用于历史研究的选池语义**，不能称历史PIT全市场；也不能把“当前传递引用+新join”写成“所有旧run逐股cap已由当时日志确证”。无证据表明普通价格Fact无意穿越时钟；这是代码公开声明的研究假设。完整运行证据见[runtime_binding](runtime_binding/READOUT.md)。

## 能量化的排除与不能量化的历史误筛

已存5576股名册中：1709当前过门、3865已知未过、2未知保留。与5517条本地标准化序列相交：1681过门、3817未过、2未知、17不在当前名册。根级独立复核确认1709已知selection身份与roster selected集合完全相同，全部cap逐值一致。

所以旧池外3817股全部不过当前门，是**建池定义所致**；不能归因为E0/I算法，也不能用跨池榜单差额宣称新增收益。

14个预定讨论股中当前排除4只：蓝箭电子46.344亿元、大唐电信90.861167亿元、法本信息59.804898亿元、友车科技61.162341亿元；银之杰、海能达、江丰电子、金海通、珂玛及其余5只均过当前门。[完整原值及日期](coverage_impact/FOURTEEN_PRE_FIXED_NAMES_CURRENT_AND_DATED_CAP.csv)包含全部14只；它们不是按未来收益挑出的统计样本。

本地已核daily_basic仅2026-05-15一天、5495股，2026-06-04拉取；2024与2026年1月没有当日cap。它没有历史available_at认证。5491股两来源均已知时，May15 TuShare total_mv与Oct24 THS company-total门结果不同482只（当前过/May未过35；当前未过/May过447）。大唐为90.861167亿对121.36548967亿，是可复核的跨门实例。**这不是482次历史错筛**：时间、来源、公司/证券股本口径及修订没有隔离。

2024或2026年初真实“应纳却漏筛/应拒却纳入”数量仍未知；两方向都可能存在。没有用当前股本乘历史价格或累计复权因子补造历史市值，也没有推算漏股收益。当前选择影响可量化，历史误筛数和账户经济影响不能由现有cap资料重建。数据覆盖、缺失与原SHA见[覆盖报告](coverage_impact/READOUT.md)。

后续选股研究可以明确标注“本地可观察价格池”并暂时取消或并列展示该当前市值门；若保留，则只能称固定当前市值子池研究。要认证历史市值门，仍需随日市值/股本、公司与证券口径、历史可用时钟以及输入叶文件的运行时冻结。这里未擅自修改策略或重新运行账户。
