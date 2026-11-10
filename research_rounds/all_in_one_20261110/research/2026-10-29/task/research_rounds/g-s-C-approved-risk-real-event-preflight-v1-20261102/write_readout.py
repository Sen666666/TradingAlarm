"""Saved-state report only; zero account progression."""
from pathlib import Path
from decimal import Decimal as D
from fractions import Fraction as F
import json,hashlib
R=Path(__file__).resolve().parent
read=lambda p:json.loads(Path(p).read_text())
x=read(R/'PARTIAL_ACTUAL_READOUT.json');assert not x['pending_pairs']
gate=read(R/'ACTUAL_FINANCIAL_GATE.json');assert gate['passed'] and gate['state_count']==32
h=read(R/'HANYU_READONLY.json');roles=read(R/'ACTUAL_ROLE_POOL_ROWS.json')
meta=read(R.parent/'g-s-C-month-continuation-20261102/inputs/2025_26/metadata.json')
f=lambda x:format(D(x),'.2f')
lines=['R0真实固定批次：已完成，待独立审计','',
 '只在原CLOSE真实账户的研究复制分支做下一ACTION/OPEN；四日期×两原模式×off/on，16分支、32事件状态。',
 '每组off与原保存ACTION、完整OPEN（含历史流水）核同；每组on仅多C逐股R0执行约束。',
 '不是从Jul1连续运行的新策略结果；这些条件分支不能相加为收益/可同时发生的交易。',
 '原源码、原账、原authority/receipt/旧仓/筹资义务在导入时核同，旧完成订单只免于追溯R0，',
 '其尚存持仓/退出风险仍完整进入原账户/行业/股票/现金守卫，没有释放旧风险或重置现金。','',
 '案例 | 版本 | 原/新买款元 | 原/新账户名义风险元（含待单/退出锁）']
for r in x['completed_pairs']:
 lines.append(f"{r['source_close']}→{r['actual_open'][:10]} | {r['case'].split('-2025')[0]} | {f(r['buygross_off'])}/{f(r['buygross_on'])} | {f(r['account_risk_off'])}/{f(r['account_risk_on'])}")
lines += ['', '一、机制真实兑现，但绝不等于只减少总资金。',
 'Jul23 C10：柳工7800→3900、徐工10300→5500、中联11800不变、三一4600→3900、恒立1200→1100；',
 '铁建预留4145→2437但两臂均0fill（原执行代理无成交）；后排海伦哲0→16500、山推0→2200。',
 '新增T/mobile/probe为上纬417、英科医疗100、海航控股100；它们不是C/R0新授权。',
 '全批买款增加25847.42，而账户名义风险只下降1013.51；资源反馈很大。',
 '其中工程机械confirmed新买491141.45→493861.81，5票→7票；不是把资本撤出该行业，',
 '只是单股风险/后排结构变化，另23127.06进入T试探。没有解决同业大额并发这个来源。',
 'Jul23 C20：柳工7900→4000、徐工10400→5600、中联11700→11900，三一0→4000；',
 'T/mobile/probe上纬343新获资、海航100未获资；买款增加8319.66，名义风险下降2693.65。',
 'C20 confirmed买款297454.65→289625.74，但T从152.08→16300.65，不能混称确认层增加。',
 '两臂原D和所有原卖出实际fill均完全相同。C10该日卖出毛额507999.23，C20为199632.87。',
 '所以不是假定旧筹资自动撤销/卖款消失；本规则会改变原批准后排和独立T路径，不能只算柳工/徐工省风险。','',
 '二、后续批与赢家代价。',
 'Jul24铁建C10 12844→5363，C20 13186→5506；能科/东方电气等本批其他C成交见逐股表。',
 'Jul7平安电工两档2500→1800；神州7600、三七5300不变，世纪华通C单100→0且整股未在该OPEN补买。',
 'Jul31广生堂两档900→700；C10国邦3800→3300，其余同批C成交见逐股表。',
 '平安/广生堂是此前真实盈利控制，但本轮止于OPEN，没有计算新退出、闭合损益或未来少赚。',
 '不以原后续P&L乘缩量比例推算策略收益；未宣称解决UP主体亏损、行业迟到或相关集中。','',
 '三、翰宇额外只读控制（2022不新增金融事件）。',
 f"Jan12原C10正量批准6700，p0={h['approved']['p0']}，原有效raw floor={h['approved']['f0']}；",
 f"R0={h['approved_nominal_risk_decimal']}元。Jan13实际p={h['actual_entry']['price']}，实际floor={h['actual_fill_floor_raw']}，",
 f"初始实际风险={D(F(h['actual_initial_nominal_risk']).numerator)/D(F(h['actual_initial_nominal_risk']).denominator)}元，为原批准{h['risk_multiple']}倍。",
 f"风险单独上界原始整数{h['risk_only_upper_before_original_qty']}，仍受原Q0=6700限制；合法局部上界{h['legal_upper_with_original_qty']}，不会由本单R0主动缩量/反向加量。",
 '原该层Jan17筹资卖出净贡献27717.32仅是旧账事实。本结论不是R0连续轨迹会必然获得6700；',
 '先行订单反馈尚未在2022模拟。C20当日无正量C授权，R0不能凭空补给它。','',
 '四、工程/边界。',
 f"32状态现金/权益/层贡献与lot股数桥通过，on共{gate['on_new_C_order_risk_mappings']}个C实际预留订单、{gate['on_actual_C_fill_risk_debits']}个C实际fill逐笔R0守恒。",
 '四个固定下一日只有现金公司行动，无拆股；所有父CLOSE均0在场买单。旧partial授权激活/一般公司行为不在本包覆盖。',
 '旧完成买单的R0债务不追溯，但仍存在的库存、实际保护线、应收、退出义务/风险锁、ACT、损耗、core epoch全部保持。',
 '物理输入截断沿用已审原loader/原输入世代；本轮没有新做物理截断，已做旧完整前缀/新身份/跨进程恢复和off整事件恒等。',
 '两主批off在正确OPEN保存后，旧报告helper缺asdict报错；原ERROR/FAILED_WORKING_STATE保留，金融未重跑。',
 '修复为单独event_comparison.py及run_prepared_fixed.py，仅报告出口/保存路径改变，交易函数及R0冻结源未改。',
 'run_open.py只用--prepare-only；run_prepared.py和旧runtime.opening_comparison为保留失败样本，禁止作为后续金融入口。',
 '当前合规金融入口是run_prepared_fixed.py，每个on强制同case off实际恒等证明，授权逐cell/源hash固定。',
 '同一原证书完整纯求解重复导致耗时；原Jul23 C10 OPEN已有291.66秒记录，本轮C10 on墙时427.89秒（含恢复、校验、存储、报告）。',
 '全套实际时钟见每分支STARTED/COMPLETED；不为提速修改经济规则/减少原检查。',
 '保留原日线H/L/量执行代理、同开盘卖款回用等限制；此包不是可实时开盘或实盘认证。',
 '结论：逐单批准风险保持覆盖了已知实际跳空放大，但它会重新分配后排并压缩某些赢家；',
 '已证机制与取舍，尚无净收益改善证据。停止于这四批，待独审，不自动延长/调参。','',
 '冻结核心b447dcb43fa72e5d25ef79f15b21de3c8e5cd41ef64eee5fa86085f2418caeb7（独立20+76合成PASS）。',
 '真实接线/完整角色池/金额/份额分别见ACTUAL_FINANCIAL_GATE.json、ACTUAL_ROLE_POOL_ROWS.json、',
 'PARTIAL_ACTUAL_READOUT.json和各ACTUAL_OPEN_COMPARISON.json。']
(R/'REPORT.txt').write_text('\n'.join(lines)+'\n')
# Small table, all native-funded roles, no future price labels.
role_summary={}
for k,vs in roles.items():
 d={}
 for z in vs:
  key=z['role']+'|'+z['pool']+'|'+z['purpose'];u=d.setdefault(key,dict(orders=0,gross=D(0),fees=D(0),stocks=[]));u['orders']+=1;u['gross']+=D(z['gross']);u['fees']+=D(z['fee']);u['stocks'].append(z['sid'])
 role_summary[k]=d
(R/'ROLE_POOL_TOTALS.json').write_text(json.dumps(role_summary,default=str,ensure_ascii=False,indent=2)+'\n')
print('REPORT_READY',len(x['completed_pairs']),'pairs')
