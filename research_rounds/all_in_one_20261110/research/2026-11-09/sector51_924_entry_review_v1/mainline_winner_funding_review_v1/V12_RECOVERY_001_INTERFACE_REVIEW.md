# V12 recovery_001 同账户恢复最终独立审查

结论：PASS_V12_RECOVERY_001_SAME_ACCOUNT，remaining_blockers=[]。只适用于已锁定的 recovery_001/recover.py SHA 1f3523957da71bc1de52fe450eeddd20241925133371f619d3a071d4729c30da。

## 证据与验证

- 原认证位置为2024-09-25：16日、395单、81只、NAV 1237652.3522767729405。
- 独立核原receipt SHA 1defa15d1bb38c6b05878fb770c8b127f16213207f996fe34ac459536351ea16、21MiB state SHA 1274a577f61286c1a56103ed6028cddedfcda640bd496858e8c3bb24b2e46a1e，以及旧manifest/批准/接口QA。
- 旧binding与FROZEN_INPUTS逐字段相同。独立流式核9121个代码/数据来源文件，859387487字节，全部hash匹配。
- 初始COMMIT/state及外置receipt日志/LATEST已原字节复制至origin_checkpoint，逐项hash相同，无receipt路径字段或binding改写。恢复仍用原load允许的候选目录范围，后续滚动cache不会毁掉这份唯一初始证据。
- 本人独立复跑38项合成及recover.py --mode check通过。完整ps检查当时无原账户或竞争恢复进程。
- builder另做真实Data与原load只验证模式，STATE_VALIDATION.json SHA b9815a3b170c6b46cb1edcf9b5fefc77de2e72635f81ad4605850dba81700050。该报告绑定当前driver并证明全部16日前缀及账户联合图验证前后相同。本人独立审核报告和代码，没有重复构造真实Data或解实际pickle。

## 恢复合同

1. 先核外部可信receipt、原state、原来源、旧批准与完整binding，再由原checkpoint.load解本地自建pickle。Data仍为原类、原9108项hash字典；新driver不会塞入旧binding、覆盖旧hash或走宽免路径。恢复批准在binding之外另锁新driver、测试、QA、原状态证据及本审查。
2. 原active/archive、CP、票、metadata缓存和最新book别名保留。运行中不给engine增加pending属性。逐日只读浅副本选择当日保存funding_book重验旧16日，不修改真实账户，联合pickle图前后相同。
3. 从9/26严格续余77个交易日，累计93日止1/20。原run_once尾部逐字提取，唯一改动是去掉pending=[]初始化；原atomic、22日前缀门、费用、checkpoint、export、status均保留。未重新开账户、重生尝试或重放首16日。
4. 恢复入口有独立外置批准、排他flock、RECOVERY_STARTED独占创建；Data前及真正续算前均重新读取完整ps，原进程不在才可推进。原RUN_STARTED保持不变，不能重启旧one-shot。
5. 合成覆盖旧source/receipt错误拒绝、别名保持、原生连续与恢复状态完全相同、日期与77天边界、原atomic阻断不推进、前缀变化在checkpoint前停下、python/uv进程识别、排他锁及重复启动拒绝。
6. 本PASS不允许其他证据/策略/源迁移或1/21执行。断连或启动结果不明时先核实际进程与持久化checkpoint/status，不得盲目重试。

## 范围

本审查未执行9/26及其后的真实历史，也未启动恢复。测试中的有限日期循环是明确的假账户控制流和原生小型合成，不是历史重放。真正恢复仍由父任务按精确hash单独批准并启动一次。

主QA：V12_RECOVERY_001_INTERFACE_QA.json
SHA：b1e36b6dbc2402cd358b2e8eaa3ab6f2f21f166920c6bf970103c2d6281e2825
