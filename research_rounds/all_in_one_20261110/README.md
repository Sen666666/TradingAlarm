> GitHub源码/文档视图：本文的完整文件数、行情与大账簿校验描述原本地归档；这些大数据没有随GitHub发布。请先读[发布范围](../../docs/GITHUB_PUBLICATION.md)。

# 量价趋势研究 · All in one

这是独立的本地研究归档项目，内含主工程研究资料、10/29—11/10外置研究树、行情/特征、大型账簿、公式、源代码、失败记录与核验入口。不是只索引原目录，也不是软链接到旧研究树。原目录完全保留。

## 从这里开始

1. [成果总导航](docs/INDEX.md)：按研究日期及主题阅读。
2. [最新研究状态与边界](docs/CURRENT_STATUS.md)：M12 v2因前缀不一致终止，认证仅到2024-09-30，不能把导出20日当认证20日。
3. [本次整理与核验](docs/DELIVERY.md)：实际文件数、逻辑大小、空间变化和校验范围。
4. [目录与流程优化](docs/OPTIMIZATION.md)：已做改进、留待另立版本的工程改造。
5. [复现与迁移边界](docs/REPRODUCIBILITY.md)：当前可离开原目录运行的只读工具，与旧研究执行器的区别。

## 目录

- `project/`：原 money 主工程的研究代码、文档、数据和旧成果。内部原相对目录保留。
- `research/2026-10-29/`：完整早期外置研究及事实数据，不仅当前M12小清单。
- `research/2026-11-01/`：账户/状态研究。
- `research/2026-11-04/`：四条研究与轻量研究流程。
- `research/2026-11-06/`：入场/状态/广度、CP与执行诊断。
- `research/2026-11-09/`：51分类、M1—M12、独立审计和阻断记录。
- `historical_dependencies/`：历史诊断依赖的两份 my-quant 行情/涨跌停资料。
- `tools/`：只读导航、归档检查和输入哈希核验；不导入、不启动研究引擎。
- `manifest/`：复制清单、来源映射、排除项、验收、去重统计和原文件身份。
- `docs/`：新的统一入口和整理说明。

## 路径配置（已落地）

默认从工具自身位置找归档根，不依赖当前终端目录或本机用户名。搬动整个目录后直接运行即可；也可用 `--project-root` 显式选择，或设置 `RESEARCH_ARCHIVE_ROOT`。显式参数优先。具体配置、构建器及测试见 [路径可移植性](docs/PORTABILITY.md)。

## 安全的只读命令

在本目录打开终端：

```sh
python3 tools/research.py status
python3 tools/research.py verify --current-inputs
python3 tools/research.py verify --archive
python3 tools/research.py check-python
python3 tools/research.py duplicates
```

`verify --current-inputs` 输出较长，主要看末尾 `passed` 与 `current_inputs.errors`。工具无需第三方包；所有被核验内容从本目录读取。`resolve 旧绝对路径` 可定位归档中的真实文件。

## 使用前须知

- 本机使用APFS写时复制：文件有独立inode和内容语义，原文件改动不会跟着变，删除原文件也不会让副本失效。初始磁盘增量远小于逻辑文件总量，但不是异盘备份；搬去其他磁盘通常需要完整逻辑容量。
- 冻结源码、合同和旧manifest保留原字节，里面仍可能写旧绝对路径。**当前交付是自包含研究资料与只读访问，不是所有旧实验搬家即能重跑的承诺。** 不应直接执行旧runner或恢复脚本。
- 明确识别的私有目录、settings、真实或模拟账户数据库、Git对象和虚拟环境已排除；没有做全档案秘密扫描，仍只用于本地私有研究，不当作可直接外发包。研究行情目录 `runtime/market` 已保留，研究检查点/失败日志也保留。
- 本次没有下载行情、安装软件、改变算法、启动回测、提交Git、发布或实盘。
