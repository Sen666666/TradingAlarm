# 窄复合权益consumer合同草案
仅设计；未实现、未注册000987或其他事件、未新增经济运行。所有原账与单次锁不动。

## 目标与不变项
新隔离版本目标仍是2022-01-04初始120万，2022 M3 A/B全部原出生窗，观察止2022-12-30。M3/common-known分母、I/PVR资格和排名、行业top2、共享probe、原预算、盈利fresh CP、至多一次ADD、退出触发、日期费率、±5bp代理、NET80不调参。原437事件逐字保留，新复合事件另有稳定ID和版本、明确扩域数。不得替换另一套Account或费用模型。

## 最小第一版支持域
只支持官方证据明确的“现金分配 + 同比例送转”事件，且逐项满足：
1. 公告事实可知上界严格早于需要它的首个决策相位。record CLOSE、ex OPEN、现金pay CLOSE、上市/可售OPEN分别有证据，不互相代替。
2. record日是ex日前一个原共同交易日，股权登记实际数量可从原账户CLOSE唯一重建。若有中间会话/不同登记归属先UNKNOWN，不推定。
3. 所有新增股份已明确于同一ex OPEN上市可售，不依据停牌计划、通常规则、factor或既有Layer.opened猜测可售。
4. 每个登记CORE/ADD层新增股数均能精确得到非负整数；不发明逐层floor、现金补偿或改分配顺序。遇零碎股/合并/认购/选择权/限售/分批上市先UNKNOWN。
5. 现金gross金额与送转ratio均由原始条款定值；独立核验原raw factor坐标匹配，不从factor倒算现金或股数来拟合。
若官方上市日更晚，不能纳入这个窄域。必须另外实现旧股可售与新增股锁定的独立数量/时钟，不能直接套原opened/T+1；未实现前明确UNKNOWN，保留已知资产及责任。此草案不承诺无界支持所有复杂事件。

## 登记、权益与资金
record CLOSE冻结实际owner_round_id、CORE/ADD和layer_id数量，0持仓不获分配；旧轮权益不迁入新轮。
现金权益只按登记旧股q * 官方gross cash * 0.8计，ex确认应收，pay CLOSE应收转可用现金，最早下一OPEN可花。未知支付日不虚构支付；是否允许已确认但未定支付日应收需独立冻结，第一版优先要求精确pay。
新增股份只据登记旧股q*(ratio-1)生成。不是buy，不收手续费、不占一次ADD、不创造新轮或新CP；原实际买入数量、spent、初始费、frozen Nd不重写。current core/add与相应层qty守恒增加。
持仓总实际成本保持不变，层成本总额保持，单位成本随股数重分；新增权益审计另记来源、received_at/saleable_at。保留Layer.opened作为原真实买入身份而不是谎称新增股早已买入；同ex可售必须由独立权益可售证据校验。
执行前必须原子校验所有数量、登记与因子。任何失败不得留下半笔股数或现金变化。

## 除权坐标与策略线
现金源坐标d_source与真实现金d_cash分开；送转ratio独立。窄正常复合公式为 f_new = f_old * ratio * prev_raw_close / (prev_raw_close - d_source)，使用原1e-11容差且要求正分母/来源连续。
不能把ratio折成假现金以绕过原PURE_CASH校验。CORE保护来自原I/factor；现存ADD保护和pending线按old_factor/new_factor转换，记录前后；不生成新fresh CP、晋升或交易信号。
仅Q0且登记确实0的待入场可以无权益地进行已证坐标转换；有实际持仓必须按登记与权益路径处理，不能用Q0绕过。

## 原执行路径最小接入
新独立tape投影437旧事件+已审复合事件；现金register/accrue/pay原函数可在精确登记和现金字段下复用。
新复合before_held/pending_coordinate适配器只处理其已审事件，其余调用原函数；新增股全部同ex OPEN可售时，在原退出前原子更新current CORE/ADD与layer数量。
普通交易、费用、排序和risk引擎不改。split底层纯算法可参考，不能混入sector_account.Account另一套状态。
原报告从action买卖重建qty，必须加入独立corporate-share ledger按“发生在第几笔真实action前”重放数量；不能伪造buy或zero-cost fill。报告实际费用/现金仍只来自真实action和已确认pay。
需新增数量恒等式：买入股数 - 卖出股数 + 已确认权益增减 = 现存层/round股数；现金恒等式沿用真实买卖+支付，不把权益股数当收入。
期末NAV仍cash + gross原价库存（含确已归属股份）+确认应收。无法可信确认某权益或锁定股估值即UNKNOWN，不能以cash/闭轮PNL替代。

## 必需QA与放行
- 同ex可售、晚于ex可售拒窄域；严格盘前钟；登记0/CORE/ADD/全退出/旧轮；整股与零碎股边界。
- 现金除权和送转factor各自验，合并验、错ratio/错现金/来源换段均fail-closed；无当前CLOSE未来污染。
- 股数/层成本/历史买入与费用/现金应收逐项守恒；幂等同event禁止重复增股或现金。
- 现存pending整退出与ADD退出使用全部已证可售数量，真实整单费用只计一次；未支持的锁定股份不借原opened混卖。
- 坐标Q0无凭空分配；CP/promotion/one-ADD与预算不变；无复合事件prefix与旧结果逐相位逐动作相同。
- 报告quantity增股重放、卖出后分层现金和PNL、年末未平仓/应收、gross NAV与假定清算、停止OPEN vs前一CLOSE端点。
- 新目录、精确源freeze、独立前审、新单次锁、900秒/6GiB预算门和事后独审；本次不能续跑旧锁。

## 条件估时
在官方完整时钟已齐、事件全满足“同一ex OPEN新增股可售且逐层整股”的前提下，窄consumer+报告数量适配+合成/已存前缀等价预计1–2小时，独立审查另20–40分钟；执行仍预算15分钟以内，不承诺全年必无新的不支持类别。若晚上市、零碎股或权利条件不同，先报告，不扩成广泛账户重构。
