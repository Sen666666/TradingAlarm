# B4 实现说明（正式输出前）

范围仅新增 `code/model.py` 与本说明，不修改旧模型、E0/R/R1、账户或历史结果。实现者未运行正式合成集、真实行情或账户。

## 接口与字段

沿用 `strength_frame(f, joint=True) -> (frame, journal)` 和 `run_valid`。输入须是无时区、无 NaT、有序唯一的 DatetimeIndex；有效观察标记为非空布尔；来源段非缺失、非空白且不得不连续复用；有效收盘/成交量须有限正数。`joint` 仅接受 Python/NumPy 标量布尔。无效观察行所有数值未知、phase 为 unknown；下一有效观察桥接价差；新来源段完全重启并将旧结构归档为 source_discontinuity。

- `r`、`mu5`、`mu21` 为实际/平滑 log 收益；对应 `*_bp` 乘 10000。`mu*_direction` 是 sign，`mu*_magnitude_bp` 是绝对大小。全部第 65 个有效收盘开始公开；EW 内部从 r1 起递推。这里的日是有效观察时钟，并非瞬时方向。
- `s` 是滞后 63 收益的典型绝对日变动尺度。`volume_reference` 是当日滞后 21 成交量中位数。`q`、`qeff`、`acute_down`、`acute_up` 只描述当日。
- `S21`、`S63`（兼容别名 local/background）是事件结构方向。`phase` 为 aligned_up、aligned_down、rebound、pullback、building 或 unconfirmed；恰好一个尺度已确认时 building_direction 记录其方向。
- `delta_h` 是**今天创建新候选会使用的阈值**，不是已经活跃的候选阈值。应通过 `up_threshold_h` / `down_threshold_h` 读取其冻结阈值。
- `up|down_{anchor,anchor_price,anchor_observation,anchor_date,created_observation,threshold,scale_at_anchor,volume_reference,frontier,credit,x,new_frontier,frontier_increment,credit_increment,volume_weight,active}_{21|63}` 是日末候选状态。确认日被消费的候选已不活跃，完整旧值在日志收据中，不能拿新反向候选解释刚完成的确认。
- `confirmed_h`、`confirmed_direction_h` 指当日新确认。`running_extreme_h` 及其 price/observation/date 是当前已确认方向的运行极值。
- journal 的 structure_confirmed 含 horizon、previous_direction、direction、r、volume、s、lag_volume_reference、close、log_close、joint 及完整 receipt。另保留 candidate_reset、frontier_extended、acute_up/down、source_discontinuity。

第一个公开观察 t64 的初始锚是前收盘 p63；冻结 s64、v64，即截至 t63 可知的完整滞后估计，不是不存在完整输入的 s63。候选阈值与量参照只在新极值/方向确认的重锚时重新冻结。两尺度分别重锚，不承诺严格嵌套。

`joint=False` 同时使结构新前沿 credit 与急性事件 qeff 的量乘数恒为 1；仍验证输入成交量，保留实际量日志。没有全局温度/grade、时间到期恢复、账户映射或交易动作。

## 预冻结实现一致性修正

初始任务文字曾写 F=max(F,x,0)。独立审查指出：若 sub-tolerance 微变仍更新 F，而不更新 Q，就会破坏 0.5F≤Q≤2F 的对应性质。正式输出前由主 agent 统一协议，明确只有 `x > F + tol` 且 `d*r > 0` 时同时更新 F、Q；否则两者都不动，new_frontier 也以该联合条件为准。此为预冻结实现/协议一致性修正，无真实结果驱动、无参数搜索。还补充空白来源段拒绝和 joint 标量布尔检查。

## 已做检查

1. Python AST 语法解析通过。
2. 手写 68 个有效收盘的最小探针：前 65 行恒价 100，随后 90、90、91，量恒为 100。验证前 64 行未知、首次下行确认、平价日结构保留/急跌消失且不称恢复、随后反向新价确认、μ 负向；总计两个尺度各两次确认。
3. 同一最小输入检查 joint=0/1/列表/数组被拒绝，空串和全空白来源段被拒绝。

这些是冻结前手写技术探针，不是正式 24 条合成材料或真实市场实验，不构成模型机制评价或晋升。正式合成/真实前缀、独立重算和图检由主流程在冻结后执行。

检查时 model.py SHA-256：`0beb0b16f2f2cac4f1aff23258b7c45722dc12f16e495be27bf5635c03888cf1`。
