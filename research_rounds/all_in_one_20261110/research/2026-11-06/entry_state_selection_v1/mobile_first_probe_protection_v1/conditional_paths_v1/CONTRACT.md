# 固定14例独立条件路径 v1

## 不可变范围
固定 NOACT round_id=[27,17,28,1527,1542,2891,2893,343,361,1942,1952,2898,2905,2897]。7快败、6右尾、江丰均按已知历史选择的机制开发集，不是样本外。统一截至2026-05-15，不末日强卖；每股/每case独立，绝不相加为组合收益。旧NOACT原始真实历史代理账保留为事实参照，不称新条件控制为原账户精确复现。

## 两个条件臂，唯一首MOBILE持有责任差
CP_CONTROL_COMMON_I_SIZE 与 I_PROBE_COMMON_I_SIZE 的每次空仓MOBILE均以信号收盘本路径NAV N，冻结2%N毛额、.25%N含费名义I风险及最大股数。初始N只在seed取原信号收盘NOACT NAV，并全部作为本独立case可用现金；不导入原他股资产/现金负担/未来批准。以后N由自己的现金、库存、应收、费用和公司行动计算。

信号参考p=C*1.0005，F=信号已知调整I线/同日factor。最大合法q须 q*p<=.02N 且 max(0,q*(p-F*.9995)+dated_buy_fee(q,p)+dated_sell_fee(q,F*.9995))<=.0025N。次OPEN只缩q，使用冻结I线/因果OPEN factor与OPEN费率重核同预算。原max(I,CP)调整线另存guard_floor：O须严格高于guard_floor/OPEN factor；I<O<=CP仍拒单。不得将新参考风险当实际最大损失保证。

live保护floor同时是原native pool/sector风险占用来源：控制用CP、候选用I。因此后续ADD可用预算差异属于首探保护责任及其原生预算含义的路径后果，不是仅挪动卖出时间、保持其他一切数值不变。

控制首探保持原ADD的CP旧线先检、存活后max(旧线,I,新CP)抬线和CP退出。候选首探标probe_mobile，以原I结构失效时钟退出；其风险账面I线随已知I更新但不因CP破线退出。两臂新追加均原CP保护，且共用 V=Q*O*.9995−dated_sell_fee > K_remaining 的盈利门。K含买费，部分卖按全股票比例退K；卖款/股息不抵K。未过只禁止新增，不退出。相同订单部分成交沿用原意图身份，不重新判为ADD。

真正fresh I CORE保留原10%毛额/.25%风险/原I退出，不改成MOBILE也不改2%；共同分列其重入。这是既有原合同，不是新增臂。probe_mobile仍role=mobile，receipt/attempt按原mobile消费，不消费core_epoch。

## 再试与外生市场时钟
从2022首个共同收盘逐前缀因果预热原epoch/global_watch；seed前core_epoch只取该股原真实CORE成交epoch，之后只由本条件路径真实代理CORE成交更新。技术预检确认部分原seed有CORE+MOBILE同时资格，独立现金下CORE可能先占槽。因此唯一seed日共同限制为该已选原MOBILE意图，保留原CORE资格和屏蔽记录；不强制成交数量/日期，风险最小单位或guard不符仍不成交。seed以后恢复完整联合fresh I/CP资格。该条件起点不等于原联合账户首笔复现。归零且撤单/挂卖清除后只能后来新鲜I/CP资格；不复活旧ticket。记录全部失败和随后再试，不只保留最后赢家。

原行业E0/CP receipt/attempt以原市场流预热；金融level、迁移、loss、库存和订单由独立账自行演化。保留原行业/池/单股限制与10%现金预留，原NOACT的account risk与confirmed60删除合同照旧。没有共享现金、其他股票竞争、他股释放资金，单股PVR排序退化为唯一槽；不挪用原未来funding/held/barriers。

## 严格复用与执行限制
复用原native Decimal ledger、joint_v3行业与买卖状态机、原NOACT route预算合同、continuous_execution次OPEN/前20已知正量1%容量/dated费用/最小单位/T+1/结算，以及原因果OPEN factor。先卖后买，挂卖阻止新增。缺OPEN不填价，买单按原day expiry失效；卖单等待下个可见合法代理窗口。江丰1/30–2/5缺bar不能声称官方停牌。

公司行动沿用原旧账previous-close权益、显式净分红/应收支付、拆股最小股数及因果调整映射，条款假设预知，不新增官方PIT主张。已知OPEN后同OPEN±5bp是条件代理，真实撮合、涨跌停、队列UNKNOWN；固定1709背景NON-PIT。

## 预检与输出
经济路径前须完成合同/代码独审，合成guard拒单、q冻结、2%/.25%、partial身份、亏损禁ADD不强退、挂卖禁买、新信号重入、缺OPEN、成本分红拆股、OPEN未来HLCV毒化不变、seed锁前缀、源hash等预检。

逐case同时给原账首层事实；新两臂信号I/CP/guard、冻结q与预算、首次最早退出触发/代理成交、费用/资金回收及合法重入。列全部回合、已闭W/L、未闭正/负/UNKNOWN、占资日/成本日、首层可见最大不利幅度、触发到代理成交间隔、原CP已退出而候选I尚持天数。较宽I扩大亏损反例必须保留。未闭不能作赢，缩股不能当胜率提升，不从固定14推35%或组合效力。

统计明确区分seed MOBILE首尝试、后续MOBILE、后续真正CORE及所有0→0回合，初层与含ADD整回合分列。回本估值用累计首层售净款+已记股息权益+剩余净清算−初层买费本金，只是CLOSE纸面估值，可能含未到账应收或T+1不可卖库存，不称实际可用现金回收。所有付款/结算明细供独立核算。MAE包含可见持有日low及实际代理卖出价，不捏造缺bar观测。
