# 复现和迁移边界

## 本轮路径改造

维护工具现共用 `tools/archive_paths.py`；根目录、映射清单和输入清单均可配置，构建器必须显式提供来源配置与新输出目录。新测试与适用范围见 [PORTABILITY.md](PORTABILITY.md)。这不表示冻结研究执行器已迁移。旧工具和本文改前字节保存在 `manifest/portability_v1/originals/`，原 FINAL_SEAL 仍作为旧快照，不改写其哈希。

## 已独立可用

本项目文件本身不依赖原研究目录。只读工具从脚本位置确定项目根，使用 `manifest/SOURCE_MAP.json` 将旧绝对路径映射到项目内部。移动整个项目后，status/resolve/verify/check-python仍按新根工作，不必修改冻结文件。工具只用Python标准库，不加载pickle，不导入研究引擎。

现有原始目录和代码保留不变。本机旧路径继续兼容原有工作，但不应把“旧路径仍可用”算作归档自身的验证。

## 没有冒称完成的部分

最新两棵研究树共1,471个Python文件，其中680个包含 `/Users/` 硬编码字符串、合计1,429处（包括文档字符串，不全是执行依赖）。核心 `joint51_candidate_v9_facts/engine.py` 直接绑定11/06、10/29和money三处根，并校验源码/输入哈希。

因此没有全局替换路径，更没有修改原冻结hash使其“通过”。当前旧runner不是随意移动即能重跑的统一CLI。需要重跑时应另立迁移适配版本：输入根与输出根显式传入、旧路径键通过映射解析、明确保留原来源hash和适配代码hash、输出到全新目录，再完成合成与因果前缀/核账验收。不得恢复失败检查点或覆盖旧账簿。

本次验收包括归档存在性/大小、原生clone成功与独立inode、文档和脚本SHA、当前M12全部冻结输入SHA、最新两树Python AST语法；**没有导入执行旧代码、安装依赖、跑研究合成测试或重跑经济账户**。

## Python环境

- 归档检查工具使用系统 `python3`，标准库即可。
- 最新M12环境取证为 **CPython3.11.13 / numpy2.4.5 / pandas3.0.3 / pyarrow24.0.0**，详见[环境记录](ENVIRONMENT.md)。这是当前安装元数据，不是已验收的可重装锁文件。
- 原 `project/requirements-research.txt` 记录：Python3.13推荐，numpy2.4.3、pandas3.0.1、pyarrow26.0.0、matplotlib3.11.2、requests2.32.5。
- 采集依赖另见 `project/requirements-fetch.txt`，本次未安装、未取数。
- 历史脚本还记录过uv缓存解释器、my-quant conda和旧venv；这些安装路径不是可搬迁的环境封装。相关版本记录只是原记录，未宣称在新环境完整安装并通过。
- 真实/模拟账户库、票据、settings.json和私有抓包不属于本次研究项目；只有公开行情 `TradingAlarm/runtime/market` 保留在原相对位置，满足当前399个冻结输入。

## 空间和备份

APFS克隆是同卷独立副本，修改时才分配变化的块；不是硬链接。复制到非同卷磁盘、云盘、压缩包通常需要完整逻辑容量，而且源与副本同时位于同一硬盘，不提供磁盘故障保护。不要依据 `du` 的逻辑统计认定实际新增了同等空间，也不要把检测到的重复字节当可直接回收的磁盘量。

冻结源文件/manifest全部保留原字节；项目内255条历史软链接仅在新副本改为项目内相对链接，原链接不改；另有2条node_modules和1条pyarrow安装链接明确排除，详见manifest/ENVIRONMENT_LINK_RESOLUTION.json。单个历史Swift工具源码已补入，未复制整套工具环境。
