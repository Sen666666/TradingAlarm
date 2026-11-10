# 2026-01-15 成交额历史分位

5517 个证券请求全部保留。完整252个此前有效同源观察：5333；缺少目标日：66；此前同一有效块不足252：118。

分位为 `(# prior amount < current + 0.5 × # prior amount == current) / 252`，不含当日，使用原成交额单位；前252个有效个股观察不等于252个市场会话。不足完整窗口保持UNKNOWN，不设阈值。`amount_history252_percentile` 为主合并列，另保原 `amount_hist252_percentile`。

current amount和prior20与已保存原特征逐值exact；4只预定股的253条original raw金额及日期与canonical逐值exact，并以整数计数/有理数独立核分位。

canonical必要列仅一次读取；每个目标函数输入在计算前物理截断到本日。0次新增PVR/E0/I/G1、账户、排序或阈值计算；此阶段未读取/计算未来路径，未按未来选择母体。历史身份、ST、停牌、涨跌幅及可交易性保持未认证未知。

主文件：`AMOUNT252_2026_01_15.parquet`；SHA256 `8d8075399e7f8573387d4b3445781030c3a901ac5e033db7be616b26df0cc080`。输入SHA、时钟、逐例和计时见 `COMPLETION.json`。
