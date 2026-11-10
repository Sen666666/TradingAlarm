1.5倍全部费用与滑点：最小进程内适配

接口
  import cost_stress as CST
  cost_metadata = CST.apply_cost_stress(V)  # 新进程，仅一次；构造runner前
  shared,receipts,cp,states,ir,identity = V.inputs(window)
  r = original_factory_class(shared,receipts,stock_cp=cp,
          industry_states=states,industry_receipts=ir)
  CST.configure_runner(r)                  # 第一事件前，原空账户
  r.source_freeze.update(cost_metadata['source_freeze'])
  RUN_METADATA明确保存cost_metadata；执行前后CST.assert_cost_stress_runner(r)。

费用
原真正被运行的FeeSchedule是sector_account.FeeSchedule，不是另一个同名
TradingAlarm.desk.execution.FeeSchedule。它的incremental硬限1/2，不能直接
塞1.5。新模块仅对1.5特判：每分项rate/minimum/maximum/rounding_quantum
一起乘1.5，用原incremental与rate_accrual以multiplier=1计算。paid与accrued
一直以真实scaled域留在原订单，不重置。对固定成交额/partial序列，每个
费用分项严格为原来的1.5倍，最低佣金5→7.5；原order/fill、shares/par_value、
side、累计最低额、cap、round语义不变。原multiplier1或2调用原函数。
schedule_id保留原收费版本身份，压力倍率另以账户cost_multiplier、新模块
VERSION和SHA记录，不能把它说成原收费制度历史上就是1.5倍。

滑点
原joint_v3.opening固定传market.window(...,1)，而FastMarket仅对2倍压力
调整滑点。新进程中wrapper先调用原window(...,1)，包括原慢/快一致检查、
source可用、量/价格/交易资格、平盘、T+1、容量、费用版本、清算与所有
None拒绝；仅对其返回的FillWindow替换execution_price为rawOPEN×(1±.00075)。
原协议slippage_bps必须确为5且stress_slippage=true，否则报错。

资金反馈
构造后配置原a.cost_multiplier=Decimal('1.5')，调用原C.activate同步CURRENT
及LR.SLIP=.00075。原planning/opening每次继续activate。原CORE保护风险、
参考价、preview、route、预留、真实_fee、partial费用记忆、结算及ACT反馈
因此承受同一压力。未改原opening/route/Account/settlement或市场原始数据。
这是完整账户输入压力，不是沿原成交簿事后扣费用。

冻结与checkpoint
进程内patched类方法不存为实例闭包；原checkpoint序列化账户cost_multiplier
及runner的cost_stress_version/multiplier，原会计类身份不变。运行metadata和
source_freeze必须包含本模块SHA以及被调用原函数源SHA。恢复只能在新进程
先应用同一模块、同一freeze，再恢复自身压力账；不能导入基线/旧账户状态。
CHECKS.json内空账checkpoint标记last_completed_event=None，明确无金融事件，
仅技术序列化/restore，不冒充真实历史重启验证。独立prefix/完整账审查另行。

文件
cost_stress.py是适配代码；check_cost_stress.py执行真实源query/原费用分项/
partial累计/CORE预估与实际_fee/空账checkpoint检查；CHECKS.json保存运行结果。
本适配目录不构建完整账户、不修改任何旧封版源或原始候选。
