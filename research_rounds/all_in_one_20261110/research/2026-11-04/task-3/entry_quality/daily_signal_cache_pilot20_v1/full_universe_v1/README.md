# 本地5517序列每日E0/I/CP/PVR缓存

已完成并通过独立最终复核。5517份每日Parquet共 **1,391,111,145字节（1.391GB）**，含 **5,814,918查询行、91字段**。生成阶段37.84分钟，全量读回及末源校验1.94分钟，主运行合计 **39.78分钟**；年度汇总和三次只读查询另约27秒。12进程，5497条新计算、20条复用，无重复未知批次、错误或剩余在途任务。未运行账户、订单或交易。

固定源为`adjusted_daily_bars.parquet`，SHA256：`11e7f9e38798e6e411f33b3250c564bcd5fcfbe34af2bda74e04c02cf8d08d9b`。缓存身份与原源码见[FREEZE.json](FREEZE.json)。完整可观察本地5517序列是约定研究母体，不认证历史全A股或历史发行人唯一身份。

## 范围与缺失

每条股票从本地实际原起点初始化，顺序计算至该股实际源尾（总源最晚2026-05-15），未统一从2014或2022重新开始。初始化累计15,739,264源行；仅导出2022起的历史日序。输出采用全本地源1054个观察日期union，非经认证交易日历，形成5517×1054查询网格。

|年度|查询行|当日实有行情|缺当日行情|
|---|---:|---:|---:|
|2022|1,335,114|1,135,629|199,485|
|2023|1,335,114|1,233,491|101,623|
|2024|1,335,114|1,280,461|54,653|
|2025|1,340,631|1,309,892|30,739|
|2026至5/15|468,945|465,370|3,575|
|合计|5,814,918|5,424,843|390,075|

缺行未沿用前日i_buy/I/PVR/CP，不推断其原因是停牌、尚未上市或退市。没有5/16—6/30同源数据，因此不称完整2026H1。完整年度知识度与市场凭证数量见[ANNUAL_SIGNAL_COVERAGE.csv](ANNUAL_SIGNAL_COVERAGE.csv)，其中i_buy和I有效计数是股日，CP是市场凭证数，都不是独立股票或成交数量。

独立数值域扫描覆盖全源15,739,264行：无重复symbol/date、无多源混合、无原OHLC几何mask拒绝，volume/amount均正且有限。本源没有历史observed/ST/停牌等认证字段；沿用原函数的默认mask不等于历史交易资格。见[数据域报告](data_domain_review/READOUT.md)。

## 数据内容与信号时钟

`artifacts/<sid>.parquet`保存：原E0/G1/I的19字段；原numeric的15字段；原CP的25字段；原PVR的10字段；结构阶段10字段；查询/价格/未知资格12字段。schema在[DAILY_SCHEMA.arrow](DAILY_SCHEMA.arrow)。

- `native__*`是原函数状态。I持有知识以E0 ready守护；新增i_buy解释另需G1 ready。`stock_signal_knowledge`仅为新增许可的就绪标签，不能据此抹去可能已经知道的I持有状态。
- `numeric__confirmed_pivot_date`是极值发生日，确认日为当前输出行day；只有事件确认时才公开，不回填到发生日。发展极值仍是未确认数据。原政策旧floor先判断，退出优先级与公式未改。
- `cp__*`是原市场凭证/候选线，原适配的`e0_valid`实际取I target，down取原numeric −1，floor取I floor。candidate不是实际持仓保护P，缓存没有入场层、数量、CORE/MOBILE或成交信息。`next_*`是本行处理后的状态，不是未来观测。
- `pvr__*`保留原21日0.9衰减公式及独立价额观察钟。未知score保持NA；原2022/1/24的177个i_buy里只有175个可排PVR，未知2个没有被填成最差分。
- `stage__*`只是此前冻结的结构诊断标签，没有应用已否决的阶段优先排序，也未新增买卖资格门。
- `price__*`沿用冻结源的复权坐标及原量额，不是原始实际成交价格。当前复权版本、历史公司行为及真实发布时间非PIT。

为统一Arrow类型，20股旧文件中11份异型schema在**新副本**规范化，全部1,918,280个值/NA独立核同；旧文件SHA未改。其余5497条输出使用相同91字段schema，模型算式与输入值未因此改变。

PVR公式原冻结摘录在[original_score_function.py](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/pvr-current-v3-information-capital-20261101/original_score_function.py:1)（SHA256 `9328109bada26c53b04cf0f3e84d719917cb528ff8608b3e9faa5d1c55ba8cb2`）；本缓存实际调用[features.py::original_pvr](/Users/bytedance/Documents/Codex/2026-11-04/task-3/entry_quality/pvr_information_v1/feature_design/features.py:37)。后者有完整导入和原观察钟，适合复核公式；逐日贡献研究直接读取已有`pvr__r/scale/amount_ref/u/b/e/E/score`即可，无须再次调用计算函数。

## 校验结果

原20股有限因果试点保留：40个常规物理前缀截点加6个真实边界；比较全部共同前缀字段。只有一个85×79保存前缀由独审重新逐值核对，其余45次是生产者执行断言与独审代码/收据检查，不冒称5517×1054逐日穷举。

本次全5517独审逐股核文件/收据SHA、cache身份、schema、查询网格、缺行无继承、CP-I对应和旧输出：

- 原三个日期：15,278个有行情请求×19字段及NA核同，1,273个缺行请求核同。
- 原七个日期PVR：36,043个有行情请求×8字段及NA核同，2,576个缺行请求核同。
- 三日就绪/持有/i_buy分母核同；全源与原源码SHA保持一致。完整证据见[最终独审索引](independent_review/FINAL_AUDIT_INDEX.json)。

从已保存缓存读取原候选母体的实测，不重新运行信号模型：

|日期|源行情行|原i_buy|PVR可排序|本次读取秒数|
|---|---:|---:|---:|---:|
|2022-01-24|4518|177|175|5.08|
|2024-09-24|5309|2313|2313|4.94|
|2026-01-15|5451|779|779|5.10|

耗时是本机本次查询记录，不是所有硬件或冷缓存保证。见[查询收据](READONLY_FIXED_DATE_QUERY_CHECKS.json)。旧CP输出来自不同prepared/THS坐标，未拿来充当本canonical同源黄金日序；CP当前是原函数与有限前缀验证，不是逐日旧CP实盘复现。

## 使用已完成缓存

正式文件清单与SHA在[CACHE_DATASET.json](CACHE_DATASET.json)。读取清单中的已验证文件，避免在中断状态下把没有收据的孤立文件当完成。

```python
import json
from pathlib import Path
import pandas as pd
import pyarrow as pa
import pyarrow.dataset as ds

root = Path("entry_quality/daily_signal_cache_pilot20_v1/full_universe_v1")
manifest = json.loads((root / "CACHE_DATASET.json").read_text())
files = [str(root / name) for name in manifest["files"]]
data = ds.dataset(files, format="parquet")
table = data.to_table(
    columns=["sid", "day", "source_row_present", "native__e0_ready",
             "native__g_ready", "native__i_target", "native__i_buy", "pvr__score"],
    filter=ds.field("day") == pa.scalar(pd.Timestamp("2024-09-24")),
)
rows = table.to_pandas()
known = rows.native__e0_ready.eq(1) & rows.native__g_ready.eq(True)
original_i_buy = rows[known & rows.native__i_target.eq(1) & rows.native__i_buy.eq(True)]
# 保留全部原i_buy；只有score已知的子集才可按PVR排序。
```

## 中断与完整性

新生成按固定230个均衡块、每块23–24条调度，每股单独提交。模型前exclusive RUNNING标记；完整Parquet写同盘临时文件、关闭/读回校验/fsync/原子rename，最后才写含SHA的原子DONE收据。SIGINT/TERM阻止下一股启动，允许当前股完成提交；硬中断的完整孤立结果可核footer/身份/旧字段后无模型恢复，其他未知或错误尝试隔离，不自动重算。

只在部分运行时使用`run_cache.py run --resume`恢复；日常查询读取清单。恢复会验证source/code/grid/schema/SHA与旧字段。6类隔离纯文件恢复测试已通过；未实测断电、强杀进程或ENOSPC。实际本次无中断/错误/未知重试，结束时LOCK、running、pending、errors均为空。完成记录见[GENERATION_COMPLETION.json](GENERATION_COMPLETION.json)。

首次可用磁盘约86GiB，48GiB内存、18核；使用12进程，10GiB磁盘下限及75分钟明显扩张暂停条件均未触发。缓存支持按股票分批生成历史状态；它没有完整B4递归checkpoint，不能只拿末行或最近63日承诺每日一行append。新复权/历史修订/源起点、mask、代码或参数变化要使相关缓存失效，不能混接旧状态。

当前5517本地母体仍有供应商、幸存者、别名和历史截断偏差，239份退市行情未统一合入。历史ST、停牌、上市身份、限价、行业成员、企业行为和真实available_at未认证，资格均UNKNOWN。这里认证固定源上的实现与保存值一致性，不认证PIT、可成交性、策略收益或经济增量。
