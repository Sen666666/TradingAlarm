# 固定20共享会话收盘路径标签

数据已封定：`PATH20_LABELS.parquet`。SHA256：`7035a30dc6d6f6ff74bd8f3fdf7e68a0262af30582a0bf802cbda576a096980d`。

保留全部133,713条原候选及原顺序，键为`window/day/sid`。不重算PVR、不建账户、不生成分数或分位组。

| 原窗口 | 全部候选 | 旧h20仅入口/终点KNOWN | 新20路径完整 | 旧KNOWN但内部缺行 |
|---|---:|---:|---:|---:|
| 2022_2024 | 79,892 | 78,048 | 77,765 | 283 |
| strong | 53,821 | 50,834 | 50,622 | 212 |
| 合计 | 133,713 | 128,882 | 128,387 | 495 |

`path20_complete`为bool，`path20_status`为字符串。另有4,566条窗口尾未成熟、188条终点缺行、72条下一共享会话缺行、5条原block切换；均保留且六个新标签为NaN。内部缺行不延长到第20个有效观察、不填充，也不补2025上半年或日历尾。

主标签`ret20_open/mfe20_open/mae20_open`以原next-shared-session OPEN reference为分母；副标签`ret20_close/mfe20_close/mae20_close`以原decision CLOSE为分母。路径严格为t+1到t+20共享会话的完成收盘价；终值为t+20。两套分母使用同一完整样本。MFE=max(path)/base−1，MAE=min(path)/base−1，均保留符号、不截零。它们是价格路径标签，OPEN reference不代表实际成交。

完整性要求：原current/next-OPEN/terminal标签入口有效，且全部20个会话的源行存在、observed、valid、close有限正数、block和source_segment均已知且与当前一致。`h20_status=KNOWN`不能代替新完整性检查。保留旧入口/终点/gap标签、缺失细项及完整路径日期/价格证据。

原已知h20终值和next-OPEN gap均逐值bitexact复现；终端截断检查为300199.SZ、2022-01-04到2022-02-08，所有scalar标签与全窗口exact，未使用第20共享会话之后的数据。该检查不把未来标签称为交易输入。

供主分析关联时，请先按当时特征冻结成员及分组，再检查整档全部成员的`path20_complete`；不删缺失后重排分位。原矩阵与日历未修改。

生成耗时约2秒。`RUN_RECEIPT.json`保存源SHA、分母和别名映射；`TERMINAL_TRUNCATION_CHECK.json`保存有限路径截断证据。`PATH20_LABELS_pre_alias.parquet`是只加六个同值短列名之前的计算原件，不供主分析读取。
