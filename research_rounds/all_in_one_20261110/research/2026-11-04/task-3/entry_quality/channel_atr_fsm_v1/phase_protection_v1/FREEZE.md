# 原CP早期保护 → 2S后TREND4：新入场分层合同 V1

## 范围与假设

仅做信号级保护影子：复用既有五股smoke_v1全部291原raw CP锚（290配对、1下一报价未知），不按未来盈亏选锚。不跑账户/资金/数量/新入场策略，不改原E0/I/CP信号；CORE原保护不变。固定首次有利收盘推进2倍初始ATR、阶段后4倍ATR，不搜索参数。

本合同仅适用于新入场时已选定该policy的CP/MOBILE层。不能给旧实仓临时换低止损线，也不能撤销已提出退出或已生效更高订单。研究中E为原锚后下一观察OPEN参考，并非证明成交；实盘必须实际fill回报后才建立层合同，无fill无阶段。

## 层身份和冻结量

每已确认执行批次一份子合同，E为该不可分割执行回报价格/VWAP，S为其原入场信号锚当时已知ATR14_prior>0。E/S/P0/版本冻结；后续部分成交另建子合同、归同目标风险账，不能用动态均价降低旧E或改旧S，更不能重置父目标股数。新的ADD层不继承老层TREND资格。

E/S/P0/Ifloor必须同一价格单位。本研究沿原同源adjusted OPEN与ATR；实盘raw fill必须用当时已知因子转入同域，公司行为只作等价单位转换，不能把raw E与adjusted S相加，也不能跨不可比source取max。

本轮每锚仅模拟一个OPEN参考的条件性完整批次，没有真实部分成交、订单ACK或资金事实。P0=max(原CPcandidate,原I_floor)。OPEN未知或≤P0仍沿原状态保留不可评，不杜撰入场。

## 收盘状态机与冲突顺序

状态EARLY、TREND4、EXIT_PENDING/UNKNOWN_PENDING。reached_2S初始False、只False→True。M_C为本层入场后已完成收盘峰（初值E）；M_H为用于以后跟踪的峰（初值E）。不得包含实际fill前日内H：首持有日只以完成C更新M_H，此后本层已跨夜持有的完整bar才用H；所有提线只用本close之前已知M_H。

每个已知可比收盘t，按如下顺序，不可重排以救样本：

1. 原I模型在本收盘已知i_target=0即硬退出；这里不是滞后一日I_(t−1)。再检已生效旧P：C_t≤P_old也退出。即使本日曾上涨2S也不能反转已锁退出。若某数据未知，仍检可知的旧P责任，不能因未知清账。
2. 原本收盘的新I_floor为硬约束；已知且I_floor≥C_t则退出，不受阶段豁免。Ifloor未知，记UNKNOWN责任，不虚构提线。
3. M_C_seen=max(M_C_before,C_t)。若M_C_seen−E≥2S，记reached_2S=True，永不因回吐撤销。只用已完成C，不用日H晋升，不回填到较早日。
4. EARLY且reached_2S且ATR14_prior(t)>0时，当close切TREND4。若当时ATR不可用，只记已达2S待数据、保持EARLY且原CP流程继续；不以ATR=0代替，也不静默停止CP。
5. 若仍EARLY，按原CP流程只升不降：Q=max(P_old,I_floor,当前原CPcandidate若本日receipt)。若已TREND4（含本日刚切换），Q=max(P_old,I_floor,M_H_before−4ATR14_prior)。**不再取当日或以后新CPcandidate的max。** 本日CPcandidate尚未安装，跳过它是入场合同预定优先级，并非事后撤销已生效订单。
6. C_t≤Q时提出次行动时钟的退出，不安装已经穿透的新线、不声称按Q成交；否则P_next=Q≥P_old。本日完成后才更新峰供未来用。
7. TREND4不可逆直到本层退出；新CP/E0不重置E、S或阶段。原I硬失效仍退出。同层首退出吸收，不因下日反弹撤回EXIT_PENDING；不能成交时实际持仓/订单责任仍存在，本信号影子不冒充已卖。

ATR/价格/源未知要显式标UNKNOWN，不能借数据恢复追溯“本来早已TREND”。已达2S事实可在已知close时记忆，保护更新需要的输入恢复后才能执行。原共同native I生命周期/source截止保持与原同锚比较一致，不跨新I补路径。

hard I/Ifloor未知时，已知可比close仍可更新独立价格事实记忆，但阶段授权保持UNKNOWN_PENDING，不能只因ATR已知就切换绕过hard未知。未知恢复后若旧P未失效，历史reached_2S可触发当前日切换，即使C已经回到2S以下；这是“曾达到”的合同语义，绝不是当前仍盈利的证明，不另加当前盈利门。本轮若先到已存common_UNKNOWN边界则结束可评轨迹，保留责任，不能杜撰恢复演绎。

## 为什么不是max(CP,4ATR)

保留的max只有此前已生效P与I硬底线，未来CPcandidate退出本层更新函数。4ATR只有追过已继承高P后才实际主导；若旧P已经很紧，本方案不能放宽它，也可能来不及帮助赢家。两种更新函数没有点态排序，ATR收缩或旧峰很高时TREND4仍可能比继续原CP更早退出。结论必须报告阶段前退出、切换同日冲突、继承P主导/ATR主导、候选早/同/晚及未知，不以“4更宽”预设更长持有。

实际已有更高live改单或EXIT_PENDING不得因phase标签撤回；需要共享单层保护台账和改单ACK才能实盘落实。本轮只有收盘提案与下一源OPEN参考，A股T+1/涨跌停/停牌/盘口和成交不可证明，不填补这些缺口。
