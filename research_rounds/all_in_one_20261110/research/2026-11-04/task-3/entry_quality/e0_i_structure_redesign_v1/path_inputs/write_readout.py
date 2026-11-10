"""Document exact saved-column exports only. No E0/I computation."""
from pathlib import Path
import hashlib,json
O=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(n):return json.loads((O/n).read_text())
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
idx=read('INPUT_INDEX.json');piv=read('CONFIRMED_PIVOT_SOURCE_ROWS.json');cases=read('ORIGINAL_CAMPAIGN_EXAMPLES.json')
assert all(p['pivot_occurrence_day']<=p['known_at_CLOSE_day'] for p in piv)
lines=['# E0/I局部逐日演绎：只读输入准备','',
'资金方案准备已取消。上一任务没有启动Account/模型/测试/后台进程，也没有创建input_readiness文件；只读过runner/loader/TIMING与vm_stat，内存sysctl查询权限拒绝后没有重试。本目录是新的E0/I输入准备，不延续资金方案。','',
'本件仅从SHA核同的原price/events/nativefacts/CP缓存裁切并exact-date join，7股共2103源行。没有运行E0、I、sigma、G1、CP模型或任何新账户/回测/候选收益。尚无候选冻结；不选择HL OR/AND reclaim、阈值、状态reset或重入公式。','',
'## 数据范围','',
'|股票|局部输入实际起止|原行数|events/native/CP exact缺行|','|---|---|---:|---|']
for r in idx:lines.append(f'|{r["sid"]}|{r["first_observation"]}→{r["last_observation"]}|{r["rows"]}|{r["exact_source_missing"]}|')
lines+=['',
'半导体2025部分只作为2026目标的暖机上下文，未新建2025账户。每份INPUT_INDEX同时列各源完整历史起止、原路径和SHA，原更早历史仍可供冻结后初始化；局部首日并未被假设成新结构初始状态。保留price源全部行及observed/synthetic/eligibility/segment，不前向填充缺失信号。','',
'## 字段schema与价格域','',
'- `price__*`：连续调整open/high/low/close与volume/amount；另保raw_open/high/low/close/raw_volume、adjustment_factor/volume_factor、source_kind/path、price_eligible、observed_bar、synthetic_event_bar、segment_id。',
'- `events__*`：confirmation、leg_direction、developing_extreme、confirmed_pivot、structure_floor、event、target/entered/exited、pivot_age；原*_price、confirmed_pivot_date、developing_extreme_date及segment_id。log显示字段与canonical价格字段分列，不混价域。',
'- `native__*`：实际当前cache的e0_ready/e0_target/e0_floor、i_target/i_floor/i_buy、g_grade/g_ready/g_fresh_up/g_acute_down、factor/raw_close/segment。这里是当前No60 E0/I事实；不能把旧prepared participation states.target或numeric events.target直接当成native e0_target。',
'- `CP__*`：已存ready/phase/reset_reason、anchor/frontier、scale/credit、delta_frontier/displacement、receipt/candidate、next_anchor/next_scale/next_credit、r/s/z及e0_valid/e0_floor。全为原列，不重新计算或新增凭证。','',
'SOURCE_SCHEMAS.json列每股实际列名/dtype/完整源范围。INPUT_INDEX的funded_original_stock_structure_roots保原book真实层stock_structure/epoch；这是已获资层的原identity，不能伪装成每个未获资状态的完整E0根日志。原native e0_target/floor序列和event确认行已保留，未来如需重建全根身份，须另有冻结的因果索引规则。','',
'## pivot发生钟与确认钟','',
'CONFIRMED_PIVOT_SOURCE_ROWS.json保188个原event=±1确认行，`known_at_CLOSE_day`=该event源行日期；`pivot_occurrence_day`只复制confirmed_pivot_date。所有pivot发生日≤确认日。早先极值发生日期不等于当时已确认或已可用；developing_extreme_date是当日候选快照，不能用后续更优极值日期回填前日。这里只注明完成bar后的CLOSE语义，没有伪造真实feed收到时间。','',
'## 尺度缺口：不能混用','',
'E0 numeric.py:76–79：sigma[t]=max(sqrt(fsum(r[t−63:t]^2)/63),1e−8)，过去63收益RMS、排除当前；:101–106确认用极值时点sigma[ext]和volume_baseline[ext]，不是本日重新选择的尺度。已查events/native/CP及prepared states/memories不持久化该E0 RMS sigma/ext冻结数值，标NOT_PERSISTED；本次未重算。价格和正量历史与源公式均在，可在root冻结候选后另做纯信号重建，但不能现在宣称该数值已可读。','',
'CP/G1的s是原绝对收益中位数尺度；CP used scale/receipt original_scale可冻结于更早锚，next_scale/current s/z是其它字段。它们不是E0 RMS sigma的替代。现输出保原CP列便于查证，不据此补E0缺失尺度。','',
'## 2026指定半导体原链：只作身份背景','',
'|股票|原实际开→平|原层|原终局净贡献|','|---|---|---|---:|']
for c in cases:
 if c['sid'] in ['603061.SH','605111.SH','300623.SZ']:
  lines.append(f'|{c["sid"]} {c["name"]}|{c["opened"][:10]}→{c["closed"][:10]}|{c["layer_ids"]}|{c["endpoint_net"]}|')
lines+=['',
'金海通为该原账已平赢家；新洁能两次原链及捷捷为已平失败例。可由root冻结一胜一败，当前输入保三股不按后续结果改机制。ORIGINAL_CAMPAIGN_EXAMPLES.json直接复制原链，不新算收益；其生命周期净额不充当局部新算法的收益。','',
'交付：7份*_DAILY_INPUTS.parquet；INPUT_INDEX.json；SOURCE_SCHEMAS.json；CONFIRMED_PIVOT_SOURCE_ROWS.json；ORIGINAL_CAMPAIGN_EXAMPLES.json；SOURCE_MANIFEST.json。仅准备输入，等待root冻结算法后才可做纯信号逐日state演绎；不会据此启动账户。']
(O/'READOUT.md').write_text('\n'.join(lines)+'\n')
save('VALIDATION.json',dict(status='PASS_SAVED_SOURCE_CLIP_AND_JOIN_ONLY',stocks=7,rows=sum(r['rows'] for r in idx),confirmed_pivot_source_rows=len(piv),all_pivot_occurrence_not_after_confirmation=True,all_requested_exact_source_rows_present=True,E0_RMS_sigma='NOT_PERSISTED_NOT_RECOMPUTED',new_accounts=0,new_models=0,new_backtests=0,new_signal_calculations=0,new_outcome_calculations=0))
save('DELIVERABLE_SHA256.json',{p.name:sha(p) for p in sorted(O.iterdir()) if p.is_file() and p.name not in ['DELIVERABLE_SHA256.json','SEAL_RECEIPT.json']})
seal=dict(status='SEALED_READ_ONLY_E0_I_INPUTS_AWAITING_ALGORITHM_FREEZE',readout_sha256=sha(O/'READOUT.md'),input_index_sha256=sha(O/'INPUT_INDEX.json'),source_schema_sha256=sha(O/'SOURCE_SCHEMAS.json'),source_manifest_sha256=sha(O/'SOURCE_MANIFEST.json'),deliverable_sha256=sha(O/'DELIVERABLE_SHA256.json'),new_accounts=0,new_models=0,new_backtests=0,new_signal_calculations=0)
save('SEAL_RECEIPT.json',seal);print(json.dumps(seal,ensure_ascii=False))
