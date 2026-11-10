"""Extract and call capped_water only; never import an engine or run history."""
from pathlib import Path
from decimal import Decimal as D
import ast,json,hashlib
O=Path(__file__).resolve().parent;ROOT=O.parent
ENGINE=ROOT/'mainline_candidate_v7_demand_capped/engine.py'
REF=ROOT/'mainline_m7_cash_batch_design_v6/once_20260630/REFERENCE_DAILY.json'
FROZEN=ROOT/'mainline_m7_cash_batch_design_v6/once_20260630/SOURCE_HASHES.json'
DAYS=['2024-09-24','2024-10-23','2024-11-07','2024-11-11','2025-01-17'];Z=D(0)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
# Check every artifact in the previously sealed baseline remains byte-for-byte unchanged.
prior=json.loads((O/'OUTPUT_SEAL.json').read_text());priorcheck={name:sha(O/name)==h for name,h in prior.items()};assert all(priorcheck.values()),priorcheck
sources=json.loads(FROZEN.read_text());assert sha(ENGINE)==sources[str(ENGINE)]
source=ENGINE.read_text();tree=ast.parse(source);node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='capped_water')
function_source=ast.get_source_segment(source,node);assert all(not isinstance(n,(ast.Import,ast.ImportFrom)) for n in ast.walk(node))
namespace={'D':D,'ZERO':Z};only=ast.Module(body=[node],type_ignores=[]);exec(compile(ast.fix_missing_locations(only),'EXTRACTED_PURE_capped_water','exec'),namespace);func=namespace['capped_water']
ref=json.loads(REF.read_text());results=[];inputs=[]
for day in DAYS:
 rows=[r for r in ref if r['day']==day];assert len(rows)==50
 assert {r['status'] for r in rows}=={'PASS'}
 assert len({r['expansion_budget'] for r in rows})==1;free=D(rows[0]['expansion_budget'])
 qualified=[r for r in rows if r['W'] is not None and D(r['W'])>0];assert all(r['M']==1 and D(r['E'])>0 for r in qualified)
 weights={r['sector51']:D(r['W']) for r in qualified};upper={r['sector51']:D(r['K'])+D(r['D']) for r in qualified};record={r['sector51']:D(r['X']) for r in rows};assert all(D(r['U'])==D(r['K'])+D(r['D']) for r in rows)
 target=min(max(Z,free),sum(upper.values(),Z));tol=D('1e-18')*max(D(1),abs(target));base,lam,unalloc=func(weights,upper,free)
 expected={s:base.get(s,Z) for s in record};recorderr=max(abs(expected[s]-record[s]) for s in record);assert recorderr<=tol
 dayinputs=[]
 for r in rows:dayinputs.append({k:r[k] for k in ['sector51','M','E','W','K','D','U','X','expansion_budget','unallocated_expansion_budget']})
 inputs.append(dict(day=day,sectors=dayinputs))
 trials=[]
 for c in [D('.01'),D(1),D(100)]:
  scaled={s:w*c for s,w in weights.items()};out,newlam,newun=func(scaled,upper,free)
  err=max((abs(out[s]-base[s]) for s in base),default=Z);sumerr=abs(sum(out.values(),Z)-target);lamerr=abs(newlam*c-lam)
  assert err<=tol and sumerr<=tol and newun==unalloc and lamerr<=tol
  trials.append(dict(W_multiplier=c,allocated_sum=sum(out.values(),Z),max_sector_allocation_difference=err,allocation_sum_identity_error=sumerr,lambda_value=newlam,lambda_times_multiplier_error=lamerr,unallocated=newun,result='PASS',sector_allocations=out))
 results.append(dict(day=day,eligible_sectors=len(weights),sum_W=sum(weights.values(),Z),free=free,eligible_sum_K=sum((D(r['K']) for r in qualified),Z),eligible_sum_D=sum((D(r['D']) for r in qualified),Z),eligible_sum_U=sum(upper.values(),Z),target=min(max(Z,free),sum(upper.values(),Z)),recorded_sum_X=sum(record.values(),Z),baseline_reconstruction_max_error=recorderr,recorded_unallocated=rows[0]['unallocated_expansion_budget'],unallocated=unalloc,numerical_tolerance=tol,trials=trials))
report=dict(result='PASS',scope='Pure capped_water extraction only; no engine module import, Data, Engine, run_loop or history invoked.',eligibility='S consists of current qualified positive W sectors, M=1 and E>0. Sum(K+D) is over S, not all 50 sectors.',identity='sum_{s in S} X_s = min(max(0,free), sum_{s in S}(K_s+D_s)).',scale_invariance='For any c>0 with S, K, D and free fixed, X(cW)=X(W), lambda(cW)=lambda(W)/c. Uniform W scale changes neither total nor relative allocation.',precision='Decimal default precision=28. PASS uses same 1e-18*max(1,target) tolerance as frozen capped_water; report actual differences, not assumed exactness.',prior_baseline_artifact_checks=priorcheck,prior_baseline_all_unchanged=True,source_hashes={str(ENGINE):sha(ENGINE),str(REF):sha(REF),str(FROZEN):sha(FROZEN)},extracted_function_sha256=hashlib.sha256(function_source.encode()).hexdigest(),extracted_function_source=function_source,days=results,caveats=['X is desired allocation of mobile capital, not executed purchases or obligatory daily target holdings. K is not a floor: X<K can create donor surplus.','Actual orders still depend on dated tradability, raw OPEN, quantity rules, caps, fees, cash and atomic unknown boundaries.','The five actual observations all have zero unallocated budget. This follows eligible U>=free, not a high sum W requirement.','Gating MATURE requests before CLOSE independent demand construction changes D and downstream targets. Rejecting only at OPEN may occur after donor sales have already been planned/executed.','This is not a proposal for shared risk pools, absolute E thresholds, or hard exposure limits.'])
(O/'ALLOCATION_SCALING_CHECKS.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,default=str));(O/'ALLOCATION_SCALING_INPUTS.json').write_text(json.dumps(inputs,ensure_ascii=False,indent=2))
num=lambda x:f'{D(x):,.5f}'
t='''# 资金权重统一缩放核验：W不决定是否投满

## 已验证的公式

设S为当前有资格参与扩张分配的行业，即冻结逻辑中的M=1、E>0、W>0行业。每行业上限U=K+D：K为可动存量，D为独立合法成熟新买需求。free为扣除固定、事件预留等之后可分配的成熟资金预算。

**Σ(S内X)=min(max(0,free), Σ(S内(K+D)))。** 求和仅限有资格的S，不是把所有50行业的K全部加进去。K不是最低必须保留的仓位，X<K时可以出现供资余额。

每行业X=min(U,λW)，λ使上述总额满足。资格S、需求D、存量K与预算free固定时，所有W同时乘任意正数c，令新λ=旧λ/c，每个λW以及封顶关系保持不变，所以每个X不变。即使所有行业达到上限，函数选取的最小可行λ也相同比例变化。

**W控制行业之间的相对分配，统一放大或缩小W不是总仓开关。** 是否分满可分配预算，由free及有资格行业的可动存量K＋独立需求D共同决定。行业间W相对比例变动、资格变动或D变动当然可以改变分配。

## 五个实际冻结CLOSE输入，三个统一尺度

只从mainline_candidate_v7_demand_capped/engine.py的AST提取capped_water函数定义，在仅有Decimal与ZERO的命名空间调用。没有import整个engine，没有构造Data/Engine，没有运行history。引擎文件哈希已匹配该次冻结运行SOURCE_HASHES。三个尺度为W×0.01、W×1、W×100。

| CLOSE日期 | 合格行业数 | ΣW | free（元） | ΣK（元） | ΣD（元） | ΣX（元） | 未分配（元） |
| --- | --- | --- | --- | --- | --- | --- | --- |
'''
for r in results:t+='| '+r['day']+' | '+str(r['eligible_sectors'])+' | '+num(r['sum_W'])+' | '+num(r['free'])+' | '+num(r['eligible_sum_K'])+' | '+num(r['eligible_sum_D'])+' | '+num(r['recorded_sum_X'])+' | '+num(r['unallocated'])+' |\n'
maxerr=max(D(tr['max_sector_allocation_difference']) for r in results for tr in r['trials']);recerr=max(D(r['baseline_reconstruction_max_error']) for r in results)
t+=f'''\n15组调用全部PASS。相对原W的最大单行业X差值为{maxerr}元；原尺度复建与冻结REFERENCE_DAILY记录的最大差值为{recerr}元。逐行业向量、λ变换及容差均记录在ALLOCATION_SCALING_CHECKS.json，原输入记录在ALLOCATION_SCALING_INPUTS.json。使用与冻结函数一致的Decimal精度和容差，不以显示到小数两位掩盖误差。\n'''
t+='''
这五日未分配均为0，是因为合格Σ(K+D)足以填满free。11/7的ΣW约86.28022，反而高于9/24约27.56481；坏段不是W绝对值天然小。这里既没有证明简单绝对E门槛有效，也没有为它选阈值。

## 与实际交易及候选门槛的边界

- 分满X不是当天真实全部成交。X是资金分配目标，预算T、新买额度、实际持仓和条件OPEN成交是不同对象；仍受价格、数量、容量、费用、可交易性、T+1、现金和未知原子边界限制。
- 要检验新的MATURE入场资格，应在CLOSE独立需求构造之前挡住不合格票据，让D及后续目标、买入计划、供资计划一起改变。
- 只在次日OPEN最后一刻拒绝，不会自动撤销前晚用该票据构造的资金需求。供资卖出可能已被计划并先行执行，出现“卖了旧仓但新票又不买”的不同实验，不能假装与前CLOSE过滤等价。
- 这是现有资金公式核验，不新增共用试错风险池、不新增硬仓位限制，也不否定为真正趋势承担本金风险。

已核验此前OUTPUT_SEAL列出的所有基线文件字节不变。此次仅新增纯函数核验脚本、报告、机读结果及输入，并更新封存清单；原肥尾基线数字未改。
'''
(O/'ALLOCATION_SCALING_READOUT.md').write_text(t)
(O/'OUTPUT_SEAL.json').write_text(json.dumps({p.name:sha(p) for p in sorted(O.iterdir()) if p.is_file() and p.name!='OUTPUT_SEAL.json'},ensure_ascii=False,indent=2))
print(json.dumps({'result':'PASS','prior_baseline_all_unchanged':True,'max_uniform_scale_difference':maxerr,'max_recorded_reconstruction_difference':recerr,'days':[{k:r[k] for k in ['day','eligible_sectors','sum_W','free','eligible_sum_K','eligible_sum_D','eligible_sum_U','recorded_sum_X','unallocated']} for r in results]},ensure_ascii=False,default=str))
