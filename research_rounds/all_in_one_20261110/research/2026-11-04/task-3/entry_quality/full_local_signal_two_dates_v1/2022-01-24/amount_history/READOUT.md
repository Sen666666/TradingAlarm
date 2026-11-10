# 2022-01-24 成交额历史分位

5517 个证券请求全部保留。完整252个此前有效同源观察：3984；缺少目标日：999；此前同一有效块不足252：534。

分位为 `(# prior amount < current + 0.5 × # prior amount == current) / 252`，不含当日，使用原成交额单位；前252个有效个股观察不等于252个市场会话。不足完整窗口保持UNKNOWN，不设阈值。`amount_history252_percentile` 为主合并列，另保原 `amount_hist252_percentile`。

current amount和prior20与已保存原特征逐值exact；4只预定股的253条original raw金额及日期与canonical逐值exact，并以整数计数/有理数独立核分位。

canonical必要列仅一次读取；每个目标函数输入在计算前物理截断到本日。0次新增PVR/E0/I/G1、账户、排序或阈值计算；此阶段未读取/计算未来路径，未按未来选择母体。历史身份、ST、停牌、涨跌幅及可交易性保持未认证未知。

主文件：`AMOUNT252_2022_01_24.parquet`；SHA256 `5d136282b5d598dca8320f88f5e553ae6f8f0639d8630d3680d92a609c0f552a`。输入SHA、时钟、逐例和计时见 `COMPLETION.json`。
