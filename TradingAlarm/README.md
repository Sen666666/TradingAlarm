# TradingAlarm 科技交易台

从本地行情工作台升级为ACT20_BREAK日常交易辅助平台。首页为科技交易台，旧行情探索在 `/quotes`。

双击 `start.command`，或从仓库根目录执行：

```sh
TradingAlarm/research/.venv/bin/python TradingAlarm/server.py
```

打开 http://127.0.0.1:8765 。新代码需要 pandas/numpy/pyarrow（已有 research/.venv 可用，另见 requirements.txt）。正式账户首次使用时录入实际可用资金，从空仓开始；不会继承历史回测资金或暂停状态。真实成交账本位于本机 `TradingAlarm/runtime/account.sqlite3`，该目录不会提交Git。

当前已接入407科技股/11行业，K线、成交金额/股数、结构支持与I事件；实际成交输入驱动持仓成本、现金和T+1。收盘指引复用冻结ACT20_BREAK，20%阶段暂停及63观察恢复条件不变。1799序列用于RS-H1参照。

运行服务时每日16:10触发增量更新，可在页面关闭定时或手动更新；服务未运行/电脑睡眠不会更新，重开服务会检查当日任务。行情与权益来自已授权同花顺9602/9603节点；会话过期须在本人官方客户端更新。数据发布要求通过前缀/完整性检查，失败保留旧资料。

DESK-ACT20-1已完成本机验收：26项新增测试和16项原有测试通过；完整信号、风险状态、选择预算及增量发布核验见 `acceptance.json` 和 `../docs/TRADING_DESK_BUILD.md`。券商委托仍由用户执行。

测试：

```sh
TradingAlarm/research/.venv/bin/python -m unittest discover -s TradingAlarm/tests -v
TradingAlarm/research/.venv/bin/python TradingAlarm/verify_desk.py
```

隔离界面测试使用 `TRADINGALARM_TEST_MODE=1 TRADINGALARM_RUNTIME=/tmp/专用目录`；页面会明确显示测试环境。虚构测试资金和成交不得写入正式数据库。

---

以下是旧版行情探索的历史说明，当前启动方式以上方为准。

# TradingAlarm

本机行情工作台：在线股票搜索、自选收藏、分时价格与分钟成交量、日/周/月 K、MA5/10/20、历史明细、CSV 导出。Python 标准库后端与无第三方依赖的 Canvas 前端。

## 启动

```sh
cd TradingAlarm
python3 server.py
```

访问 http://127.0.0.1:8765 。也可双击 `start.command`。Python 3.10+；无需 npm install。端口冲突可使用 `python3 server.py --port 8766`。Ctrl+C 停止。

已于 2026-10-17 获得用户授权并在 `settings.json` 启用在线适配器。启动时先展示本地采集数据；点击刷新或选中在线搜索结果时查询行情。数据来自 2026-10-16 的本人客户端抓包，不能当作当前实时行情。初始采集目录含 1,143 个标的。在线搜索已接入，不再受该目录限制；新增标的会保存在 `data/discovered.json`，沪深标的选中后自动查询行情。

## 使用

- 输入中文名称、代码或拼音缩写进行在线搜索。`/` 聚焦搜索框。
- 星标管理自选，保存于当前浏览器 localStorage。
- 分时显示实际分钟价格；分钟成交量由累计成交量作差，缺失保持为空。
- K 线支持近 30/90 根、全部、Ctrl/Command + 滚轮缩放及拖动平移。
- 历史明细按日期倒序分页；CSV 导出当前周期全部已加载记录。
- 周/月 K 由已有日 K 聚合，边界周期可能不完整。复权参数 Q 的具体口径未交叉验证。
- 提醒功能不在本版本中。

## 在线适配器与会话接续

当前已启用。可以用环境变量覆盖配置：

```sh
TRADINGALARM_ENABLE_LIVE=0 python3 server.py  # 临时关闭在线模式
```

启用后点击“刷新”读取所选标的报价、分时及最多约 750 根日 K；同一标的 60 秒内复用结果。勾选“每分钟刷新当前标的”后，仅页面可见时查询，不在后台常驻轮询。自动刷新默认不勾选，刷新页面会关闭。

会话来自本人同花顺 Preferences 中的 `HXPassport`、`HXSignature`。每次会话检查重新读取文件，按原客户端算法在内存中组装已有签名，识别票据内容变更；不读取密码、不修改原 App、不生成签名、不延长服务端有效期。原捕获文件只提供协议版本与设备信息模板，若原 App 切换账号会拒绝混用，需更新对应模板。

当前节点 `119.3.43.91:9602`，模板为相邻研究目录的 `handshake/stream-9-client.bin`。配置可用 `TRADINGALARM_HANDSHAKE`、`TRADINGALARM_HOST`、`TRADINGALARM_PORT`；节点变更应核实目标及授权。`TRADINGALARM_SESSION_SOURCE=capture` 可显式回退到捕获文件票据，默认读取同花顺最新偏好文件。

已于 2026-10-17 在线验证重建票据，取得 688008 的报价、241 个分时点和 750 根日 K；也已通过浏览器应用刷新。详情见 `online-verification.json`。

到期依据是 `signvalid`，按本机上海时区解释；握手需要明确 `Reply=login` 和 `VerifyCode=0` 才继续查询。网络错误采用 30/60/120/240/480/900 秒退避；明确鉴权拒绝后停止请求，直到票据内容改变。缓存跟随票据代次失效，不向浏览器返回会话内容。

**接续依赖同花顺正常登录并保存新票据。** 原客户端票据到期会重新登录，并未发现单独的 refresh_token 交换。TradingAlarm 自动跟随更新，尚不能脱离同花顺独立登录续期。提前撤销、长期运行、节点失效等行为还需实际观察。支持当前目录中的沪深标的；不要将本机研究服务暴露到公网。

## 数据与验证

```sh
python3 build_data.py           # 离线重建脱敏行情数据
python3 -m unittest -v test_market.py
node --check static/app.js
```

`data/market.json` 是纯行情，不包含登录验证包。默认浏览模式可单独使用该 JSON。重建和在线解码需要相邻 `artifacts/ths-analysis-20261016/deep` 中的研究解码器；当前 HX RLE 解码器为有限 ARM 指令解释原型，产品化应替换为独立实现并加强输入校验。

抓包存在未支持的响应格式，构建器在 `decodeSkipped` 记录跳过数量；没有补造缺失行情。K 线按市场/股票/日期去重。报价、分时和历史来自不同时刻的请求，快照时间可能不同；图表单独标明覆盖范围。

## 在线搜索

已获用户授权，使用原客户端搜索节点 `8.134.69.102:9605`，只读查询股票名称、代码、市场。协议为 `id=8`，输入按客户端规则转大写、GB18030 编码。已验证中文“贵州茅台”“建设银行”、拼音“jsyh”、代码“601939”和无匹配查询。

搜索输入防抖 400 ms；同一会话代次的同一关键词缓存 5 分钟；过时请求结果不会覆盖新的关键词。失败会提示并保留本地匹配结果。新搜索到的标的会写入不含凭据的 `data/discovered.json`。搜索结果可涵盖其他市场，但现有行情连接只支持沪深市场，其余标记“仅搜索”。服务端可能截断或模糊匹配，不保证一次查询枚举全市场。

原客户端静态与抓包证据见 `../artifacts/ths-analysis-20261016/deep/search-protocol-static.json`。原先已获授权的会话生命周期保护同样用于搜索，不输出凭据。
