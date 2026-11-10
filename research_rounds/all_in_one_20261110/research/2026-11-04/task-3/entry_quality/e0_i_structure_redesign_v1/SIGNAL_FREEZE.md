# E0/I结构候选冻结：只演绎信号，不运行账户

本轮资金方案已撤回。没有启动候选账户、回测、资金候选测试或后台进程；两准备owner均确认没有实现文件。OS拒绝ps，故不作全机进程声明。本件不改原市场数据/原E0事件，不生成交易、仓位、费用或候选收益。

## 1. 原公式与需要修改的含义

原E0以正finite close/volume观察为钟：r_t=log(C_t/C_(t−1))，sigma_t=max(sqrt(sum(r_(t−63:t)^2)/63),1e−8)，排除本日收益；volume基准为此前21个有效量中位数。当前方向d所属ext不断随新极值更新，反转确认用ext时冻结sigma/量基准：

`a=clip(sqrt(mean(V_(ext+1:t))/median(V_(ext−21:ext))),.5,2)`；
`confirmation=(-d)*log(C_t/C_ext)*a/(sqrt(5)*sigma_ext)`。

达到1在t CLOSE发布event=−d，确认ext为低点(+1)或高点(−1)。ext日期不是确认可知日期。保留该量价自适应公式，不加入新的反转阈值。原numeric不是B5 frontier credit；两者不可混同。

当前base E0：先C<=旧floor失效，+event在active时ratchet低点或重新开启，−event本身不关。当前G1_I：新进入需E0/warm>=2+fresh，已活只按E0 off或旧I floor退出；G1转冷不自动退出。CP又把I_target接作e0_valid，故它不构成独立的大尺度趋势证明。

缺陷是把‘局部反转完成’、‘结构已上升’、‘持有/新增权限仍有效’混在一个布尔量中；不是原规则没有任何退出。

## 2. 输入、初始化和两个不同的预注册候选

只用原E0已发布pivot，全部是**close极值**。每个点保存(value_adjusted,pivot_occurrence_day,confirmed_at,segment,event_id)。确认当天收盘之后才能登记；禁止居中rolling极值和将pivot发生日当known日。

每股从其原完整source事件前缀开始递推，再截展示区间；不在2103行展示slice首日静默OFF初始化。source不可比段清空结构证书并标UNKNOWN；缺C/事件不补造False转折。原E0 RMS/ext量基准未持久化，记录NOT_PERSISTED；新结构计算只依赖原已发布事件，不用CP MAD补它。

两个候选分别输出，不按结果选最优：

- **U_OR（用户逻辑参照）**：确认凭证为相邻已确认低点抬升，或收盘收复事先已确认前高。
- **S_PAIR（主动提出的更严格结构定义）**：HL只称REPAIR；必须有HL且收盘超过冻结关键前高才称CONFIRMED。为了不把下降阶梯最近的更低高点自动变成更低门槛，关键前高为START时此前最后两个已确认高点的max，START期间不因lower-high下调。它是两个摆动的有限记忆，不是全历史最高价；不足两个高则暂不能S_PAIR确认。严格性可拒一部分lower-high反弹，但会迟认深V/无回踩单边行情，不能称收益更好。

## 3. 共同状态与转移：OFF/START/CONFIRMED

字段：mode、generation、support、start_at、key_H及其已知日、latest_H/L列表、fresh_HL_certificate、certificate_origin、exit_event、launch_event、confirm_event、downgrade_event。原E0+event而非旧base.entered是启动证据，避免旧E0仍active时新I无法重启。

每个有效CLOSE按以下固定顺序：

1. **先检查t−1已知support**。若已有mode且C_t<=support_old，旧generation失效，发support_exit，清旧HL确认凭证。该退出不能被本日新线/新pivot回写抹掉。
2. 读取原E0本日event；只在本日收盘登记该pivot及confirmed_at。价格重夺使用的高点只能来自t−1已发布列表，不能用今日刚确认的高点当今日突破证据。
3. 若OFF且本日event=+1，建立新START/generation，support=本次刚确认低点，发launch_event；U_OR key_H取此前最后一个已确认高，S_PAIR取此前最后两个已确认高的max。旧generation刚退出也允许发布新的START，但两代事件分别保留；这不表示未成交旧仓已可抹去或同价新买。
4. 若已START/CONFIRMED且本日+event，比较相邻两个真正已确认低点（不是maxfloor）：newL>prevL则登记本日新HL凭证、support=max(old,newL)；否则发结构退化、mode回START、HL凭证清空，support不放低。
5. 若本日−event且newH<prevH，则发lower-high退化，mode回START，HL凭证失效，重新冻结key_H（U_OR为本日之前高点与新高的max；S_PAIR为最近两已确认高的max）；不得靠下调前高立即恢复CONFIRMED。等高不是lower-high，保原证书并单列无进展标记。
6. **U_OR晋级**：本次generation有本日/其后未失效的新HL凭证，或C_t>key_H且该H在t前已确认。**S_PAIR晋级**：新HL凭证有效且C_t>key_H。这里‘收复’用当前已在其上方的状态，不硬要求START当天刚cross；避免E0确认滞后于真实价格突破而锁死。满足时发confirm_event并记录依据。
7. 没有新pivot/破坏时保持既有CONFIRMED，不要求每天fresh，也不设持有超时/固定冷却。未曾发生reclaim的HL-only证书仍需后续LH/LL/支撑破坏检查；发生reclaim后若C_t<=该key_H但仍高于support，发failed_reclaim并退START、清HL凭证，等待真正新HL或重新收复key_H，而不是机械等天数。

同日support破坏后新+event：旧exit保留、新START单独generation；新高参考只能用t−1已知高。若本日发生lower-high/非HL退化，不得仅用被清掉的旧HL凭证复活；真正价格重夺冻结key_H仍可恢复。原价格/事件只读，不依据未来盈亏改变任何分支。

## 4. I输出必须拆开，不能只换名字后继续原MOBILE通道

`I_hold = mode in {START,CONFIRMED}`；`I_expand = mode==CONFIRMED`。START允许启动试探资格（launch_event），结构失效发support_exit；退化仅撤趋势新增许可，现有持仓的最终处理此轮只输出事件，不生成数量或卖单。

将来若接账户，原CORE接启动试探事件，MOBILE需真实新CP且I_expand；不能再把buy_allowed一律替换market_buyable后忽略这个结构许可。G1保留为独立诊断，不用资金参数冒充结构确认。原CP只有对照，不按新I重算其锚/收据；因此本轮不能声称获得完整新E0/I/CP联合策略。

## 5. 固定展示路径与反例

盈新000620至2022-02-08；山东601019至2023-06-30；太保601601至2024-10-10；海002583至2024-11-27；半导体金海通603061、捷捷300623、新洁能605111至2026-06-30。金海通胜、捷捷/新洁能败均来自已保存已平链，只作反例选择，不使用收益作为状态输入。每股全前缀初始化，展示原事件、pivot双钟、L/H、key_H/support、两mode、I_hold/I_expand和原因，原CP/原入场只作对照。

逻辑反例固定保留：L80→H95→L82在更早H100之下，U_OR的HL分支可能误认成熟，S_PAIR仍需越100；99→101越H100再落99导致failed reclaim，不能因后来看失败而改最初信号；强V低点更低但快速越高可被U_OR确认、S_PAIR仍START，启动参与不禁止但成熟授权可能明显迟。

本轮只做逐日信号演绎及因果前缀核对，不写账户、不回测收益、不选择参数、不用事后高点。所有改动待真实路径反例和独立审查后由用户判断。
