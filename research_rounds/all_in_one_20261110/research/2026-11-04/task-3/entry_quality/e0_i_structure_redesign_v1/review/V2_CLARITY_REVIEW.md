# V2 独立薄审：核心因果定义通过

只审当前 `SIGNAL_FREEZE_V2.md` 文本与原源时钟；未运行候选信号/账户，不审收益。本件不覆盖旧预审收据，也不将旧 U_OR/S_PAIR 或 source_logic 的 AND 假设视为主规则。

V2 已把两个独立分支写清：A 是 START 前已知关键高的直接收复，START 日已经站上也可确认；B 是相邻 L1—H12—L2 的 HL 加收复 H12，不要求 A 的远端关键高。两者都不是 bare HL，最终按 OR。相邻 pivot 发生日与 confirmed_at 分开；当日新高不能偷换为此前高；A 的初始锚取规则确定，lower-high 后修复门只能提高，不能追着更低峰降低。

旧 P 先判破坏，本日新 L 随后 max ratchet；同代 P 不回撤。新 START 可以同日另开 generation，但旧 exit/P 需封存。A/B 各有参考和 active；一个退回其高线，只撤该分支，另一分支有效仍可 CONFIRMED。无新事件不自动失效；基础仍合法则可重新站上恢复，基础已被新非HL/LH破坏则按卡等待真实新证据。以上更新顺序没有发现前视或循环自证的必然错误。

曾提出的以下两项澄清，已亲读并确认合入当前 V2：

1. **UNKNOWN 是当前可用性。** 缺 C/不可比段时可以保留 last-known mode 供审计，但不能把旧 CONFIRMED 输出成当前可新增。当前 I_expand 应 UNKNOWN/不可授新资格；不可比段更不能延续跨段参考。三值 OR 应保留：A 未知但 B 已知 true，整体可 true；两路都未知或 false/unknown 时，不凭 unknown 授权。这里是缺失语义，不是增加趋势门。
2. **KA 初始与修复来源分开。** START 冻结的 initial_KA 确实来自 START 前；LH 以后提升的 current_KA 可以来自 START 后、但在本次修订前已确认的 H_prev。应保存 initial/current/reference event/confirmed_at/updated_at，避免把后者仍误称 START 前锚。提升不得通过将 KA 变 UNKNOWN 后重新取较低 H 来绕过 max。

另已明确 OFF 不因普通突破自动 START、同一 pivot 只登记一次，以及源不可比时封存旧代/退出责任。这些属于输出澄清，未要求新机制、参数、窗口、等待或再次确认。冻结稿当前无剩余文本阻碍；实现和信号输出尚未审。若文档再变，当前收据只绑定所读版本，需对新字节另行确认。

已知经济限制继续保留：远端 KA 可长期压住 A，但 B 独立可行；A/B 都可能假突破或晚确认；START 试探与 I_expand 不是资金数量。新 I 未重算 CP，原 CP 只作对照；同日新代 I_hold=true 也不表示旧退出已成交/现金已释放。七股完整前缀的实际 trace 与 prefix 检查仍待提交，不能将本次静态通过称为完整新策略验证。
