# R2：三个独审反例与原生收盘/批次小闭环

父版本原样保留：`../g-broad-s-concentrated-native-synthetic-20261101/native_capital.py`，SHA `403da82de9fe6f1bac4ecfa86fe81142792d4098385ed4eba6a3178f64d21c09`。
合同仍为原基底+V2，复合身份 `a26b1959379ed6c7e8d82e35f9d3fca9dd050caa5e824850a0d75543005bcc50`。F1冻结内核不改，原生财务组件文件不改。
本目录为独立R2实现；没有历史账户路径、生产、服务或实盘操作，未启用D1。

复验（使用不存在的目录名，保留所有旧失败）：

```sh
/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/research/.venv/bin/python -B research_rounds/g-broad-s-concentrated-native-r2-20261101/test_revision.py independent-001
```

最终本地结果：`runs/final-005/RESULTS.json`，31/31，2.270秒测试时间，加载另计。
31包含21个原组件回归及10个新增方法，不是31个独立市场样本。最终源码副本保存在同次运行的`source/`。

## 三个反例的修复证据

原独审证据复制在 `inherited-independent-failures/`，字节hash单列，不覆盖原件。

|反例|新结果与直接入口|
|---|---|
|999股已有200退出，ACT漏799|用例22：原native exit ID `exit:A0:25`不变，原200责任不撤，追加799份额，最终native target及风险锁并集均999。同层先请求200再请求100只增加原因，不增到300。|
|1股退出×0.5后UNKNOWN余量0被跳过|用例23：在任何native/policy/价格/因子变更前拒绝该action；前后完整账户/政策digest相同，仍持400、退出目标1，action未登记。另验造出零余量UNKNOWN及伪造fill ID，聚合都报UNKNOWN，不能变0。零余量释放必须对应实际native sell receipt及该层parts。|
|不可卖mobile借旧core库存|用例24：旧core999保持不动；新mobile次日才可卖，早窗实际无成交。次日实际卖mobile200、费用7.2552718元，physical batch与economic layer共同减少，core仍999。|

指定库存接口在`native_exit_selected.py`，对原`SectorAccount.fill_exit`只有两个精确替换点：可卖数量查询、实际扣股选择。原定价、费用累积、现金、FillReceipt、Settlement、完成事件正文不另写。逆替换必须与原函数源完全相同。
`NATIVE_EXIT_SELECTION_SEAMS.json`提供替换前后文本与code身份；原生源码文件没有改动。

每个实际buy fill给原生InventoryLot附稳定的receipt ID，`inventory_map`映射到经济层；整数送转新增批次保留parent/action及可卖时间。checkpoint/pickle保留批次ID，`assert_lot_bridge`独立检查每层实际库存。卖出parts来自native批次真实减少量，不能先按策略期望写parts再用总量桥掩盖。

## 新调度与批次验收

- 用例25：`event/planning`依次执行原生结算、保护前快照、ACT整包cutoff、股票旧线失效及存活层ratchet、F1、scoped unlock、K、旧单重验/新意图。同close F1 advance不能解锁新事故，所有已有部分退出义务合并补齐。
- 用例26：实际旧mobile95线先被94价格触发；同包新I96/CP197不能倒改旧层保护，也不能拿新线初始化退出前快照。
- 用例27：10个候选，真实只获准9单；所有9次window回调均观察到已有9笔预留。首单随后无window并实际ACK取消，后来释放的现金不重跑第10只。资金预留和后验执行结果分开。
- 用例28：真实冻结F1的S首次permit时200股高价最低单位超试探目标，全部不买；下一原生advance由收盘入口自动成熟/激活K，次日主动实买79.92078424%。没有在此用例手动赋予mature、K或许可。
- 用例29：完整输入、物理截断输入和被改坏的未来输入在相同close得到相同完整指纹；close checkpoint跨进程续一个OPEN，所有经济/政策/F1/事件状态与不中断分支一致。保留待卖及新意图，拒绝重跑已完成cursor。
- 用例30：同股core100与mobile200职责，一张native卖单、一次实际300股receipt；分层费用之和恰等native费用，不重复最低佣金，不用别层可卖资格。
- 用例31：真实F1 permit暂弱使旧买单请求取消；未ACK不退款，新CP1不延长原deadline。未来known_at输入在状态变更前拒绝。

所有财务仍只有一份native account。桥检查初始现金+真实成交净流+确认股息+同源库存估值，以及现金资产、层现金、费用、物理股数。估值用同一native as-of mark，不冒充独立行情源。没有NAV残差补齐。

## 新发现、保留失败

`runs/lifecycle-003/`保留一次失败及当时源码：完整close初版在G支持未变、仅被动价格上涨时误触行业20%配置减仓。修为按支持/context/K目标变化触发配置，不能把价格/NAV漂移当卖出事件。31项后续验证通过；这不是改交易门槛。

## 仍然不是历史runner就绪

1. I/Q/CP1和完整优先键仍是明确因果接口输入；没有加载历史1709源，也没有重算指标或构造新账户历史。F1本体确实是原冻结kernel。新用例25—29不手动授予F1待测结果。
2. 任一受影响数量域会产生不可精确归属零股时，当前选择原子拒绝整个公司行为，必须停下报告。未实现一般零股成本/退出份额归属，不得直接跑含此类事件的历史路径。
3. 多层指定退出已接native；但`funding_reductions`中“同股多个旧G层的聚合估费/同比例腾挪计划”仍显式拒绝，而不是伪造可用现金。单层/股的既有腾挪案例继续通过。
4. 多单同时降为G目前按真实占用逐单保守重验，可能全部请求取消；尚未做“保留优先子集并等待其余ACK”的批次降级规划。单单原G限额/部分成交缩量已回归，不称所有V2批次退化都已闭合。
5. 这里只是生成源驱动的最小原生事件入口，不含历史输入装载、旧SC/PVR策略切换授权迁移或正式运行命令。不可将旧checkpoint的行业stage直接设为F1成熟，也不可清空旧现金、责任或ACT。

当前停止在合成审计入口。独审尚未作出R2结论；没有策略晋升或经济路径授权。
