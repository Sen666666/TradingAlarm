# 技术失败保留

- 首次technical/short在初始日缺少复制函数的INITIAL全局名而中止。short.log及失败初始日账完整保留；补入相同100万元常量，未改规则，技术复测为short-v2。
- raw.png最初窗口与腾景/海星/长光旧实际成交日期不对应，只能作一般量价背景；保留并另外按旧成交日期生成raw-v2/overlay-v2，不把错误窗视为成交归因。图形缓存提示不影响图或金融。

- 准入脚本首次裸导入run_study被旧依赖sys.path中的同名脚本遮蔽，导入阶段即失败、未启动经济。改为按本轮绝对文件路径加载，金融代码和参数不变。

- 结果展示第一版因状态计数含numpy.int64而JSON序列化中断；失败的post-results.json与首版CSV保留。展示v2显式转换Python整数，另写post-results-v2.json/rotation-funnel-v2.csv，金融结果不改、不经济重跑。
