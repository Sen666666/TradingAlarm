银之杰300085.SZ原事实准备完成，未运行effective-balance候选。保留原CP完整前缀2680行（2013-01-04至2024-11-29）、2024年9—11月全部58个原观察日和16个CP事件，不按原成交或未来盈亏选事件。

[ORIGINAL_CP_RECEIPT_TABLE.csv](ORIGINAL_CP_RECEIPT_TABLE.csv)逐CP列真实canonical ID、调整/原价、原r/m/delta_frontier/displacement/credit/used_scale/next_scale及scale_frozen_at。16个receipt日期、candidate、used_scale均与No60真实2024年度canonical逐值一致。没有用仅含2025—2026的universe receipt视图冒充2024 ID。

| 原日期 | raw C | 原E0 event | 原CP处理 | 原r | 原fresh/credit | 原candidate |
|---|---:|---:|---|---:|---|---:|
| 10/9 | 47.20 | 0 | 发CP并重锚 | +0.18138979 | 0.18138979 / 0.27194156 | 216.51663069 |
| 10/10 | 37.76 | −1 | E0_down_reset | −0.22314355 | 0 / 0 | 无 |
| 10/11 | 32.00 | 0 | lower_anchor | −0.16551444 | 0 / 0 | 无 |
| 10/14 | 36.57 | +1 | 再发CP | +0.13349233 | 0.13349233 / 0.20008138 | 167.75451662 |
| 10/16 | 42.78 | 0 | 再发CP | +0.18232156 | 0.15684247 / 0.22986942 | 196.24113265 |
| 11/1 | 46.99 | −1 | E0_down_reset | −0.21823687 | 0 / 0 | 无 |
| 11/5 | 56.02 | 0 | 再发CP | +0.10512253 | 0.10512253 / 0.17192871 | 246.14477539 |

表中10/10原I_target仍为1。原模型在负event重锚及更低anchor后，可从新的较低起点再次累计新高信用；没有把此前市场跌幅保存成账户损失。本表只描述已保存市场状态，不证明这些新CP无价值，也不把清零credit当作修复了经济损失。

原No60 B账在本段仅有实际买层1963：10/9信号，10/10 OPEN代理买300股@49.874925，原kind=add/MOBILE，调整保护线216.5166306929101。真实源索引为B.json.gz `trades[3490]`；后续卖parts及资金结果附在[ORIGINAL_REAL_ACCOUNT_ANNOTATIONS.json](ORIGINAL_REAL_ACCOUNT_ANNOTATIONS.json)。原kind=add不等于新候选已成熟；只保原字段，不新算ADD资格、股数或资金。

10/14、10/16原保存CORE和MOBILE双intent均保留，不能因没有实际成交就从CP母体删掉；58日的无CP、原申请、旧持层/pending/ACT及原I/G1也完整保留。原intent缺失不被重新解释为算法不合格。

文件：

- [ORIGINAL_FULL_PREFIX_CP_FACTS.parquet](ORIGINAL_FULL_PREFIX_CP_FACTS.parquet)：原q、完整CP缓存、native I/G1、原E0确认事件及raw价同日精确join；不填未来、不重算价格/收益/CP。
- [ORIGINAL_DAILY_FACTS.json](ORIGINAL_DAILY_FACTS.json)：58日原市场与原账户条件旁注。
- [ORIGINAL_RESET_ROWS.json](ORIGINAL_RESET_ROWS.json)：全部原reset/start/lower-anchor行，不只列有利个案。
- [PREPARATION_RECEIPT.json](PREPARATION_RECEIPT.json)：完整source SHA与0候选/账户/新收益声明。

原账是daily-bar proxy模拟执行，不是新数学候选的收益。等待root冻结公式/共享helper，本目录尚未运行candidate。
