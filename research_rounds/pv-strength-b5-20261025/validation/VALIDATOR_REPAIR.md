# 验证器 v2：Parquet 日期表示修复

正式 `technical-run-v1` 已完整保留：182 项检查，166 通过，16 失败。失败全部发生在 `serialized_policy_replay` 对事实表的读取后 dtype 断言：冻结 B4 的 `object` 日期字符串列，经 pandas 3 / Parquet 读回成为 `StringDtype(na_value=nan)`。这 16 项在该断言处停止，不能声称其后政策重放已经执行通过。

v1 中原事件、旧 E0 全状态/ledger、冻结 B4 全列与日志、物理前缀、强度独立性、67 观察低点反例、12 个注入政策单测和两个来源重置派生均通过。`source_identity_before_after` 也通过。

本次只在独立 `code-validation-v2/` 修复验证保存/读取工具；不改 `code/` 生产实现、不改原 freeze、不改任何既有输入或 v1 结果。`test_contract.py` 从原验证器复制，生产模块仍从 `BASE/code` 加载。

`serialization.write_frame(frame, path)` 排他创建 Parquet 与 `.schema.json` sidecar。sidecar 登记原列顺序、dtype 和 object 列缺失值的 None / pandas.NA / NaT / NaN 表示；`read_frame(path)` 只凭这两份落盘文件恢复明确登记的 object 日期表示。其他 dtype 意外变化直接报错。浮点证据不转换、不舍入，所有证据、政策状态和 ledger 仍使用 `check_exact=True` 与 `check_dtype=True`。没有增加 `allclose` 或放宽字段比较。

原 20 个端到端合成、12 个明确注入政策单测、2 个固定重置派生均不变。v2 验证器及 sidecar 工具重新冻结后，输出到独立 `technical-run-v2`；账户、取数、阈值搜索均为 0。

真实来源验证器另有独立工具错误：`../results-v1/` 对 15 条来源、35,590 行、60 个物理前缀尝试形成 91 项检查，均因比较器 `astype(object).eq` 遇到 `pandas.NA` 抛出 `TypeError: boolean value of NA is ambiguous`。比较同一证据表与自身也能复现，所以不能把这批异常当作已发现 91 项算法不相等，也不能报告通过。逐项异常保留在 `../results-v1/differences.json`；v2 使用独立 `../results-v2/`。

真实验证器 v2 明确先比缺失位置；只有双方非缺失的单元格才使用原值 `==`，同位缺失视为相同。未引入容差；独立探针覆盖一个 binary64 ULP 的差异以及缺失位置迁移，均须检出。真实验证器原版、原失败和错误明细保留；修复只写入 `code-validation-v2/verify_real.py`。
