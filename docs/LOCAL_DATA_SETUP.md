# 本地数据与运行环境

GitHub仓库包含代码和研究文档。第三方市场数据、会话和账户只在用户本机保存，不由本仓库分发。

## 应用所需资料

应用启动首先读取 `TradingAlarm/data/market.json`。科技交易台还依赖以下原研究资料或等价、通过身份检查的本地发布：

- `research_rounds/tech-compound-design-20261026/proposed-pool.csv`；
- `research_rounds/tech-finite-compound-20261026/prepared-v2/`中的signals及h1.npz；
- `research_rounds/e0-reclaim-accounts-20261026/prepared/facts/`；
- `research_rounds/actual-risk-recovery-20261027/recovery.csv`；
- `research_rounds/tech-finite-compound-20261026/data/core-v3/manifest.json`及其中引用的权益资料；
- 原产品合同及 `SELECTED_STRATEGY.json`声明的冻结依赖。

本机已有更新时，`TradingAlarm/runtime/market/current.json`指向更新后的prepared目录；该指针和目标必须一起恢复，并核对路径、文件身份和源前缀。不要复制另一人的真实/模拟账户数据库作为新账户。

历史manifest保留原绝对路径。只改路径不等于原依赖仍然通过核验；完整复现须在单独版本中明确路径适配与身份验证。原本机完整研究归档仍是数据和完整账簿的来源，GitHub没有替代它。

## 会话及在线行情

默认保持 `TRADINGALARM_ENABLE_LIVE=0`。有本人合法客户端会话时，可参考 `docs/DATA_SOURCES.md`做独立本机设置。`TradingAlarm/settings.example.json`仅含离线默认值，复制为settings.json后仍需自己配置授权输入。仓库不含可用握手模板或签名，也不提供脱离客户端的独立登录续期。

应用没有券商委托接口。测试虚构账户必须使用 `/tmp` 中的专用运行目录，不能写入实际账户。
