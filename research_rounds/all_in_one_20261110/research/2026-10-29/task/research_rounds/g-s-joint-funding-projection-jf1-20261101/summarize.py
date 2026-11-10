"""Read-only evidence packet for component review. No historical event API."""
from projector import *
from test_projector import state,lot,demand,simple_exit_state
import inspect
O=Path(__file__).resolve().parent
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
def minima(c):
 out={}
 for r in c['validation']['checks']:
  k=r['constraint']
  if k not in out or D(r['residual'])<D(out[k]['residual']):out[k]=r
 return out
def main():
 gate=read(O/'SYNTHETIC_RESULTS.json');assert gate['passed'] and gate['tests']==20
 full=read(O/'jul3/ORIGINAL_FULL_REJECTED.json');final=read(O/'jul3/FINAL_CERTIFICATE.json');saved=read(O/'jul3/ACTUAL_SAVED_CERTIFICATE.json');inp=read(O/'jul3/INPUT.json')
 assert final['source_sha256']==sha(O/'projector.py') and final['native_source_binding']==source_binding()
 assert saved['requires_native_existing_funding_reconciliation']
 try:CertificateBook().accept(saved,'actual-existing-16')
 except ValueError as e:saved_block=str(e)
 else:raise AssertionError('existing excess funding was silently approved')
 mx=max(D(x['value']) for x in full['validation']['checks'] if x['constraint']=='account_risk6')
 assert mx==D('64497.35268487967810098736595')
 stages=minima(full);residuals=minima(final)
 save(O/'CONSTRAINT_RESIDUALS.json',dict(full_target_minima=stages,approved_preproposal_minima=residuals,
   approved_terminal=final['validation']['terminal'],unchanged_not_newly_applied=['probe .5%/10% and core .25%: Jul3 proposed buys are confirmed mobile; affected constraints separately exercised in synthetic cases'],
   actual_postproposal_requires_native_reconciliation=saved_block))
 # Transparent examples use the SAME planner/native fee/quantity components.
 partial=solve(state([lot()]),[demand()]);allok=solve(state([],cash='1000000'),[demand(q=100)])
 no=demand();no['eligible']=False;zero=solve(state([lot()]),[no])
 ns=state([lot(q=1100,mark='8',floor='7.45')],cash='1200');nd=demand(q=200,mark='1',floor='.98')
 nonmono={str(q):preview(ns,[nd],{'NEW':q}) for q in (100,200)}
 es,ed=simple_exit_state();existing=solve(es,ed)
 save(O/'CASE_BEHAVIORS.json',dict(zero=dict(Q=zero['Q'],D=zero['donors']['rows']),partial=dict(Q=partial['Q'],D=partial['donors']['rows']),all=dict(Q=allok['Q'],D=allok['donors']['rows']),
   genuine_nonmonotonic=nonmono,existing_pending=dict(before_risk=es['rows'][0]['risk'],before_available=es['available'],conditional=existing['validation'],new_D=existing['donors']['rows']),
   restart=read(O/'restart/RESTORED.json'),actual_events=0))
 base=O.parent/'g-s-historical-native-nextsession-20261101'
 assert sha(base/'INPUT_OUTPUT_SHA256.json')=='b85aafe358213f1ae5dac3a55fb9644746dee9f4048e9b439626787119feba4f'
 for rec in read(base/'run/saved-state-audit/VERIFICATION.json')['checkpoint_restores']:assert sha(Path(rec['checkpoint']))==rec['checkpoint_sha256']
 save(O/'AUTHORIZATION_AND_FREEZE.json',dict(parent_thread='01a1869e-bab0-73ad-a5ca-8b65eb61f01b',scope='isolated JF1 implementation; synthetic and readonly Jul3 projection only; no historical account events',
   contract_sha256=CONTRACT_SHA,native_binding=source_binding(),sources={str(p):sha(p) for p in sorted(O.glob('*.py'))},
   input_checkpoint_sha256=inp['evidence']['checkpoint_sha256'],old_seven_checkpoints_and_artifact_index_unchanged=True,original_R4_guards_unmodified=True,financial_events=0))
 lines=['JF1 联合筹资纯投影：交独审，未接入历史账户执行','',
 '20/20组件合成通过。没有账户step、订单提交、实际fill/cancel/结算或历史路径重跑。复用原生FeeSchedule.incremental、QuantityRule及core保护风险算法；资源投影不冒充成交账。',
 '真实输入只读Jul3保存checkpoint；全部价格/有效线来自该收盘，下一日仅查原有已知版本的数量/费率和交易钟，不读取未来开盘价。原K、6%等数值、原优先序与筹资捐资顺序不变。','',
 '一、原满目标反例',
 'Q=博敏4500/大金1300/汇绿4200/天齐1400。纯捐资选择器完全复现原16项数量与101121.22566730345元预计回款。',
 f'全部预留后名义风险{mx}元；计入原生卖买费用/滑点的最差账户风险残差{stages["account_risk6"]["residual"]}元，明确拒绝。',
 '原未扣新费静态上限59882.01375724元只能作为宽松上界；证书按每个预留/成交前amend资源边界扣费，不能用该上界冒充通过。终端已填资源用mark估值，风险比预留阶段略低，二者单列不混淆。','',
 '二、发送原16项请求前的只读规划视图',
 '保存状态本身在16项请求之后，当前风险59259.6943090151。只对规划输入识别并剥离这16项同close新筹资元数据，恢复普通持有风险58679.5601494749；580.1341595402差额是新锁相对已接受线的额外charge。现金/数量/价格/保护/历史流不变。不是把历史锁从真实账户删除。证据含精确eid/layer/qty/requested_at核同及筹资前coverage.assets=[]。',
 f'按已冻结原序贪心，检查103个合法Q：{final["Q"]}；新D为空，零筹资。每个候选从上界逐量下降，每次重建D(Q)及全部资源；不是只砍末股、不是对联合可行性二分。',
 '首股1500股可用已有现金，更多股受账户风险限制；合同禁止为单纯风险余量额外卖有效旧仓。后排暂为0的原序前缀选择不是全局最优搜索，可能存在不同组合，本轮不换目标优化。',
 f'条件末值（不是历史账户新结果）：{final["validation"]["terminal"]}。最小约束残差：']
 for k,r in residuals.items():lines.append(f'  {k}: {r["residual"]} 元；发生边界 {r["stage"]}')
 lines += ['',
 '三、原保存状态的16项旧待卖不得抹掉',
 f'若条件假设16项都真实卖成并结算，数值投影另得Q={saved["Q"]}，没有新增D。该视图保留旧单/锁，不是取消后重算的同一状态。',
 f'旧筹资有可整单过量覆盖，证书提交明确阻断：{saved_block}。必须沿原goal/cancel+ACK做核对，不能自动取消、释放、发替代筹资或把这组Q当新授权。历史16单本轮一笔未改。','',
 '四、合成证据与边界',
 '- 0/部分/全部可行、原排序下前缀保持；失败后排试探不擦掉前排合法D。',
 '- 真非单调例：q100无需筹资但风险不容纳；q200触发合法整手捐资并释放风险后可行，防止“最小单失败就全拒”或一次二分。',
 '- STAR每个新单最低200、200以上step1；已有持仓不改变新单minimum。',
 '- 原生最低佣金、部分成交后增量佣金；部分卖出AR/部分结算与已用现金分开，覆盖不重复。未成交锁当前risk/cash保持，投影actual释放字段始终0。',
 '- 取消未ACK、重复资产、未知可卖数量、未来报价、破线、原core试错2%/.25%和probe约束均拒绝对应新增量。',
 '- 证书cap扣已实际预留/成交；新fresh不恢复raw满目标，取消请求不释额度，ACK仅释原剩余，原deadline不延长。真实子进程恢复保留50已成交+50待撤，cap仍0；ACK后仅余50，过期0。',
 '- 证书绑定本源码、合同及原生费用/数量/风险源码与normal cost；错误native/source绑定拒绝。',
 '- 首轮14/15：发现core单次2%目标未显式检查，已补回原限制；原失败源/输出在failures/v1。最终20/20。','',
 '覆盖界限：这是纯规划组件、持久证书和原生费用/数量调用；未把JF1提交器接入冻结R4历史runner，也未执行任何新的真实金融事件。既有待单复杂撤销/ACK只阻断和保留，不伪称已完成原生取消全链。Jul3提取器明确核无原待买/应收，在该视图上验证；其他状态使用显式合成资源输入。K均分、主线集中与卖有效赢家的策略问题均未解决。','',
 '命令：',
 '/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/research/.venv/bin/python -B test_projector.py',
 '/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/research/.venv/bin/python -B readonly_jul3.py  # 已有jul3目录时拒覆盖；不可静默覆跑',
 '主要入口：projector.py；jul3/FINAL_CERTIFICATE.json；jul3/ORIGINAL_FULL_REJECTED.json；CONSTRAINT_RESIDUALS.json；CASE_BEHAVIORS.json；restart/；AUTHORIZATION_AND_FREEZE.json。',
 '完成后停在组件独审；无新日期、无收益结果、无调参。']
 (O/'REPORT.txt').write_text('\n'.join(lines)+'\n')
 save(O/'ARTIFACT_SHA256.json',{str(p.relative_to(O)):sha(p) for p in sorted(O.rglob('*')) if p.is_file() and p.name!='ARTIFACT_SHA256.json'})
 print(json.dumps(dict(passed=True,tests=gate['tests'],source_sha256=sha(O/'projector.py'),artifact_index_sha256=sha(O/'ARTIFACT_SHA256.json'),financial_events=0)),flush=True)
if __name__=='__main__':main()
