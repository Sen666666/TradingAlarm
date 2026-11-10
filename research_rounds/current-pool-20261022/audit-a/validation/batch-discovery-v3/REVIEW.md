# 有限历史批次发现修复

旧代码只扫描 downloads 直接子目录的 protocol.json，不能看到 queue/batches/批次，因此会漏掉实际队列历史来源。旧文件、哈希与修复范围保存在 prior/ 和 scope.json。

修复只发现根目录、直接子目录及 child/batches/*（也支持直接传 queue 根）；接受 schema_version=1 且每项具备历史请求形状、9602/9603 节点与 tail/full 模式的协议。快照协议不会进入历史源。不会改 collector、重启请求或运行账户。

真实只读核验时，旧路径有 7 个直接协议目录；新路径发现 53 个合规 history 协议目录，其中当时 queue-state 已完成的 9 个港股批次全部被包含。53 包含正在执行或仅已准备协议的批次，不能称已完成。详见 real-completed-queue-discovery.json，包含读取时 queue hash 与路径。尚未运行全池 finalize。

同一证券的输入顺序按 full 优先、请求起点更早优先、请求终点更晚优先；不按收益或价格挑选。完整源可覆盖的旧无重叠/空来源失败保留原文并记 resolved_by_independent_complete_source；数值冲突、哈希、身份或路径完整性失败永不自动消解。短 pilot 无权消解全史缺口。A head 每条 1 页只验证供应商边界，空首请求仍为边界未证；没有自动重试。供应商首日从不等同 IPO/BSE 挂牌日。

A/H 每个 manifest 行均带完整 master_record；输出复制全量 master-input.csv，协议明确 master_total/selected，空行情证券仍有行。HK 币种标签注明 current_HKEX_snapshot、historical_currency_certified=false。

28 项技术测试通过（test-attempt-03.txt）。第一次失败仅为 macOS /var 与 /private/var 的测试期望路径未 resolve，原失败保留；没有放宽发现条件或数据校验。test-attempt-02 同为 28 项通过，之后仅补 master 字段和 HK 币种来源说明后再验。未运行网络、账户或全池归并。
