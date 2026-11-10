"""Read and quote active-source lineage only. No strategy imports or tests."""
from pathlib import Path
import hashlib,json
O=Path(__file__).resolve().parent;E=O.parent.parent
W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
RR=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds')
ROOT=Path('/Users/bytedance/Documents/ChatGPT/money')
T=Path('/Users/bytedance/Documents/Codex/2026-11-04/task')
R=RR/'actual-risk-recovery-20261027/code/risk_policy.py'
J=W/'case-stage-ledger-20261031/v3/joint_v3.py'
L=W/'case-stage-ledger-20261031/v3/launch_v3.py'
N=W/'pvr-slot1-native-readiness-20261101/native_rank.py'
A=T/'pvr_pool_feasibility/native_adapter.py'
REF=ROOT/'TradingAlarm/desk/refresh.py'
REC=W/'mainline-absolute-Q4-20261031/recovery.csv'
GEN=W/'mainline-absolute-Q4-20261031/experiment.py'
LOAD=E/'trend_exit_controls_v1/load_inputs.py'
RUN=E/'trend_exit_controls_v1/run_account.py'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
sources={}
def excerpt(p,start,end):
 p=Path(p);sources[str(p.resolve())]=sha(p);lines=p.read_text().splitlines();return '\n'.join(str(i)+': '+lines[i-1]for i in range(start,end+1))
def block(p,start,end):return f'[{p.name}:{start}]({p}:{start})\n\n```python\n'+excerpt(p,start,end)+'\n```\n'
metadata=[]
for w in ['2022_2024','strong']:
 p=E/'trend_exit_controls_v1/runs/BASELINE'/w/'RUN_METADATA.json';z=json.loads(p.read_text());sources[str(p.resolve())]=sha(p)
 keys=[(p,h)for p,h in z['source_freeze'].items()if p.endswith('/recovery.csv')]
 assert keys==[(str(REC),'76599d9013946bc5fc501a57b046f36a2868ad61f147ef1a6c73c9575b35906a')]
 assert sha(REC)==keys[0][1]
 metadata.append(dict(window=w,arm=z['arm'],active_RECOVERY=keys[0][0],sha256=keys[0][1]))
sources[str(REC)]=sha(REC)
parts=['# 当前No60的ACT源码证据','',
'范围：只亲读当前文件、摘取行号、核静态调用链和已有BASELINE元数据的文件身份；没有import策略模块、调用advance/step/compute_recovery、模型、数据重算、账户、测试或回测。v4设计与故障理论追加已停止。以下描述代码状态，不提出新规则。','',
'## 1. 当前runner确实调用ACT20_BREAK','',
'已完成BASELINE入口选`A.Runner`；A继承N.Runner，声明planning为N的planning、opening为J的opening。N.planning先完整调用J.planning，再应用PVR优先级。J在收盘planning内明确给step传`ACT20_BREAK`，不是依赖engine的默认RISK_MODE。','',block(RUN,14,26),block(A,16,40),block(N,115,120),
'静态继承：A.Runner → native_rank.Runner → account-risk-ablation.adapter.Runner → launch_v3.PreparedRunner → J.Runner。BASE只替换route/预算类别；A只替换No60 route/预算类别，未替换ACT函数。',
block(W/'account-risk-ablation-20261031/adapter.py',5,19),
'## 2. peak、drawdown、pause、resume的原始代码','',block(R,8,19),
'代码读取：on时先把peak更新为max(peak,nav)，再计算`1-nav/peak`；当前模式ACT20_BREAK走阈值`.2`。达到或超过阈值把on置False。off时只有flat且恢复条件为True才把on置True，并把peak重设为当时nav、episode加1。当前模式恢复变量取breakout；ACT20_FAST的fast切换分支是代码中的另一mode，J当前没有传它。','',
'初始化是首次缺risk_state时建立on=True、peak=1000000、episode=0；每次调用不重新初始化已有risk_state。','',block(R,21,29),
'flat严格定义为没有任何正实股、没有退出单、没有实际买单。代码不以没有planned intent、当前现金比例或共享loss余额代替flat。RECOVERY只查不晚于当日的最近一行；breakout仅在该行日期恰好等于当天才可为True，缺当日行不沿用旧breakout。','',
'由这段状态赋值可以直接确认：恢复把peak改成当前nav；它未保持初始1000000作为每个后续episode的比较峰。这里仅陈述状态，不作宏观或绩效评价。','',
'## 3. 当前使用的RECOVERY文件与BREAK63生成源','',
'risk_policy.py第6行有默认CSV加载，但当前PreparedRunner会覆盖同一个`J.M.E.risk_policy.RECOVERY`。wire把M.O指向mainline-absolute-Q4；两份当前BASELINE元数据均绑定同一文件：`'+str(REC)+'`，SHA256=`'+sha(REC)+'`。因此不能只读risk_policy所在目录的默认recovery.csv就声称它是本No60的实际外部时钟。','',block(W/'case-stage-ledger-20261031/wire.py',9,10),block(L,82,103),
'该CSV的生成脚本从原固定股票signal与原sector映射构roster，直接调用TradingAlarm.desk.refresh.compute_recovery，并另置fast_on=breadth>.6。','',block(GEN,19,32),block(REF,27,44),
'BREAK63准确条件见43行：market严格大于**排当前**的前63观察最高值，market当日差分为正，并且breadth>.6。不是读取官方指数的63日高点。该函数逐stock/segment生成log return与经金额调制的21-span平滑量，前64观察置warmup；行业内均值后行业等权合成market。breadth按行业内至少5个已知股票的正平滑量比例，再要求至少8个已知行业。这里没有重新运行生成器或逐行验证现存CSV。','',
'## 4. 暂停状态在J中的实际限制和先后顺序','',block(J,213,229),block(J,241,251),
'收盘顺序：先取I packet/事件与原排序；逐账户expire_day_buys并读真实balance NAV；step(ACT20_BREAK)；清本次pending；再处理存量。on=False时对该股全部live layer请求ACT_pause退出，continue跳过该股其余持仓处理。随后新意图母体记录ACT_paused barrier，why非空不生成可执行pending。','',block(J,302,324),
'下一OPEN先遍历已有exits调用原fill_exit，再settle/sync，随后才路由并预留新的买单，所有预留完成后才查买入execution window。此处没有在OPEN重新调用ACT step，也没有把发出卖请求当成已成交。','',
'risk_policy.override函数在31–33行存在，但当前J.planning不调用它；当前暂停的实际路径是上列J225/J246。不能把这个未被J调用的helper当作当前pause唯一实现。','',
'## 5. risk_policy模块对象的上游别名链','',
'J经wire加载mainline adapter；该adapter的E=C.E；C从LR.BP.E取E；LR取probe pilot的E；probe pilot从PVR experiment取E；experiment优先加入ACT/code后import engine；ACT engine第3行import risk_policy。以下为真实文本链，不执行这些import。','',
block(W/'mainline-I-quarter-2025Q3-20261031/adapter.py',6,12),block(W/'lr1-cp1-add-preflight-20261031/adapter.py',8,11),block(RR/'lot-risk-allocation-20261029/code/study.py',8,13),block(RR/'probe-pyramid-pilot-20261029/code/pilot.py',10,14),block(RR/'pvr-act-comparison-20261027/code/experiment.py',4,11),block(RR/'actual-risk-recovery-20261027/code/engine.py',1,4),
'## 6. 本件边界','',
'本件只确认ACT源码、当前选择入口与静态/既有元数据lineage。不把旧报告、探索卡、替代arm或尚未接线方法当当前规则；不重算历史恢复事件、收益或持仓覆盖。其它dossier片段到达后另作只读lineage核对，不改变本件源文件。']
O.mkdir(parents=True,exist_ok=True)
(O/'EVIDENCE.md').write_text('\n'.join(parts)+'\n')
for p in [LOAD,R,A,N,J,L,REF,GEN,REC,Path(__file__)]:sources[str(p.resolve())]=sha(p)
src=dict(status='ACT_CURRENT_SOURCE_AND_STATIC_LINEAGE_CONFIRMED',source_sha256=sources,active_recovery_metadata=metadata,evidence_sha256=sha(O/'EVIDENCE.md'),new_strategy_imports=0,new_model_calls=0,new_tests=0,new_accounts=0,new_backtests=0,new_synthetic_paths=0,limits=['Static source/alias/class lineage plus archived currentBASELINE metadata identity; no fresh runtime introspection or source function execution.','No recomputation of CSV values or event/outcome tables; quoted generation source and active file identity distinguished.'])
(O/'SOURCE_SHA256.json').write_text(json.dumps(src,ensure_ascii=False,indent=2)+'\n')
print(src['status'],src['evidence_sha256'],sha(O/'SOURCE_SHA256.json'))
