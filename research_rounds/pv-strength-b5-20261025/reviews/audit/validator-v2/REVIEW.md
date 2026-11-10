# v2 验证器修复独立审查

结论：**本有限审查通过，可按收据中的三个 v2 源码哈希冻结并执行正式兼容验收。** 本次没有调用 B5 模型或账户；只测试比较器及序列化的技术行为，不提前宣称完整真实历史已兼容。

[独立脚本](audit_validator.py)与[23/23 项收据](run-v1/receipt.json)保存了实际受审源码哈希；对应源码副本保存于该运行目录。原 v1 代码、原 77 文件冻结和此前失败收据均保留。审查运行前后 v2 源码没有变化，原 77 文件与 freeze 全部一致。

父 agent 随后创建 `freeze-validation-v2.json`；[冻结身份补审](frozen-identity.json)确认三个受审 v2 源码的审计哈希、正式冻结哈希和当前磁盘哈希三者完全相同。

v2 `Checks.frame` 先比较缺失 mask，再仅对双方均非缺失的值做原始精确等值比较，从而避免 pandas 3 将 `pd.NA` 转 object 后 `.eq` 触发的异常。独立注入 1 ULP 的 floor 差异、float/nullable Int64/object 缺失位置变化、不同字符串、dtype/index/列序变化，真实比较器和 technical `assert_frame_equal(check_exact=True)` 均检出。相同含缺失表正常通过。未使用 `allclose`、舍入或改写支持值。

序列化 sidecar 仅含列顺序、行数、dtype 与 object 列各类缺失的坐标。读取时只允许已声明 object 列恢复 object dtype，并先要求当前 Parquet 的 object 缺失 mask 与声明 mask 完全一致，再恢复 None/pd.NA/NaT/nan 的表示。原非空值没有放入 sidecar，浮点列不 cast、不从原表回填。

审计额外修改自己生成的 Parquet 文件：将 floor 增加 1 ULP、移动 float 缺失、修改非空日期，读取后变化仍保留，精确比较均失败；把原 object 缺失改为非空值、或把原非空值改为缺失，读取直接拒绝，没有把被改内容覆盖掉。非声明浮点 dtype 变化与重复缺失坐标也被拒绝。正常往返的 float64 位模式完全相同。

该审查只认可技术修复及其不放宽精确性的性质。v1 中的比较器异常不能说明原数值已经相同；正式 v2 仍须实际重跑固定技术矩阵及真实历史并完整保存差异，再决定兼容结论。
