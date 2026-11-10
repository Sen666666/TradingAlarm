# E0/I局部逐日演绎：只读输入准备

资金方案准备已取消。上一任务没有启动Account/模型/测试/后台进程，也没有创建input_readiness文件；只读过runner/loader/TIMING与vm_stat，内存sysctl查询权限拒绝后没有重试。本目录是新的E0/I输入准备，不延续资金方案。

本件仅从SHA核同的原price/events/nativefacts/CP缓存裁切并exact-date join，7股共2103源行。没有运行E0、I、sigma、G1、CP模型或任何新账户/回测/候选收益。尚无候选冻结；不选择HL OR/AND reclaim、阈值、状态reset或重入公式。

## 数据范围

|股票|局部输入实际起止|原行数|events/native/CP exact缺行|
|---|---|---:|---|
|000620.SZ|2021-01-04→2022-02-08|264|{'events': 0, 'native': 0, 'CP': 0}|
|601019.SH|2022-01-04→2023-06-30|360|{'events': 0, 'native': 0, 'CP': 0}|
|601601.SH|2024-01-02→2024-10-10|184|{'events': 0, 'native': 0, 'CP': 0}|
|002583.SZ|2024-01-02→2024-11-27|218|{'events': 0, 'native': 0, 'CP': 0}|
|603061.SH|2025-01-02→2026-06-30|359|{'events': 0, 'native': 0, 'CP': 0}|
|605111.SH|2025-01-02→2026-06-30|359|{'events': 0, 'native': 0, 'CP': 0}|
|300623.SZ|2025-01-02→2026-06-30|359|{'events': 0, 'native': 0, 'CP': 0}|

半导体2025部分只作为2026目标的暖机上下文，未新建2025账户。每份INPUT_INDEX同时列各源完整历史起止、原路径和SHA，原更早历史仍可供冻结后初始化；局部首日并未被假设成新结构初始状态。保留price源全部行及observed/synthetic/eligibility/segment，不前向填充缺失信号。

## 字段schema与价格域

- `price__*`：连续调整open/high/low/close与volume/amount；另保raw_open/high/low/close/raw_volume、adjustment_factor/volume_factor、source_kind/path、price_eligible、observed_bar、synthetic_event_bar、segment_id。
- `events__*`：confirmation、leg_direction、developing_extreme、confirmed_pivot、structure_floor、event、target/entered/exited、pivot_age；原*_price、confirmed_pivot_date、developing_extreme_date及segment_id。log显示字段与canonical价格字段分列，不混价域。
- `native__*`：实际当前cache的e0_ready/e0_target/e0_floor、i_target/i_floor/i_buy、g_grade/g_ready/g_fresh_up/g_acute_down、factor/raw_close/segment。这里是当前No60 E0/I事实；不能把旧prepared participation states.target或numeric events.target直接当成native e0_target。
- `CP__*`：已存ready/phase/reset_reason、anchor/frontier、scale/credit、delta_frontier/displacement、receipt/candidate、next_anchor/next_scale/next_credit、r/s/z及e0_valid/e0_floor。全为原列，不重新计算或新增凭证。

SOURCE_SCHEMAS.json列每股实际列名/dtype/完整源范围。INPUT_INDEX的funded_original_stock_structure_roots保原book真实层stock_structure/epoch；这是已获资层的原identity，不能伪装成每个未获资状态的完整E0根日志。原native e0_target/floor序列和event确认行已保留，未来如需重建全根身份，须另有冻结的因果索引规则。

## pivot发生钟与确认钟

CONFIRMED_PIVOT_SOURCE_ROWS.json保188个原event=±1确认行，`known_at_CLOSE_day`=该event源行日期；`pivot_occurrence_day`只复制confirmed_pivot_date。所有pivot发生日≤确认日。早先极值发生日期不等于当时已确认或已可用；developing_extreme_date是当日候选快照，不能用后续更优极值日期回填前日。这里只注明完成bar后的CLOSE语义，没有伪造真实feed收到时间。

## 尺度缺口：不能混用

E0 numeric.py:76–79：sigma[t]=max(sqrt(fsum(r[t−63:t]^2)/63),1e−8)，过去63收益RMS、排除当前；:101–106确认用极值时点sigma[ext]和volume_baseline[ext]，不是本日重新选择的尺度。已查events/native/CP及prepared states/memories不持久化该E0 RMS sigma/ext冻结数值，标NOT_PERSISTED；本次未重算。价格和正量历史与源公式均在，可在root冻结候选后另做纯信号重建，但不能现在宣称该数值已可读。

CP/G1的s是原绝对收益中位数尺度；CP used scale/receipt original_scale可冻结于更早锚，next_scale/current s/z是其它字段。它们不是E0 RMS sigma的替代。现输出保原CP列便于查证，不据此补E0缺失尺度。

## 2026指定半导体原链：只作身份背景

|股票|原实际开→平|原层|原终局净贡献|
|---|---|---|---:|
|603061.SH 金海通|2026-01-19→2026-02-12|[674, 677, 684, 702]|6309.0257909942000|
|605111.SH 新洁能|2026-01-29→2026-02-03|[704]|-1361.5170509444500|
|605111.SH 新洁能|2026-05-28→2026-06-09|[1085]|-1287.1731448073500|
|300623.SZ 捷捷微电|2026-02-04→2026-03-04|[737, 743]|-4805.2176916106000|

金海通为该原账已平赢家；新洁能两次原链及捷捷为已平失败例。可由root冻结一胜一败，当前输入保三股不按后续结果改机制。ORIGINAL_CAMPAIGN_EXAMPLES.json直接复制原链，不新算收益；其生命周期净额不充当局部新算法的收益。

交付：7份*_DAILY_INPUTS.parquet；INPUT_INDEX.json；SOURCE_SCHEMAS.json；CONFIRMED_PIVOT_SOURCE_ROWS.json；ORIGINAL_CAMPAIGN_EXAMPLES.json；SOURCE_MANIFEST.json。仅准备输入，等待root冻结算法后才可做纯信号逐日state演绎；不会据此启动账户。
