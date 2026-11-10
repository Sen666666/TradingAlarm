# 权益适配接桥只读复核

2026-10-23。范围：`code/action_normalize.py`与`current_pool_bridge.py`字段/边界连接；未联网、未运行账户，也不认证全池权益完整。

归一现金每股、原币、拆合ratio和逐事件来源可直接接桥。A每十股与HK每股明确区分；外币不混入报价币，实物分派/供股/可选现金留unresolved，不发明支付/可卖日期。根status=needs_review保留，不能由parser自行升级成signal或ledger ready。

首轮审查提出三个实际接口问题，已只读确认修复：稳定security_id与native source_symbol分开并显式market；原点当日权益留unresolved，不能绕过信号原点规则；A未知条款仍保留已独立验证的事件日期，从而正确区分真正源起点之前的记录。

最终合并历史后必须按真实合并origin重新规范；当前pilot腾讯只有2023起尾部，不能由该pilot的窗外记录数声称2013–2023无权益问题。当前没有阻塞性的schema差异；这不表示未解析事件和来源覆盖已经解决。

被复核代码SHA256：`d8e6085722b315caa07d66b36df7783bb2a31db95b1e95c9ada8b231f39b5dbf`。
