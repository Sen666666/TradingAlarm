# V12 恢复停止原因：已落盘结果交接

本次只读诊断已结束。没有修改冻结策略、参数、准入、认证门或旧封条，没有构建 Data、解 pickle、重放历史或重启。

## 已确认

- 导出已完成，RUN_STATUS.result=PREFIX_MISMATCH，source_hashes_verified=true，usable_bounded_result=false。
- 20日 raw 账截止2024-10-08，612单，NAV 1609921.8057109198675。认证仍只有19日，截止9/30，573单；最新可靠checkpoint仍是9/30。10/8是原atomic_step完成后前缀校验失败，并没有通过认证。
- 截至10/8，AVAILABILITY_EVENTS双方各10条，按完整JSON记录且保留重数的 Counter 完全相同。无新增、缺失或按(day,sid,event,ticket_id)配对后的字段改变。
- 唯一差异是全局零基下标7、8两条10/8 PAUSED_CLOSE_NO_PRICE_SIGNAL交换：原v1为000506.SZ、603268.SH，恢复输出为603268.SH、000506.SZ。JSON附件保留两端完整原记录和逐字段差异。
- 其余24个daily family截至10/8逐条有序完全相同，包含订单、日账、持仓、费用相关账项及4个资金family。4个资金family在父级最后停止进一步核查的消息到达之前已经随原比较完成。总数是25族，不是25个其他族。

## 确切原因与尚未覆盖部分

原M7 mainline_m7_cash_batch_design_v6/engine.py第72、88行已对该family用完整记录Counter。v2 prefix_check.py第42–47行却哈希有序日列表，因而这次互换触发拒绝。原PAUSED_CLOSE日志源在 mainline_candidate_v2_pending_quote_pause/engine.py第92–98行迭代paused集合；源码未规定跨股票顺序。没有捕获实际hash seed，不能冒称已证明具体种子。

不能据此宣布整次前缀通过。M12 state_fingerprint包含availability列表，该摘要进入CLOSE scratch.before/after，再进入book_id；下一OPEN decision引用book_id，自身scratch也包含availability。10/8已输出OPEN decision当前与原v1完全相同，但互换发生在其后的CLOSE。daily断言先失败，10/8 book检查尚未执行。最后停止指令后未流读book，实际book差异及次日传播均未验证。

若以后另获继续授权，下一位应先只读比对现有完整10/8 book的全部分支与摘要字段，确认经济字段和每条记录重数不变，再审窄范围、有版本的比较契约。仅改AVAIL比较不足以推定恢复可过；不可泛删hash、改源binding或自动续跑。当前不实施任何修正或后续实验。

## 文件

- V12_RECOVERY_20241008_SNAPSHOT_DIAGNOSIS.json：25族逐日hash、完整顺序差异、源码位置及输入hash。
- V12_RECOVERY_20241008_HANDOFF_DIAGNOSIS.json：最终交接结论、两端完整变位记录、完成状态与未认证范围。
- diagnose_recovery_20241008.py：仅落盘JSON比较脚本，不导入策略或运行历史。此次未调用其final模式，避免最后停止指令后重复核查。
