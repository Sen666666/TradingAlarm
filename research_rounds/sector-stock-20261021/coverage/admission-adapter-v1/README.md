# S1准入适配技术交付

状态：**43项合成边界测试通过，可进入数据桥接和执行集成；尚不能进入经济账户。** 新账户0次，趋势算法修改0次，未改正式仓库。

- `implementation-scope.json`：实现前冻结范围及正式来源哈希。
- `protocol.json`：技术协议及来源一致性复核。
- `INTERFACE.md`：输入/输出、最小语义解释和具体集成缺口。
- `verification.json`：最终43项技术验证收据及代码/测试身份。
- `independent-review.md`：独立发现、修复和复审边界。
- `test-attempt-01.txt`至`09.txt`：保留全部技术失败与后续结果。
- `sector_stock_admission.attempt-*.py`：关键失败及复审前版本，不覆盖证据。

实现：`../../code/sector_stock_admission.py`；测试：`../../code/test_sector_stock_admission.py`。从工作目录运行 `python3 -B research_rounds/sector-stock-20261021/code/test_sector_stock_admission.py` 只执行技术测试，不运行任何账户。
