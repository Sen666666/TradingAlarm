"""Read-only reporting and local necessity checks for the two saved projections."""
from selector import *
from inputs import STATIC,BASE
import csv
def read(p):return json.loads(Path(p).read_text())
def minima(result):
 m={}
 for z in result['validation']['checks']:
  k=z['constraint']
  if k not in m or D(z['residual'])<D(m[k]['residual']):m[k]=z
 return m
def main():
 assert read(O/'SYNTHETIC_RESULTS.json')['passed']
 out=O/'report';out.mkdir(exist_ok=False);summaries={};lines=[]
 for k in ('2025_26','2022'):
  x=read(O/'inputs'/(k+'.json'));s=x['snapshot'];A=read(O/'results'/k/'A_JF2.json');B=read(O/'results'/k/'B.json')
  assert read(O/'results'/k/'RESTORED.json')['exact']
  assert A['snapshot_sha256']==B['snapshot_sha256']==J.digest(s)
  assert B['selector_sha256']==sha(O/'selector.py') and B['joint_guard_sha256']==sha(J.__file__)
  old=read(O/'pre-minimality/results'/k/'B.json');assert old['Q']==B['Q']
  comp={c['sid']:c for c in x['evidence']['full_union']};ds={d['sid']:d for d in x['B_demands']};trace={t['sid']:t for t in B['trace']}
  chain=[]
  for m in x['mother']:
   sid=m['sid'];t=trace[sid]
   chain.append(dict(**m,A_joint_quantity=A['Q'].get(sid,0),B_joint_quantity=B['Q'].get(sid,0),B_mobile_target=B['mobile_targets'].get(sid,0),B_reduction=B['D'].get(sid,0),
     B_rejection_or_bounds=t.get('reason') or json.dumps(t.get('blockers_or_necessary_bounds',{}),ensure_ascii=False),
     conditional_single_window_fill_upper=min(B['Q'].get(sid,0),int(m['prior20_fill_capacity_upper'])) if m['prior20_fill_capacity_upper'] is not None else None,
     note='conditional resource quantity, not actual execution; future HLV/window unknown'))
  save(out/(k+'-QUALIFICATION_RANK_TARGET.json'),chain)
  with (out/(k+'-QUALIFICATION_RANK_TARGET.csv')).open('w') as f:
   w=csv.DictWriter(f,fieldnames=list(chain[0]));w.writeheader();w.writerows(chain)
  necessity=[]
  for sid,q in B['D'].items():
   trial=dict(B['D']);less=less_sale(s,sid,q);trial[sid]=less
   tested=evaluate(s,x['B_demands'],B['Q'],trial);assert not tested['validation']['ok'],('redundant donor still exists',k,sid,q-less)
   necessity.append(dict(sid=sid,name=comp[sid]['name'],rank=comp[sid]['competition_rank'],selected_sell=q,restoring=q-less,blocked_by=tested['validation']['violations']))
  save(out/(k+'-DONOR_MINIMALITY.json'),necessity)
  h=collections.Counter()
  for z in s['lots']:
   if z['role']=='mobile':h[z['sid']]+=z['qty']
  recipients=[dict(sid=sid,name=comp[sid]['name'],rank=comp[sid]['competition_rank'],old_mobile_qty=h[sid],increment=q,target=B['mobile_targets'][sid],use=ds[sid]['use']) for sid,q in B['Q'].items() if q]
  beforeD={};pairs=[]
  for t in B['trace']:
   now=t.get('D',beforeD)
   for sid,q in now.items():
    inc=q-beforeD.get(sid,0)
    if inc>0:
     assert comp[sid]['competition_rank']>comp[t['sid']]['competition_rank']
     pairs.append(dict(new=t['sid'],new_rank=comp[t['sid']]['competition_rank'],old=sid,old_rank=comp[sid]['competition_rank'],incremental_sell=inc,not_cash_earmark=True))
   beforeD=dict(now)
  save(out/(k+'-PRIORITY_DONOR_PROOF.json'),pairs)
  Bcash=sum((J.buy_cost(d,B['Q'].get(d['sid'],0)) for d in x['B_demands']),Z);net=sum((D(z['net']) for z in B['donors']['orders']),Z)
  core=sum((num(z,'capital') for z in s['lots'] if z['role']=='core'),Z)
  row=dict(A_Q=A['Q'],A_donor_layers=len(A['donors']['rows']),B_increment_names=len(recipients),B_new_mobile_names=sum(not r['old_mobile_qty'] for r in recipients),B_existing_mobile_add_names=sum(bool(r['old_mobile_qty']) for r in recipients),
   B_donor_names=len(B['D']),B_buy_cash=Bcash,B_donor_net=net,B_core_fixed_capital=core,B_conditional_terminal=B['validation']['terminal'],
   B_conditional_exposure=D(B['validation']['terminal']['capital'])/D(B['validation']['terminal']['nav']),A_conditional_terminal=A['validation']['terminal'],
   B_minima=minima(B),A_minima=minima(A),recipients=recipients,financial_events=0,actual_source_orders_preserved=x['evidence']['actual_saved_funding_orders'])
  summaries[k]=row
  lines += [k,f"  A原收盘S筹资层JF2：Q={A['Q']}，D层数={len(A['donors']['rows'])}。不是完整下一OPEN G/T目标。",
    f"  B fresh={len(x['B_demands'])}；可行增量{len(recipients)}股，其中已有mobile追加{row['B_existing_mobile_add_names']}、当前无mobile{row['B_new_mobile_names']}。",
    f"  B预计买入含费{Bcash}，拟减持{len(B['D'])}股/预计净款{net}，core资本{core}原样固定。",
    f"  条件投影末值={B['validation']['terminal']}，条件曝险={row['B_conditional_exposure']}；不是实际新NAV/收益。",
    '  recipients='+json.dumps(recipients,ensure_ascii=False),
    '  最小残差='+json.dumps({n:r['residual'] for n,r in row['B_minima'].items()},ensure_ascii=False),'']
 save(out/'SUMMARY.json',summaries)
 oldguards=W/'g-s-joint-funding-projection-jf2-20261102'
 for rel,hsh in read(oldguards/'ARTIFACT_SHA256.json').items():assert sha(oldguards/rel)==hsh
 assert sha(BASE/'INPUT_OUTPUT_SHA256.json')=='b85aafe358213f1ae5dac3a55fb9644746dee9f4048e9b439626787119feba4f'
 for r in read(BASE/'run/saved-state-audit/VERIFICATION.json')['checkpoint_restores']:assert sha(Path(r['checkpoint']))==r['checkpoint_sha256']
 static_sources=read(STATIC/'SOURCE_SHA256.json');assert sha(RANK)==static_sources[str(RANK)]
 intro='''B-M2合成与原Jan6/Jul3条件目标投影（完成，停待独审）

14/14合成通过，两真实输入包跨进程重算结果完全一致，全部财务事件0。原账户/原JF2包逐文件hash保持，真实9/16旧卖单一笔未改。未回测、未给收益优越结论。
先说明比较口径：A参考保留已审“原CLOSE S筹资目标形成+修正JF2联合裁量”，是1/4项原筹资目标；不是完整下一OPEN G/T订单模拟。B按原fresh资格独立形成29/94项G/成熟S增量域。因此5/8对1之类不能解释成整户B更好，也不能全归因取消K；Jul3 B前3只G用途尤其不是原A的S筹资项。资格、母域与未进入A筹资的标记逐项公开。

共同点是原股票/F1收盘更新后、原A筹资规划前的显式analysis-only政策比较视图：现金/股数/core/保护/源价格完全保留；只去掉本close原A新筹资元数据的附加锁收费。旧未预留规划愿望/3579.34等源记录完整保存，两种假说在同一视图重新形成当前fresh条件目标；不把这当已撤真实订单或已解除旧真实责任，不能提交为实际账户权限。真实目标/覆盖接线仍需原生provider认证。

B不沿A的裁Q或行业余量：独立上界取fresh原资格、单股10%总量/用途总上限与原数量规则，随后完整(delta,D)共用JF2 validate。捐资只取更后排合法mobile，含同业；core/前排/不可卖固定。空D可行不新增卖。除冻结“弱者先、末股最小”外，成功后还回填可撤销的冗余减量，最终每只再少减一合法步均不通过。
只对固定D使用必要上界剪枝，没有把联合可行性当单调二分；微型合法离散枚举oracle核同。新单STAR仍最低200，已有仓不改minimum；多mobile层按指定FIFO、同股费用一次，绝不借core。NA留原槽不造零分。

'''
 tail='''
主要观察及不利代价
Jul3长城军工/德福科技/北方铜业（联合1/2/4）均保留原mobile数量，无fresh也不强制卖。它们没有因原四项更后排需求而被B取用。B当前新增量对应涛涛车业、京北方、东威科技、博敏电子、华盛锂电；这不是未来赢家名单。
Jan6 B追加京北方、创维数字、以岭药业、华润三九，另给中原传媒、羚锐制药、康恩贝、昆仑万维新mobile目标；天山未获增量。原A修正后仍给天山1900/D9，不能把它当原bug满量筹资。
B换手非常大：为新股更高的名义保护风险，可能卖出大笔仍I/A有效但PVR较后的旧mobile，现金反而增加，条件曝险未到90%。它是排序+风险替换政策的代价，不是资金凭空释放，也不是低排名仓已经失败。所有D在当前选定Q下再少减一合法单位均碰约束；这仅证明本规则局部必要，非全局最小换手/最优组合。
固定反例：本条件B减工商银行并给京北方增量；两者同日比较已存价格标签中，后5观察京+17.19%/工行+5.76%，后21变成京-4.53%/工行+1.83%。同一前缀能先赢后输。不是一笔旧卖专供该新买的真实现金归属，也不是原保护退出策略PnL。PVR迁移到配置卖出可能错卖整理赢家并追冲高股，后续原股无fresh还可能无法及时买回。
严格半导体May7 fresh前8仅1只、前10仅3只的已知事实未改变；本两日投影不能保证该主题80%，更没有把多电子链合并。

覆盖/故障保留
- 首轮Jan6在第7项遇Decimal全量风险release多1e-25/1e-24，被原guard拒绝；failure-v1保留。修B全量释放使用原精确risk，不提高容差、不改JF2。
- pre-minimality保留600415可少减100仍可行的原稿；加入只回填D、保留Q的必要性收口。两日Q前后完全一致。
- restore首轮只认合成demands字段，真实文件B_demands触发KeyError；restore.failed-schema-v1保留。只修两个明示schema分支，合成/真实两种均测，未改selector或重跑账户。
- 运行后新增报告/I-O烟测源码单列，实际执行selector/联合guard SHA与结果一致。所有结果analysis_only、submit_allowed=False，不能装回真实账户。

验收未知：目标换手后实际卖款/部分成交/价格跳空/保护退出/重入/长期收益均未验证。下一步只独立审此包，不自动接runner或扩历史。
入口：CONTRACT_V2及MINIMALITY_CLARIFICATION；selector.py；inputs/*.json共同点证据；results/*；report/*-QUALIFICATION_RANK_TARGET.csv/json；DONOR_MINIMALITY；PRIORITY_DONOR_PROOF；restart；SOURCE_OUTPUT_FREEZE.json。
'''
 (O/'REPORT.txt').write_text(intro+'\n'.join(lines)+tail)
 auth=read(O/'PROJECTION_AUTHORIZATION.json');fixes={p:{'executed':h,'current':sha(O/p)} for p,h in auth['code'].items() if sha(O/p)!=h}
 assert set(fixes)<= {'restore.py','test_selector.py'}
 save(O/'SOURCE_OUTPUT_FREEZE.json',dict(contract_sha256=CONTRACT_SHA,minimality_sha256=MINIMALITY_SHA,selector_sha256=sha(O/'selector.py'),joint_guard_sha256=sha(J.__file__),rank_sha256=sha(RANK),
   code={p.name:sha(p) for p in sorted(O.glob('*.py'))},post_run_io_smoke_fix=fixes,input_files={k:sha(O/'inputs'/(k+'.json')) for k in summaries},
   tests=14,real_input_crossprocess_exact=True,old_financial_checkpoints_unchanged=True,old_JF2_package_unchanged=True,financial_events=0))
 save(O/'ARTIFACT_SHA256.json',{str(p.relative_to(O)):sha(p) for p in sorted(O.rglob('*')) if p.is_file() and p.name!='ARTIFACT_SHA256.json'})
 print(json.dumps(dict(ready=True,selector_sha256=sha(O/'selector.py'),index_sha256=sha(O/'ARTIFACT_SHA256.json'),tests=14,financial_events=0)),flush=True)
if __name__=='__main__':main()
