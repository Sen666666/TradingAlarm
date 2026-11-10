# 原e双记忆纯特征导出

已完成并封定`DUAL_MEMORY_FEATURES.parquet`：133,713条原候选、1,660只股票，原键`window/day/sid`及`candidate_index`顺序均保留。SHA256：`5420a140242e00bcf5c39832770569f941ecc8b60711253ba8b13561877bb54c`。`e`列就是当前`e_t`，没有新score、排序或账户。

原source full history先按原PVR时钟重建r/scale/amount_ref/u/b/e。公式与原`feature_design/features.py::original_pvr`六个标量步骤保持原样：r=Δlog(C)，scale=1.4826×此前63个|r|的中位数（已知值下限1e−8），amount_ref=此前21个amount中位数，u=tanh(r/scale)，b=tanh(log(amount/amount_ref))，e=u×(1+0.5×|u|×b)。缺失不填下限。正且有限close/amount、原可选valid masks和原segment共同决定有效观察；invalid/source变化重启。没有用稀疏CP事件或score反推e。

固定快段：`E_fast=sum(k=0..4,.8**k*e[t-k])/sum(k=0..4,.8**k)`；只要求同当前原block的5个有限e。固定慢段：`E_slow=mean(e[t-62]..e[t-5])`，58项，不与快段重叠；要求这63个观察槽位均在当前原block且所用58个e有限。两段均为原有效观察时钟，不冒称63个共同市场交易日。当前CLOSE完成后才可知。

| 原窗口 | 候选数 | fast已知 | slow已知 | fast-only |
|---|---:|---:|---:|---:|
| 2022_2024 | 79,892 | 79,868 | 79,304 | 564 |
| strong | 53,821 | 53,815 | 53,687 | 128 |
| 合计 | 133,713 | 133,683 | 132,991 | 692 |

`fast_status`与`slow_status`独立；`dual_memory_status`仅表示共同可评，不能拿它筛fast-only启动队列。30条fast暖期、722条slow暖期保留NaN；当前e独立已知133,692条。`fast_known_count5/slow_known_count58/e_known_count63/observation_count63`、各窗口起止日期、原block/segment/观察序号和源SHA均保留。

六个标量在全部primary及全部1,660股的1,606,880个原export日期点上，已知性与有限值bits均一致；其中e有限1,524,702点。原四项clock字段相同。真实截断海能达至2024-11-01（2,833行，对全源3,310行）和300058至2022-01-04（2,077行，对全源3,237行）重算，所有共同列exact，并再与原scalar六列bitexact比较。

`FOUR_STOCK_63E_EVIDENCE.parquet`保留四股全部382条原候选的63个e及日期：000620为94条、300666为96条、300085为83条、002583为109条，均有完整63e。这些值可逐条exact重建所存fast/slow。若用反向Python逐项sum替代本实现的时序NumPy sum，最大浮点顺序差fast为4.44e−16、slow为1.11e−16，不是公式或时钟差异。

完整导出约25.55秒。一次早期执行在收到独立fast有效性澄清后于约400股处主动中断，未落任何parquet或receipt；保留中断日志。此后只有一次完整执行，0账户、0新score、0排名、未读取未来价格标签。原策略和原导出文件未修改。
