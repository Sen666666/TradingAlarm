# 独立 PVR + CE 首次建仓排序

本目录是独立新臂，只新增股票优先级排序，不叠加亏损加仓门，也不使用 E3。原 120 万基准和所有共享源码均只读。

## 唯一干预

ce_account.CERunner 在原 N.Runner.planning 完成后，直接汇总当前反事实账户的真实 pending。was_empty 严格取该信号收盘的 quantity == 0，不使用基准持仓、core_Q 或下一 OPEN 卖出后的状态。

全部空仓股票组中，仅当原 PVR 已知且 ready、同股票同信号日存在原生 fresh CP 可计算 CE 时，整组股票 rank 可交换。CORE+MOBILE 可以共同移动，CORE-only 如当日确有 fresh CE 也可以移动。已有仓、无当前 fresh CE、原 PVR 未知组留在原数值槽。没有旧 CP 复用、K20、连续重编号、额外行业过滤或资格筛选。

排序完全调用已冻结 empty_first_rank.rank_empty_first_stock_slots：CE.round12 降序、原 PVR.round12 降序、原 rank、sid。封装只修改原 pending 和 decisions 的 rank。priority_rank、PVR、资格、角色、clock、quote、CP1、预算、止损等所有非 rank 字段在调用前后作字节快照断言；候选/角色多重集、固定槽和同股 rank 一致性另行断言。

原 A.Runner.route、J.Runner.opening 和 NoConfirmed60Budget 保持原函数身份。下一 OPEN 仍先按股票 rank、同股 CORE 优先 MOBILE，原 done 规则每股最多预订一笔。并未承诺 CORE 成交不受此前现金占用变化影响。

## 输入和连续账户约束

- 120 万初始现金、NAV、预算现金及 ACT peak 同时初始化；2022-01-01 起空仓，无年度重置。
- 原连续输入、复权、现金桥、费用、执行代理和 ACT 不变。
- 与原 run_1200000/PREDECLARED 的 input_identity 精确比较，只排除并单独记录实测耗时 seconds；44 个原 source_freeze 文件启动时逐一核验。
- CE 模块全局只读查表，共 1709 名册、1687 完整源、22 明确无数据、232520 原生 receipt。其 177668 个原候选域外 receipt 不依赖原账持仓。
- CE 232520 行 DataFrame 不进入 runner/checkpoint。runner 只保存身份/hash、逐股日志与每日审计。
- 新版 EMPTY_FIRST_MANIFEST hash 硬钉为 7bc25d5e2fe74a50adde848979adf06860cdff8b3f58576caff0c186000699dd。全池 5061 截断 prefix 证明及新版宽口径审计一并 source freeze。
- restore 在原 checkpoint provenance、source freeze、集成规则核验外，再核 CE 身份及全部直接输入的当前字节哈希。

## 已完成的准备验证

本源码准备任务没有构造或执行财务账户。SYNTHETIC_TESTS.json：11 项测试加 160 组确定性合成不变量测试通过，覆盖空队列、全 None PVR、双 role、CORE-only、held、未知、稀疏 rank、tie、序列化恢复、非 rank 恒等与基准输入防漂移。INPUT_ONLY_CHECK.json：23 个 CE 文件和全部 232520 行输入校验通过。系统 Python 缺 parquet 引擎，未安装软件，改用既有研究虚拟环境完成校验。

账户预检和正式回放由父任务单独执行。准备验证不能替代实际 restart+当前/future HLCV poison gate、输出独核或正式经济结果。

## 父任务执行命令

解释器必须使用已有研究虚拟环境，并禁用共享源码 pycache 写入。以下均为手动显式执行命令，不会由导入自动启动。

```sh
PY=/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/research/.venv/bin/python
DIR=/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1/account_comparison_continuous_v1/ce_entry_v1
PYTHONDONTWRITEBYTECODE=1 "$PY" -B "$DIR/run_ce_entry.py" --execute --out preflight_20220207 --end 2022-02-07
PYTHONDONTWRITEBYTECODE=1 "$PY" -B "$DIR/verify_preflight.py" "$DIR/preflight_20220207"
```

仅预检 DONE、restart/poison gate、独核均通过且所有冻结源码未变后，再运行：

```sh
PYTHONDONTWRITEBYTECODE=1 "$PY" -B "$DIR/run_ce_entry.py" --execute --out run_1200000 --preflight "$DIR/preflight_20220207"
PYTHONDONTWRITEBYTECODE=1 "$PY" -B "$DIR/verify_preflight.py" "$DIR/run_1200000"
```

输出目录必须是本目录下尚不存在的直接子目录，拒绝覆盖及隐式重跑。失败状态只作诊断，不能把部分事件当完整 checkpoint 恢复。

## 输出接口

- CE_STOCK_RANK_AUDIT.jsonl.gz：每个信号日的全部真实候选股票组，保存原 rank、新 rank、was_empty、实际 roles、PVR、CE/known/reason、收盘 quantity、固定/可动理由。并非只保存移动行。
- CE_DAY_AUDIT.jsonl.gz：每日分组、移动、CORE 移动、unknown、固定槽与非 rank 快照断言。
- BASELINE_SOURCE_AND_INPUT_GUARD.json：原基准同池同输入同源证明，仅记录排除秒数。
- RESTART_OPEN_PERTURB_GATE.json：同一 checkpoint 正常 OPEN 与 current/future HLCV 扰动 OPEN 的全状态摘要相等。
- INDEPENDENT_CE_PREFLIGHT_CHECK.json：verify_preflight 对全部队列独立重排、CE 同日查询、daily 收盘持仓、原 PVR、native 函数身份、资金桥及 checkpoint 逐项核验。
- LIVE_ANNUAL_METRICS.json、LIVE_PERIOD_METRICS.json、MONTHLY_PROGRESS.json：实际交易月末更新，console 同步输出 NAV、年初至今收益与回撤。
- 原 pair/PVR.json.gz、daily、funding、journal、checkpoint 和最终年度/期间指标保留，供父任务 analyze_comparison.py 独立评估完整 0→0 费后回合。

完整回合胜率至少 30% 是待检验目标，不是已得结果或保证。年度收益、金额盈亏比、回撤、大行情和未平回合必须一起报告。不存在随机账户对照、网格选择或真实订单。
