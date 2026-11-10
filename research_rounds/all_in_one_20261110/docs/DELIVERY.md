# 整理完成与验收

归档根：`/Users/bytedance/Documents/ChatGPT/money/research_rounds/all_in_one_20261110`

## 实际交付

- **685,923份普通研究文件 + 255条项目内部相对链接**，共686,178条有效归档记录。
- 研究payload **374,971,218,952字节，约349.22GiB（374.97GB）**。额外入口、清单与收据不计入该payload数字。
- 主工程副本约44.24GiB；五个日期外部研究及两份历史行情依赖完整纳入指定范围。组别明细见 `manifest/ARCHIVE_RECEIPT.json`。
- APFS独立克隆初始磁盘增量小；从开始到交付观察可用空间变化约 **837.4MiB**，剩余约 **46.38GiB**。这包含同期系统活动，不是独占归因；异盘复制需按完整逻辑容量规划。
- 原目录未移动、未删除、未覆盖。新增主工程入口为 `money/ALL_IN_ONE_2026-11-10.md`。

## 已通过

1. 全686,178条归档记录：存在、大小、内部链接检查无错误；原生clone成功、独立inode及复制时源稳定性已记录。
2. 17,036份文档/源码文件：源与副本SHA匹配，交付前按清单再次核对。
3. 当前M12 **9,108/9,108个冻结输入SHA匹配**，总859,282,876字节；全部从新项目内部读取，未以旧路径仍存在充数。
4. 255条归档链接全部只指向新项目内部；补入一份历史Swift工具源码。2条node_modules、1条pyarrow安装链接明确排除，不伪装成已搬迁的环境。
5. 只读CLI搬到另一个根并从 `/` 运行，status和resolve通过；未导入研究引擎。11/06同级顶层 `cp_sequential_full1709_v1.py` 已实际纳入。

## 保留的已知历史失败

AST检查1,473个Python文件，1,472通过；1份历史失败尝试 `append_seed_equivalent_check.py:27` 有未闭合括号。原目录和归档SHA一致，原 `SUPPLEMENT_TECHNICAL_FAILURES.json` 已明确记载此失败，后续 `append_seed_equivalent_check_v2.py` 已存在且本次AST通过。保留旧失败是证据完整性要求，不是迁移引入的问题；未改旧代码。

## 校验范围不混淆

大文件没有逐一全部重新计算SHA；全目录验证依赖APFS clone成功、字节大小、独立inode与源稳定性记录，当前冻结输入另做全量SHA。没有安装/运行旧依赖，没有执行合成或历史经济回测，没有宣称所有旧脚本可直接跨机器运行。

最新实际环境与旧requirements不同，见 [环境取证](ENVIRONMENT.md)。M12认证仍止2024-09-30且结果不可用，见 [当前状态](CURRENT_STATUS.md)。

## 去重发现

在已重算SHA的文档/源码范围内发现 **6,275组**相同内容，首份之外 **8,417份**、逻辑约 **62.52MiB**。不是所有大数据的完整去重，也不是可回收磁盘量；此次不删除任何重复证据。明细和最大30组见 `manifest/DUPLICATE_REPORT.json`。

## 核验收据

- `manifest/FINAL_DELIVERY.json`：最终交付摘要。
- `manifest/FILES.csv`、`SUPPLEMENTAL_FILES.csv`：完整逐文件记录。
- `manifest/ARCHIVE_VALIDATION.json`、`CURRENT_INPUT_VERIFICATION.json`：独立校验。
- `manifest/EXCLUDED.csv`、`ENVIRONMENT_LINK_RESOLUTION.json`：明确排除项。
- `manifest/KNOWN_HISTORICAL_FAILURE.json`：已有失败与v2替代证据。
- `manifest/PORTABLE_SMOKE_TEST.json`：只读工具异根验收。

明确识别的私有目录、settings、账户数据库和运行环境已排除；没有做全档案秘密扫描，仍只限本地私有研究，不是可直接对外发布包。
