# First late contraction preflight v1

只读原保存事实，2026-11-08。未运行经济、consumer、参数搜索或删单收益。所有金额均为原路径闭合回合描述，不是新规则收益。实际BUY仅指原条件next-common OPEN full-fill proxy，不是交易所真实成交。独立CORE采用原已独审的逐日费用净额，FULL仅辅助。

## 最终作用域与语义

研究候选是当前root尚未建立PROBE parent的fresh continuing frontier invitation，且全N同业leave-one-out当日M3净变化上界严格小于0。UNKNOWN、FLAT、POSITIVE均不因本条件被阻止；root birth首探原样旁路；已存在parent的零/部分成交、已有仓位与ADD不变。之后必须使用当日真实新receipt重新申请，不能复活旧票。

FIRST_ALL_STRATEGY_BUY是独立窗口初始化FLAT后的描述标签，不证明连续历史从未买过该股。按最新范围，过去买过同股不是永久准入标记。之前提出永久has_prior_buy或将正常新root晚邀永久豁免的解释已撤回。原退出后新root晚邀单独报告；不混入窗口首次层，也不永久豁免或禁止。root birth始终旁路。

54例准确表述是“出生申请未获首仓，后续fresh续邀首次建立该root目标”，不能说“后续才首次申请”：全部54例出生当天已有APPLICATION。无真实broker order/ACK/fill证据，不能把proxy无parent外推为实盘无零/部分parent。

## 原窗口首次层：完整分组

TARGET_GROUPS.csv提供2022/2024、ALL/原COMMON、全窗口首次/窗前root/本窗出生、四方向及TOTAL，actual数、互斥金融分区、CORE/FULL闭合数、胜数/率、均值/总额。

全窗口首次晚邀2022=461，2024=626。其中窗前root为286、162，不可声称出生当天被挡。旧总表2024 prewindow_root为空，已按2024-09-02重建并与修复底表prewindow_root_fact逐行一致；2022窗界2022-01-04。

严格可观察出生层2022=175，2024=464：
- 2022 ALL POS actual23/CORE17，胜8=47.06%，mean +259.48，sum +4,411.11；NEG12/12，胜3=25.00%，mean -957.10，sum -11,485.23。
- 2024 ALL POS112/105，胜54=51.43%，mean +1,211.05，sum +127,160.05；NEG42/39，胜11=28.21%，mean +598.10，sum +23,326.01，另3经济UNKNOWN。
- 原COMMON 2022 POS14 mean +626.44，NEG8 mean -848.09；2024 POS103 mean +1,202.28，NEG39 mean +598.10。
- 扩张与收缩均值差方向两窗一致，但不能据原分组盈亏推删单收益，也不能因2024 NEG为正直接否决候选。原未来收益未用作选票条件。

NEG54占原实际PRICE BUY：2022 12/2395=0.50%；2024 42/1198=3.51%。2022为12股票、11信号日、7行业、11行业×日；2024为42股票、21信号日、22行业、34行业×日，最多同日7例、同一行业日2例。不是54个独立市场冲击。

## 原执行身份核验

TARGET_IDENTITY_AUDIT.csv和QA.json：
- 1087窗口首次晚邀在当前signal前原全策略BUY=0、原PRICE proxy parent=0，原joint stock_state_before均FLAT。
- 本窗出生639例均能看到出生fresh receipt，且出生信号未导致原任何策略BUY。
- NEG54全部同根此前无登记回合、birth和当前signal前无parent。
- NEG出生PRICE原结果：2022 9未进TOP2、2合法AB优先压制、1行业false；2024 33未进TOP2、8合法AB优先压制、1最小手数/风险不通过。原AB优先压制不等于实际AB持仓，已查全策略BUY为0。

## 正常退出后新root的独立晚邀层

REENTRY_ROOT_GROUPS.csv、REENTRY_ROOT_IDENTITY_AUDIT.csv：2022 ALL237（原COMMON184），2024 ALL22（COMMON19）。全部259例核实前次原sell_all严格早于新root生日，birth和当前续邀都没有该root PROBE parent；无同日先卖后生样本。

- 2022 ALL POS49/CORE43，胜15=34.88%，mean +172.08，sum +7,399.48；NEG23/CORE19，胜5=26.32%，mean -1,133.26，sum -21,531.96，另4经济UNKNOWN。
- 2024 ALL POS5/CORE3，胜1=33.33%，mean -968.99，sum -2,906.98；NEG3/CORE3，胜0，mean -1,782.35，sum -5,347.06。
- 原COMMON 2022 POS43 mean +172.08，NEG18 mean -1,015.52；2024 POS3 mean -968.99，NEG3 mean -1,782.35。
- 2022震裕科技300953一例birth曾登记PRECHECK_Q0_NO_SUBMIT，未建立parent/未BUY，后来同根初仓；其ΔUNKNOWN。因此“出生未建立parent”成立，“出生从未登记”不适用于完整237。严禁把q0无提交当成已有零成交parent。
- 2024收缩仅3例，不能称强验证。四方向完整统计和金融缺失见表，不与前述54合并假装同一参与层。

## 54例静态未来机会，仅原市场票

STRICT_NEGATIVE_NEXT_OPPORTUNITY.csv和SAME_ROOT_FUTURE_FRESH_RECEIPTS.csv：
- 同原root后来fresh frontier：2022 10/12、2024 37/42。
- 同原root后来首张Δ非NEG：9/12、35/42。方向2022 UNKNOWN7/FLAT1/POS1；2024 UNKNOWN20/FLAT5/POS10。
- 9/35均有后来原四行业、stock资格、PVR、条件close sizing与next OPEN sizing可见的fresh票。农业银行首张非NEG12-05的stock资格不全，下一张12-06才完整。
- 这些都是潜在新申请。原AB接管、行业TOP2竞争、旧持仓屏蔽、原队列和原OPEN条件不能当作新策略动态结果。没有重建竞争，没有计算新成交、费用、ADD或收益。
- 机械示例：宋城演艺1-05原NEG后1-06同根FLAT，条件OPEN1-07；拓普集团9-06原NEG后9-10同根UNKNOWN，条件OPEN9-11。上海机场1-06后至1-20才有同根POS；四方股份9-20后9-25同根FLAT。
- 新root born另一条原样旁路已列STRICT_NEGATIVE_NEW_ROOT_PATH.csv / LATER_NEW_ROOT_BIRTH_RECEIPTS.csv。计入这条路径，保存窗口内任一路可见2022 11/12、2024 35/42。2022国药股份、安宁股份同根无非NEG，但分别3-24、6-06有后来新root born。剩余1/7仅表示本保存窗内未见，不是永久禁入。
- 原root failed/unknown仅复用纯市场状态。未来新root和same-root均未使用原赢家/输家标签选例或选票。

## 固定早例

FIXED_EARLY_CASES.csv：
- 海能达2024-09-20 born旁路；9-23 POS、9-24 UNKNOWN、9-25 POS，不会被本收缩条件挡住。
- 电气风电2024-09-25 UNKNOWN不作负；root7-24在窗前，不能称出生错过。
- 江丰电子2025-12-15 born旁路；12-17、2026-01-05、1-15 UNKNOWN不作负。仅信号事实，没有2026经济或连续账户参与结论。

## 结论与停止边界

已完成窄预检、身份/作用域、双窗描述对照和静态未来机会。扩张vs收缩差方向一致，但窗口首次层影响有限，正常新root重入层尤其2024样本极小；不足以宣称已获得策略改进。应由父线程据交易哲学和完整scope决定下一步，不按旧组盈利删单。本次到此停止，不运行经济。

主要文件：TARGET_GROUPS.csv、TARGET_IDENTITY_AUDIT.csv、STRICT_NEGATIVE_54.csv、STRICT_NEGATIVE_CONCENTRATION.csv、REENTRY_ROOT_GROUPS.csv、REENTRY_ROOT_IDENTITY_AUDIT.csv、STRICT_NEGATIVE_NEXT_OPPORTUNITY.csv、STRICT_NEGATIVE_NEW_ROOT_PATH.csv、FIXED_EARLY_CASES.csv。各阶段SOURCE_HASHES/QA保留原源未变证据；FINAL_OUTPUT_HASHES.json封存本目录结果。
