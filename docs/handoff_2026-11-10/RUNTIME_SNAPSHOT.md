# M12 运行状态快照

采样UTC：2026-11-10T03:56:06.325677+00:00。此页为动态事实的保存快照，后续以原日志和LATEST为准。

- 原目录：/Users/bytedance/Documents/Codex/2026-11-09/sector51_924_entry_review_v1/mainline_candidate_v12_winner_funding_cash_688200_v2
- PID：46341。进程查询返回码：0。原始查询输出见 RUNTIME_SNAPSHOT.json。
- 最近认证日：**2024-09-30**；COMMIT和receipt/state SHA已保存。
- 最新DAY日志：`DAY 2024-09-30 {"orders": 573, "NAV": "1487366.1552308087935", "stocks": 67, "branches": 305, "prefix_days_checked": 19}`
- 顶层RUN_STATUS存在：False；once_20250120/RUN_STATUS存在：False。缺最终状态时不能写成完成。
- 当前冻结输入 9108 个，路径缺失 0 个；本次只核存在性，未把旧manifest SHA说成重新hash全量数据。

本次只读进程、日志、JSON和文件信息，未加载pickle、未执行策略步、未停止或重复运行。当前仍是已准入同一M12 v2账户恢复，不是新实验。先前M12 v1仅有22日到2024-10-10；此次目标到2025-01-20共93日，目标不是完成凭证。

## 恢复及后审边界

恢复起点为9/25认证状态，续跑从9/26，止1/20；严格同manifest、精确9108输入绑定、原22日prefix门不变。不要删除RUN_STARTED或RECOVERY_STARTED，不要重复启动run或recover。最终后审目录 mainline_v12_account_audit_v2 此前只有 PREPARED_SYNTHETIC_ONLY，应等待真实输出后独立审核，不能把合成28项通过当经济PASS。

运行详情与独立贡献在 contributions/m12_runtime/，其封条和复制manifest单列保留。该贡献与本页时间可能不同，不以较早采样覆盖较晚日志。
