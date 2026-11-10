# 复现顺序

使用原任务指定Python，设置PYTHONDONTWRITEBYTECODE=1。

1. evaluate_scc21.py：七例分数与逐日检查。
2. write_case_report.py：七例报告。
3. candidate_test/run_candidate_test.py score：全母体Q和覆盖检查，不读未来标签。
4. candidate_test/run_candidate_test.py evaluate：唯一冻结同K排名，封存后读取原标签评价。
5. candidate_test/audit_outputs.py：最终基线、原根、未来标签污染、UNKNOWN固定槽验证，补N/K及七例名次。
6. candidate_test/write_report.py：明确epoch敏感性、主报告、回填七例后续索引。

原始缓存均只读，新产物只写本目录。原外部绝对路径见脚本；没有账户引擎或原指标调用。execution_sensitivity由父任务独立只读补充，不属于Q方案的第二轮调参。

本次执行中第一次完整评价在原根CSV比较处因字面None被默认解析为NA而停；修复keep_default_na=False后从封存结果继续。续做时检查代码的局部变量作用域问题已修复，最终audit_outputs全部通过。没有重跑或更改已封存排名、分数、年度路径；参数和资格从始至终未改。run_candidate_test_score_snapshot.py保存评分阶段脚本，SOURCE_BEFORE_SCORES可核对应hash。
