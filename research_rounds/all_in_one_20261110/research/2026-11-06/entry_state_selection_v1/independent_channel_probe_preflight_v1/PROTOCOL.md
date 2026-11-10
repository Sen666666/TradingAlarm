# 固定价格/量职责分解预检

按用户在首版五例后的明确要求继续。这是已消费病例上的机制诊断，不是样本外、不是未看案例提出的独立验证。唯一固定同五窗口；无参数搜索、账户、收益或新成交。

价格职责：当日C>严格此前20High，独立建市场根，发一次首探收据，不要求旧E0/I/G/PVR或金额确认。a为此前20Close最近最低日，若再入a不早于前根失效日；冻结a/U/Ca/B/R于出生时。B严格a之前21有效金额median；没有B或金额链不全，仅量态UNKNOWN，不能阻止价格首探。

量职责：从a起F=Q=0；每次新收盘前沿delta=max(0,log(C/Ca)-F)，F=max(F,log(C/Ca))，Q+=min(1,sqrt(A/B))*delta。R=log(U/Ca)冻结。Q>=R才是CONFIRMED，否则PROBE。需要记正delta的新前沿日缺金额后Q数值UNKNOWN不能回填；非新前沿delta=0时无须金额，既知Q不受影响；此前已确认的历史事实不倒销，未确认者保持PROBE_AMOUNT_UNKNOWN。出生同日已满足R可以已确认，但仍只有一份首探意图，不能首探加仓双发。

保护：S=minLow[a..birth]，后续先用旧S判断C<=S失效；未失效才以E0ready且target=1的有效floor抬max。出生不接E0floor，无固定止盈/冷却/次数门。旧I关闭不作为退出。失效当天不重新建根，下日新证据可以重入；实际须完成卖出责任。价格/源/复权坐标UNKNOWN隔离根；不当卖出、不解锁真实持仓。

市场收据：出生即一份。活跃根后来仅严格新收盘前沿delta>0发行新身份(root,sid,source,day)；同价、横盘巨额、旧票不得重发。当前实现sid+root_day+day身份在固定来源段内唯一；跨源前根隔离，新根另日出生。每个收据只许可立即下一个共同OPEN的尝试，不跨日缓存。

执行条件合同（未模拟实际执行）：首探为原初仓政策的小目标，上限沿原初仓/风险预算；本预检不设新股数。每根最多一个probe parent固定Q。NOFILL、partial或cancel后真实terminal ACK与fill ledger必须对账，无未结leaves/退出/未知责任；晚于解锁known_at的新receipt才可续该parent Q-F，不能提高Q或用旧receipt续。没有新前沿不重试。若根失败，取消未成交余量并永久退役旧root，已成交责任不清零；新根需另有资格且旧卖出完成。

全部probe已成交并真实complete/ACK获知后，CONFIRMED且又有晚于该获知的新receipt，才有一次候选ADD的市场许可；实际仍须健康持仓、原资金/行业/规模/风险/费用条件。本轮不生成ADD数量或新成交。已经有partial parent只能补其余量，不能改名ADD。同根至多一次ADD完整目标；未结责任阻止另单。量确认不等于真实执行完成或收益已足够。

T收盘才知信号，最早下一共同OPEN；如当日成交最早再下一共同OPEN卖，T+1。日线OHLC或一字价不是真实成交/ACK证据。NEXT_OPEN_OBSERVATIONS只列观察，绝不判fill。

与V5：继承真实fill/target/ACK责任思想，不宣称这些是新。V5的市场根仍来自原E0/V3、slot绑原UP，零fill可续旧合法parent；这里市场根由20High独立出生，每次续单额外要求新的frontier receipt，数量同parent不增。与E1：取消其旧buy/PVRAND、20Close/2R箱体/5日冷却；与LER：取消E0准入、改为20High独立根而非3日休整后昨日High。

前缀QA仅本函数在冻结输入上的时间可见性，不等于上游复权/E0原生因果完整复核。

执行纯函数补充：在立即next common OPEN核eligible_open等于decision_open，否则过期。probe与唯一ADD各保存独立固定Q/F/live_leaves/complete_known_at；零fill后的ADD只续同ADD余量，不再申请新ADD。函数为纯准入检查，目标登记与receipt消费必须由执行器原子持久化，未实现broker提交或真实对账。

probe/ADD parent必须绑定当前root且未retired；新root不得继承旧目标Q、旧fill或旧许可，纯函数对错根/退役parent明确拒绝，旧实际责任仍保留。
