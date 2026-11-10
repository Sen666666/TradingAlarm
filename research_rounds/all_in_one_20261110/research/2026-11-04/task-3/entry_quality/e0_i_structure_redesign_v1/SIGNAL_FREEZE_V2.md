# E0/I V2：两条独立结构确认通路

本文件取代SIGNAL_FREEZE.md的U_OR/S_PAIR候选；旧稿只保留历史，不运行、不按结果选优。唯一主版本是下述A OR B。保留原E0量价自适应反转事件，只做7股完整历史前缀上的信号演绎；不账户回测、不下单、不生成候选收益。资金候选已撤回且未启动。

## 1. 因果输入和确定的参考选择

原E0 event=+1在其确认CLOSE发布一个close低pivot L；event=-1发布一个close高pivot H。每点存price_adjusted、pivot_day、confirmed_at、source_segment/id。pivot_day不是known_at；不使用盘中H/L或居中窗口。原事件的RMS/量能阈值保持不变，缺失的原sigma不拿CP尺度填充。

每股从原source完整事件前缀递推，然后截展示区间。source不可比段进入UNKNOWN；不得在展示slice首日将历史前高/状态静默清空。当前CLOSE可登记本日刚确认低点，但所有被当作‘此前高点’的参考必须在t前确认；原交替event保证L1-H12-L2的H12在L2确认前已发布。

### A：直接收复触发前关键前高，不需要第二个低点

OFF遇原E0正event建立START。将t−1已发布高点中**最近两个**取max作为K_A；不足两个但有一个时用唯一高并标SINGLE_HIGH；没有高则A_UNAVAILABLE。不从全历史挑对结果有利的高，不在本次START中随lower-high下调K_A。

`A_active(t) = A_ref_known and C_t > K_A`。

START确认日C已在K_A上方也可成立，不硬要求当日才cross，避免E0量价确认滞后于价格突破而锁死。记录首次cross/已站上，仅作诊断。

关键高的age（距其确认日的有效观察数）、确认日和被选规则全部输出。**本稿不再添加日龄阈值**：很旧但同源可比的高仍是较大范围锚；没收复就不发A，保持START，由B独立确认。缺失、跨不可比段或无法核确认钟时A未知，不能换未来更低峰补位。旧高长期压住A是反例，不能隐去；此时B不必越该旧高。

### B：更高低点＋突破其间局部高，不需要收复A的远端高

本日确认新低L2时，从同source按事件顺序取相邻前低L1及两者之间唯一原确认高H12；要求`pivot_day(L1)<pivot_day(H12)<pivot_day(L2)`且H12.confirmed_at<t。

`B_base = valid(L1,H12,L2) and L2 > L1`；
`B_active(t) = B_base and C_t > H12`。

两个低点都必须已发布，H12必须事先已发布；B不要求C>K_A。每次新的+event用最新相邻三点更新B_base及H12，非HL则B_base=False；不得用max ratchet floor代替相邻低点。允许L2刚确认的本收盘同时满足B，资格只从此CLOSE后使用，不回填pivot_day。

最终：`I_expand(t)=A_active(t) OR B_active(t)`，不是HL AND K_A。

## 2. 共同状态与单向保护线

状态为OFF/START/CONFIRMED；另保A/B参考、独立active/原因、generation、P保护线、原pivot列表。在当前C与支撑均已知时I_hold=START或CONFIRMED；I_expand始终按三值A OR B输出，输入未知规则优先于mode摘要，不能只写mode==CONFIRMED。START发试探启动事件，不因没有第二个低点而禁止参与。降级START只撤成熟新增许可，不自动卖出旧仓；破P才发该结构的退出事件。G1只作原对照，不在本稿加新暖门或资金参数。

同一generation：

`P_t = max(P_(t−1), 本日新确认L)`（若没有L则保P_old）。

只要仍为同代，降级START也不能降低P。初次START令P=L_launch。新generation可有新P，但旧generation的P及退出事件封存不改；新START不能将旧未成交仓位责任重置。

## 3. 每日顺序、失效、新增许可和重入

1. 先用t−1已知P检查`C_t<=P_old`。命中则旧代OFF，发布support_exit并封存旧P、退出日；清其A/B基础。不得用本日新线遮掉旧破坏。
2. 原E0本日pivot在当前CLOSE登记。若仍OFF且本日event=+1，发新START/generation，以L_launch建P；A只取本日之前高点，B按上面原相邻三点计算。旧代本日刚退出也可发新代START，但保留两件事件；这不表示真实旧卖已完成或允许同价无缝新买。OFF遇负event只记高，不无支撑开START。
3. 在已有START/CONFIRMED中，本日+event先按max更新P，再更新B三点。第2步刚启动时允许本日三点立即判B，但同一pivot只登记一次。L2不高于L1时B_base无效，但不为此放宽P；A仍能独立收复关键高，允许深V。
4. 仅在START/CONFIRMED中，若本日负event确认`H_new < H_prev`，这是新lower-high证据：清B_base；A的修复门提升为`max(K_A,H_prev)`（若原A未知且H_prev已知则采用H_prev），绝不降到更低H_new。此H_prev在本日前已确认；当前lower-high确认C必在H_new以下，因此不会刚撤权就凭同一低门复活。输出启动时initial_K_A和修订后K_A及各自来源；修订参考可能在启动后确认，不能假称都是启动前高。只记结构退化，不修改P。等高不等于lower-high。
5. 分别计算A_active、B_active。任一路已知有效则CONFIRMED；两路均无效或未知而仍有P支撑则START。OFF无支撑不得自动变START。只在START→CONFIRMED发confirm_event，不每日重复。A跌回`C<=K_A`只撤A；B跌回`C<=H12`只撤B；另一分支仍有效则保CONFIRMED。
6. 价格跌回某分支高线、但未破P且B的HL基础未被新低/LH破坏时，后来重新站回该分支线即可恢复，不设冷却、不要求多等一次cross或新低。若B_base已被真实LH/非HL清除，则B必须等新确认HL；A仍可直接突破更高修复门恢复。
7. 无新pivot、未破参考线/支撑时保既有结构与权限，不要求每天fresh、不设固定期限。缺C时历史mode可留作memory，但当日I_hold/I_expand=UNKNOWN，不沿用旧CONFIRMED自动授权。单支参考未知按三值OR：A未知且B已知真仍可确认；没有已知真且存在未知时I_expand=UNKNOWN，不可新增。源尺度不可比时封存旧代及旧退出责任，当前权限UNKNOWN；新source只能由其本身合法正event建立新代，不能在不同单位间max或虚构低点/突破。

保持CLOSE得知→后续可用的时钟。全部HL/LH/突破/max选择沿原numeric.compare误差tie规则；支撑用compare<=0，tie保留旧参考来源，不能造成线回撤。旧P的检查只要求有效可比C，不因缺量而跳过；缺量只阻止原量价事件产生，不能豁免旧支撑。

## 4. 与当前E0/I/CP的接口差分

保留原E0事件而不是只认旧base.entered：否则新I失效时旧E0还active，强反弹可能无法再启动。持有支撑用新P；新增结构许可用新I_expand，不能继续仅靠I_hold把MOBILE的buy_allowed一律替换为market_buyable。未来账户若接入，试探事件与成熟新增资格必须分别消费，不在本轮设资金比例。

旧CP输入e0_valid实际是旧I_target，因此原CP不是独立验证。此次只在表中列原CP/原买入，**不按新I重算CP或执行任何订单**；原CP收据在新联合系统是否仍成立是未执行处，不能把信号演绎称为完整策略绩效。

## 5. 7股输出与明确反例

固定展示盈新000620、山东601019、太保601601、海002583及2026半导体金海通603061/捷捷300623/新洁能605111。每股从完整source前缀初始化，只展示既定slice；输出每日C、原event、每个pivot发生日/确认日、L1/H12/L2、K_A及来源/age、P_old/P_new、A/B可用/active、mode、I_hold/I_expand及原因，对照原I/G1/CP/实际入场日期。

反例必须直接展示：深V无HL但突破K_A可由A确认；lower-high背景的小HL若没越H12仍不能B确认；K_A很旧/不存在时START不被封禁而B可独立成立；假突破随后跌回只按当时事实退权，不因日后亏损追溯抹去最初确认。持续单边没有L2时不因B缺失否定A。两路都可能假突破/晚确认，不声称收益。

旧SIGNAL_FREEZE.md只作SUPERSEDED历史，禁止以其OR/AND输出替代V2；当前没有运行过该旧稿的信号轨迹。
