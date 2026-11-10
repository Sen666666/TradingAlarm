# 原CP接口、缓存与20股适配边界

本次只读源码和历史输出，没有运行CP、stock模型或账户。**此前35–45分钟是完整stock_signal的E0/B5/G1/I估计，不含CP、CP trace或逐持仓保护线。阶段轻链55.71秒也不含CP。** CP额外成本须在20股试点中单列实测。

## 原函数与输入

`continuous-protection-lines-20261028/code/model.py:26`：`calculate(f, price_only=False)`，源码SHA256 `85f21ad1622863645618f570b5f2e832558ebaca218ff2c71d0b4a0b545dd0bf`。该模块没有账户、持仓、资金、订单输入。

| 输入 | 股票原绑定及约束 |
|---|---|
| index | 继承原I事实的价格观察index，唯一、递增、每日一行 |
| close | 同源调整价，正且有限 |
| amount | 同源成交额，正且有限；不是volume |
| segment_id | 显式、不缺失、同段不能非连续重复 |
| e0_valid | **实际是原G1_I的i_target布尔值，不是e0_target** |
| e0_down | 原numeric事件等于−1，不是I退出或价格下跌的替身 |
| i_floor | 原G1_I保护线；不参与receipt计算，供输出引用及逐起点保护投影 |

绑定原文见`common.py:17–24`、`case-stock-cp1-warmup/generate.py:23–28`。`calculate:57`输出名`e0_floor`实际复制i_floor；名称不能被解释成base E0线。NaN不能直接astype(bool)变成True：新适配先取原有效价/I事实index，原raw I应为0/1；缺失或错误状态不能冒充布尔授权。

## 有效钟：原样继承，不新清洗

`native-I-cache-interface/cache.py:20–22`先用原eligible_prices排除OHLC/原source标记等无效**价格**行，并断言与原G1价格index完全一致。之后CP沿该index读取amount。

`generate.py:26–27`对保留行的close/amount作正有限校验，失败即ValueError，原文为“no row removal allowed”；`:44–46`记`blocked_CP1_input`。CP本体`features:12–19`也对整frame严格校验。它不会为坏amount自动drop、fill、拆段或跳过重开。缺交易日不补行，观察钟也不是官方市场日历。

因此20股若在原价格钟上全部CP输入有效，可原样调用；否则对应股票CP阻断/UNKNOWN，不借PVR的amount有效子集改变E0/I钟。已有原source segment可按原值传入，不能为跨坏额继续计算临时造新segment。原函数全frame校验也意味着后段坏数据可能阻断整次调用，不能宣称早期结果已经有完整公共CP缓存。

## 公共证据与实际持仓线

原特征为前63个绝对log-return中位数×1.4826（最小1e−8），再把CP尺度钳至`log1p(.001)`；成交额基准是排除当日的前21中位数。`m=1+.5*abs(tanh(r/s))*tanh(log(amount/B))`。EPS为固定gamma4。

状态为phase/anchor/frontier/冻结scale/credit。仅新frontier推进积累credit，位移和credit都达到`sqrt5×旧冻结scale`才发receipt；当日candidate为`C×exp(−sqrt21×旧冻结scale)`。receipt后市场状态直接重锚，即使没有持仓或订单也如此。无效I/未准备、下行E0、低点重锚等原优先级见`model.py:31–50`。

公共输出包括ready、phase、reset_reason、anchor/frontier/scale/credit、delta_frontier/displacement、receipt/candidate、next_*，及r/s/z/B/u/v/m、e0_valid/e0_floor。**同输入下空仓与持仓可以共用这些数值。** ready只是价格/额窗口准备好，不是I有效、S0准入或新增授权。next_*是本日处理后、供下一观察使用的状态，并非未来数据；不能用next_scale重算本日以旧scale生成的candidate。

实际P不能对空仓伪造：`joint_v3.py:223–240`先检查I/ACT退出及已有MOBILE旧P，再在未触线时取`max(旧P,I_floor,当日receipt candidate)`；CORE保持自身原规则。新MOBILE起始参考为`max(I_floor,当日candidate)`（`:255`），仍不代表最终成交。`model.project:60–72`也要求外部start/initial、先判旧线、吸收退出，是单起点影子，不是每证券唯一公共持仓线。公共试点保存candidate与I线引用即可；实际P、持仓退出、下单资格保未计算，不能ffill candidate跨所有epoch冒充真实P。

## 旧缓存可以复用什么

原1709 manifest SHA为`59d12b9c9ed287101e12b8be6c19ebc1d52b6f257525a70e1e342a879ad674f0`，保存facts、CP1_input、完整每日CP1及compact receipts/formation签名。三只抽核的输入和输出SHA均吻合旧manifest；输入起于2013-01-04、止于2026-06-30，来源为旧prepared-v2 signal/events/states和IX/G1链。

它们不是当前canonical SHA11e域：银之杰9/24 old close为83.49603500392514，canonical为15.82；盈新1/24分别4.53288843167426和3.98；海能达9/24分别29.44843966825181和5.24。九个固定价格例全不相同，成交额也不同，见CSV。即使部分差异像常数复权/单位比例，也不能据此称所有CP锚点、I状态、舍入边界和receipt逐值复现。

当前三份全canonical stock_signal快照schema均无CP字段。受界检查的旧1709源引用没有canonical adjusted_daily_bars；在这些已审产物中未识别同canonical历史CP输出。此为明确范围的证据，不是穷尽全工作区的“不存在”断言。不能拿旧prepared CP补当前canonical的2026/5/16至6/30尾缺口。

## 最小20股适配

1. 复用已冻结20 IDs及原stock调用链，从各股实际可得首源日计算至2026-05-15，之后再截2022以后的输出；不能统一从2014或2022重置暖机/锚点。记录源SHA、CP模型SHA、参数及amount原单位，不猜CNY或换用旧源金额。
2. 用同一原价格index，把daily raw i_target、i_floor、numeric_event分别映射到上述CP输入；原amount按index精确join。记录输入是否全有效、坏行及阻断原因。不要新filter或填值。
3. 调原calculate一次，完整保留public每日CP证据和candidate；实际持仓P留空。新source-domain identity单独绑定，不把旧receipt ID复制过来。若生成trace，形成区间与confirmation day按当时状态记录，旧E0 episode/market消费与账户实际消费不能混同。
4. 与原stock快照核E0/I/close，并在独立物理短前缀上核CP全列、receipt和冻结尺度；目前旧源prefix验证不能代替新canonical检验。确认日才公开事件，不能把发生在旧pivot/anchor日的事实回填为当时已知。
5. CP无额外future terminal attrs；日末next_*可保存作状态。实际账户线和trace完整性仍有各自初始条件。目标2026H1须明确同源只至5/15，后续为缺源，不混接旧CP。

源码原文、路径行号与哈希在SOURCE_EXCERPTS/SOURCE_IDENTITY；旧缓存与当前输入域证据在EXISTING_CP_CACHE_PROVENANCE、OLD_VS_CANONICAL_INPUT_EXAMPLES。未自行启动试点、全池或账户。
