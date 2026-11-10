# E0阶段与原信号缓存：成本及安全条件

本次只读源码、已保存耗时和日期元数据；新模型/账户调用均0，未修改旧封存。

**当前三日期的阶段快照已生成，可直接复用。只需E0事件与轻量阶段时，不应重跑完整B4/G1/I。完整历史日序可考虑一次原函数顺序计算、按日期取状态行；尚不能承诺现成增量append或无条件安全缓存。**

## 实测成本：两条链不可混称

新阶段链是原numeric加轻量E0/phase replay：full新批3275请求、3271完成、4缺失，处理9,470,899个eligible行，10worker墙钟55.7076秒。另有pilot12请求、39,463行、1.2164秒；最终快照累计3287请求/3283完成，累计9,510,362行。两种行数和计时分母已分开，不能拿累计行数配full单批wall。3283条的8个原E0/numeric/close字段均与已保存原信号精确相同。

按该轻链full批吞吐，全部15,739,264源行一次计算的比例外推为92.58秒（10worker）。这是计算量级，不包含尚未实测的完整每日状态落盘，也不是纯numeric单项profile或全5517新实测。长leg、事件密度和I/O仍会影响成本。现有阶段函数只返回末日snapshot，历史逐日状态并未全部保存。

旧full `model_cpu_seconds`测的是整个`stock_signal.calculate`，不能把它叫numeric时间：

| 日期 | 新full模型调用 | 输入前缀行 | 已完成模型CPU秒 |
|---|---:|---:|---:|
| 2022-01-24 | 4514 | 10,345,565 | 15,485.869 |
| 2024-09-24 | 5185 | 13,045,291 | 20,101.905 |
| 2026-01-15 | 5445 | 15,275,004 | 23,099.259 |

约1.497–1.541毫CPU秒/行，包含价格校验、numeric、participation、E0 policy、B5 evidence、B4 strength、G1 classify和I project，排除读源、JSONL/fsync、旧复用、控制股和中断丢失工作。numeric与B4没有独立CPU分项；不能据静态代码给占比。2026的776.247秒只为续调用，含中断总墙钟2358.350秒，不能混用。

完整G1/I日序如仍需重新生成，按相同全函数费用外推：全源CPU约23,559–24,253核秒，理想12worker计算墙钟32.7–33.7分钟；可先按35–45分钟规划含落盘，但这**仅是估计，未执行缓存构建**。1054个源观察日期若逐日重跑完整前缀，粗估397–598小时，不能采用。

原PVR矢量全前缀导出已有3worker、35.034秒收据，但只保存7日期的38,619行；它也不是现成每日缓存。当前canonical仅至2026-05-15，2022后5,424,843条源行、1054个源日期（不是官方交易日历），不能声称覆盖完整2026H1或全年。19个8字节槽粗估约0.825GB，尚未计key、mask和字符串；压缩落盘大小未测。

## 时间依赖与具体缓存内容

- **numeric事件**：`numeric.py:74–79`的sigma只用前63个return；shift+21中位volume基线排除当前。`:100–106`活动额只取ext+1至当前；direction/ext/active/floor顺序更新。gamma4为固定机器精度，不是全样本估计。没有发现未来窗口依赖，但缓存必须保相同输入起点、float64值、mask及观察钟。局部`math.fsum`重复求长leg总量最坏可呈平方成本，不能为提速擅换成累计和相减或不同加法顺序。
- **原E0政策**：numeric的target/floor不是通用E0政策替身。实际base由`e0_policy`产生；事件钟要求正C/V，价格政策钟可在有效价但坏量时继续检查保护线。应分开存numeric事件/确认日/原pivot与base E0 ready/target/floor/entered/exited。pivot发生日期早于确认日，绝不按pivot日期回填授权。
- **B4/G1/I**：B4前63 return、前21 volume与EW mu5/mu21均向后；mu从首个return暖起，第65有效价才公开，不能仅截最近63行或统一从2014起算。B4 epsilon是当前两比较值的局部容差，log原点是segment首价，不是全样本峰值。G1须保previous_grade/prior_s21/prior_extreme；I须保active/floor、segment和同日退出优先。B4 terminal attrs只有部分结构state，缺EW mu、滚动缓冲与完整初始化接口，不能凭最后一行或terminal立即append。
- **PVR**：旧scale和amount基准为shift后的63/21过去窗；E21、fast5及shift5后的slow58只用当时历史。PVR amount有效钟与E0 C/V事件钟不同，不可共享“第n观察”索引。`selected_rows`的`source_last_observation_day=全frame最大日期`只是源尾元数据，不能用于历史选股。
- **未来解析信息**：participation/E0 ledger在后续解决时写resolved outcome；B4 terminal是末端状态。历史研究只取当日state/event行，或按resolved/confirmed日限制可用性，不能按created/pivot日连接后来结果。

若以后实现真增量，需要numeric的direction/ext索引与价/冻结sigma和volume基准、last63 returns/21 volumes及原顺序leg volume；E0/participation的active/floor/ready/previous-close与pending/ID；B4的EW、两尺度方向、高低点、候选anchor/threshold/frontier/credit和日期；G1与I上述状态。现接口均从头初始化，没有这些已认证checkpoint/API。本次不实现它们。

## 缓存准入必核

1. 固定source SHA `11e7f9e38798e6e411f33b3250c564bcd5fcfbe34af2bda74e04c02cf8d08d9b`、各股实际首源日、精确ID、OHLCV/amount单位与复权版本、有效mask/segment、参数和原代码SHA（见ORIGINAL_SOURCE_IDENTITY）。参数包括joint=True、event_exit=False、21/63/5、1e−8、活动clip0.5–2、decline_candidate=False、B4尺度21/63和pace5/21、G1_I。新阶段/排序公式另加自身代码和参数身份，旧rank不能代替新母体排名。
2. 新全序writer若获授权，必须与三日期既存完整5517请求的19原字段、未知值、日期、missing/reject状态逐一核同；新增numeric锚点还须核已保存三股的完整prefix事件/确认日期。当前只有三股9/24→10/8的有界追加测试，不是全5517、所有边界证明。
3. 在warmup前后、确认/保护线同日冲突、价有效但量无效、invalid/source分段、近epsilon边界、长leg等分支做物理截断前缀一致性检查，全部未来字段不能反写旧行。只有另获授权才执行；本次未运行。
4. 保存状态行应按日期精确查询；缺当日源行返回UNKNOWN，不ffill旧i_buy。不得用ledger未来outcome、末端attrs或全源尾来补状态。新stage replay当前只返回末日snapshot，必须在循环中另存当日副本并复核，不能切片末端快照冒充全history。
5. 源重修/新qfq vintage、历史行变化、mask/segment/起点或代码参数变化即失效或重新验证。相同源下的算法前缀因果性不认证历史复权available_at、PIT证券池、ST/停牌或真实交易资格。

可用方案是先利用已生成三日期状态评估机制；若确需日序，再一次顺序原函数→历史state行缓存，并通过上述边界，避免逐日重复前缀或先建增量平台。速度证据不代表候选有经济优势。
