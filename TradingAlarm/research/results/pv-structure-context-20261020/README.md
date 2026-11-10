# 量价结构语境：算法研究阶段B/C/D

2026-10-20，完成原始图、v0和一次v1机制修订及全体复盘。**账户调用0；不将本轮标签直接用于交易；不自动续跑任何旧账户队列。** 主报告在仓库docs/RESEARCH_STRUCTURE_CONTEXT_2026_10_20.md。

## 阅读顺序

1. `raw/protocol.json`、`raw/case-index.json`：固定15例×2截点。
2. `raw/review-prefix1.md` → `raw/review-prefix2.md`：先保存第一截点判断再揭示第二截点；所有历史仍是已见开发数据。
3. `protocol-v0.json`、`review-v0.md`、`v0/*-trajectory.png`：第一版15图及逐图判断。
4. `protocol-v1.json`、`review-v1.md`、`v1/*-trajectory.png`：唯一机制修订及15图复评。
5. `counterexample.png`：复盘后选取的解释性对照，不是新测试。
6. `comparison.json`、`case-comparison.csv`：27条序列未改字段逐项一致；描述变化量不是优劣分数。
7. `v0/validation.json`、`v1/validation.json`、`mechanical-validation.json`、`mechanical-validation-v1-final.json`：最终运行和独立属性检查。

## 产物边界

主agent实际看了30张原始截点图、v0的15张模型图、v1的15张模型图。图/表中只有历史收盘价、量、结构方向、腿方向、量价描述、已存旧状态、价格排名和布林描述；没有账户净值或成交推演。现有价格含原研究复权口径，不能把它们宣称实盘成交价。

结构方向与发展中方向分开；e/s是相邻运动的活动/速度比例，retrace是相邻两腿绝对对数位移比例，均不是概率或整个主导趋势的强度。v1在本地导入同目录v0，因此两个模型文件都是依赖。RS采用四段63有效观察收益的受O'Neil启发近似，252观察只用于该排名，不用于结构启动；ETF17包含A/H相关ETF，只是所存样本分组，不是行业或全市场。A3在历史早段没有252条有效观察时排名为空。

`orderly`仅指反向腿平均相对成交较轻且单位观察位移较慢，不能解读为健康/安全/继续持有。`supported`必须结合结构方向阅读，可支持下降。现有方向模型仍有旧锚点陈旧、局部摆动升级、恢复迟钝问题；否决直接交易映射。下一步只研究推进的保留、侵蚀与收复，账户继续后置。

## 失败证据

- `v0-attempt1-failed/`：布尔赋值运行失败；同时归档候选失守晋升漏洞的原代码。
- `v0-attempt2-failed/`：未来缺失导致前缀数字dtype变化。
- `v0-attempt3-failed/`：测试错误地移动零量位置改变有效时钟；此目录有部分CSV，未通过整体验收。
- `v1-attempt1-failed/`：真实同价端点浮点相消造成单位缩放标签差异；旧独立验证未覆盖此反例，最终补测。
- `mechanical-validation-v1.json`是浮点修复前的中间验证，不能代替final文件。
- 后处理比较脚本首次把checkpoint汇总误匹配为资产文件，排除该文件后通过；未改变模型数据。

## 哈希与复现

`archive-manifest.json`覆盖本轮文件（不含清单自身）。各版本freeze含当时模型/runner/协议及27份输入哈希；protocol-v1额外记录v0依赖。`source-mirror-validation.json`证明本轮使用的27份镜像输入与完整工作树完全一致。模型检查失败后的原始文件没有删除。

默认阅读已有结果。若明确要复现，使用新输出根，不直接运行固定目录runner。例：在仓库根，使用已安装numpy/pandas/matplotlib的Python执行：

```sh
python TradingAlarm/research/results/pv-structure-context-20261020/code/replay_context.py \
  --source-dir TradingAlarm/research/results/pv-event-structure-20261020 \
  --output-root /private/tmp/pv-context-replay-new \
  --version v1
```

输出根必须不存在。包装入口只复制冻结代码/协议并指定迁移后的输入目录，运行的仍是同一轨迹代码，没有账户依赖。原始freeze中的绝对路径是当时来源记录，跨机器使用同名文件及哈希核验，不假设原绝对路径存在。该包装入口在本轮只做静态语法检查，未重复运行整轮。
