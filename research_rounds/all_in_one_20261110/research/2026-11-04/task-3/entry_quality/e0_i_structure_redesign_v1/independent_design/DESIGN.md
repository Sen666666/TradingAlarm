# E0启动与I结构确认：独立因果状态机草案

本稿是可编码的定义与反例审查，未运行模型、账户、回测或覆盖统计，也未增加资金参数。保留原E0量价反转确认作为START，不用G1暖态资格禁止初始探索。这里的START/CONFIRMED是结构信号状态，尚未接入持仓退出、预算或MOBILE角色。

**先明确原pivot是什么。** 原B5事件使用有效C/V序列的**收盘价极值**，不是日内high/low，也不是居中窗口事后选出的局部极值。每个不可修改的pivot记录：

`(source_segment, kind=L/H, price, occurred_at, confirmed_at, source_event_id)`。

`event=+1`确认一个先前低点L；`event=-1`确认一个先前高点H。`occurred_at=confirmed_pivot_date`，`confirmed_at=事件输出所在CLOSE`，可用时钟为该确认CLOSE完成之后。发生日至确认日前严禁把这个pivot当已知结构。当前CLOSE确认的新L可以参与本CLOSE完成后的状态输出，供下一可执行时点使用；这不是回填到pivot发生日，也不额外拖延一根日线。运行中的extreme只供原E0 kernel使用，不能冒充已确认H/L。

原事件尺度原样保留（同segment的有效C/V事件观察序列，r为log return）：

```
sigma[t] = max(sqrt(sum(r[t-63:t]**2)/63), 1e-8)  # 不含当前
vref[a] = median(V[a-21:a])                     # 极值发生时的过去量基准
activity[a,t] = clip(sqrt(mean(V[a+1:t+1])/vref[a]), .5, 2)
reversal[a,t] = (-direction)*log(C[t]/C[a])*activity[a,t] / (sqrt(5)*sigma[a])
```

按原compare函数，`reversal>=1`才确认反向pivot；sigma与量基准都冻结在原极值anchor。**这是原E0的prior63 RMS尺度，不是CP/PVR的1.4826×median(abs r)，也不是receipt旧scale。** 不再发明第二套pivot、固定百分比反转、右侧n根确认或冷却天数。原启动暖机及量缺失mask也不改。

最小状态为`OFF / START / CONFIRMED`，另有证据位而非资金档位：`HL_valid, reclaim_valid, proof_type, upper_progress(HH/LH/equal/unknown)`。至少保存最后两个已确认L和H（同类型相邻，而非相邻两天）、本次start_id/start_close、冻结H_ref、当前已保护L、最近收复H与原source clocks。所有比较沿用原compare精度规则，无新epsilon。

1. **START。** 任一当前合法原`event=+1`，若旧结构OFF，则建立新start_id；本次确认L成为本次启动低点。允许探索；不要求已有盈利、不要求G1≥2。已处于START/CONFIRMED时的新+event只是新结构证据，不清空已有保护线、失败记录或发放新“初始”预算。START时冻结当时已经确认的最近前高`H_ref`，后来的lower-high不得偷偷下调它。
2. **HL证据。** 本次START后有一个新确认的L2（同日START确认的新L也可），其同类前邻L1已确认、价格L2>L1、当前C>L2，则`HL_valid=true`；结构支持位升至L2。先前两个早已确认的低点不能每天反复作为“新确认事件”重开I。若这是首个可用L，没有L1，则HL未知，不能填真。严格相等只记横向，不叫抬升。
3. **前高收复证据。** 比较用**t−1已知**的H_ref：已在START时，`C[t-1]<=H_ref && C[t]>H_ref`为真正CLOSE cross。另对**本日真正新START**，若`C[t]>H_ref`，以“新E0启动时仍站在已知前高之上”接纳一次reclaim proof，不强求cross恰好和有延迟的E0确认同日，否则会错过先突破、后确认的强反弹。两种reason分别记录，均在当前START输出时才生效，不倒填过去。已在高位且没有新START/cross不能每日制造“重新确认”。H_ref未知则此证据未知。OFF不因普通突破自动凭空产生START；原+event启动与reclaim proof可以同CLOSE输出START→CONFIRMED。
4. **最小OR合同。** 在旧失效未触发、支持L可知且当前C>L的前提下，`CONFIRMED := HL_valid OR reclaim_valid`。分别保留`HL_ONLY / RECLAIM_ONLY / BOTH`，不能将三者统称“已证明完整HH+HL上升趋势”。
5. **持续检查。** 每个有效CLOSE先按旧支持L检查`C<=L`，触破即旧结构失效；不得用本日刚确认的更低L放宽旧边界。新确认HL才上移支持，绝不下移。新确认H只更新HH/LH/equal结构说明：LH表示推进减弱，单独LH不是新收益标签，也不等同已跌破支持。没有新高的观察日不自动失效，不设几日必须创新高。
6. **假突破回落。** 最小可编码选择：已收复H的证据在`C<=该H`时失效；若HL证据及其支持仍有效，则保留HL_ONLY，否则降回START（不永久封锁探索）。这是一条**需要主设计明确接受的语义选择**：零缓冲跌回即取消breakout proof会对普通回踩敏感，不能声称已验证更好；若主设计只允许跌破L才退出，应保留`reclaim_failed=true`诊断而不让该位单独驱动退出。两种不可混写成同一个规则。

旧状态先检查、新证据后登记的单CLOSE次序：

```
old = immutable_snapshot(state_at_previous_known_close)
if source_segment_changed:
    invalidate_cross_segment_proofs_and_emit_source_reset()  # 不伪装成市场下跌
if not valid_price:
    emit UNKNOWN_with_last_known_state()                    # 不确认、不新授信
    stop
old_fail = old.support_L_known and C <= old.support_L
old_reclaim_fail = old.reclaim_valid and C <= old.reclaimed_H
emit_old_invalidation_if_needed(old_fail)                    # 不可被后面撤销
if old_reclaim_fail: clear_reclaim_proof_if_option_6_adopted()
admit_only_the_current_confirmed_E0_pivot()                   # 不读未来pivot
if old_fail: state = OFF; clear_active_proofs_keep_audit()
if state == OFF and current_E0_event == +1: start_new_epoch()
if state != OFF:
    evaluate_new_HL_and_cross_or_new_START_above_known_H_ref()
    ratchet_support_only_upward()
    classify_HH_LH_and_valid_proof_bits()
    state = CONFIRMED if any_valid_proof else START
emit_after_CLOSE_state_and_all_reason/source_ids()
```

同日若“旧边界失效”与“新+event”并存，输出两个不同epoch事件：旧INVALIDATE先成立，新START随后成立；禁止用新信号取消旧退出责任。新START不意味着同日原持仓已卖、现金已释放或已经能再买，实际pending锁仍属于执行层。无需人为固定冷却。`event=-1`是确认此前高点，不等于“当日return<0”；它不会单独强制退出，避免把正常回踩直接等价成趋势终结。若新确认H与已知旧H的cross同日出现，cross仍比较旧H；不得把本日新确认H拿来改写比较基准。

源与缺失：只在同一可比价格单位和source segment内比较。segment变更先清空活动结构、重暖机并保留来源失效原因；不把前段H/L拼入新段。停牌/缺量且价格仍有效时，旧支持可被价格检查；无有效量不制造新E0 pivot。价格缺失时不产生突破/失效结论，也不把未知当可新增。公司行动或价格单位不可比且无当时已知的转换事实时，走source reset/UNKNOWN，不能用未来复权锚消掉断点。

**必须保留的反例与歧义。**

| 因果纸面路径（不是历史回测） | 当时能知道什么 | 最小合同的限制 |
|---|---|---|
| 已确认H1=100；确认L1=80后START；后来确认H2=95；再确认L2=82，确认时C=90 | L2>L1确实成立，但H2<H1、C<95/100 | 用户给定的HL OR reclaim会产生HL_ONLY，却仍是lower-high反弹。若要求“完整上升拓扑”，需另明确HH+HL或收复何高；不能悄悄把OR改AND或宣称HL_ONLY已排除此例。 |
| H_ref=100；C从99→101，下一观察跌回99，支持L=90未破 | 首次cross是真实当时信号，后来回落才能认定假突破 | 当时不可能预知假突破。上述选项6可取消reclaim proof，但其回踩误伤代价未知；不能以事后失败取消当日cross。 |
| H_ref=100；反弹确认lower-high=95，再C从94→96 | 收复95是局部进展，但未收复本次START冻结的100 | 禁止把H_ref动态降为95来“救”确认。若在旧结构失效后的真正新START中选择95为新ref，必须新epoch且保留旧失败，不是旧信号延期。 |
| 已知支持L=90；C收于89，本日同时新确认较低L=85并产生+event | 旧90已破，新+event也是当时可知 | 旧失效先发生；新START可重启，但不能把旧L换85假装原趋势一直未坏。 |
| 新pivot发生于d0、在d3 CLOSE才确认 | d0—d2只能知道developing extreme | 禁止把d3确认低点回填到d0，或用该价格给d1的仓位授权。 |

尚需主设计裁决三点：①“确认”是否接受HL_ONLY，还是只称结构修复，二者不能仅换名字却沿用同一强授权；②前高是本次START冻结最近高、最近主高还是累计高（本文采用前者，无新窗口）；③跌回突破H是否直接令I降级，还是仅记失败并等待L破坏。本文提供唯一可追踪字段和两个明确分叉，不选盈利后补规则。趋势识别有延迟且会被假突破欺骗，这些事实不能靠新资金参数修补。
