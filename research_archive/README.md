# 精简研究档案

正文、算法源码、合同和小型结果仍按原研究目录放在 `research_rounds/`，研究入口见 `docs/RESEARCH_DIRECTORY_INDEX.md`。

为了减少数千份重复展开的结果/身份文件，一部分原始研究JSON/CSV元数据放入 `research_metadata.tar.gz`。它只包含已脱敏发布候选中的研究元数据，不是行情、账户数据库、pickle或巨型逐步账。

- `METADATA_INDEX.csv`：精确路径、字节数、SHA256及原本机来源相对路径。
- `publication/METADATA_PACKAGE_QA.json`：逐成员实际解压并核SHA的回执。
- `scripts/read_research_metadata.py`：无需解包即可列出或读取一份原始元数据；不导入研究引擎。

```sh
python3 scripts/read_research_metadata.py
python3 scripts/read_research_metadata.py 'research_rounds/某实验/FROZEN_INPUTS.json'
```

列表里的路径是原档案身份，不代表对应行情及大账簿在GitHub。完整本地资料和已核依赖仍由独立研究归档保留。生成网页、第三方解包程序及重复控制台转储没有混入这个元数据包。
