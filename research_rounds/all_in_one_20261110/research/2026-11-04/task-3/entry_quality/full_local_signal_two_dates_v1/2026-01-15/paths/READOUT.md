# 2026-01-15 冻结信号的收盘路径

779个事先冻结i_buy证券全部保留，原PVR全部已知。5和20个未来同源有效个股观察均779完整，0删失。

全source日期union共同第5/20端点为2026-01-22、2026-02-12；5观察778只同端点、1只到1月27日；20观察777只同端点、另2只分别到2月25/27日。具体证券见PATH_RECALC_AND_NUMBERS.json；数据缺行不认定停牌、退市或交易限制。

5观察收盘变化中位+2.2139%、均值+2.6175%；499正、278负、2零。20观察中位+0.7899%、均值+3.2659%；419正、360负。

与924/2022同公式：anchor为当日已知qfq收盘，terminal=C_h/C_0−1，MFE=max(0,max(C_j/C_0−1))，MAE=min(0,min(C_j/C_0−1))。有效性严格为有限正close+amount、明确原source和存在的原mask；显式invalid/source变更截断，不跳过，不填缺。5/20是个股有效观察，不是共同市场会话；完整路径允许跨后来I状态，只是价格诊断，不是原持仓/可成交收益。

母体与原PVR排名先于future读取冻结，输入SHAd38790c89ccfbccab64ea6d015a54826ceda93d6bda6df651b8e71b441e238fe。0模型、0账户、未读OPEN。保存LONG_PATHS逐股逐点重算1558个horizon均bitexact。历史ST/halt/limit和源尾原因保持UNKNOWN。覆盖、时钟、原输入与输出SHA见FREEZE.json、COVERAGE_METADATA.json。
