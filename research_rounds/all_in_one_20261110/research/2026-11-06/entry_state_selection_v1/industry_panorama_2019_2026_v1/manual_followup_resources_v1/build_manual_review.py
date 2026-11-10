import pathlib,json,hashlib,pandas as pd,numpy as np
O=pathlib.Path(__file__).parent;P=O.parent
names='小金属 非金属材料 金属新材料 塑料制品 油气开采及服务 橡胶制品 农化制品 化学原料 化学制品 化学纤维 石油加工贸易 种植业与林业 农产品加工 建筑材料 环境治理 环保设备 电力 燃气 港口航运 公路铁路运输'.split()
a=pd.read_csv(O/'AUXILIARY_130_REVIEW_INPUT.csv').set_index('record_id',drop=False);m=pd.read_csv(O/'MERGED_CYCLES_RECOMPUTED.csv').set_index('record_id',drop=False);c=pd.read_csv(P/'COVERAGE_90.csv').set_index('name');d=pd.read_csv(O/'DAILY_PATHS_20.csv',parse_dates=['date']);prices={s:z.set_index('date').close for s,z in d.groupby('sector')}
# The following prose and ratings are manual decisions made after reviewing all four daily charts,
# all 130 auxiliary records, month-end paths for every year, and adjacent-bridge values.
# No return/MDD threshold classifies these rows and no ranking/extraction algorithm chooses them.
decisions='''
A0398|普通或可错过|2018低点至2019春普遍修复，随后回吐32.6%并长期整理；不是后续2020主升的同一上升段。
A0399|普通或可错过|2019年底短反弹仅到2020年初，之后回到更低的2020年4月底部；不以30%触发晋级。
A0400|重点候选|2020年4月重建底部后至2021年8月形成持续抬高并加速主升，2022各反弹均未超过该主峰；19/20上涨且中位169.8%，固定池支持较广。
A0401|普通或可错过|2022年初为旧主峰后的短反弹，结束后再跌35.3%；不作为新增主行情。
A0402|普通或可错过|2022年4月急跌后的广泛修复有实质幅度，但7月峰仍低于2021主峰，随后下降延续到2024；保留次级机会。
A0403|普通或可错过|2022年底至2023初短修复，未改变中期下降路径；不单因涨20%提升等级。
A0404|普通或可错过|2024年2月第一轮修复后再退28.6%，保留为筑底前波，不把4月峰当2024至2026整轮终点。
A0405|重点候选|2024年7月二次底部起跨2025至2026年3月主峰，后续6月峰略低且7月再大幅回撤；20/20上涨、中位272.8%、top3占33.5%，不依赖一两只。
A0406|普通或可错过|2026年3月下跌27.4%后的修复虽强，6月峰仍略低于3月且随后再跌32.9%；是高位反复，不另算新肥尾。
A0407|普通或可错过|2026年7月底后短反弹，8月峰明显低于3月和6月，且截至观察末再次下行。
A0370|普通或可错过|2018底至2019春修复后回撤29.6%，之后2019夏重新筑底；仅4个已知成员，不能用反弹幅度代替广度。
A0374|普通或可错过|2023年末反弹未越过2022主峰，指数43.1%而固定池中位仅12.4%，随后快速回落；不晋级。
A0375|普通或可错过|2024年2月反弹后9月再创新低，和后续大主升分为筑底前波与重启主段。
A0376|重点候选|2024年9月更低的二次底部之后持续跨年上行，2026年6月主峰后回撤39.0%；7/7上涨、中位410.8%，但7/17覆盖不能外推历史全行业。
A0377|普通或可错过|2026年7月底深跌后的修复，9月高点仍比6月主峰低22.9%，不延长原主峰也不另作重点。
A0054|普通或可错过|2018底至2019春修复，其后持续回落至2019年11月；6只端点已知、覆盖有限，后段独立重建起点。
A0058|普通或可错过|2022年底至2023初反弹仍低于2022年8月主峰，后续继续盘落；不单列为主周期。
A0059|普通或可错过|2023年末弱修复，2024年初迅速回撤34.1%；仅属下行过程的短波。
A0060|普通或可错过|2024年2月修复后9月再探，未形成持续突破；作为后续长行情背景，不和主段收益相加。
A0504|普通或可错过|2018低点至2019春普遍反弹，后续回退21.0%并再筑底；不是独立的持续主升。
A0507|普通或可错过|2022年深跌后的修复全池11只上涨，但峰值仍低于2021主峰，后续2023至2024再下降；保留广泛次级反弹。
A0508|普通或可错过|2022年10月至2023年2月第二次修复仍未过前峰，之后回撤42.1%；不把两次反弹重复升格。
A0509|普通或可错过|2024年第一波修复指数45.7%而成员中位17.3%，随后9月再探；仅作筑底前波。
A0510|重点候选|2024年9月二次底部至2026年6月高点持续跨年抬高，11/11上涨、中位347.6%；top3达68.1%且只覆盖11/78，必须限定为固定池表现。
A0511|普通或可错过|2026年7月底25.8%回撤后的反弹，9月仍低于6月主峰8.4%，属于高位次级修复。
A0031|普通或可错过|2019春反弹后反复下行到2020至2021底部，49.4%上涨没有转化为持续行情。
A0032|普通或可错过|2019年底至2020年初短反弹，之后回撤26.1%并创新底；不晋级。
A0033|普通或可错过|2020年5月至9月筑底试探，2021年1月几乎回到原低位；主升从后一底部单独观察。
A0034|重点候选|2021年1月底至2022年3月形成持续抬高后尖峰，7/7上涨且中位43.2%，保留为次于2024至2026的重点价格周期；尖峰和小覆盖限制结论。
A0035|普通或可错过|2022年4月回撤34.7%后的缓慢恢复虽8/8上涨，中位53.9%，但2023年10月仍未越过2022尖峰，属于较有广度的恢复段。
A0036|普通或可错过|2024年2月至4月反弹仍未有效超过旧峰，随后9月重新回落；作为后续主段背景。
A0037|重点候选|2024年9月重启后2025抬升、2026初加速至3月尖峰，8/8上涨、中位78.8%；指数180.2%明显强于中位，且峰后已跌44.3%，不能称普遍同幅暴涨。
A0038|普通或可错过|2026年6月底大回撤后的短修复，仍离3月主峰约30%；不算新一轮大行情，截止日只是观察终点。
A0512|证据不足|指数2019春反弹可识别，但全固定池仅1只、现成员22只，1/1和100%top3没有行业广度证明力。
A0515|证据不足|指数2023年末短反弹且随后急跌，固定池仅1只，无法据该股判断行业参与面。
A0516|证据不足|2024年第一轮修复后8月再低，只有1只成员证据；保留价格阶段，不评为广泛行业行情。
A0519|证据不足|2026年7月至9月次级反弹，固定池仅1只且个股8.8%弱于指数22.6%；不外推行业。
A0493|普通或可错过|2018底至2019春广泛修复后回撤31.1%，2020年2月重新筑底；单列普通反弹。
A0496|普通或可错过|2024年2月至5月修复后7月再探，尚非连续主升；不与后续长周期重复相加。
A0497|重点候选|2024年7月二次底部至2026年3月主峰跨年抬升，21/21上涨、中位144.1%、top3占30.7%，固定池参与较广；峰后回撤32.4%。
A0498|普通或可错过|2026年7月深跌后的修复，9月仍低于3月峰16.5%，成员中位15.8%；不晋级。
A0039|普通或可错过|2018底至2019春普遍恢复，后续回撤29.4%并到11月筑底；不与2019至2021主升拼成一条收益。
A0040|重点候选|2019年11月底部起步，2020震荡并未破坏底部，2021年9月形成主峰；13/13上涨、中位201.8%，随后下降至2024，边界不按年底切割。
A0041|普通或可错过|2022年4月底反弹后8月峰明显低于2021高点，成员中位仅21.0%，随后继续长期下降。
A0042|普通或可错过|2024年2月至5月首轮修复后9月再探，不能把局部峰当新一轮终点或重点机会。
A0043|重点候选|2024年9月底部重启，跨2025延伸到2026年3月，14/14上涨、中位102.7%，峰后回撤27.3%；日线支持完整上升周期。
A0044|普通或可错过|2018底至2019春反弹后8月再筑底，和后续持续跨年周期分开；虽广泛但属于初始修复。
A0047|普通或可错过|2024年2月至5月修复未持续，9月再跌后才形成主升；不把40.4%自动定为重点。
A0048|重点候选|2024年9月至2026年2月形成持续抬高，29/29上涨、中位95.2%、top3占24.3%；固定池内扩散较充分，不能等同183只历史成员。
A0499|普通或可错过|2018底至2019春修复后长时间回落，2020年2月重建底部；仅4只端点可知，普通波段。
A0500|重点候选|2020年2月至2021年9月主升持续，5/5上涨、中位119.8%；主峰后下降30.2%再有恢复，后者没有突破主峰，保留独立主段并明确小覆盖。
A0501|普通或可错过|2022年4月至2023年2月恢复段终点仍低于2021主峰5.4%，之后再大幅下降；不升格为新主升。
A0502|普通或可错过|2024年2月至5月修复后回撤26.8%再筑底；保留为后续行情背景。
A0503|重点候选|2024年9月至2026年5月延续上行，6/6上涨、中位132.5%；只知6/8固定池端点及8/29现成员，广度只能限定该池。
A0475|普通或可错过|2019春反弹指数45.7%而成员中位23.3%、top3占75.8%，随后退回2020年5月底部；不算广泛主行情。
A0479|普通或可错过|2024年第一轮修复成员中位仅8.4%，随后9月再探；只算筑底反弹。
A0480|重点候选|2024年9月二次底部至2026年3月新主峰，7/7上涨、中位77.1%；覆盖7/27且top3占61.9%，只支持固定池较普遍获益。
A0481|普通或可错过|2026年7月至9月恢复仍明显低于3月主峰，22.0%只够称次级反弹。
A0001|普通或可错过|2018底至2019年6月上升幅度可观，但4/5端点已知、仅覆盖5/29现成员；先保留有限样本价格机会，不外推全板块。
A0002|普通或可错过|2019年底至2020年初短反弹，随即回到更低的2月底部；不作独立重点。
A0003|重点候选|2020年2月至8月形成清晰主升，5/5上涨、中位67.8%；是固定小池的较普遍机会，只有5/29覆盖，不能称历史全行业。
A0004|普通或可错过|2020年11月至2021年1月为主峰后的反弹，终点仍低于2020年8月峰，随后回落23.2%；属于高位箱体波动。
A0007|普通或可错过|2024年2月至3月短修复，成员中位8.5%、top3占95.0%，之后7月再创新低，价格与成员并不同幅。
A0008|证据不足|2024年7月至2026年3月指数长升130.7%，但5只池中top3占96.4%、中位仅43.1%且池仅5/29；无法据此认定行业广泛肥尾，保留重点价格观察。
A0009|普通或可错过|2026年7月至9月强反弹接近但未越3月主峰，之后再次回落；中位30.3%支持短修复，不新增主周期。
A0018|重点候选|2018年10月至2019年4月明确上升，5/5上涨、中位157.4%；作为较强首轮价格机会保留，但5个端点对43现成员覆盖很小。
A0019|重点候选|2020年2月至8月第二次主升峰值显著抬高，5/5上涨、中位115.2%；与2019之后长时间回调分开，仍只支持固定小池。
A0020|普通或可错过|2021年7月至2022年8月回升仍低于2020主峰，只有3/6上涨、中位8.6%、top3占100%；指数35%不等于成员普遍获益。
A0021|普通或可错过|2024年2月至5月修复后9月再低，27.0%不足以表明新主升已成；7/7端点上涨仅支持当段。
A0022|普通或可错过|2024年9月至2025年11月有连续恢复，但行业70.0%、成员中位39.4%、top3占71.3%，且随后32%回撤；保留次级长波，不和高广度翻倍主升混称。
A0023|普通或可错过|2026年6月至9月反弹仍低于2025主峰，属于大回撤后的普通恢复。
A0063|普通或可错过|2018底至2019春反弹后回撤23.5%，8月重新起步；保留早期修复。
A0064|重点候选|2019年8月至2022年1月完整跨年主升，13/15上涨、中位131.8%，中途2020至2021平台不按年份截断；之后各恢复未越主峰。
A0065|普通或可错过|2022年4月至6月弱恢复未超过1月主峰，后续持续下行到2024；成员中位20.8%，不晋级。
A0066|普通或可错过|2024年2月至5月第一轮修复仅23.1%、成员中位9.6%，9月再低，不能当新主周期。
A0067|重点候选|2024年9月至2026年2月持续跨年上涨，16/16上涨、中位110.5%；top3占56.0%、仅17/73覆盖，不能声称全行业同幅。
A0482|普通或可错过|2018底至2019春修复后长时间横向反复，未建立持续上升结构；48.1%本身不是主行情判据。
A0483|普通或可错过|2019年6月至7月仅一个月的短反弹，未过4月峰，随后继续下行；不升级。
A0484|普通或可错过|2020年2月至9月反弹后回撤30.6%，中位20.5%并未显示广泛大行情；保留普通恢复。
A0485|普通或可错过|2021年2月至2022年1月广泛恢复但峰值仅略超2020，随后回撤30.8%；虽17/17上涨，仍属多年横盘中的独立反弹。
A0486|普通或可错过|2022年4月至2023年8月缓慢修复未越旧峰，中位15.0%、top3占72.7%；指数与成员获益都不足以晋级。
A0487|普通或可错过|2024年首轮反弹中位10.6%，9月再探；只作后续主升背景。
A0488|重点候选|2024年9月至2026年5月由低位持续上升，21/21上涨、中位66.6%；相对前期横盘有清晰重启，但21/111固定覆盖很低，不能称历史全体。
A0662|证据不足|2019春指数反弹清晰，但固定池只有2只、现成员30只，2/2不能支撑行业广度。
A0663|证据不足|2019年6月至7月两周短反弹且未过旧峰，固定池仍仅2只；无广度结论。
A0664|证据不足|2020年2月至8月反弹，固定池仅2只且路径内MDD近20%；不能以2股收益代表行业。
A0665|证据不足|2021年2月至12月指数45.7%，仅1/2上涨且中位2.9%；固定池少且分化显著。
A0666|证据不足|2022年4月至2023年2月指数恢复，只有1/2成员端点可知；更不能推断全行业。
A0667|证据不足|2024年初修复后再探底，2只中位7.9%远低于指数35.7%；证据不足。
A0668|证据不足|2024年9月至2026年5月指数149.8%的跨年长行情真实，但2/2上涨和中位201.3%只是两股统计；2/30覆盖不能认定广泛行业行情。
A0669|证据不足|2026年7月至9月修复未越主峰，2只中位12.5%；只能保留价格阶段和样本限制。
A0265|普通或可错过|2018底至2019春普遍恢复后回撤26.9%，2020年2月重新筑底；不能与后续主升重复计算。
A0268|普通或可错过|2024年2月至5月广泛修复后9月回落22.3%，中位25.9%；作为二次底部前波。
A0269|重点候选|2024年9月至2026年6月持续抬高，55/59上涨、中位65.4%、top3占25.1%；不是少数电力个股拉动，但59/61端点和61/110池覆盖仍非历史全体。
A0270|普通或可错过|2019春短反弹后回到低位，只有4个端点可知，普通修复而非持续主升。
A0271|普通或可错过|2020年2月至8月反弹后2021年2月几乎回到原底，不能以28.9%触发视作主行情。
A0272|普通或可错过|2021年主升段相对短且峰后回撤32.8%，其后2022峰也未创新高；4只样本仅支持一次普通恢复。
A0273|普通或可错过|2022年4月至8月反弹没有超过2021主峰，此后到2024仍长时间平台；不升级。
A0274|重点候选|2024年2月起的低位平台经9月突破并连续延伸至2026年3月，6/6上涨、中位123.0%；top3占85.3%且6/27覆盖，定为有限固定池重点候选而非全行业证明。
A0275|普通或可错过|2018底至2019春恢复后回撤31.5%，2020年2月独立筑底；保留普通反弹。
A0276|普通或可错过|2020至2022年慢上行实际存在，但19/20上涨不等于同幅：中位30.4%、top3占58.7%；随后17个月调整，不把少数航运巨涨代表整个港口航运。
A0277|重点候选|2024年2月至2026年3月持续跨年抬升，24/24上涨、中位57.3%、top3占31.1%，固定池扩散较早一轮充分；指数83.6%不是逐股相同收益。
A0278|普通或可错过|2026年6月至9月回升仍低于3月主峰，成员中位19.7%；普通恢复，不延伸原上升终点。
A0279|普通或可错过|2018低点至2019春恢复后回撤23.7%，2020年3月重建低位；不并入后续五年慢行情。
A0280|重点候选|2020年3月至2025年11月完整慢上行，日线中没有足以切成独立新主升的长期跌势，10/11上涨、中位95.4%；这是五年多累积行情而非短期暴涨肥尾，2026下行已单独注明。
'''
D={}
for line in decisions.strip().splitlines():
 k,priority,reason=line.split('|',2);assert k not in D;D[k]=(priority,reason)
merge_decisions={
'RM01':('证据不足','2019年8月底部到2022年8月最终高峰合为长周期。2020年2月至3月24.7%下挫之后低点仍高于2019底，2022年32.2%深回撤后8月再创新高；将三个机械段视为同一上升及高位再冲的包络，2023至2024随后进入持续下降。长周期本身+345.6%明确，但端点K从子段5至6缩成4，top3占97.4%，不足证明全行业广泛肥尾。'),
'RM02':('重点候选','2019年11月启动到2022年8月最后新高为长周期包络，2020年疫情回撤及2022年深跌不按20%机械切断。必须同时显示2022年MDD−42.1%，这是含大幅中断的两级主升，不能暗示可轻松一直持有；2023至2024逐步下降使终点有后验支持。6/6上涨且剔除top3后均值仍89.2%，仅支持固定池。'),
'RM03':('重点候选','2024年9月底部后的长升穿过2026年2月局部峰，3月仅24天调整23.3%后6月再创新高4.4%，终点延至6月而非再生成一个独立肥尾。随后跌33.4%支持高位转折；按新端点重算，10/10上涨、中位212.0%。'),
'RM04':('重点候选','2019年8月至2021年9月统一观察，2020年12月至2021年2月20.4%调整只是高位整理，随后主峰再抬高14.5%；不把机械阈值附近一刀切成两次主行情。6/6上涨、中位224.2%，但只覆盖11/78现成员中的6个端点，外推弱。'),
'RM05':('证据不足','2019年8月至2022年8月连续上升及最后再冲合为价格长周期，2022年35.7%深回撤必须保留，随后8月高点比2021峰高3.1%并进入长期下降。池只有1只，不能把该股涨104.2%当行业广度。'),
'RM06':('证据不足','2024年8月二次底部至2026年1月为统一主升；2025年3月至4月20天的20.1%回撤后快速恢复并继续新高，不独立成两轮。指数+132.6%可描述，固定池1只无法判行业参与面。'),
'RM07':('重点候选','2020年2月至2022年7月完整主升，2021年9月至11月约20.1%调整后再创新高14.2%，不机械切断。20/20上涨、中位264.4%、剔除top3后均值226.5%；但全路径仅13，价格端点广度不等于20只全程可交易。'),
'RM08':('重点候选','2019年8月至2022年8月合为完整主升和高位二次新高；2022年4月的27.7%回撤是必须暴露的中断，8月比2021主峰再高1.4%，随后2023至2024持续下降。新端点为21/24上涨而非子段全涨，防止沿用子段广度夸大。'),
'RM09':('重点候选','2020年2月启动，2021年12月峰后回撤30.5%，2022年8月重新略创高0.7%，统一列主升及高位再冲包络，不能把两个20%机械段各称独立肥尾。48/51上涨、中位63.9%、top3仅19.5%；全路径36/51，不能当完整历史全体。'),
'RM10':('普通或可错过','2020年5月至2023年2月为一次主升后的高位反复包络，2021、2022、2023峰几乎同高，不把后两次反弹变成新增主行情。新终点虽指数+80.2%，成员中位仅51.1%、top3占75.1%，剔除前三均值29.9%；原2020至2021阶段更强但后续明显分化，整体不优先。'),
'RM11':('普通或可错过','2021年2月至2023年8月合成高位箱体恢复段。2022年4月6天跌22.4%后反弹，两个机械段峰值仅小幅抬高，均未形成相对2020主峰的有效趋势突破；新端点仅3/5上涨、中位0.11%、剔除top3均值−6.2%，不是广泛行情。')}
phase_notes={
'A0371':'2019至2020启动子段，疫情回撤后保留在RM01，不单独重复计数。','A0372':'2020至2021为RM01主升核心；子段5/5与长周期4/4的样本不相同。','A0373':'2022年深跌后的最后新高并入RM01；其6/6统计只属于子段。',
'A0055':'2019年底启动和2020年2月局部峰并入RM02。','A0056':'2020至2021主升核心并入RM02，不能漏掉其后的42.1%回撤。','A0057':'2022年反弹至最后新高纳入RM02，10/10是子段而非长周期样本。',
'A0061':'2026年2月为RM03中途局部峰，后续6月更高，故不截断。','A0062':'2026年3月至6月是RM03后段再冲，不另算独立重点。',
'A0505':'2019至2020上升第一段归入RM04。','A0506':'2021年在短暂整理后再创新高，是RM04延续。',
'A0513':'2019至2021主升归RM05，成员池只有1只。','A0514':'2022年反弹再创新高归RM05，35.7%中断不能省略。',
'A0517':'2024至2025首段归RM06，2025年3月不是整轮终点。','A0518':'2025年4月后继续上升归RM06，仍无行业广度证据。',
'A0494':'2020至2021主升核心归RM07，2021年9月不是完整周期终点。','A0495':'2021至2022上升延伸归RM07，重新实算后不是两段收益相加。',
'A0045':'2019至2021主升归RM08，保留此阶段原始统计供比较。','A0046':'2022年回撤后最后新高归RM08，其28/28不能冒充长周期21/24。',
'A0266':'2020至2021主升归RM09，2022年深回撤计入整段风险。','A0267':'2022年8月最后微创新高归RM09，不独立重复晋级。',
'A0476':'2020至2021核心上升归RM10，原阶段成员中位147.8%在完整终点大幅回落。','A0477':'2021至2022第一次高位恢复归RM10，不作新增主行情。','A0478':'2022至2023第二次高位恢复归RM10，终点仅略超过前峰。',
'A0005':'2021至2022高位箱体前段归RM11。','A0006':'2022至2023高位箱体后段归RM11；合并后中位接近零，不能以两段4/5上涨称广泛。'}
sector_notes={
'小金属':'两轮主升分明：2020年4月至2021年8月，以及2024年7月至2026年3月。2021主峰之后到2024的下降不是新主行情；2026年3月和6月近似双顶，因6月略低，主终点保留3月。2024年2月至4月单列筑底前波，7月二次底部为后段起点。',
'非金属材料':'2019夏至2022夏合并为包含疫情回撤和2022深回撤的长周期，之后2023至2024下降清晰。长周期端点只有4只、top3极高，因此价格很大不直接晋级广泛行业重点；2024年9月至2026年6月7只固定池表现更齐。',
'金属新材料':'2019年11月至2022年8月跨年包络里存在42.1%深回撤，应与低波动趋势严格区分。2024年9月后的主升不在2026年2月局部峰截断，6月更高才是这一轮观测到的最高端点。',
'塑料制品':'2019至2021不是两个独立主行情，2021初约20%整理后继续创新高；2022和2023为未过主峰的恢复。2024年9月至2026年6月形成独立新轮；高成员收益来自固定大市值池11/78，不能替代全行业。',
'油气开采及服务':'2021至2022存在一轮中等强度上升，2022至2024多次恢复仍未稳定越过旧尖峰。2024年9月至2026年3月是更大的新轮，但末段尖峰和44.3%峰后回撤使其不同于平稳行业牛市。',
'橡胶制品':'行业指数可识别2019至2022、2024至2026两个大周期；后轮2025年4月短暂跌20%后续创新高，应合并。所有成员判断仅有1只，全部标证据不足，不能以这只股票证明行业行情。',
'农化制品':'2021年9月不应作为整轮终点，之后约20%调整后再创新高，长周期延至2022年7月。2023至2024持续回落后，2024年7月二次底部至2026年3月成为下一轮。两轮固定池较广，但早轮全路径完整成员只有13。',
'化学原料':'2019年11月底部至2021年9月主峰为第一轮，2022年恢复未创新高，随后长期回落。2024年9月至2026年3月为第二轮；不按2020、2021、2025年末切断。',
'化学制品':'2019年8月至2022年8月包含主升和最后新高，2022深回撤不能隐去；长端点广度降为21/24，与两个子段全涨不同。2024年9月至2026年2月为新轮，29只固定池扩散比较充分，但全行业现成员183只。',
'化学纤维':'2020至2021主升后，2022至2023恢复并未创新高，因此保留为普通段。2024年9月至2026年5月形成新主升；两轮端点仅5或6只，价格与固定池支持存在，但样本覆盖限制必须醒目。',
'石油加工贸易':'2020至2023把几乎同高的三次峰作为一次主升及高位反复，不制造三个独立机会。完整端点成员收益比2021主升峰明显回吐，故整体普通；2024年9月至2026年3月新轮更清晰。',
'种植业与林业':'2020年2月至8月是清晰主升，2021至2023高位箱体不能当每年一轮新行情。2024至2026指数再次大涨，但5只固定池贡献集中于前三，保留重点价格观察并判行业广度证据不足。',
'农产品加工':'2018底至2019春与2020年2月至8月两轮上升分开，2020主峰后2021至2023主要是横向恢复。2024至2025再升虽连续，成员中位与幅度不及前两轮，作为普通长波；2026为下跌后的恢复。',
'建筑材料':'2019年8月至2022年1月主升中间存在长平台，不能在2020年底截断。2022至2024持续下降后，2024年9月至2026年2月独立重启，前后两轮均有固定池的广泛收益支持。',
'环境治理':'2019至2023多次反弹集中于同一大区间，不能因为每段20%就评为肥尾；2024年9月至2026年5月才出现更连续的跨年抬高。21/111覆盖说明只能讲固定池内参与。',
'环保设备':'价格路径2019至2023主要是恢复后再跌，2024至2026确有大主升。但池仅2只，所有阶段一律保留证据不足，尤其不能用两只的中位201.3%证明30只历史行业全体。',
'电力':'2020至2022主升及高位二次新高合并，中间30.5%回撤揭示持有难度。2024年9月至2026年6月为新轮，两个大周期的中位和低top3集中度比许多小池行业更能支持固定池扩散。',
'燃气':'2019至2023反复回到底部，不构成多年持续牛市。2024年2月起底部抬高，9月突破后延续到2026年3月，保留为完整周期；6只样本全部上涨但top3占85.3%，仍属有限覆盖。',
'港口航运':'2020至2022虽缓慢上涨，成员中位30.4%而前三占58.7%，不能以航运龙头涨幅代表港口航运全行业。2022峰后17个月调整使2024底部成为可辩护的新周期起点；后轮24/24、集中度下降，广度更好。',
'公路铁路运输':'2020年3月至2025年11月是五年多慢上升，跨年连续观察不能把每年小台阶单独当肥尾。累计118.5%与中位95.4%值得保留，但年化速度远低于两年翻倍板块；2026回落不是未观测的未来收益。'}
used=set();final=[];ledger=[]
for _,r in m.iterrows():
 rid=r.record_id;priority,reason=merge_decisions[rid];ids=r.auxiliary_ids.split(';');assert not (used&set(ids));used.update(ids)
 row=r.to_dict();row.update(priority=priority,boundary_rationale=reason,origin='manual_merged_recomputed',manual_boundary='long_cycle_envelope',price_priority='重点价格观察' if rid in ['RM01','RM05','RM06'] else ('重点价格观察' if priority=='重点候选' else '普通价格阶段'))
 final.append(row)
 for aid in ids:
  t=a.loc[aid].to_dict();t.update(manual_cycle_id=rid,manual_priority=priority,review_disposition='并入人工长周期，不独立重复计数',review_reason=phase_notes[aid],cycle_boundary_rationale=reason);ledger.append(t)
for aid,r in a.iterrows():
 if aid in used:continue
 assert aid in D,aid
 priority,reason=D[aid];rid='RS'+aid[1:];row=r.to_dict();row.update(record_id=rid,auxiliary_ids=aid,priority=priority,boundary_rationale='人工接受该段底部与峰值作为本级价格周期端点。'+reason,origin='manual_review_reused_exact_aux_stats',manual_boundary='independent_main_or_secondary',price_priority='重点价格观察' if priority=='重点候选' or aid in ['A0008','A0668'] else '普通价格阶段')
 final.append(row);t=r.to_dict();t.update(manual_cycle_id=rid,manual_priority=priority,review_disposition='人工选为重点候选' if priority=='重点候选' else ('保留价格周期，广度证据不足' if priority=='证据不足' else '审阅保留普通或可错过，不晋级'),review_reason=reason,cycle_boundary_rationale=row['boundary_rationale']);ledger.append(t)
f=pd.DataFrame(final);l=pd.DataFrame(ledger);assert len(l)==130 and l.record_id.is_unique;assert set(l.record_id)==set(a.index);assert len(f)==116;assert f[['sector','start','end']].duplicated().sum()==0
f['order']=f.name.map({v:i for i,v in enumerate(names)});f=f.sort_values(['order','start']).drop(columns='order');l['order']=l.name.map({v:i for i,v in enumerate(names)});l=l.sort_values(['order','start']).drop(columns='order')
for col,new in [('positive_members','member_n'),('known_members','member_K'),('research_pool_members','member_P'),('current_all_members','member_F')]:f[new]=f[col]
f['K_over_P_pct']=f.known_members/f.research_pool_members*100;f['P_over_F_pct']=f.research_pool_members/f.current_all_members*100;f['K_over_F_pct']=f.known_members/f.current_all_members*100;f['membership_basis']='2026 static 1709-stock research pool; NON-PIT; not historic whole-industry membership'
f['breadth_scope']=f.apply(lambda r:('不足：端点样本仅'+str(int(r.known_members))+'只；不得判定行业广度') if r.known_members<=3 else ('仅支持固定池端点；K/P='+str(int(r.known_members))+'/'+str(int(r.research_pool_members))+'，P/F='+str(int(r.research_pool_members))+'/'+str(int(r.current_all_members))+'；不代表历史全体'),axis=1)
f['annualized_endpoint_return_pct']=((1+f.industry_return_pct/100)**(365.25/f.calendar_days)-1)*100
# n/K/P/F and full_path are intentionally separate; no endpoints are forward-filled.
for _,r in f.iterrows():
 p=prices[r.sector];q=p.loc[r.start:r.end];assert abs((q.iloc[-1]/q.iloc[0]-1)*100-r.industry_return_pct)<1e-8;assert abs((q/q.cummax()-1).min()*100-r.mdd_pct)<1e-8;assert r.member_n<=r.member_K<=r.member_P<=r.member_F;assert r.full_path_members<=r.member_K
for sec,z in f.groupby('sector'):
 z=z.sort_values('start');assert all(z.iloc[i].end<z.iloc[i+1].start for i in range(len(z)-1)),sec
assert set(f.name)==set(names);assert all(c.loc[name].manual_records==0 for name in names)
f.to_csv(O/'MANUAL_INDEPENDENT_CYCLES.csv',index=False);l.to_csv(O/'AUXILIARY_REVIEW_LEDGER.csv',index=False)
oldmem=pd.read_csv(P/'MEMBER_RETURNS_ALL.csv');oldmem=oldmem[oldmem.record_id.isin(a.index)].copy();newmem=pd.read_csv(O/'MERGED_MEMBER_RETURNS.csv');parts=[newmem]
for _,r in f[f.origin.str.startswith('manual_review')].iterrows():
 z=oldmem[oldmem.record_id==r.auxiliary_ids].copy();z['source_aux_id']=z.record_id;z['record_id']=r.record_id;parts.append(z)
mem=pd.concat(parts,ignore_index=True);mem.to_csv(O/'MANUAL_MEMBER_RETURNS.csv',index=False)
summary=[]
for name in names:
 z=f[f.name==name];ar=l[l.name==name];summary.append(dict(sector=z.sector.iloc[0],name=name,auxiliary_reviewed=len(ar),manual_cycles=len(z),key_candidates=sum(z.priority=='重点候选'),ordinary_or_skippable=sum(z.priority=='普通或可错过'),insufficient_evidence=sum(z.priority=='证据不足'),merged_cycles=sum(z.origin=='manual_merged_recomputed'),research_pool_members=int(c.loc[name].research_pool_members),current_all_members=int(c.loc[name].current_all_members),coverage_note='已逐段人工复核全辅助候选并审视连续日线；不是历史全成员覆盖',sector_rationale=sector_notes[name]))
su=pd.DataFrame(summary);su.to_csv(O/'SECTOR_REVIEW_SUMMARY.csv',index=False)
protocol='''# 资源、化工、公用及相关20行业人工日线复核协议

## 范围与输入
只处理父任务指定20行业，原COVERAGE_90中manual_records均为0。2019-01-01至2026-10-22为核心观察窗，允许保留2018年起点以避免跨年截断。行业日线20×1891个核心窗口有效收盘，图中增加2018背景；没有外部新数据，没有经济回测、订单、账户或信号收益测试。

## 人工判断顺序
1. 查看20行业所有130个固定20%辅助段及成员字段。
2. 查看全部20行业2018至2026的连续日线图、逐月月末路径、相邻段回撤和峰值关系，再决定何处保留独立修复、何处把子段合成跨年主行情包络。
3. 分类由路径持续性、主峰关系、幅度、成员分布与样本覆盖共同人工判断，不用统一涨幅阈值决定重点，也不按年度截断。普通段也完整保留，不只选最大段。
4. 此处“独立周期”是本次选定叙事级别上的互不重叠价格区间，不是数学上唯一分割。合并包络可包含2022年30%至42%深回撤；子段仍在逐段账本可见，但不作为另一次独立重点重复计数。主升和其后的反弹/高位修复要分清，不能把不同层次相加。
5. 11个新边界长周期必须用原日线从新start到新end实算收益、最大回撤和各成员相同端点；不能把辅助段收益拼接，不能沿用子段成员广度。
6. 105个其余区间人工接受既有端点，复用原辅助段相同端点成员统计；行业收益与MDD重新由导出日线逐条验证。旧段同口径数据来源由原SOURCE_HASHES检验。

## 三类结论
- 重点候选：有值得继续研究的独立长行情或显著主升，固定池内成员分布提供一定支持。它不是经济回测结论，更不直接等同“肥尾”。较低覆盖必须跟随结论出现。
- 普通或可错过：真实反弹/恢复/慢箱体仍保留，不能单因超过20%就晋级。普通不等于无利润或必须错过。
- 证据不足：可确认指数价格周期，但成员样本或集中度不足以推断广泛行业行情。K为1至3强制本类；4只且极端集中、5只且极端集中等也可人工保守归此类。另设price_priority保留显著价格候选，不让成员证据不足抹掉指数行情。

## 指标和限制
- industry_return_pct、mdd_pct及所有pct字段单位为百分点；MDD为负。无向前填充，收盘使用原signal adjusted close，仅observed_bar且price_eligible、非source_invalid、非synthetic_event_bar、正有限值。
- n=同一start/end上涨的固定池成员数；K=两端都有有效价格的固定池成员数；P=该行业在2026静态1709幸存大市值研究池中的股票数；F=2026映射中该行业现成员数。P/F只是现覆盖，不是历史全体。
- full_path_members单独报告，只有端点可知不表示全路径连续可交易。unknown_members=P−K，unknown_symbols列出池内端点未知者；outside_pool=F−P，不假装知道池外收益。
- member median只对K计；top3_positive_share_pct=等初始名义本金下正收益贡献前三/全部正收益贡献，不是行业指数权重贡献。小池top3比例有结构性高基数，不能和大池直接无条件比较。
- 年化字段只作描述时间长度，不是可实现策略年化；公路铁路运输五年多慢涨尤其不能被累积118.5%误读为短期暴涨。
- 峰后跌幅只统计至2026-10-22已观察部分；没有用未来信息预测，端点是后验人工描述，不是可交易信号。2026尾部未构成明确新主升的阶段不凭空填候选。

## 可复查材料
DAILY_REVIEW_1..4.png；DAILY_PATHS_20.csv；MONTHLY_PATHS_20.csv；ANNUAL_PATHS_20.csv；ADJACENT_SEGMENT_BRIDGES.csv；MANUAL_INDEPENDENT_CYCLES.csv；AUXILIARY_REVIEW_LEDGER.csv；MANUAL_MEMBER_RETURNS.csv；SECTOR_REVIEW_SUMMARY.csv；SOURCE_HASHES.json；QA.json。
'''
(O/'PROTOCOL.md').write_text(protocol)
lines=['# 20行业全候选人工复核','', '已复核20行业、130个辅助段，形成116个互不重叠人工价格周期，其中11个跨段长周期由新端点重新实算。重点、普通、证据不足分别为 '+str(sum(f.priority=='重点候选'))+'、'+str(sum(f.priority=='普通或可错过'))+'、'+str(sum(f.priority=='证据不足'))+' 个。所有结论仅涉及固定2026研究池，非历史全行业；不构成经济回测或买卖建议。','', '**口径：n/K/P/F=上涨数/端点可知数/固定研究池数/2026现成员数。中位和top3均仅在K上统计。全路径完整人数另列，unknown=P−K。**','', '## 先看不能遗漏的区别','', '- 农化、电力、化学制品的旧主升延长到2022最后新高后，必须重算广度而不能保留原子段“全涨”。','- 非金属材料2019–2022指数+345.6%，但新长端点仅4只、top3占97.4%，归证据不足；价格大不自动代表广泛。','- 金属新材料旧长周期含−42.1%回撤，保留完整大周期不等于可以无痛持有。','- 橡胶1只、环保设备2只，一律不能拿个股表现代替行业；种植业2024–2026的5只集中度也不足以认定广泛行业行情。','- 公路铁路运输2020–2025为五年多慢行情；港口航运2020–2022的固定池分布偏集中，不能用少数航运龙头替代行业。','']
for name in names:
 z=f[f.name==name];r=su[su.name==name].iloc[0];lines+=['## '+name,'',sector_notes[name],'',f'覆盖：原辅助段{r.auxiliary_reviewed}个，人工周期{r.manual_cycles}个；重点{r.key_candidates}、普通{r.ordinary_or_skippable}、证据不足{r.insufficient_evidence}。现固定池P/F={r.research_pool_members}/{r.current_all_members}，非历史成员。','']
 for _,x in z.iterrows():
  lines += [f'### {x.record_id}｜{x.start} 至 {x.end}｜{x.priority}',f'- 指数 {x.industry_return_pct:+.2f}%，MDD {x.mdd_pct:.2f}%；n/K/P/F={int(x.member_n)}/{int(x.member_K)}/{int(x.member_P)}/{int(x.member_F)}，全路径 {int(x.full_path_members)}，unknown {int(x.unknown_members)}。',f'- 成员中位 {x.member_median_pct:+.2f}%，top3正收益占比 {x.top3_positive_share_pct:.2f}%；峰后已观察最大回落 {x.peak_to_observed_low_pct:.2f}%。',f'- 边界及定级：{x.boundary_rationale}',f'- 对应辅助段：{x.auxiliary_ids}。','']
 lines += ['逐段去向：']
 for _,x in l[l.name==name].iterrows():lines += [f'- {x.record_id} → {x.manual_cycle_id}：{x.review_reason}']
 lines += ['']
lines+=['## 审计说明','', '每日路径图与月度表用于审视，不是自动定级器。所有合并区间股票同起止端点重新计算，105条原边界统计复用后逐条验证行业收益/MDD。逐段账本130行无遗漏，人工周期同一行业无重叠，不同层次不可相加。更换周期叙事级别会改变端点与样本，需再次实算，不能将本次界定当成唯一客观答案。']
(O/'REVIEW_BY_INDUSTRY.md').write_text('\n'.join(lines)+'\n')
# Ensure read-only input sources stayed unchanged and validate member aggregates independently.
sources=json.loads((O/'SOURCE_HASHES.json').read_text());orig=json.loads((P/'SOURCE_HASHES.json').read_text());relevant_input=[P/'AUXILIARY_20PCT_WAVES.csv',P/'COVERAGE_90.csv',P/'MEMBER_RETURNS_ALL.csv',P/'MANUAL_RECORDS.csv']
for p in relevant_input:sources[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
for p,h in list(sources.items()):assert hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()==h
# Verify the original universe manifests and static mapping hashes, plus every original source used by reused aux stats.
for p,h in orig.items():assert hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()==h
for _,r in f.iterrows():
 z=mem[mem.record_id==r.record_id];known=z[z.known==True];assert len(z)==r.research_pool_members;assert len(known)==r.known_members;assert sum(known.return_pct>0)==r.positive_members;assert abs(known.return_pct.median()-r.member_median_pct)<1e-8;assert int(z.full_path.sum())==r.full_path_members
(O/'SOURCE_HASHES.json').write_text(json.dumps(sources,ensure_ascii=False,indent=2)+'\n')
qa=dict(sectors=20,auxiliary_reviewed=130,manual_cycles=116,key_candidates=int(sum(f.priority=='重点候选')),ordinary_or_skippable=int(sum(f.priority=='普通或可错过')),insufficient_evidence=int(sum(f.priority=='证据不足')),recomputed_merged_cycles=11,exact_reused_cycles=105,merged_aux_rows=len(used),auxiliary_coverage_complete=True,all_original_manual_records_zero=True,no_sector_overlap_with_prior29=True,all_same_sector_cycles_nonoverlap=True,industry_return_and_mdd_rechecked=True,member_aggregates_rechecked=True,manual_member_rows=len(mem),core_daily_sessions_per_industry=1891,monthly_industry_rows=len(pd.read_csv(O/'MONTHLY_PATHS_20.csv')),original_source_hashes_verified=len(orig),read_stock_sources_for_merges=153,source_unchanged=True,no_accounts_or_backtests=True,cutoff='2026-10-22')
(O/'QA.json').write_text(json.dumps(qa,ensure_ascii=False,indent=2)+'\n');print(json.dumps(qa,ensure_ascii=False,indent=2));print(su[['name','auxiliary_reviewed','manual_cycles','key_candidates','ordinary_or_skippable','insufficient_evidence']].to_string(index=False))
