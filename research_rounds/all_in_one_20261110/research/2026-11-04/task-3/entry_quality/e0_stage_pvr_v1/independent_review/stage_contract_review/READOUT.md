# 冻结E0阶段排序：独立纸面质询

结论：按已冻时序可定义为因果的阶段排序，未见纸面必然前视；这不是实现PASS，也不提供经济有效性。尚须owner以原E0 target/floor/entered/exited逐bit核同，ready与事件有效观察分开核同，再审核保存阶段/排名。独审零模型、零账户，未改FREEZE或已封源码件。

1. 排序是有限名额硬优先，不是弱权重融合。BREAKOUT总数达到K时，所有START（含无旧峰）与RETRACED都无缘topK；即使其PVR远高也不能越级。完整母体保留与同K比较是必要公平条件，却不消除这一实质排除。应原样报告每日期阶段N、top20/top100构成、旧PVR高名次降级/替换名单，以及预定强尾部/亏损标签的位移；不为了保住某股改优先级。

2. E0 floor不能取numeric.active/floor代替。numeric只用正且finite close/volume观察，原E0 policy检查eligible所有有效价格CLOSE；量缺失日也可能触旧线。旧线先判、exited禁同日重入，其后才+event ratchet；E0 ready不能凭numeric event=0推断。需共享原eligible mask/source/初始化/compare，而非从完整未来事件表填回发生日。

3. 必须分开last_confirmed_peak与本次H。仅−event确认的是峰；+event的confirmed_pivot_price是谷，不能拿来作H。确认当日才更新last_peak；+event生效时冻结此前已知最近峰为H，随后C>H可同日晋升。未来developing extreme/后来确认峰不得替换当时H。若down仍在原E0内，只降级RETRACED，不把它称为I破位或卖出。

4. BREAKOUT是latched历史状态，不保证当前C仍高于H。在未出现下一确认down、且原floor未破之前，价格跌回H以下仍可能保BREAKOUT；应在解释中区分当前gap与曾经收复证书，不能把阶段名字表述成每日现价过滤。新−event撤去证书，后续+event才能按新冻结H再晋升；不能静默用当前C/H覆盖冻结递推。

5. 初始化与截断有经济方向。原数值初始化先假定下行developing leg，第一个+event可先于任何已确认峰；缺峰应留START_NO_REFERENCE，不能冒成RETRACED或INACTIVE，也不能从样本起点以前猜峰。若完整可用源起点更晚，阶段及峰的年龄/来源均会变化；本地6000行上限或上市前历史缺失不是无历史阻力证明。源内日历缺行也不能自动等同新segment或重启。

6. 按冻结文字，H取全可用历史最新已确认峰，不仅当前E0 epoch；若它来自旧epoch，应保存/展示该事实，不擅加年龄门或选更有利高点。后来确认lower-high作为新的最近峰可能降低下一次突破门槛，这是本规则的真实弱点；不能把BREAKOUT称为宏观高点突破或长期趋势成立。

7. 无参考/未预热/意外inactive已知i_buy必须分别处理。2022的2个PVR UNKNOWN仍在177母体，但不能进入排名；三个known-score比较池应保持原175/2313/779和同量top20/top100。若已知原i_buy却重建出inactive/unknown阶段，按FREEZE应阻断该日期最终排序并查原时钟，不能塞到最后队列算作不合格。

8. 最终结论仍是原路径依赖i_buy母体中的三日价格关联。原I、CP和退出保持只读，不代表新增排序未来执行时成交股不变；本轮并无订单/资金/行业slot模拟。先锁stage/ranks再读既存标签，不能从未来赢家改H、阶段、优先级或母体。

现有反例已经在冻结稿保留：深V/新股可能无峰留START；常态波动强趋势反复确认down受罚；较低局部峰可使衰退中的反弹获BREAKOUT；同一突破状态也可能同时容纳失败与强尾部。它们是预注册待证伪点，尚非已证明的经济结论。
