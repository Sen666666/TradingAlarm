# 有限独立静审：公式/时钟相符，EMA影子元数据有错

独立读取FREEZE、kama.py、run_observation.py，并只读原run_v1收据/影子和指标字段。未重新运行KAMA/EMA、前缀测试、合成路径、母体或账户；不是独立数值复现PASS或经济有效性PASS。

- ER窗口正确：第10个close用前10均值种K；第11个close才有11个C/10个差分，首次ER和更新（kama.py:43—50）。分母0置ER0。alpha范围4/961至4/9，逐日映射固定EMA span为479.5至3.5，算术正确；不等于固定真实滞后。
- s在加入当日abs(r)以前，从此前63个连续值取MAD尺度（37—39、59行）。invalid/源变更清暖，不用CP/I重新种K。seed_weight乘积正确表达给定ER路径下该初始K的剩余线性系数，不是全部初期价格影响或统计依赖长度；ready10不代表已忘初值。
- 保护时钟遵守冻结稿：当前原I硬退、旧P判当前C在先；新Q=max(P,I,band)只给下次close；即使Q≥今日C也不倒查今日触线（80—98行）。后续不叠加CPcandidate；KAMA与EMA20同P0/I/band/clock。相对原CP仍混有更新时钟差，不能全归ER。

**具体元数据问题**：shadow的`anchor_seed_weight`（108行）和step的`seed_weight`（97行）对EMA20也取KAMA列；generic `alpha`也一直是KAMA的alpha。指标parquet的`EMA20_seed_weight`/`EMA20_alpha`本身正确，轨迹所用EMA20_proposed_band也正确，故不是EMA计算或退出路径错误，但不能引用EMA影子这些字段作EMA初始化/alpha证据。例如海9/20 K权重2.4277e−85、EMA权重3.2074e−97，影子摘要却给两者相同K权重。应只读正确指标列补报告，不偷改已绑定运行产物。

只读6锚已有steps：首20源观察内KAMA组件退出4/6；EMA20组件1/6，另1/6原I硬退。合计首退4/6对2/6；5锚KAMA早、1锚同日。自然频率在此首批不相同，不能称等频或据此声明ER边际价值。全部最终首退6/6只是吸收结构，不是真实交易频率。6锚来自5源且银重复，不是6个独立样本。

纸面反例（未运行）：强涨ER高、带贴价并已抬P后，单日洗盘只要C≤旧P，ER当天降低也无法撤旧线，随后恢复仍已退；深V如10观察回到旧起点，净位移0而总变差>0，ER0会让恢复初段alpha很慢；持续单向下跌反而ER可接近1。更快跟踪可能保护失败，也可能截断真赢家，不自动分真假。

推广前缺口：shadow公共截止继承原CP pair.common_end_day，且未显式核native.segment_id等于price source；遇原共同horizon因UNKNOWN_HLC终止、但close仍可用于KAMA时，可能只因循环结束标RIGHT_CENSORED。这六锚的common_end全为ORIGINAL_I_INVALID、ever_unknown均False，没有覆盖上述未知分支。原RUN_RECEIPT绑定代码和源，但没有绑定FREEZE.md；本审查绑定当前稿，不能反向补成原运行时paper字节证明。

结论只限：未见这六锚当前合同下的立即致命公式/保护时钟冲突；需纠正EMA元数据引用与等频表述。未完成独立逐数值重算、未知分支/前缀测试、母体频率及效果检验，root不能称这些已独审通过。所有源/产物本线未改。
