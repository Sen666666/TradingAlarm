# V3：每个E0下行事件撤销成熟新增，最新已确认峰恢复

用户明确变更。V2及输出封存，不作结果选优。本版本只在盈新000620、山东601019、太保601601、海能达002583的原完整source前缀上演绎状态，再截既定展示区间。0账户、0订单、0资金比例、0候选收益、0新E0/CP重算。只消费保存的原E0事件/收盘/原信号注释。

## 1 输入与量纲

原E0正event在确认收盘发布低pivot L，负event发布高pivot H。每点保price_adjusted、pivot_day、confirmed_at、source_segment/id；发生日不等于可用日。所有比较沿原numeric.compare/gamma4，tie保旧来源；保护支撑用compare<=0。当前有效可比C即可检查旧P，缺量不豁免；pivot只能按原合格事件发布。完整source前缀，不在展示起点重置。

## 2 状态与公式

持有结构以generation区分，`hold_active`与同代P保留V2语义。成熟许可另设恢复周期`recovery_cycle`、最新负event峰`R`、`up_after_R`、最新B三点基础。持有生命周期为OFF/HOLD_ONLY/START/CONFIRMED；当前输入未知的外显mode可UNKNOWN，memory不可直接授权。

每个原负event，无论HH/LH/等高、当前有无持仓结构：

```
recovery_cycle += 1
R <- 本负event刚确认的H（明确允许比旧R低；这是恢复门，不是保护P）
up_after_R <- False
B_base <- False；旧A/B成熟证据撤销
I_expand <- False（有效已知输入时）
hold_active且旧P未破：mode=HOLD_ONLY，I_hold=True，不发价格退出
```

此后原正event：建立/继续START并发一次`trial_event`；`up_after_R=True`。若持有结构未开则以新L建立新generation/P；若仍active则P只上抬。正event当天收盘已越恢复峰即可成熟确认，不要求再等一次cross，不回填低点发生日。

```
A_t = hold_active AND up_after_R AND R已在t前确认 AND compare(C_t,R)>0
B_base = 最新相邻L1-H12-L2有效 AND compare(L2,L1)>0
         AND L2.confirmed_at > 最近负event确认日
B_t = hold_active AND up_after_R AND B_base AND compare(C_t,H12)>0
I_expand = A OR B（三值逻辑；有效数据且未up_after_R时已知False）
I_hold = hold_active且当前C/P可比；P失效则False；当前C/源未知则UNKNOWN
```

无负event重置时，跌回恢复价门仅降START，P未破仍持有；后来再次站回同一门即可恢复，不需冷却或新正event。新的负event必须撤销此恢复许可，重新等待原正event。每次正event的试探是事件，不是每天可反复消费的试探bool；数量与费用本轮未定义。

### B的代数退化必须报告

原事件交替。在任意一次负event后、下一负event前，最新L1-H12-L2的H12就是R。故`B=True => A=True`；B是HL解释标签，不再是独立绕过R的恢复路径。输出逐日检验B真/A不真的行数，不能为保留双路径而偷偷另选高点或旧pair。

## 3 每个收盘的冲突顺序

1. 源段不可比：封存旧generation/P/旧退出责任，当前权限UNKNOWN；清本段不可比引用。新段的合法事件从其真实前缀重建，不跨单位max。缺C时不判突破/退出，不沿用CONF授权。
2. 先用C检查t-1旧P，`C<=P_old`则旧代support_exit并封存，不得用当日新低线遮掉。原退出事件不等于已成交。
3. 仅当前收盘登记本日原pivot一次。负event优先执行第2节撤成熟/冻结R；OFF只保存R，不凭高点打开持有结构。
4. 正event才建立/继续START与trial_event。OFF新建P=L；旧代active则`P_new=max(P_old,L)`。旧退出与新START同收盘分代同时保存，新START不能抹未成交旧退出。R独立于持仓代际，P破后仍保最新可比峰，不能丢掉旧峰而用较低未来峰任意恢复。
5. 本正event按最新相邻原低-高-低更新B；旧证书不复活。计算A/B三值OR。有效为真→CONFIRMED；为假且已有up_after_R→START；尚未新up→HOLD_ONLY。OFF无支撑不自动START。只有非CONF→CONF发confirm_event；CONF失许可时发撤权事件，不重复日发。
6. 没有pivot时仅用当时C与已知R/H12/P检查维持/跌回/恢复，不以未来峰、未来盈亏或原成交结果修订。

此稿按“下行之后先有新的原向上E0，才重新开放成熟确认”解释用户时序。若C先越R但原正event尚未发布，记录PRICE_ABOVE_R_BEFORE_UP，不提前授权；统计这种差异，不隐藏延迟。

## 4 真实逐日与恢复统计

输出4股每个展示日C/rawC、原event、原pivot发生/确认日、R来源、up_after_R、L1/H12/L2、P_old/P_new、A/B/I_hold/I_expand、trial/confirm/revoke/support_exit事件；旧I/G1/CP及原请求只作注释，不输入新状态。

每个负event给确认日、峰发生日/价、确认C、此前是否成熟、新正event日期/C、同恢复周期首个成熟日/C、恢复前参考被下一负event替换或样本结束的删失原因。R/recovery_cycle跨P退出保留，因此不能把P退出当恢复周期删失；P退出另列为持有generation事件。若只看原代持有到退出，标作holding-generation子区间而非cycle首恢复。天数用本股有效收盘观察数：当日撤权→下一有效收盘恢复=1（当日1个不可新增收盘）；另报区间内旧真实获资信号被撤的层号。

海能达单列全2024展示期与2024-09-19至11-27观察段、原持仓期间。所谓“正常回调/误降级”仅是事后诊断描述，不能作输入。须列所有down而不只选择后来迅速恢复者；未恢复须报告。太保924前后、盈新1/17→1/20→1/24→1/26、山东恢复/再次撤权为固定重点。对既定完整source做每股两次截断前缀一致性（共8），不另扫阈值。

本轮不重算新I下CP、不导入Account、不算候选买卖/现金/收益。原信号被撤只证明成熟许可变化；trial可用及新CP/资金路径未接，不能称原成交一定消失或收益改善。

## 5 可证伪与替代

若Sea持续上行期间每次down导致长时间无成熟新增/关键原请求被撤，直接报告时长及旧请求，不能按收益选择性撤down。本轮主V3不添加振幅门。独立纸面给振幅分级替代，只能使用当时已确认摆动与历史波动；阈值若有仅为明确待检假说，不依此样本调参，不运行替代账户或信号筛优。
