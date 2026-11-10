# 同股结构信用：最小接口与原链反例

状态：**纸面候选，未实施、未证明经济有效**。本目录只读真实 No60 源码与已保存原账户，未导入策略、运行模型、账户、回测或改策略。预算是参考授权，保护线及波动压力价不保证可成交损失。

## 1. 唯一采用的身份与重启规则

`market_root` 是真实 E0 `off→on` 的开启观察，不是 I 的开关，也不是一条 E0 正 event。`family_id=(sid, canonical_E0_open_observation_id)`；原已保存的 `stock_structure=sid|segment|root_day` 可作接口输入，但须区分真正开启和数据段首行造成的初始化。source/segment 变更只建立 alias；没有连续性/真开启证明时，不凭新段编号另发信用。原金融 `watch_epoch`、I 开关、CORE/MOBILE、行业 episode/attempt/pool 与 CP ID 均只附着到该 family，不重置其账。

规则只有三条：

1. 同真根下，平仓后重入仍用原 `B,G,H,D`；新 I buy event、新 CP、行业 confirmed、ACT 恢复都不能刷新 B。新 CP 是申请剩余额度的资格，不能当风险货币。
2. 只有**新的真实 E0 根**，且原合法 I/CP 资格成立、同股旧库存/买余量/退出余量/撤单责任全部已实际清除，才允许首次成功 reserve 建立新 family 的 B。新根出现但旧退出未完成，只记录候选根并等待；不得借新根提前释放旧责任。等责任清后仍须当时有原合法信号，不能复用过期证据。
3. `B=0.0025×首次成功reserve所对应signal_NAV`，沿候选原 CORE 风险单位，**不是已证最优值**。第一笔 reserve 前只暂算 B，通过全部原门并真实 reserve 才原子冻结；此前被拒的信号不建 B，root 日不冒充 B 的 NAV 日。首次 reserve 零 fill 后取消，也不重锚 B。旧 family 的 G/H/D、原根与新根的前后继关系全部保留；新根新 B 是公开追加一次风险许可，不能称旧亏已收回或跨根总损失封顶。

同根 flat 且 `D+最小合法新单责任>B`，结果就是**同股该根暂停新风险**。不加新高、支撑、1R、等待或强制盈利毕业门救样本；也不强卖健康持仓。若长期没有新 E0 根，这个暂停可以长期存在。预算与最低手/最低费可能令正探针不可行，不能同时承诺有限累计试错额度和无限正成本尝试。

## 2. D 与 R 的同币账：人民币，实际 receipt 原子更新

为避免 pure mark 风险遗漏尚未实现的本金损失，最终采用本金/当前市值到压力退出的**较大责任**，不把两者相加。以下与 parent 最小卡一致，不是把上轮并发卡悄悄改名。

```text
G_0=H_0=D_0=0
实际买fill：ΔG = −实际增量buy_fee
实际卖fill：ΔG = Σpart[q_part×(实际sell_price−对应remaining_gross_unit_cost)]
                   −该whole receipt的实际sell_fee
随后一次更新：G←G+ΔG；H←max(H,G)；D=H−G

X_l=min(M_l,h_l)×exp(−2s63)×(1−原sell_slip)
R_live,l=max(0, max(K_gross_remaining,l, Q_l×M_l)−Q_l×X_l+F_sell,l)
```

`G` 是净已实现经济损益，不是本金收付；已付 buy fee 当付立即记一次，因此 K 使用 **gross 剩余买入本金，不含已入 G 的 buy fee**。partial 按实际 part 移除对应 gross basis；公司行动后股数、每股 basis、h/M 必须同域转换。现金分配如纳入 G，须沿原实际净入账及 CA 口径另留收据；本目录两例 dividends 都为 0。H 包含初始 0，不能仅用正交易高水位。一个物理卖 fill 的多层 parts 先合成一个 ΔG，不能先记盈利层抬 H、再记亏层造出依赖数组顺序的 D。不同真实 receipt 按保存的真实 journal 顺序更新。

`s63` 沿最小单位风险卡：同段此前 63 个已知日收益绝对值中位数×1.4826，严格排除信号当日，已知尺度保留原地板；缺失不能填地板。2 只是待检压力系数，非置信水平、合法跌幅或损失尾界。h 保实际持有合同：CORE 沿 I，MOBILE 沿原逐层 CP/I 线；信号域到 raw 需真实 factor，不将 stressfloor 当新卖出触发线。`M` 是实际 native mark；不得偷换成 raw OPEN 来凑守恒。

候选买单先投影一次真实 fill 后的 book/mark/费用：未付买费先在 pending 责任中保留，实际 fill 后转为 ΔG 一次，不能同时留在 pending 再记 G。`R_new=q×p_buy−q×X_new+F_sell,new` 仅在同一价格/mark/费用域且满足对应条件时是简式，最终必须按 projected live 公式重算。买费不再重复塞入 R_live。若旧买单未 ACK，余量的 principal-to-stress、未付增量买费和卖费仍占用。

费用：已有 exit order 按真实 order_id、已 paid/accrued 后的**增量**估一次；尚无 exit order 的 live 暂按每个原层一个逻辑卖单，新层另一个。若实际已合并成同一物理卖单，以真实 group 替代旧估算，绝不叠加两套最低费。这个预设会影响纸面容量，不是未来必按层成交的预测。

授权检查为 `D_projected + R_live + R_buy_pending + R_exit_locked ≤ B`；D_projected 只含本次预计实际 fill 的费用，R_buy_pending 只含投影后仍未 fill 余量的未付费，不能两处再放同一费用。同层 live 与 exit affected 集合互斥。exit pending 按请求时锁定责任与当前重算较大者保留，真实 partial 按已成交 parts 释放；cancel_pending 在真实 ACK 前不释放。触线、跌停、停牌、卖不出、mark 低于 h，都不等于责任为 0。浮盈既不进入 G，也不作为负 R 抵扣 D；真实卖出利润可以降低既有 D，超过旧 H 又重设 H，不能把历史累计利润无条件当永久新增 B。

这不是同步共同跳空模型：各层 h 不同，R 是逐层执行参考责任求和。同股、行业原并发/资本/现金门仍按原授权范围全量重算，不能拿同 family 已过 B 代替它们。共同跳空、不可卖延迟或费用变化可以穿透 B；账如实超支，不能 clamp 掉损失。当前原系统 `shared_loss` 的 record_only 也不会自动实现此候选。

## 3. 与 No60 原接口的准确差分

| 原接口 | 精确来源 | 本候选的附加责任 |
|---|---|---|
| E0 root lookup | `joint_v3.py:190–194`，`on & ~on.groupby(segment).shift(...)`，填充至 E0 on | 保留原 token；对 source 段首行另做真开启/连续性证明，不能新 segment 自动发 B |
| I financial epoch | `joint_v3.py:216–219`，key=`(i_target,segment_id)`，变化就自增 | 原 epoch 不改，增加到 family 的 alias；不把这个自增用作清损耗键 |
| 原 I buy | `policies_g1.py:20–34`；E0 shadow/warm 与 entered/fresh | 资格保持；I True 本身不是新信用；退出仍按旧线先检查 |
| 新鲜证据 | `grade.py:24–29`；正 E0 event、S21/S63 确认、running frontier 增加任一 | 均不是经济信用重启；特别是 running extreme 增一点仍可 fresh |
| CORE/mobile | `joint_v3.py:243–256`，mobile freshCP+continuingQ 可独立于 CORE | 角色/退出合同不改，跨角色同 family 共账 |
| 行业 confirmed | `joint_v3.py:175–212`、`budget_v3/model.py:127–152` | 保持行业证据状态，不改成该股盈利/验证完成；也不清同股 D |
| 成交与费用 | `joint_v3.py:101–135`，real reserve/fill callbacks | 必须新增 family 事务账；不能直接复用原只记录 gross loss+fee 的 loss() 当净 G/H |

绝对原码：

- `/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/v3/joint_v3.py`
- `/Users/bytedance/Documents/ChatGPT/money/research_rounds/b5-g1-20261025/code/policies_g1.py`
- `/Users/bytedance/Documents/ChatGPT/money/research_rounds/b5-g1-20261025/code/grade.py`
- 实际 No60 覆盖由 `/Users/bytedance/Documents/Codex/2026-11-04/task/pvr_pool_feasibility/native_adapter.py:11–40` 确认；不得把模板已删的 confirmed60/global3% 门重新写回。

## 4. 两条真实原链：根和损益已核，冻结日期/候选收益未核

原始来源是 No60 BASELINE 的 `2022_2024/pair/B.json.gz` 和 `strong/pair/B.json.gz`，并非 13 条 COMPLETE_ORIGINAL_CHAINS。完整 metadata、原 trades、原 journal 及索引已保存 [ORIGINAL_CHAIN_EXTRACT.json](ORIGINAL_CHAIN_EXTRACT.json)。下列仅汇总原闭合层 cash，不是新账户收益、候选 D 路径或少买收益。

| 股票与原区间 | 原层 | 原闭合净额（元） | 保存的 stock_structure / financial epoch |
|---|---|---:|---|
| 山东出版 2022-08-29—09-16 | 620,628 | −932.94 | `601019.SH\|0\|2022-05-05` / `[0,5]` |
| 山东出版 2023-03-21—06-27 | 1148,1161,1183,1230,1267,1283 | +10,445.94 | **同根、同 epoch** |
| 航天发展 2025-10-29—11-24 | 415,483,485,493 | +2,881.36 | `000547.SZ\|0\|2025-10-22` / `[0,3]` |
| 航天发展 2025-11-25—11-28 | 506 | −2,332.45 | **同根、同 epoch** |
| 航天发展 2025-12-02—2026-01-16 | 548,555,565 | +51,001.61 | `000547.SZ\|0\|2025-11-28` / `[0,5]` |

山东的第一段 mobile 亏损后很久仍同 E0 根；如果当时 D 与最小新责任超过其冻结 B，2023 恢复确可能持续被拒。这是本方案的真代价，不能按平仓 campaign 另发 B 来遮掩。但尚未抽取完整时点 B、逐次 G/H 和当时 R，所以不能断言必拒或哪日拒。航天 11 月的净盈利大部分来自首层，随后多笔加仓亏损；11-24 多层同一个 sell receipt 应先净额聚合，不能用首层 +9,739.03 单独抬 H 后再算其余亏损。11-25 重入仍旧根，债务不得洗；11-28 真新根对应 12 月恢复，提供本规则**允许**新家族重新申请的真实接口案例，但不证明候选能买到原数量、通过资金门或取得原利润。

完整提取也保留航天 2022 root `...2022-08-01` 原层562净 −387.49 与 2024 root `...2024-07-22` 原层1844净 −136.19，防止只选晚期赢家。两原书均无这两例的剩余未平仓层；上述金额不包含未观测候选路径。

## 5. 明确否认的保证与尚缺的验证

真 E0 根比 I 开关稳，但它也可能连续假启动；因此“新根给新 B”仍允许跨根连续亏损，无法声称全序列损耗硬封顶。反过来，若将所有历史 D 永久压在固定 B 内，又可能锁死山东式同根恢复。这个取舍不能由换 ID 消失。frontier+支撑的新重启门是未采用的第二信号政策，不能为救两条案例临时拼进本卡。

本轮已确认的是原根、epoch、交易/费用收据与接口可分离；未证明 D+R 有主亏覆盖、能保赢家或优于单纯并发预算。原历史已用于研究；无样本外结论。尚需独立账本实现审查和在明确授权下的后续验证，本轮不执行它们。
