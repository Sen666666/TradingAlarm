# 2022-01-24 冻结信号的收盘路径

177个事先冻结i_buy证券全部保留：175可排名，2个PVR_UNKNOWN维持缺失排名。5和20个未来同源有效个股观察均177完整，0删失。

全source日期union共同第5/20端点为2022-02-07、2022-02-28；176只实际同端点，1只延后至2022-02-10、2022-03-03。具体证券见PATH_RECALC_AND_NUMBERS.json；这只是数据缺行代理，不认定停牌、退市或交易限制。

5观察收盘变化中位−5.6738%、均值−6.0493%；39正、138负。20观察中位−2.3155%、均值−0.6638%；70正、106负、1零。2个PVR未知仍在分母，后续按既定UNKNOWN桶汇总，不赋造rank。

与924同公式：anchor为当日已知qfq收盘，terminal=C_h/C_0−1，MFE=max(0,max(C_j/C_0−1))，MAE=min(0,min(C_j/C_0−1))。有效性严格为有限正close+amount、明确原source和存在的原mask；显式invalid/source变更截断，不跳过，不填缺。5/20是个股有效观察，不是共同市场会话；完整路径允许跨后来I状态，只是价格诊断，不是原持仓/可成交收益。

母体与原PVR排名先于future读取冻结，输入SHA1ef967d79503448fe57b86434de3dbe0cefce1a866a30798558335fb680aa314。0模型、0账户、未读OPEN。保存LONG_PATHS逐股逐点重算354个horizon均bitexact。历史ST/halt/limit和源尾原因保持UNKNOWN。覆盖、时钟、原输入与输出SHA见FREEZE.json、COVERAGE_METADATA.json。
