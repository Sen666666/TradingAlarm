# 参与度与价格响应研究：独立输入就绪报告

检查时间：2026-10-20T11:00:47.877425+00:00。本轮主线仍为已有14条OHLCV/18固定窗口；仅复制输入、核对哈希并定位其余15条的原始来源，未联网、未采集、未运行模型或账户、未重新画图。

## 已冻结主输入

本轮根目录：`/Users/bytedance/Documents/ChatGPT/money/research_rounds/pv-participation-response-20261020`。`inputs/`含14份字节不变的CSV、18项`cases.json`、`observation-mask-addendum.json`、既有来源清单和旧输入冻结记录。`inputs/manifest.json`逐项记录直接来源的仓库相对路径、SHA256、旧来源关系及字段、日期、行数。代码`code/data_utils.py`按字节复制，保持独立价格时钟；`load_inputs(round_root)`返回`(frames, cases, manifest)`。

- 输入manifest SHA256：`3e71bf6414fa37b431c6cc82ab709f3910cc8ddcc3e5b2025f2ea88f2f4f0d6c`。
- data_utils SHA256：`c2537b9a235c678666f0556b5a227286e78f8e49a7af16ee40363abc84d33cc9`。
- 14份CSV共27,674保存行，按既有独立掩码有27,655合格价格观察；逐份哈希一致，load_inputs验证通过。
- 原15案例涉及12唯一标的；另2条通信指数+黄金GOLD窗口组成18窗口、14唯一标的。全部历史已见，不能称未见验证。
- `inputs/raw-chart-index.json`引用上一轮18张完整OHLCV原图及其数据/图片哈希，逐图文件哈希本次核验一致；没有复制旧results或重新画图。

| 标的 | 保存起日 | 保存末日 | 保存行 | 合格价格行 | 输入SHA256 |
|---|---|---|---:|---:|---|
| USHJ518880 | 2018-07-17 | 2026-10-16 | 2000 | 2000 | `81b982157bc23296b3d7b46f4a909983e45441b7d5cf2839588723ef5ef36c2e` |
| USHJ512480 | 2019-06-12 | 2026-10-16 | 1781 | 1781 | `c1beba864692a65919f14246abcfc243b3e6012861c09640707ee295c2951394` |
| USHJ510300 | 2018-07-17 | 2026-10-16 | 2000 | 2000 | `d58bda48420e58f0ae3b263e43558f8871eafed0a7f888e33a2cfbd2a058ac06` |
| HK00002 | 2020-01-02 | 2026-10-16 | 1674 | 1671 | `3613fcdc18ff5f1238c7575a7610dcf1321415f34b523897fd650850b0fed0c3` |
| HK09618 | 2020-06-18 | 2026-10-16 | 1560 | 1557 | `891ebf91c808069a37d8ad1c743dd58617cd3642c596ae38b3ae451125c28e8d` |
| HK00700 | 2020-01-02 | 2026-10-16 | 1674 | 1671 | `4c9f32f947e755f86e8e39cebe7c734a4b13a457a88cacd314dd8fbc8d2c854d` |
| HK03033 | 2020-08-28 | 2026-10-16 | 1511 | 1507 | `ad7b0cb053c6374f904b0c6f995d518192a1df3083f4b80dfe62b25b21ec0937` |
| HK00101 | 2020-01-02 | 2026-10-16 | 1674 | 1671 | `4a206ade69d8ad38158660ae70cf3a9f635956ba6dae9d00c2d7ecf8998a131d` |
| HK03690 | 2020-04-27 | 2026-10-16 | 1596 | 1593 | `7d78e3bd0ff3bb2d76a6d0a100da0bf0efe5ee29660ad4a3f67b048b2cc06a98` |
| 600919.SH | 2023-09-06 | 2026-10-16 | 750 | 750 | `d7d364cc2ee655319fb0e31c9c45c6a626585744b7fc2096101601ab69d076eb` |
| 600059.SH | 2023-09-06 | 2026-10-16 | 750 | 750 | `68277e7f058a44d195dd4ba85a943c713d49f32c9a4152febe7137fb08ebabad` |
| 600917.SH | 2023-09-06 | 2026-10-16 | 750 | 750 | `200449e3a8c54b6c5134c05b03c024ed56c9d722c53e03e1ebfb5334136c30b6` |
| URFI881129 | 2007-08-01 | 2026-10-16 | 4666 | 4666 | `4ef6020bef8780840c2f2ae82cf3204e05b28c356713c1f73c81b1db425a281b` |
| UZZI000994 | 2005-01-04 | 2026-10-16 | 5288 | 5288 | `782663f3f234ce8e9c6694c1d85e7d198ade4b171f2ba144005660f63d1e9482` |

## 必须继承的数据边界

- 价格时钟由OHLC有限正值、四价几何、observed_bar、synthetic_event_bar及已核实异常定义，不用普通缺量删除有效价格，也不把缺量当缩量。
- 原6条HK的2023-07-17、2023-09-01、2023-09-08为已交叉核实的供应商占位；HK03033额外隔离2020-08-28源异常。
- 半导体512480的2024-10-08有量、H=L，仍保留价格观察，收盘区间位置未知。不能补振幅或假造位置。
- ETF/HK调整四价是收盘后信号研究口径；A股理论除权因子不等于现金总回报。量单位与拆股处理沿用源记录，不能把绝对成交量跨标的混比。
- 通信设备/全指通信是两条主题指数代理，不是已识别的趋势动物截图ETF；历史发布/成分及聚合量边界保持。
- 旧量价原基座只需作为对照时，必须保留其原时钟/输入身份。上轮已记录浮点边界与重建价格微差；不能将其当作量机制增量，也不能宣称原27条与当前14条的每个中间诊断逐字段无条件相同。

## 其余15条：本地源已定位，但未准入本轮

**结论：15条全部有本地独立原始OHLCV及已有数据层处理线索，不需要新增网络采集才能启动有限补齐。当前只能确认“有可核验来源”，不能把它们说成已取得合格调整OHLCV。** 本次仅解析原字段并核对源日期/几何，未重建复权、未生成新CSV、未扩充14条主输入。

有限检查：15份原源日期唯一且有序、四价均有限为正且满足H/L包含O/C；裁剪到原保存signal起止日后，全部日期索引与旧signal一致。此结果不认证公司行为完整性、停牌占位或真实可成交性。

| 标的 | 原始源起日 | 末日 | 原始行/旧signal行 | 零量行 | 正量零振幅行 | 权益来源/主要待核对 |
|---|---|---|---|---:|---|
| HK00005 | 2019-01-09 | 2026-10-16 | 1915/1674 | 3 | 0 | USD分红、滞后USD/HKD、已保存发行人固定汇率记录；不可简化成HKD现金 |
| HK00883 | 2019-01-09 | 2026-10-16 | 1915/1674 | 3 | 0 | 原始JSON内现金/回购注释；HKD现金分派与占位交叉核查 |
| HK02800 | 2018-09-04 | 2026-10-16 | 2000/2000 | 3 | 0 | hongkong-dividend-events.json；现金权益同因子及占位核查 |
| HK02820 | 2019-07-25 | 2026-10-16 | 1784/1784 | 4 | 2 | 旧层未采用额外权息；无注释不等于独立证明无公司行为；零量逐日辨别 |
| HK02845 | 2020-01-17 | 2026-10-16 | 1663/1663 | 3 | 1 | 旧层未采用额外权息；无注释不等于独立证明无公司行为；零量逐日辨别 |
| HK03110 | 2018-09-04 | 2026-10-16 | 2000/2000 | 14 | 37 | 原始JSON分派注释；旧层2018-09-20金额1.51明确修正；14个零量日逐日辨别 |
| USHJ511010 | 2018-07-17 | 2026-10-16 | 2000/2000 | 0 | 0 | 本地Eastmoney权益HTML；独立四价同因子/拆股量调整及与旧close比较 |
| USHJ512010 | 2018-07-16 | 2026-10-16 | 2000/2000 | 0 | 0 | 本地Eastmoney权益HTML；独立四价同因子/拆股量调整及与旧close比较 |
| USHJ512400 | 2018-07-17 | 2026-10-16 | 2000/2000 | 0 | 0 | 本地Eastmoney权益HTML；独立四价同因子/拆股量调整及与旧close比较 |
| USHJ512660 | 2018-07-17 | 2026-10-16 | 2000/2000 | 0 | 0 | 本地Eastmoney权益HTML；独立四价同因子/拆股量调整及与旧close比较 |
| USHJ512690 | 2019-05-06 | 2026-10-16 | 1807/1807 | 0 | 0 | 本地Eastmoney权益HTML；独立四价同因子/拆股量调整及与旧close比较 |
| USHJ512800 | 2018-07-17 | 2026-10-16 | 2000/2000 | 0 | 0 | 本地Eastmoney权益HTML；独立四价同因子/拆股量调整及与旧close比较 |
| USHJ512980 | 2018-07-17 | 2026-10-16 | 2000/2000 | 0 | 0 | 本地Eastmoney权益HTML；独立四价同因子/拆股量调整及与旧close比较 |
| USHJ515030 | 2020-03-04 | 2026-10-16 | 1605/1605 | 0 | 0 | 本地Eastmoney权益HTML；独立四价同因子/拆股量调整及与旧close比较 |
| USHJ515220 | 2020-03-02 | 2026-10-16 | 1607/1607 | 0 | 0 | 本地Eastmoney权益HTML；独立四价同因子/拆股量调整及与旧close比较 |

零量不能沿用一个“全部删除”规则，尤其：
- HK00005：2023-07-17, 2023-09-01, 2023-09-08。其中不是OHLC全等于前收的日期：无。本次没有另源交叉核实，不据此自动删价。
- HK00883：2023-07-17, 2023-09-01, 2023-09-08。其中不是OHLC全等于前收的日期：无。本次没有另源交叉核实，不据此自动删价。
- HK02800：2023-07-17, 2023-09-01, 2023-09-08。其中不是OHLC全等于前收的日期：无。本次没有另源交叉核实，不据此自动删价。
- HK02820：2023-07-17, 2023-09-01, 2023-09-08, 2024-09-05。其中不是OHLC全等于前收的日期：2024-09-05。本次没有另源交叉核实，不据此自动删价。
- HK02845：2023-07-17, 2023-09-01, 2023-09-08。其中不是OHLC全等于前收的日期：无。本次没有另源交叉核实，不据此自动删价。
- HK03110：2018-09-14, 2019-07-03, 2019-11-26, 2019-12-04, 2019-12-11, 2020-01-24, 2020-03-31, 2020-05-13, 2020-06-24, 2020-07-30, 2020-09-11, 2023-07-17, 2023-09-01, 2023-09-08。其中不是OHLC全等于前收的日期：2019-12-11, 2020-03-31, 2020-05-13, 2020-06-24, 2020-07-30, 2020-09-11。本次没有另源交叉核实，不据此自动删价。

若未来独立授权补齐，按同一有限步骤：保留原OHLCV；仅从已保存、带日期的权益重建统一四价因子；明确量拆股口径；核对完整旧close/volume及日期；分离价格时钟和量可用性；验证前缀调整。HK00005与HK03110有额外已记录规则，不能套用最简单模板。失败或无法重建者保留排除原因，不以旧close/raw_close反推任意因子来凑一致。

## 其余15条原始来源身份（只读定位）

| 标的 | 仓库相对路径 | SHA256 |
|---|---|---|
| HK00005 | `TradingAlarm/research/data/hk-stock-raw/hk00005.json` | `07167bfdb94090cc5dc2ef82c4492831f170eea1bda7af84260ec2a3f8456a4a` |
| HK00883 | `TradingAlarm/research/data/hk-stock-raw/hk00883.json` | `4000bde30a8f1f2d534a660c9cdc6cab7ba7e5b7cbc45e76a2e0056ae73aa45c` |
| HK02800 | `TradingAlarm/research/data/tencent-hk02800.json` | `f03da7ee408b7ae5d4f4c4e45b924f8145666480993200d6a4f0f630cd859976` |
| HK02820 | `TradingAlarm/research/data/tencent-hk02820.json` | `e7e4f74dc2bd039faeb0a7a7c754f9d0d9619d67a1959495bf67ec35c9a6d73b` |
| HK02845 | `TradingAlarm/research/data/tencent-hk02845.json` | `3ceb855127dc7fa6efde4ac7d19d147562a309b1ebaad2ba20048110b1a64977` |
| HK03110 | `TradingAlarm/research/data/tencent-hk03110.json` | `7d2dd5210d115587f26beb9701cde1528f9c333907a0cdd3c052b3e79ad4eab1` |
| USHJ511010 | `TradingAlarm/research/data/tencent-sh511010-raw.json` | `c5069af04a7b3dda317a66041f4337e94622821836e1826f82b377378c72696a` |
| USHJ512010 | `TradingAlarm/research/data/tencent-sh512010-raw.json` | `a4ab9f6c77ccaadaa692c5187fb9305d9ddafae9b9796dc0e9ef71a2fd3f0244` |
| USHJ512400 | `TradingAlarm/research/data/tencent-sh512400-raw.json` | `8f28c9902464d968d98a22c4738888e54ac85dbb91d90ec5a678f0f85c377c61` |
| USHJ512660 | `TradingAlarm/research/data/tencent-sh512660-raw.json` | `0763dafa3951f79b2ff97c88abfa9632fd679ece0f2d5fd989c83cd9583a5c29` |
| USHJ512690 | `TradingAlarm/research/data/tencent-sh512690-raw.json` | `f4cb90531fc5efe00aaaa0c656c6e1055237631fcf7e97d119d5b24be928ac59` |
| USHJ512800 | `TradingAlarm/research/data/tencent-sh512800-raw.json` | `b87348a082098f24e494af3695cbe5f4ac73746ba7f51e173bafc2ba29fdfa31` |
| USHJ512980 | `TradingAlarm/research/data/tencent-sh512980-raw.json` | `4f256a41dbab2f0f0ce8eab6007e351ffe856d3e628c49197cbf6f4380b04672` |
| USHJ515030 | `TradingAlarm/research/data/tencent-sh515030-raw.json` | `91058c558dd1b4751b90c5b9657db22985c620ecfc082323e536036f45a9687c` |
| USHJ515220 | `TradingAlarm/research/data/tencent-sh515220-raw.json` | `bc3c269fec0a48469fc8dace0305b0d2c362ad71e131b60b1bf684b3b5fb1dde` |

辅助权益来源与代码仅作为处理出处，本次没有import账户模块或运行loader：

| 文件 | SHA256 |
|---|---|
| `TradingAlarm/research/cross_market.py` | `3a903bce38ffba93469edd7038112ecb28432398213c0d63a2c3acbe87a9ba07` |
| `TradingAlarm/research/data/eastmoney-fhsp-511010.html` | `b05065ec7daa58004142e46c533a9851ebaf33152afd23f1462203352dbf860f` |
| `TradingAlarm/research/data/eastmoney-fhsp-512010.html` | `6266c974a10b1cab3887ebf116dfb4e187073d5bb1ffaac6fb0526c24156c08f` |
| `TradingAlarm/research/data/eastmoney-fhsp-512400.html` | `13c0cc282ee4a2acc892917ca40ac36414c4280727a072c86387478d0671e22a` |
| `TradingAlarm/research/data/eastmoney-fhsp-512660.html` | `5ab2ed6cfb9fbb1dfa245840eb0f459086167124492f03837dc2aed263bb4b08` |
| `TradingAlarm/research/data/eastmoney-fhsp-512690.html` | `3c0707759120ed65d4be300da7a7cfe0631f0574315aa2821a8545a0b38c396d` |
| `TradingAlarm/research/data/eastmoney-fhsp-512800.html` | `f6b0ae9e83d9814edf71b7771b7b855795b6eb125e0d7419af2ff7858cb67b10` |
| `TradingAlarm/research/data/eastmoney-fhsp-512980.html` | `8550dab35af4a107ac254e00c3893cc49dff0756052b70fb7407b9977659ba28` |
| `TradingAlarm/research/data/eastmoney-fhsp-515030.html` | `5df007af7fcfaff09fd8ecdba14bf7a03e2cea2cef1a075ad72da4e4dc2dbbe4` |
| `TradingAlarm/research/data/eastmoney-fhsp-515220.html` | `e1f10fdc12c29db67ff7c87996c27a760a8cf4e941a7b66817ca83c9ce024c16` |
| `TradingAlarm/research/data/hk-stock-pilot/usd-hkd.json` | `98272b15aa1f50dfc262b41920bba34c1f40e4e3021c262b9051b72611f8ca3c` |
| `TradingAlarm/research/hk_cash_annotations.py` | `56479cfc7be8bc7ef0da977b78e6ee1eac627d12e7f60cdfc042e5749d0f3e7a` |
| `TradingAlarm/research/hk_cash_stock_campaign.py` | `f390b1f740e1c1a89ac68cc6daa38ae60030e061d7f39d99559d654d01f58d69` |
| `TradingAlarm/research/hk_extension.py` | `39629557bb9785d85ad2c0e70bdd7b73c8bc4ef67a44d5979660d4010c5e47fb` |
| `TradingAlarm/research/hk_foreign_stock_campaign.py` | `b612c34cf5828debe4da9bb1e7aa183b0c561b96eec1277c5b70af98b0f477c0` |
| `TradingAlarm/research/hk_stock_account_pilot.py` | `e0738158e1d10d5a56ea858a3843fef71779488a4253bc8f51e17433690e320c` |
| `TradingAlarm/research/hongkong-dividend-events.json` | `e6cc8a5edcda5da8d492998bcd0c11c595d692afe99b8d9e25f3b9627619613d` |
| `TradingAlarm/research/portfolio_data.py` | `42a4a04901143eba47c61d1dd9ea9e8d701a027fc4bd191216ac4c9c1f1828a8` |
| `TradingAlarm/research/results/hk-hsbc-dividend-audit/issuer-records.json` | `2b8a7efd89a0a6531cebcb07bc600d7ac41c349956c59285882de11e7cc3d5ba` |

本轮没有将上述15条写入inputs，也没有扩大固定窗口。账户运行0、候选运行0、网络请求0、新增图0。
