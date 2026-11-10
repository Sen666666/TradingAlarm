# 2022 PVR显著正浮盈后亏损回合：保护与退出证据

仅审计242个已闭亏损、完整真实日末观察且max(U/Krem)>=3%的回合。3%仅沿用诊断分组，不是建议的新止盈阈值。没有改策略或运行账户。

## 关键反证：不能把CORE少一个if当已发生漏止损

读取joint_v3.py第222—240行：CORE持仓在i_target仍真时更新last_core_line后continue，不直接以C<=floor发卖出；i_target假才I_structure_exit。MOBILE/add先比较当日signal close<=旧floor；触发才卖，未触发才max(old floor,I floor,新CP1候选)抬线。

但源码差别不等于实际漏保护。在这242回合的2528个CORE层持有日中，有2441层日i_target=True；当日signal close<=前日last_core_line、<=当日last_core_line、<=当日I_floor三种情形均为0。新开当日用初始买入floor作前线；前日与当日线分开，不混用复权单位。

因此当前样本没有证据支持“CORE价格已穿线但I仍真，漏了一个硬floor判断”这一故障，更不能以此实施最小CORE硬floor修复。范围是本B组，不声称核了全部2022 CORE或其他年份。

## 峰值时保护线与股票整体成本

每回合取真实日末U的金额最高时点（不是全未来走势峰值，也不是比例峰值）。U是剩余全股市值按close减5bp及当日估卖费，减股票移动平均含费剩余成本Krem。用同日original fullfacts.factor将层signal线还原raw价格，和Krem/Q比较。

242回合中207至少一层的线低于股票平均成本，193所有存续层线均低于均价。182回合峰值有mobile层，其中136全部mobile线低于均价。峰值共224个mobile层，157层线低于均价；93个CORE层，88个last_core_line低于均价。

CORE的last_core_line是风险账引用线，不是直接卖出触发线，不能与mobile止损线混称同一种可成交保护。线在均价以上亦不保证有利润：部分层数量、后续新买/卖、费用、close触发及下次open成交都会影响整体PnL。线在均价以下则说明原规则并无自动全股保本承诺，不能单凭此认定该改成本线。

## 退出事件与重复日志

原pilot_layer_exit日志逐步合并layer集合，同一层可能在同一次close被重复列出。原展开表EXIT_TRIGGERS.csv有439行，不应当作439次唯一触发。
按layer+trigger_at+reason去重，EXIT_TRIGGERS_UNIQUE.csv共有363事件：175 I_structure_exit、163 CP1_add_protection、25 ACT_pause。163个CP1唯一触发全满足signal close<=旧floor。363事件全在下一共同交易日09:30 OPEN出现实际卖出，没有本样本中的多交易日待卖拖延；不代表没有隔夜或节假日跳空，也不代表价格可按floor成交。

242回合按最终退出原因的最终亏损：143个I退出−170425.152024327231元；76个CP1退出−104607.393573705723元；23个ACT退出−32422.35451045263元。最终退出原因不等于该回合全部部分卖出的原因。

## 三个大额例子

000620.SZ，1月12日至2月8日完整回合最终−14893.92元。
- 1月25日剩余12600股，净浮盈U7751.07元，股票平均剩余成本3.757004，close4.38。
- CORE2600股的当日last_core_line(raw)2.99；mobile10000股的抬后floor3.772437，已略高于全股均价。不能说全部mobile线尚在成本下。
- 之前1月19日第一批mobile旧floor3.259284，close2.99触发，1月20日成交；之后又加了新的mobile层。
- 1月27日mobile旧floor3.772437，close3.55触发，1月28日成交。
- 2月7日CORE close2.88低于前日I线2.99，同时i_target=False，发I结构退出，2月8日成交。此例没有“穿线而I仍真”的证据。

002911.SZ，7月26日至9月19日最终−8330.93元。
- 8月2日剩余4000股，U7822.26元，平均成本15.872678，close17.86。
- CORE600股I引用线9.04，mobile3400股floor16.607457，mobile线高于整体平均成本。
- 8月3日close16.1低于旧mobile floor16.607457，8月4日卖出这批mobile。
- 后来另有mobile新层，8月26日close15.15低于其旧floor15.502326，8月29日成交。
- CORE到9月16日close12.82低于前日I线12.89，同日i_target=False，9月19日成交。不能把早先mobile保护线覆盖理解成整股已锁利润、以后再加仓也不再风险。

000029.SZ，12月2日至12月8日最终−6683.49元。
- 12月5日2700股、U3927.84元，平均成本13.368842，close14.85；两mobile层抬后floor均13.255948，仍低于均价。
- 12月6日还有新增mobile层。12月7日close12.03低于旧floor13.255948，三层发CP1保护，12月8日成交。
- 在收盘触发时价格已低于线1.225948元，不能把之后实际卖出损失全称次open跳空；跳空进一步分解交由独立成交诊断，不在本报告重复。

## 可支持的下一步与不可支持的结论

证据支持分别检查：保护线相对整体成本的覆盖、原有盈利mobile退出后新mobile尝试、CORE残余风险，以及收盘触发前越线幅度。不能把242回合合成一个“出场太慢”原因，也不能从缺一条if推导现有实现漏止损。没有固定同一入场/资金路径的对照，本审计不声称任何退出修改可挽回金额；尤其不能把每个回合事后峰值总和当可获取利润。

文件：PEAK_ROUNDS.csv、PEAK_LAYERS.csv、EXIT_TRIGGERS_UNIQUE.csv、CORE_COUNTEREVIDENCE.csv、THREE_EXAMPLES_DAILY.json（逐日qty、close、U、每层raw线曲线）与SUMMARY.json。保留原始重复展开表供核对。数据来自SHA验证的120万元2022存档，所有线、因子、qty、现金均使用对应当日记录，未用年末layercash冒充历史值。
