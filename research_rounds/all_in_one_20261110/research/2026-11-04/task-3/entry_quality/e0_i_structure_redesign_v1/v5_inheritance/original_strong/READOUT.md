# strong原账：没有找到所要求的晚层继承实案

只读取现存No60强窗原账，未导入策略、未重放账户、未计算新数量、未新建账户或回测。原账没有V5 probe parent、执行认证或carrier witness；`metadata.pool=probe`不是V5用途，`role=mobile`/`kind=add`也不证明当时满足V5 mature。

## 筛选范围与结果

范围为2025-07-01至2026-06-30，242个原CLOSE快照、1171个原层，其中867个`metadata.role=mobile`（其book.kind实际为`add`）。从原真实sell receipt的正shares parts筛选`CP1_add_protection`，得到492个sid×实际sell时间事件、666个MOBILE卖出parts。

严格实案要求：早层已于该sell全平；更晚MOBILE在该sell之前已实际买入；sell后仍live；两层`stock_structure`相同。666个早层均在对应sell全平，其中174个parts在卖前已有更晚MOBILE；但这些更晚层也在同OPEN退出。**严格候选0，取消同structure限制仍为0。** 原当日CLOSE快照再次核对：407个事件全股flat，85个事件只剩CORE，0个事件仍有MOBILE。

这不是“不可能发生”的数学结论，只是该原账内没有找到所要求的实案。最终层的opened/closed与实际sell.parts交叉检查未把“同一OPEN先卖一part、随后又卖另一part”冒充持续健康存量。每日快照是当日原成交后的结果，不能当OPEN之前已知字段。

完整492事件、666个逐part条件及卖后快照摘录见`ALL_ORIGINAL_CP_SELL_CHECKS.json`；范围与分母见`SUMMARY.json`。

## 非合格对照：000711.SZ只剩100股CORE

共同原结构ID：`000711.SZ|0|2026-01-23`。

| 原层 | 原实际买入 | 原数量 | 2026-03-25实际卖出parts | 卖后存量 |
|---|---|---:|---:|---:|
| CORE713 | 2026-01-30 OPEN | 100 | 0 | 100 |
| MOBILE723 | 2026-02-03 OPEN | 12400 | 12400 | 0 |
| MOBILE733 | 2026-02-04 OPEN | 12100 | 12100 | 0 |
| MOBILE761 | 2026-02-12 OPEN | 10700 | 10700 | 0 |
| MOBILE769 | 2026-02-13 OPEN | 3200 | 3200 | 0 |

3/23已知四个MOBILE旧保护均为adjusted `10.81979630295092`。3/24收盘raw C=4.45、adjusted C约10.714441，低于旧CP线；原当日pending_sells含该股。3/25原真实sell receipt一次卖38400股，price=`4.407795`，四个parts分别12400/12100/10700/3200；原交易索引1516。卖后CLOSE只剩CORE713=100，其`last_core_line=6.524973879393744`；不能用CORE初始`layer.floor=4.020924862947436`替代当时I线。

3/23—3/25原facts均I_target=1、G1=-3。这不是V3/V5 mature值；不能把原I真或真实ADD历史转译成当前mature。该例只能说明“同结构仍有CORE100，并且以前确实有大ADD”依然不足以建立V5认证继承。全原字段、C/因子/I/G1、旧线、实际parts与前后快照见`CORE_ONLY_CONTRAST_000711.json`。原样本没有V5履历，不能把该例当作V5会拒单或接受的已验证结果。

## 纸面边界：继承的是资格谱系，不是持仓布尔值

允许健康晚层继承的最小语义，是事前认证target完成后形成的certificate，只有在当时已合法授权并真实成交的ADD后代上记录其lineage。若原probe层局部CP退出、同一有效结构中仍有这样的健康ADD存量，退出仅移除受影响carrier，不能无条件清除所有后代。这里没有证明当前原账的任一`add`已经拥有该新certificate。

拟申请ADD时仍须当前market_mature为真、相同有效structure/root、无相关未决退出/撤单责任且有新的合法CP；不因certificate仍在就放行降级中的新增。结构失效后不能复制旧certificate到新root。mature下降期间certificate是“历史记录保留但当前不可用”，还是直接失效并要求重试，是需要主卡明确的政策差别，不能含混地称继承。

只剩tinyCORE要分两种：若它就是事前批准且真实complete的原probe，引用的是原资格而非晚层继承；这依然不创造market_mature或新增规模证明。若原probe已退出、只剩别的旧CORE，则仅有held、同root或“曾发生过ADD”均不足；必须能证明该存量本身是合法certificate的carrier。所有ADD后代已受保护退出时，不能把失效资格自动倒灌到无谱系CORE。无需为此引入经济最低额、1R等待或新资金参数。

当前结论是原路径类比未找到，且无真实V5认证证据；不是赢家继承政策已被证实或已被否决。

## 交付与复现

`extract_original.py`仅解析原JSON/gzip/parquet；`SOURCE_MANIFEST.json`绑定原book、daily、单股facts与提取脚本SHA。未把原成交或原现金复制到任何新路径。
