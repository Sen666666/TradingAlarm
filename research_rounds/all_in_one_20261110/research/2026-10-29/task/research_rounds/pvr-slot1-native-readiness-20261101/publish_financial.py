"""Publish only completed, verified books. Never imports/runs an account."""
from pathlib import Path
from decimal import Decimal as D
from datetime import datetime,timezone,timedelta
import json,gzip,hashlib
O=Path(__file__).resolve().parent;W=O.parent
def read(p):return json.loads(Path(p).read_text())
def n(x):return D(str(x))
def fmt(x):return f'{n(x):.2f}'
def wan(x):return fmt(n(x)/10000)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):
 p=O/p;p.parent.mkdir(parents=True,exist_ok=True);t=p.with_name(p.name+'.tmp')
 t.write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n');t.replace(p)
def main():
 results=[read(O/'analysis'/w/'COMPARISON.json') for w in ['2022','2025_26']]
 assert read(O/'END_INPUT_CACHE_VERIFICATION.json')['passed']
 assert all(read(O/'runs'/w/'VERIFICATION.json')['passed'] and read(O/'analysis'/w/'COMPLETION.json')['passed'] for w in ['2022','2025_26'])
 auth=read(O/'FULL_RUN_AUTHORIZATION.json');started=auth['at'];evidence=[]
 for w in ['2022','2025_26']:
  r=O/'runs'/w;done=read(r/'DONE.json');timing=read(r/'TIMING.json');meta=read(r/'FROZEN_RUN_METADATA.json')
  completed=datetime.fromtimestamp((r/'TIMING.json').stat().st_mtime,timezone.utc)
  evidence.append(dict(window=w,completed=done['completed'],total_seconds=timing['seconds'],
    replay_seconds=done['run_seconds'],ending_NAV=done['ending_NAV'],
    completion_file_mtime_UTC=completed.isoformat(),
    approximate_start_UTC_derived_from_duration=(completed-timedelta(seconds=timing['seconds'])).isoformat(),
    timestamp_scope='observed after execution from atomic-file mtime and recorded monotonic duration, not retroactively claimed pre-run capture',
    initial_cash=meta['initial_cash'],resume_after=meta['resume_after'],authorization_sha256=meta['authorization_sha256']))
 save('RUN_EXECUTION_EVIDENCE.json',dict(authorization_captured_before_launch_UTC=started,
   completed_paths=evidence,full_path_count=2,baseline_replays=0,tool_session=61096,
   exact_command='python -B run_trial.py --execute --windows both --authorization-file FULL_RUN_AUTHORIZATION.json --seconds-per-window 600',
   original_strict_diagnostic_gate_remains_failed=True,separate_explicit_exploratory_trial=True))
 save('COMPARISON.json',results)
 lines=['PVR_SLOT1｜两固定窗已完成，待独立金融/行为审计，不晋升',
 '原SC/Bdiag=原单遍、迁池耦合、无账户3%准入门；PVR_SLOT1只替换ready股票优先序，NA留H1原槽。各100万新起点；旧SC只读，不重跑。',
 '原strict信息代码门未过的记录保持；这是另行授权的探索试验。无SD/C1/R1/两遍/新stage/新阈值/输入刷新。','',
 '窗口 | SC收益/DD | PVR收益/DD | 平均曝险SC→PVR | 峰值曝险SC→PVR | 费用SC→PVR(元)']
 for r in results:
  a,b=r['SC'],r['PVR_SLOT1'];lines.append(f"{r['window']} | {fmt(a['return_pct'])}%/{fmt(a['global_DD']['percent'])}% | {fmt(b['return_pct'])}%/{fmt(b['global_DD']['percent'])}% | {fmt(a['mean_exposure_pct'])}%→{fmt(b['mean_exposure_pct'])}% | {fmt(a['peak_exposure_pct'])}%→{fmt(b['peak_exposure_pct'])}% | {fmt(a['fees'])}→{fmt(b['fees'])}")
 lines+=['','两窗相对净收益/DD改善，平均曝险基本相同，说明这个固定优先序在当前两账中有实际资本价值；不是只用了更多平均资金。但仍是已消费研究窗，尚无新政策成本/延迟验证或实盘认证。',
 '弱窗仍亏28.50%，不能叫识别了无主线；强窗更多尾部仍未全平，不能停在漂亮浮盈上宣称完成。','',
 '贡献(万元)：窗口/政策 | 已全平正 | 已全平负 | 未全平层净 | 已全平肥尾 | 未全平肥尾']
 for r in results:
  for ref in ['SC','PVR_SLOT1']:
   c=r[ref]['contributions'];op=n(c['open_positive'])+n(c['open_negative'])
   lines.append(f"{r['window']}/{ref} | {wan(c['closed_positive'])} | {wan(c['closed_negative'])} | {wan(op)} | {wan(c['closed_tail'])} | {wan(c['open_tail'])}")
 s,t=results[1]['SC']['contributions'],results[1]['PVR_SLOT1']['contributions']
 op=n(t['open_positive'])+n(t['open_negative']);oldop=n(s['open_positive'])+n(s['open_negative'])
 lines+=['层净贡献=实际现金流+已确认分红+剩余库存估值，全部加总到NAV；未全平层贡献含其生命周期已收现金/分红，不全等纯未实现价差。肥尾沿原层净/买款>=30%描述口径，不是独立胜率。',
 f"强窗94.90万元净盈利中，未全平层{wan(op)}万元({fmt(op/n(t['net'])*100)}%)；相对SC多赚{wan(results[1]['delta_NAV'])}万元，其中未全平贡献差{wan(op-oldop)}万元({fmt((op-oldop)/n(results[1]['delta_NAV'])*100)}%)。",
 '强窗已全平负贡献反而58.68→62.22万元；闭合正贡献77.88→94.01万元。不是所有新增试错都更好。','',
 '参与/资本反馈：']
 for r in results:
  w=r['window'];a,b=r['SC'],r['PVR_SLOT1'];c=r['funded_changes'];bridge=r['stock_delta_bridge']
  lines.append(f"{w}: 预留{a['admissions']}→{b['admissions']}，实际有fill订单{a['actual_filled_orders']}→{b['actual_filled_orders']}，零fill{a['zero_fill_reservations']}→{b['zero_fill_reservations']}；实际股票{a['funded_stocks']}→{b['funded_stocks']}，新{c['all_stocks']['gained']}/失{c['all_stocks']['lost']}。")
  lines.append(f"confirmed freshCP1实际成交凭据{a['confirmed_filled_receipts']}→{b['confirmed_filled_receipts']}/{a['market_qualified_mother']}市场合格母体，ACT暂停不删母体，末收盘{a['source_right_boundary_receipts']}张next-open在窗外。行业attempt {a['funded_attempts']}→{b['funded_attempts']}，新{c['all_attempts']['gained']}/失{c['all_attempts']['lost']}。")
  lines.append(f"总买款{wan(a['buy_cash'])}→{wan(b['buy_cash'])}万元；按实际参与集合的NAV差额桥：新获资股{wan(bridge['new_funded_stock'])}、失去股{wan(bridge['lost_funded_stock'])}、共同股{wan(bridge['common_funded_stock'])}万元。它是账本分解，不是可独立赚取/替换的反事实利润。")
  lines.append(f"ACT暂停收盘{a['paused_closes']}→{b['paused_closes']}；旧/失效attempt probe平均占额{wan(a['waits']['old_or_inactive_probe_mean_capital'])}→{wan(b['waits']['old_or_inactive_probe_mean_capital'])}万元。")
  for ref in ['SC','PVR_SLOT1']:
   q=r[ref]['waits'];lines.append(f"  {ref}迁池等待{q['layers']}层，终点{q['statuses']}；只有后来已迁入子集的median/max={q['observed_migration_lag_median']}/{q['observed_migration_lag_max']}观察，不概括全体。")
 lines+=['2022新增获资股群净亏10.96万元，与未获资原股票的差额+10.65万元基本抵消；少亏主要落在共同股不同资本路径，不能说扩大试错本身已胜。',
 '强窗新获资股+25.65万，但失去原获资股差额−10.86万；共同股不同路径+28.57万。原赢家鼎泰高科3.89万、铜冠铜箔3.19万没有参与，不能删去这些代价。','',
 '固定行为案例(实际主动买款/行业峰值含被动涨价)：']
 cases=read(O/'analysis/2025_26/THREE_FIXED_STRONG_CASES.json')
 for sec in dict.fromkeys(x['sector'] for x in cases):
  a,b=[x for x in cases if x['sector']==sec]
  lines.append(f"{a['industry']}: 首买{a['first_actual_buy']}→{b['first_actual_buy']}，新买{wan(a['active_buy_cash'])}→{wan(b['active_buy_cash'])}万元，峰值{fmt(a['peak_weight'][1])}%({a['peak_weight'][0]})→{fmt(b['peak_weight'][1])}%({b['peak_weight'][0]})。")
 lines+=['长飞：SC9/1首次200、9/4追加100、12/19重入100；PVR9/1首次100、12/19重入200。净贡献4.56→8.80万元，多数在末期未全平层，不是每个初始机会都更早/更大。',
 '德福：初买同900，PVR7/3追加800；SC4/22重入400，PVR5/7才重入200。净贡献4.31→2.94万元；较早较高峰值不代表后段全抓住。',
 '中船特气：PVR7/2首次261股，后来真实退出；4/22fresh重入389、5/6追加294，净贡献19.07万元，其中18.80万仍未全平；SC未参与。',
 '唯特偶：PVR9/24先100、9/26加500，后退出；4/17重入200、4/20加200、4/24加300；SC直到5/18首次200。净贡献2.78→11.83万元，PVR其中12.09万元正未全平贡献及−0.27万元已全平损耗。',
 '2022确定性失败案例盈新仍亏0.84万元(SC1.52万)，说明近期排序没有消除结构失败/反弹试错。两强窗命名股中际/新易均未获资；本试验未改整手目标或加白名单。',
 '首次/追加/全清后重入、所有买入的原H1/PVR/行业stage/ACT/目标/保护与退出request→实卖链均已保存。重复CP1不是实际ADD；已平层与未平层不混胜率。','',
 '首个实际预留差异：2022首笔SC300199 core300→PVR002246 core700；强窗第一笔601606 core100共同，第二笔SC300723 core200→PVR002015 core600。其后差额会经原core-first/资源/迁池/ACT/退出反馈，不能用未来赢家回填逐股独立因果利润。',
 '集中/空闲：强窗平均持股52.36→51.49、行业31.71→30.63，前三行业平均NAV占比21.09→25.62%；最大单股峰值9.81→13.67%(含被动上涨，原新买10%检查保留)。未变成稳定少数行业账户，也不保证全抓事后主升。',
 '旧probe等待与资源共存仍真实存在；原route并集拒因不能全部归于旧probe或某个单一cap，不做额外松约束/账户重放。','',
 '工程/时间与审计：']
 for e in evidence:lines.append(f"{e['window']}: 加载+执行+落盘{fmt(e['total_seconds'])}秒，run_prepared记录{fmt(e['replay_seconds'])}秒，resume_after={e['resume_after']}，endingNAV={e['ending_NAV']['B']}。")
 lines+=['共484日现金/股数/权益/pool/费用桥、3318笔fill、8次split、8季度checkpoint原生module/class/function及SHA核同。242+242决策的原H1槽→冻结PVR优先键逐一重算exact。',
 '14072份原I/CP1/行业/receipt/PVR源、新score及旧PVR缓存末端SHA核同。SC书与原审计SHA一致，SC未重跑；新native_rank SHA5ec91c2323b2d3b8fa5c99df504139e2ac7af9b5b84359222c3d6353d0cd697c。',
 'NAs没有删资格/填中性：2022PVR有1笔NA core实际成交，强窗0笔，原SC两窗均0；因此不能继续用原CP1母体NA零成交概括新native轨迹。',
 '这是当前snapshot非PIT、已消费样本、日线完整OHLC/量有效性与开盘卖款复用代理下的normal研究结果；权益支付/送转时点未知沿原代理。并未验证开盘真实可得性、PVR政策压力或未见行情。',
 '只两条授权路径已完成，保持源码/数据/旧门失败记录，不调参、不自动续年/压力/新变体；等待独立金融与行为审计。']
 (O/'FINANCIAL_RESULTS.txt').write_text('\n'.join(lines)+'\n')
 # Transparently track preflight output regeneration; never patch old bytes to match.
 prior=read(O/'ARTIFACT_SHA256.json');known=read(O/'END_INPUT_CACHE_SHA256.json');changed=[]
 for p,h in prior.items():
  got=known.get(str(Path(p).resolve())) or sha(p)
  if got!=h:changed.append(dict(path=p,preflight_sha256=h,current_sha256=got))
 assert all(x['path'].endswith('/input-readiness/2022/INPUT_GATE.json') for x in changed),changed
 current=read(O/'input-readiness/2022/INPUT_GATE.json')['identity'];current.pop('seconds',None)
 assert current==read(O/'PREFLIGHT_GATE.json')['input_identities']['2022']
 save('PREFLIGHT_OUTPUT_REGENERATION.json',dict(changed=changed,
  reason='authorized unchanged original 2022 input loader regenerates derived readiness gate with fresh timing; no source/cache/account/technical-prefix overwrite',
  semantic_input_identity_without_runtime_exact=True,old_artifact_manifest_not_rewritten=True))
 ready=dict(ready=True,independent_financial_audit_pending=True,policy='PVR_SLOT1',full_new_financial_paths=2,
  baseline_replays=0,native_rank_sha256=auth['native_rank_sha256'],contract_sha256=auth['contract_sha256'],
  original_strict_gate_remains_failed=True,source_input_cache_hashes_exact=True,all_daily_bridges=484,
  actual_fill_records=3318,actual_splits=8,quarter_identity_checkpoints=8,
  source_and_result_reference='FINANCIAL_RESULTS.txt / COMPARISON.json / analysis / runs',
  financial_result_sources={str(p):sha(p) for p in [Path(__file__),O/'analyze_results.py',O/'behavior_evidence.py',O/'verify_results.py']},
  no_further_paths_running=True,default_or_live_promotion=False,
  unknowns=['future realization of open contributions','new-policy cost/delay robustness','unseen/PIT/live executability','exclusive causal attribution of every resource rejection'])
 save('FINANCIAL_READINESS_FOR_INDEPENDENT_AUDIT.json',ready)
 save('FINANCIAL_ARTIFACT_SHA256.json',{str(p.relative_to(O)):sha(p) for p in O.rglob('*') if p.is_file() and p.name!='FINANCIAL_ARTIFACT_SHA256.json' and '__pycache__' not in p.parts})
 print('FINANCIAL_PUBLISHED two paths, no promotion, audit pending',flush=True)
if __name__=='__main__':main()
