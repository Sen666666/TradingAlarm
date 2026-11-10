本目录是原生代码的只读反向审查，不是策略实现或回测结果。
优先阅读HELD_I_INCREMENT_CODE_REVIEW.txt；I_CP_USES.json列I/CP四种用途；
SOURCE_EVIDENCE.json绑定代码行、摘录及SHA，OUTPUT_SHA256.json绑定本次交付。

重要既有更正：物理库存FIFO与sell_layers目标策略层的成交分配不同。见
upside_state_v1/code/FIFO_LAYER_CORRECTION.txt及FIFO_LAYER_SOURCE_EVIDENCE.json。
旧OLD_MECHANISM_DEDUP.txt中从physical FIFO推“必留晚坏层”的概括已撤回；不能
仅由同股hard/soft mixed诊断flag认定尾仓不可执行。

本轮未实现HELD_I_INCREMENT、新source、尺寸分配器或资金路径；未加4/6%目标、次数、
EMA/新高/第二证明等门槛，未运行新指标、账户、回测或参数测试。
