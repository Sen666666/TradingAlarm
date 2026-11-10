# 2022 独立保存账队列审计

只读 gate_2022 完整封存账及原 Joint economic_2022，不导入工程模块、不执行 consumer/economic；OUTPUT_SEAL 全量核验通过。

16项检查零失败。实际 gate 读取5004次，ALLOW4488、DENY516。全部 DENY 无PRICE入队或selected，只保留原selector自然APPLICATION。24733条APPLICATION与旧Joint完全一致，并已独立对齐固定receipt parquet。

从自然最终offers独立重建2848个行业日队列、6377行决策，known PVR降序/sid平局、unknown PRICE最后、每行业前2 selected均吻合；同股合法AB全部优先。新初始signal日期均在2022，actions未越过2026-06-30。

以sid+event（PRICE event包含receipt）匹配保留轮次：AB1687、PRICE2219，actions、权益claims和exit均完全一致。共享PRICE队列close sizing字段亦exact。此结论不代表全部AB不受影响：旧AB有29条不再selected、新增53条；290个AB事件的状态或native rank变化。旧PRICE不再selected192条，其中151直接DENY、22非top2、16 BLOCKED_HELD、3 BLOCKED_UNKNOWN；新增PRICE99条。旧AB减少29条由20非top2、7 BLOCKED_HELD、2 BLOCKED_UNKNOWN构成。

确认边界：独立排序基于保存的自然最终offers；没有重做经济sizing，只有共享候选字段核对。全部候选完整性通过固定receipt域与APPLICATION exact保障，但不据此声称独立经济复算。续单不读gate由源码插入范围核实，未重放consumer。2024尚待后续审计。

完整逐事件明细见 queue_paths_2022.json；固定域见 queue_domain_pre_snapshot.json。
