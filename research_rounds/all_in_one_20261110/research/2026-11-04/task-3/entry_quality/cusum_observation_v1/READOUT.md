# 负 CUSUM：固定五股观测

仅全 source 前缀纯价格/原 I 周期观测。五股为000620、002583、300085、603061、300623，源统一截至2026-06-30。原 E0/I/CP 模型、Account、卖单均未执行。

r=ln(C/Cprev)；s=1.4826×过去63个连续有效 r 的绝对值中位数（不含当 r）；D=max(0,Dprev−r/s−0.25)，h=3只作level及cross观测。1e-8为log单位数值guard，不是经济最优参数，不赋予工业过程误报率或股票尾部概率含义。

有效收盘沿既有engine.close_valid严格flags与source同域，不需要H/L。显式invalid/unknown或source改变断连续return窗口，不能跳过凑63；原日历整行缺失未全面核证。scale独立于I周期，CP收据不复位D。原I=0→1或已观察新source且native同源确认I=1才启动D0，启动close不纳r；源首个I1若无证据则leftcensored。结束I0 close可记录旧D，不新增active warning。任何周期必要输入未知后该周期D保持UNKNOWN，至下一有证据新I周期才可重新D0。

|原锚|本I周期首cross|Dprev→D|原CP退出|预警后的下一raw OPEN参考|
|---|---|---|---|---|
|盈新2022-01-07|2022-01-18|1.773261→4.431723|2022-01-19|1/19 3.08|
|海能达2024-09-20|2024-11-04|2.279091→4.489155|2024-11-04|11/5 23.00|
|银之杰2024-09-12|2024-10-10|0→7.041030|2024-10-10|10/11 30.21|
|银之杰失败锚2024-10-09|2024-10-10|0→7.041030|2024-10-10|10/11 30.21|

盈新1/18原C=3.28、旧CP线同日raw参考3.259284未破；CUSUM首cross在原1/17 E0down之后、CP退出前1观察。海/银首次cross已经是原旧CP穿线日，并不提前；不能称避免其原亏损。

CP每日旧线是对原缓存P0/Ifloor/CPcandidate的只读展开，先检旧P再更新proposal，4锚退出日及线逐值等于既有savedCP；不是重算CP公式，也不是原实际持仓。原CP退出后CUSUM仍可观察，oldP不再冒充live。

全前缀五股12600行。海106/银100行D UNKNOWN均保留；本五股没有leftcensored或low-scale-guard实际行，相关边界是源码规则，不能称本样本已实测覆盖。原缺行情不恢复、下一OPEN仅参考，执行真实性未知。没有构造新收益或卖出策略。

主表：run_v1/*_CUSUM_DAILY.parquet。三case及失败锚：*_CP_CUSUM.json。FIRST_CROSS_CASE_FACTS.json为递推输出上的单步算术核对与报价旁注，未冒充独立完整状态重跑。RUN_RECEIPT.json绑定原源及脚本。
