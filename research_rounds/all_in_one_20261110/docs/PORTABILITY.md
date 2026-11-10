# 路径可移植性改造 v1

## 已修复

- `tools/archive_paths.py` 是唯一的归档路径解析层。优先级：`--project-root` > `RESEARCH_ARCHIVE_ROOT` > 工具位置。不依赖启动目录、用户名或原研究目录是否存在。
- `tools/research.py` 的 status、resolve、verify、check-python、duplicates 统一使用选定根；支持 `--source-map`、`--input-manifest`。清单必须在所选归档内部。
- resolve 同时接受归档内相对路径、当前归档绝对路径和历史来源路径。历史来源只作为映射键，缺少副本时明确失败，绝不回读原目录。
- 拒绝 `..`、映射目的地越界、外部软链接及重复/重叠目的地。读取前检查实际解析路径。
- `tools/build_archive.py` 不再写死本机根；必须提供 `--source-map` 与 `--output`。`--dry-run` 不写文件，真实构建拒绝既有目标，维持 APFS 独立 clone、排除私有目录及旧证据不覆盖规则。兼容 macOS `/var` 与 `/private/var` 的规范化。

## 日常用法

在归档根打开终端：

```sh
python3 tools/research.py status
python3 tools/research.py resolve project/README.md
python3 tools/research.py verify --current-inputs
PYTHONDONTWRITEBYTECODE=1 python3 tools/test_portability.py
```

从任意工作目录调用时，给工具自身路径即可。需要选择另一份归档时：

```sh
python3 tools/research.py --project-root "$ARCHIVE_ROOT" status
RESEARCH_ARCHIVE_ROOT="$ARCHIVE_ROOT" python3 tools/research.py status
python3 tools/research.py --project-root "$ARCHIVE_ROOT" --source-map manifest/SOURCE_MAP.json --input-manifest project/docs/handoff_2026-11-10/CURRENT_INPUT_DEPENDENCIES.csv verify --current-inputs
```

`ARCHIVE_ROOT` 由调用者设置为实际目录；未设置环境变量时无需额外配置。所有全局参数放在子命令之前。Python 3.9+，标准库即可。

## 新归档构建

创建自己的 JSON 来源配置，格式沿用 `manifest/SOURCE_MAP.json` 的 `roots` 数组，每项含 `source`（当前机器实际绝对路径）、`destination`（目标内相对路径）、`kind`（file/directory）。必须恰有一个 directory 映射至 project。历史 SOURCE_MAP 不要修改；重新构建时新建配置，源已搬迁就填新位置。

```sh
python3 tools/build_archive.py --source-map "$SOURCE_CONFIG" --output "$NEW_ARCHIVE" --dry-run
python3 tools/build_archive.py --source-map "$SOURCE_CONFIG" --output "$NEW_ARCHIVE"
```

`SOURCE_CONFIG` 和 `NEW_ARCHIVE` 必须由调用者指定。构建器只克隆配置列出的资料并生成清单，不自动拷贝本次工具、文档或补充清单，也不代替历史那次完整整理流程。真实构建仍只支持 macOS/APFS，同卷 clone 失败时不自动退化为巨量复制；本次只运行小型临时夹具，没有重建真实大归档。

## 验证与证据

`tools/test_portability.py` 使用全新临时目录（含中文与空格），从 `/` 启动，旧路径为不存在的模拟根。覆盖8项用例：状态快照迁移、旧/相对路径解析、根选择优先级、输入与归档哈希及篡改失败、越界/外链拒绝、坏映射、缺文件不回退、真实小型APFS构建/相对链接/禁止覆盖。不是借原目录仍存在来让测试通过。

- 回归结果：`manifest/portability_v1/TESTS.txt`。
- 当前真实输入与归档复核：`manifest/portability_v1/VERIFICATION.json`。
- 改前工具与文档原字节：`manifest/portability_v1/originals/`，SHA见 `BEFORE.json`。
- 最终改动身份与范围：`manifest/portability_v1/AFTER.json`。

首次测试发现 `/var` 与 `/private/var` 差异导致断言和内部软链接映射失败，已修复规范化并全部重测。原 `FINAL_SEAL.json` 是改造前的真实快照，继续保留，不改成新哈希伪称原件未动。

## 本次最终验收

8项迁移回归全部通过，4个活动工具AST通过。真实当前输入9,108个、859,282,876字节SHA全部匹配且均从归档读取；全归档686,178条检查无错误，其中17,036份已登记SHA的文件逐项匹配、255条内部链接通过。其余大型文件按大小及原clone收据核对，不宣称本轮全量内容hash。

## 明确未做

未批量替换 project/、research/ 内的冻结 engine、runner、合同或哈希清单；未解锁 M12、恢复检查点、生成新金融结果、安装依赖、下载行情或改原 money/Codex 项目。当前状态依旧是 M12 PREFIX_MISMATCH、认证截止 2024-09-30。

历史代码的绝对路径仍在，其作用包括源码身份/来源证据和真实运行依赖。全研究执行器搬迁需要另立适配版本、输入输出合同及前缀/核账验收。本轮维护工具通过，不等于旧研究引擎全部可移植，也不是完整金融验证。
