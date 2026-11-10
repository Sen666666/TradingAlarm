"""Interpret completed projections. Only here join OLD actual outcomes."""
from pathlib import Path
from decimal import Decimal as D
from fractions import Fraction
import sys,json
O=Path(__file__).resolve().parent;sys.path.insert(0,str(O));import extract as X
def main():
 m=X.read(O/'INPUT_MANIFEST.json');out=[];lines=[]
 # These historical outcomes never enter matching.py/project.py inputs.
 actual=X.read(O.parent/'replacement-quality-six-batches-v2-20261102/ALL_ROWS.json')
 lines.append('固定六包 HARD/WEAK/OFF：CLOSE有界条件投影，不是成交或策略收益\n\n')
 lines.append('结论：硬门改变3/6包，弱门改变1/6包。华胜Aug8、翰宇Jan13、欧陆通Aug15三个既定正例包均有完整原Q/D资源见证。硬门保留Aug13旧华胜6800股，却令当批中际原300股增量为0；不能把它称为无代价保住肥尾。六包是既定特选机制样本，不推断全80包开放度或收益优势。\n\n')
 lines.append('域/身份：沿原六批SAMPLE_BINDING；包括Aug13中际入资包，不包括后续Aug15→18中际出资包。后者8条交叉关系只能引用既有粗筛，不据此宣称该包完整可行。Q只原正量股票/原Q上界，D只原层/原数量上界，原0Q不能复活；六包D层数均等于D股票数，未发生多层原D实包。\n')
 lines.append('OFF重新计算原完整Q/D的逐步资源、费用与持久budget，donors/validation及budget-after逐项等原结果；原完整projection对回原证书digest。复用旧选择器搜索，不把原实际fill反推Q，不重跑账户。开放全部匹配边时111/83/41/51/65/101个资源状态核同原约束。\n')
 lines.append('资源匹配：每原生guard/阶段单独有理数流。原自由余量可给所有原Q；D现金、资本、风险只给合格接收者、各自不重复。未用D余量封存，费用/NAV拖累真实扣除，旧超限先占背景修复且不产生自由额度。不是只配现金就允许风险串用。原严格Decimal守卫仍必须全过；最大1e-16的比较仅审计不同运算次序，不用于接纳松限。实际释放现金/风险0。\n\n')
 lines.append('金额表：买=原CLOSE价+原滑点的毛新增目标；卖=原CLOSE mark×计划减持股数；非OPEN实际毛成交，两列不能当实际换手或损益。\n')
 lines.append('批次 | OFF买/卖万元 | HARD买/卖万元 | WEAK买/卖万元\n')
 for c in m['cases']:
  x=X.read(O/c['input']);ds={d['sid']:d for d in x['demands']};lots={z['id']:z for z in x['snapshot']['lots']};old=x['original_D'];label=c['arm']+' '+c['day'];row=dict(case=x['case'],label=label,modes={})
  for mode in ['OFF','HARD','WEAK']:
   r=X.read(O/(mode+'-'+c['arm']+'-'+c['day']+'.json'));Q=r.get('Q',r.get('original_Q'));dm=r.get('D',r.get('original_D'));n=r['native'];
   buy=sum((D(Q[s])*D(ds[s]['mark'])*D('1.0005') for s in Q),D(0));sell=sum((D(z['q'])*D(lots[z['layer']]['mark']) for z in n['donors']['rows']),D(0));fee=sum((D(o['fees']) for o in n['donors'].get('orders',[])),D(0));
   oldmark=sum((D(z['q'])*D(lots[z['layer']]['mark']) for z in x['original_D_parts']),D(0))
   changes=[]
   for sid,orig in x['original_positive_Q'].items():
    if Q[sid]==orig:continue
    a=next(z for z in actual if z['case']==x['case'] and z['side']=='Q' and z['sid']==sid)
    changes.append(dict(sid=sid,name=x['scores'][sid]['name'],original_authorized=orig,new_authorized=Q[sid],original_actual_qty=a['actual_qty'],original_actual_layer_outcomes=a['actual_account_outcomes'],
      no_scaled_counterfactual_PNL=True,original_trace=next((z for z in r.get('trace',[]) if z['sid']==sid),None)))
   kept=[dict(sid=sid,name=x['scores'][sid]['name'],original_D=old[sid],new_D=dm.get(sid,0),retained=old[sid]-dm.get(sid,0)) for sid in old if old[sid]!=dm.get(sid,0)]
   row['modes'][mode]=dict(Q_positive=sum(q>0 for q in Q.values()),D_positive=len(dm),buy_gross=str(buy),D_mark_gross=str(sell),D_preview_sale_net=str(sum((D(z['net']) for z in n['donors']['rows']),D(0))),
      D_preview_sale_fees=str(fee),original_D_mark_retained=str(oldmark-sell),projected_old_risk_release=str(n['validation'].get('projected_risk_released',0)),terminal=n['validation']['terminal'],
      Q_changes=changes,D_retained=kept,initial_original_plan_failure=r.get('initial_original_plan_failure'),
      preserved_original_full_plan=mode=='OFF' or r.get('preserved_original_full_plan',False),seconds=r.get('seconds',0))
  vals=row['modes'];lines.append(label+' | '+' | '.join(f"{D(vals[k]['buy_gross'])/10000:.2f}/{D(vals[k]['D_mark_gross'])/10000:.2f}" for k in ['OFF','HARD','WEAK'])+'\n');out.append(row)
 lines.append('\n逐包变化与资源原因\n')
 for row in out:
  lines.append('\n'+row['label']+'\n')
  for mode in ['HARD','WEAK']:
   r=row['modes'][mode]
   if r['preserved_original_full_plan']:lines.append(mode+'：原Q/D完整保留，原自由资源和各合格边联合分配有见证；不是仅某donor找到一个伙伴。\n');continue
   lines.append(f"{mode}：相对原D保留mark市值{D(r['original_D_mark_retained']):.2f}元；原满Q/D首先不通过{r['initial_original_plan_failure']['why']}，阶段{r['initial_original_plan_failure']['stage']}。随后按原固定队列/有界供资路径重解，非全局最优。\n")
   for z in r['D_retained']:lines.append(f"  旧{z['name']}：D {z['original_D']}→{z['new_D']}，保留{z['retained']}股。\n")
   for z in r['Q_changes']:
    outcomes=z['original_actual_layer_outcomes'];net=sum((D(v.get('total_contribution',v.get('total_closed_contribution','0'))) for v in outcomes),D(0))
    desc=f"原实买{z['original_actual_qty']}、原层净{net:.2f}" if z['original_actual_qty'] else '原未成交，无原层收益'
    lines.append(f"  新{z['name']}：授权{z['original_authorized']}→{z['new_authorized']}（{desc}）。不按缩量比例计算新策略损益。\n")
 lines.append('\n解释与反例\n')
 lines.append('1. Jul22机械包：硬门保留常山北明2000、鹏鼎400、道通2144、四会2500原供资份额，mark合计206491.76。三一4600→900、恒立1200→800；铁建16734→2374、海伦16500→0、山推2700→0。后三票原OPEN本来未成交，不可称省掉它们实际损失；柳工8200、徐工10800、中联11800原授权仍保留，不是消灭机械主亏。全预留阶段风险余量仅约0.17元，而现金有约12.81万元余量；现金存在不等于新增风险可入。\n')
 lines.append('2. Aug13通信包：保留旧华胜6800及其他少量旧股，mark合计113986.02。原自由风险在供资成本后约−5027元，本就需先修复旧占用；硬门不能把这些释放全部借给不支配接收者。前序分配后中际300→0、太辰光300→100，其余原量。中际本身不是无信号/趋势失效；在本固定供资路径下失去增量，不证明所有替代联合组合都买不了。原中际144层后来净−1582.09，但其D+21后验价格潜力+71.30%；两者都不能当本投影收益。这正说明“保护强旧仓”也可阻挡新肥尾参与。\n')
 lines.append('3. Aug20包：原有现金余量约23.24万元，但原风险已超6%预算、供资费用后缺口约5005元。硬门下没有合格资源通道，三原接收增量全0，全部原D保留；不是现金被全禁。弱门仍卖原四股同量，仅埃斯顿1300→1100：总风险能过并不够，它可用的合格风险释放还需单独匹配；原满量匹配缺口约295.97元。欧陆通被保留不代表后面一直上涨，既有21日价格路径后来为负，仍需退出。\n')
 lines.append('4. 华胜Aug8：原现金足够，但风险不是；硬门把原D的风险给占优华胜/广立，徐工可由原自由风险支持，整包原Q/D保留。华胜138层原实际净59068.21（已按独审勘误），原批准7300、原实际7100，不能混称均已成交。翰宇Jan13原6700和全包原Q/D同样保留；旧风险释放/现金各自匹配，不借小额翰宇给其他不合格者背书。Jan瑞可达原H1自适应h与多数原252不同，本轮沿原分数且明确限制，指定翰宇九对均同原252；不重算分数救结果。\n')
 lines.append('5. 弱门在六包5/6原样，只在Aug20小幅改变；不能据此称全80批无用。硬门在六包3/6有实质代价，却没有已证收益优势，交叉不是“新股差”。当前结果支持讨论资本所有权与双尺度冲突，不能宣布硬门胜出或立即推广账户。\n\n')
 lines.append('失败留档：OFF初检先发现未按原完整键排序的检查序列差异；第二次发现C20独立整批预算检查漏接。均在HARD/WEAK前关闭，原例和原源码未动；failures/保留代码/证据，PREFLIGHT.json为最终PASS。\n')
 lines.append('验收范围：18个最终Q/D原生资源/费用再核及每个精确匹配见证独立复算；10个小A/大B、现金/资本/风险分别泄漏、重复占用、封存余量与原自由资源反例。六包没有新金融事件、公司行为/跨日撤单/实际成交仿真或新收益路径；没有全80包优化。源表和已冻结合同保持，原账户与报告未覆盖。\n')
 X.save(O/'SUMMARY.json',dict(cases=out,financial_events=0,no_counterfactual_PNL=True,selected_six_not_all80=True))
 (O/'REPORT.txt').write_text(''.join(lines))
 X.save(O/'ERROR_HISTORY_STATUS.json',dict(current_preflight='PASS',historical_errors_preserved=['failures/01_off_unsorted_input','failures/02_off_C20_separate_budget_guard'],financial_events=0))
 print('REPORT_READY',X.sha(O/'REPORT.txt'))
if __name__=='__main__':main()
