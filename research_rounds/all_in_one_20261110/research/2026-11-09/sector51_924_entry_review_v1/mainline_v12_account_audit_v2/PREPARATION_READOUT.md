# M12 v2 独立后审准备

状态：**PREPARED_SYNTHETIC_ONLY，未审新真实实验，未判候选最终准入PASS。**

新目录 mainline_v12_account_audit_v2。原 mainline_v12_account_audit_v1 主报告、69个封存文件及保护线附录未修改。只读取已经生成的合成gzip及当前源码文本，没有导入候选引擎/Data，没有history，没有联网，没有解任何pickle。

## 已准备和验证
- compression_integrity.py：先核压缩SHA/字节数与OUTPUT_HASHES绑定，再分块解压核JSON原字节SHA/长度；拒绝损坏、截断、内外hash或长度不符。无损声明不是证明，合成数据另与reference_export原JSON逐字节hash对照。
- stream_branch_books.py：支持普通JSON或gzip文本，仍每次只保留一个完整branch；完整branch哈希与完整book哈希的口径不变。
- audit_streamed_branches.py：复用v1已验证的原D/K/U/X/T、bar_q、身份、固定退让、逐lot y/逐ADD-EVENT q、共同OPEN前缀、原预检、WAIT身份预算、CP/EVENT单次消费和实际偏离解释；候选目录与输出目录显式传入，不再硬编码22日或Jan20。
- prefix_independent.py：从保存输出逐日比较v1的25类经济/选择日志，每个branch全部字段做hash。只在10/10的book元数据允许移除book_id及scratch_integrity.before/after，两边仍要求before==after且passed=True；未知顶层字段不能被忽略。此前所有book完整相等。
- accounting_core.py：独立费用、现金、权益、整手、T+1、库存、持仓、NAV和逐轮PnL算术不改，基准唯一为原M7。
- analyze_saved_paths.py：按实际认证日生成固定1677身份及cohort结果、动态现金事件总核验、角色不可变、每日现金/融资/原D/ADD支出。11/6锚定只有达到该日才启用；同时区分旧轮后续增量与新轮实际损益。
- 三只股票：水井坊、银之杰、常山北明的原9/23身份，逐日收盘净清算PnL/MFE、逐lot保护价、10/10锁定层后续真实卖单、截止仍未平或真实已平结果。日内MFE、保证按保护价成交、虚构每lot分摊收益均不计算。
- checkpoint_metadata.py：只核外部receipt SHA、COMMIT状态/认证日、binding、代码/数据manifest、opaque STATE字节hash/长度及来源范围。即使STATE不是合法gzip/pickle也不反序列化，以测试证明只做字节审计。

## 合成准备结果
PREPARATION_QA.json 为 PASS_PREPARATION_SYNTHETIC_ONLY，28项断言。合成gzip/原文book descriptor一致；损坏gzip、内外SHA错误、长度错误、旧前缀任一经济字段改变、未知book字段、无可信receipt、认证日越界和STATE字节修改均被拒绝。支持2日部分认证frontier的单元测试通过。

此结果不是新真实账务、策略收益、最终源码冻结或PIT认证。来源中的engine hash只是准备时观察值，不替代独立最终封存。

## 真实实验结束后的入口
必须等父级明确下发已结束的实际结果，再调用：
python -B mainline_v12_account_audit_v2/audit_saved_outputs.py --audit-saved-output --candidate mainline_candidate_v12_winner_funding_cash_688200_v2/once_20250120 --run-status mainline_candidate_v12_winner_funding_cash_688200_v2/RUN_STATUS.json --output mainline_v12_account_audit_v2/actual_<新的唯一名称>

入口只读保存结果，绝不启动、恢复或延长history。COMPLETED要求93日到2025-01-20；ATOMIC_BLOCK或CHECKPOINT_STOP可审最后已认证日，但不得把缺失未来窗口当成完成。RUNTIME_ERROR或PREFIX_MISMATCH拒绝经济认证。
先交小文件账户/cohort/MFE结果，再流式审大book，避免全分支耗时阻住有用经济结论。

## 精确新增688200边界
原准入集合必须逐行保留，只新增688200.SH / 2024-10-11 / 688200.SH|LOCAL_DISTRIBUTION_007；10/10登记持仓必须0，10/11只许原生零数量FACTOR_BRIDGE，现金/应收都为0。其后新的实际交易不预设与v1相同，应据真实输出审计。不能把新增公告误当策略改变或倒改v1阻断结果。
完整期现金检查应动态数已准入有效事件，不再硬编码v1的534项。若原267事件加一个精确事件完整生效，预计原M7 267项、M12 268项，总535项；这是事件数预期，必须以实际清单验证。

## 仍需最终实际证据，不提前PASS
1. 新EXPERIMENT_APPROVAL、FROZEN_INPUTS、SOURCE_HASHES及独立接口审查最终hash尚需在实际审计时绑定。入口要求独审 PASS_V12_CASH688200_CONTINUATION_INTERFACE 且无remaining_blockers，source_manifest_sha一致。
2. 保存的全期final TICKET_STATE不等于历史10/10 final state。独立逐日25类日志和完整books可比；历史内存的active/archive/CP别名、pending共享和完整缓存恢复，由独立checkpoint/runner源码与合成连续性测试作单独证据。此审计不解pickle，不能声称独立重建了那份完整内存状态。
3. 仅以原始保存q/y或H自报不能证明选择信息来源无未来。沿用独审静态相位/poison测试绑定，原全日OHLC no_fill与非PIT源限制不消失。
4. 原固定19组来自原M7完整Jan20已闭合正轮的后验前10%标签，不能用于入场选择，不能称样本外；未到达的光伏/晚期身份不得算漏票或零收益。
