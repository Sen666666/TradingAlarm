# C入口冻结预检

仅基线真实状态的影子候选/配额诊断，不执行C、不产生新收益。多个同股影子C不能相加当成ABC入场；真实第一次C成交会清资格并改变后续状态。

     window  broad_persistent_fresh  same_I_prior_AB_loss  unconsumed_marker  current_FLAT_with_marker  PVR_known_after_marker  close_feasible  AB_remaining_slot  C_PVR_shadow_awarded  shadow_awarded_unique_stocks  next_open_known_proxy  next_open_NOFILL  next_open_UNKNOWN  next_open_pending_end  direct_AB_event_conflicts
       2022                    1101                   317                203                       203                     203             201                164                   160                           146                    160                 0                  0                      0                          0
   2024_924                    1080                   556                414                       414                     414             392                318                   238                           220                    236                 2                  0                      0                          0
2026H1_SEMI                      61                    24                 22                        22                      22              20                  9                     6                             6                      6                 0                  0                      0                          0

2022固定20早例，在错过原较早A/B后、旧臂后来入场前，出现获剩余名额且次开已知代理C的病例：1/20。

AB直接同日事件冲突为0；但较早C持有/UNKNOWN可阻断未来AB，详见LATER_AB_CONFLICT_RISK.csv。此为风险足迹，不是新臂实际阻断结果。

模型和成本完全冻结：原interval relative时钟；原close、含费24000预算、3000风险、原20正成交量观察容量、5bp双向滑点、原dated lot/fees。行业AB先处理，C只分剩余，不看次开结果替补。

每窗口AB股票集合对C定义闭合，因为窗口外标记不继承且必须窗口内合法AB落选造标。1627并集之外82只无此必要条件，不是漏算符合定义的C；原NON-PIT和历史交易许可限制仍存在。

文件：FUNNEL.csv、CANDIDATE_PREFLIGHT.csv、FIXED_CASE_STATUS.csv、FIXED_DAILY.csv、AB_SAME_DAY_SLOT_DENOMINATORS.csv、MARK_TRANSITIONS.csv、PREDECLARED_EXAMPLES.csv。DAILY_FEATURES_0..7.parquet保存全股票窗内日级市场知识状态，FREEZE.json与POSTPROCESS_SEAL.json固定输入。

经济ABC未运行，须独审通过并再次明确授权。
