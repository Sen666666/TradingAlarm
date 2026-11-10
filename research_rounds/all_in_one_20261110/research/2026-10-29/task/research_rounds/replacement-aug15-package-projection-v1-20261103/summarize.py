"""One fixed package readout; no solver/account invocation."""
from pathlib import Path
from decimal import Decimal as D
from fractions import Fraction
import json,hashlib
O=Path(__file__).resolve().parent;R=O.parent
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def main():
 x=read(O/'INPUT.json');q0=x['original_positive_Q'];d0=x['original_D'];ds={z['sid']:z for z in x['demands']};lots={z['id']:z for z in x['snapshot']['lots']}
 results={m:read(O/(m+'.json')) for m in ['OFF','HARD','WEAK']};summary={}
 for m,r in results.items():
  buy=sum((D(q)*D(ds[s]['mark'])*D('1.0005') for s,q in r['Q'].items()),D(0));sell=sum((D(z['q'])*D(lots[z['layer']]['mark']) for z in r['native']['donors']['rows']),D(0))
  summary[m]=dict(Q={s:q for s,q in r['Q'].items() if q},D=r['D'],buy_gross_C_close_preview=str(buy),D_mark_gross=str(sell),
    D_preview_net=str(sum((D(z['net']) for z in r['native']['donors']['rows']),D(0))),
    projected_old_risk_release=r['native']['validation']['projected_risk_released'],
    terminal_conditional_projection=r['native']['validation']['terminal'],
    matching_states=r['matching']['checked_resource_states'],seconds=r.get('seconds',0),
    mid_old300_retained=300-r['D'].get('300308.SZ',0),old_guangku1100_retained=1100-r['D'].get('300620.SZ',0))
 hard=results['HARD'];weak=results['WEAK']
 assert hard['D']=={'003031.SZ':200} and hard['Q']['002534.SZ']==1600 and hard['Q']['002518.SZ']==0
 assert weak['D']['300308.SZ']==300 and weak['Q']['002534.SZ']==6200 and weak['Q']['002518.SZ']==3200
 earlier=R/'replacement-six-package-projection-v1-20261103/HARD-C10-2025-08-13.json';e=read(earlier)
 assert e['Q']['300308.SZ']==0 and not e['D'].get('600410.SH',0)
 boundary=dict(Aug13_independent_original_snapshot=dict(source=str(earlier.resolve()),sha256=sha(earlier),hard_mid_new_Q=e['Q']['300308.SZ'],hard_old_Huasheng_D=e['D'].get('600410.SH',0)),
    Aug15_independent_original_snapshot=dict(input_sha256=sha(O/'INPUT.json'),old_mid_qty=300,hard_mid_D=0,weak_mid_D=300),
    continuous_chain_proved=False,combining_favorable_snapshots_prohibited=True,
    conclusion='For this original Zhongji chain, hard gate does not preserve both early funding and later retention under the fixed-order snapshots. Later legal reentry and continuous wealth remain unknown.')
 save(O/'CROSS_TIME_BOUNDARY.json',boundary);save(O/'SUMMARY.json',dict(modes=summary,financial_events=0,conditional_not_fills=True,not_counterfactual_PNL=True))
 out=[]
 out.append('Aug15 CLOSE→Aug18 OPEN C10单包补充：同冻结实现的独立条件投影\n\n')
 out.append('结论：HARD令旧中际D300→0，保留原300股；WEAK仍D300，不能保护这次中际供资。HARD的代价是西子原Q6200→1600、科士达3200→0，整个新增毛目标43.37→2.91万元。WEAK保留西子/科士达原量，新增毛目标30.60万元。全部是CLOSE已知价/原线/费用的条件计划，不是新成交或损益。\n\n')
 out.append('固定来源：原C10证书6b5bef52cbbdaa48c486c9c1091d356c51932af85b33930d465450325b913ef6；从原Aug15完整checkpoint提取可信规划前snapshot，保留原正Q8、D6及逐层上界。使用原六包project.py/matching.py/extract.py原件、原合同；仅P.O输出目录重绑定，没有任何策略分支/参数/域/顺序变化。OFF的原donors/validation/budget-after逐项等原结果，全部开放边的121资源状态通过；HARD41、WEAK89个资源状态与原严格守卫复算。金融事件0，实际资源释放0。\n\n')
 out.append('逐接收目标（股数，原Q不是原成交量）\n股票 | OFF | HARD | WEAK\n')
 for sid in q0:out.append(f"{x['scores'][sid]['name']} {sid} | {q0[sid]} | {hard['Q'][sid]} | {weak['Q'][sid]}\n")
 out.append('\n旧供资份额（股数，0表示在本静态包不因机会筹资减持）\n股票 | OFF D | HARD D | WEAK D\n')
 for sid in d0:out.append(f"{x['scores'][sid]['name']} {sid} | {d0[sid]} | {hard['D'].get(sid,0)} | {weak['D'].get(sid,0)}\n")
 out.append('\n金额/风险口径\n')
 for m in ['OFF','HARD','WEAK']:
  z=summary[m];out.append(f"{m}：新增毛目标{D(z['buy_gross_C_close_preview']):.2f}元；D的CLOSE毛市值{D(z['D_mark_gross']):.2f}元、原预览净卖款{D(z['D_preview_net']):.2f}元；条件释放旧名义风险{D(z['projected_old_risk_release']):.2f}元。实际释放仍0。\n")
 out.append('原D的CLOSE总市值385122元；HARD保留其中373852元（含中际300股CLOSE市值71415元），只允许中瓷200股供资；WEAK保留光库800股CLOSE市值65600元，其余原D仍执行计划。不能把这些CLOSE市值替换成Aug18实际成交金额。\n\n')
 out.append('为何买入削减：原自由现金高于10%保留线有252175.94元，但原6%风险余量仅1424.44元。HARD下，旧中际与8新股均交叉、其他多数旧D也没有硬合格伙伴；仅中瓷有7个硬伙伴。其约406.79元原风险释放也不能无限放大，因此按原队列只容纳盛弘100、西子1600、上海100；原自由现金仍可用，并未整体禁掉。HARD满量首先失败于西子reserve阶段的风险匹配。\n')
 out.append('HARD末次全预留阶段风险余量约14.50元，现金保留线以上仍约234325.55元；资金闲置与风险容量不能混称。WEAK虽允许中际的8条交叉边，却不能将光库大量风险转给其双维落后的西子/科士达等；只可给合格盛弘/博威等实际需求，不能借很小的盛弘为其他股票背书。其原满量首先在中恒阶段风险匹配失败；原D光库1100缩至300，中恒4600→3800、上海10800→100、新雷能800→0、网宿100→0，其余原Q保留。\n\n')
 out.append('赢家代价：原路径西子实际6200股层净+7925.53、科士达3200股层净+11060.40；HARD会削减/删除它们本批授权，不能只宣传留住中际。这里未按股数比例缩放这些历史利润，更未计算保留中际后的假设收益。原新雷能本来未成交，HARD/WEAK取消其Q不能称省掉既有损失。\n\n')
 out.append('跨时点一致性：Aug13同一HARD已因保留旧华胜/固定前序资源分配而使中际新Q300→0；所以这个仍含原中际300股的Aug15 HARD包是独立诊断，不是Aug13 HARD的连续后态。现有证据反驳“这条硬门能同时原样保留中际早期获资与后来持续持有”这一具体目标；既不能拼接成先买后拿住，也不能据此断言后续一定没有其他合法入场或连续收益更差。WEAK允许交叉，因此本包仍卖中际300，亦非这一持有问题的修复。\n\n')
 out.append('完整数量、逐资源流和原生限制余量见OFF/HARD/WEAK.json。run.py只提取旧输入、调用冻结纯投影及复核，不调用任何账户事件；父六包目录文件/hash完全不变。不得接runner/外推所有主线/追加其他包。\n')
 (O/'REPORT.txt').write_text(''.join(out))
 sources=read(O/'VERIFICATION.json')['sources_sha256'];sources[str(earlier.resolve())]=sha(earlier)
 manifest=dict(scope='ONE_ADDITIONAL_AUG15_ORIGINAL_SNAPSHOT_STATIC_PACKAGE',financial_events=0,new_indicators=0,new_forward_labels=0,not_a_continuous_path=True,submit_allowed=False,
   inherited_contract_sha256=x['contract_sha256'],sources_sha256=sources,
   files_sha256={f.name:sha(f) for f in sorted(O.iterdir()) if f.is_file() and f.name!='DELIVERABLE_MANIFEST.json'})
 save(O/'DELIVERABLE_MANIFEST.json',manifest);print('REPORT',sha(O/'REPORT.txt'),'MANIFEST',sha(O/'DELIVERABLE_MANIFEST.json'))
if __name__=='__main__':main()
