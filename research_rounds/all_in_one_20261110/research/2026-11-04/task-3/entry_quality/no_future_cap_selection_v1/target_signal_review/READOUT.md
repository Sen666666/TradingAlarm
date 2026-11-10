# 六股跨七日目标信号补充独审

PASS_BOUNDED，无剩余执行阻碍。旧candidate/median独审目录未修改。

预定000620、300085、002583、300666、603061、301611×7日，42请求全部保存；38个精确目标bar计算出原纯stock信号，4个无目标bar不运行模型、不补信号。38点完成close及factor/amount等与此前封存canonical/PVR源字段逐bit核同；36点E0 ready，2点仍未ready，不能因有输出行就视为可用资格。

FREEZE中的原算法代码SHA、输入SHA、实际driver、6worker原JSONL/DONE与汇总逐项核同。driver每请求实际过滤symbol且trade_date<=t后才调用原stock_signal；保存prefix_end/max/last均不晚于请求日，present时等于当日。这里未另扫每个完整原prefix或重跑递推，只结合实际源代码过滤、输入身份和保存时钟核查。

三条2024-09-24旧值核对：银之杰300085对fixed35，盈新000620和海能达002583对PILOT；全部signal字段一致，浮点逐bit核同。TARGET42 JSON/parquet各signal字段及CSV close也一致。

stock_signal输入只有原OHLCV/segment，cap/currentroster不进模型。所有full_S0_eligibility_q仍None，scope明确不是订单授权。I_target、i_buy、grade及ready是原stock条件信号，不能替代完整行业/市场/H1/CP/法律或资金许可。未知或未ready不授执行。

qfq参考日期、因子vintage、历史published/received/available_at仍未PIT认证。<=trade_date只证计算输入前缀，不证明当时现场可取得或成交。此为六股小范围补全，不是5517全部合格候选，也不提供账户收益或规则有效性结论。本审计0新模型、0账户、0网络。

两条保存未ready请求：301611.SZ 2024-09-24、301611.SZ 2024-10-08。
