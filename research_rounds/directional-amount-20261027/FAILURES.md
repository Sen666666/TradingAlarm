# 保留失败

- 初始只读数据扫描：直接对含None的synthetic_event_bar列取反，TypeError。未写行情、未运行算法或账户；改用已冻结eligible_prices解析，保留这一技术失败，不当作经济尝试。

- 报告首次导出在403股后因4只北交所股票展示名称为NaN，严格JSON拒绝输出。失败目录report-v1-failed保留；改用已有账户元数据名称/代码作为展示回退，重建报告。价格、算法、全部账户和收益不变，非经济重跑。

报告第二次输出的提示框换行被Python解释为JavaScript字符串内换行，脚本未执行。保留report/index-v2-failed.html；仅修复HTML及生成器的转义，不改变算法或经济结果。
