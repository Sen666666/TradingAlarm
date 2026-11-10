"""Concise semantic/read-only behavior report; no policy or account execution."""
from pathlib import Path
from decimal import Decimal as D
import json,hashlib
O=Path(__file__).resolve().parent;W=O.parent;R=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds')
def read(p):return json.loads(Path(p).read_text())
def f(x):return f'{D(str(x)):.2f}'
def wan(x):return f'{D(str(x))/10000:.4f}'
def main():
 assert read(O/'COMPLETION.json')['passed'] and read(O/'2023/COMPLETION.json')['passed'] and read(O/'EXACT_SOURCE_VERIFICATION.json')['passed']
 ss=read(O/'SUMMARY.json');text=['原G1当前状态与历史I资格｜只读语义/实际行为审查｜2026-11-01',
 '结论：当前G1与历史I有效确实不同，但本批主要损耗仍在当前暖级发生；不把“当前未暖”作为主要修复方向，不启用新门，也不把下表直接当删除交易后的政策收益。2023两关注股和全年前三行业的真实参与不足另列，不能用一个温度门替代资金/持有问题。',
 '', '精确语义/原代码位置',
 'grade.py:6/9/30/44：g_grade为{-3强冷,-2冷,-1弱冷,0中性,1修复,2暖,3热,4扩张}，score=25*grade；g_ready表示本观察强度输入有效且已暖机，不表示grade>=2。g_fresh_up和g_acute_down是另两字段。原project暖=ready&&grade>=2，冷退出候选=ready&&(grade<=-2||acute_down)。',
 'B4 model.py:158-185：r=log(C_t/C_prev)，mu_h=(2/(h+1))*r+(1-2/(h+1))*mu_prev，h=5/21；s=max(1.4826*median(|前63个r|),1e-8)，z_h=sqrt(h)*mu_h/s。q_eff=(r/s)*sqrt(clip(V/median(前21个V),1,4))，<=-2急跌、>=2急涨，按正量有效强度观察钟，自第65个有效收盘公开。S21/S63是原双尺度、价格位移和量能信用共同确认的方向状态。',
 '原proposal顺序：双尺度均未确认→0；mu21<0且mu5<=0→-3(双负结构)否则-2；mu21<0且mu5>0→1(S21正)否则-1；mu21>0→3(双正结构)、2(S21正)、1(mu5正)、否则-1；mu21=0时按mu5正/负/零给1/-1/0。双正且z5/z21均>=1覆为4；急涨+新E0正事件+mu5正可至少2；z5<=-1至多-2；acute_down至多-3。',
 'grade.py:23-46：上调另需fresh_up：新E0量价正事件，或新S21/S63正确认，或原S21上行中新的运行价格前沿。降级立即，升级若无fresh则grade保留旧值；source segment重置。故g_grade是逐观察更新、带晋升记忆的状态，并非无记忆当日温度，也不是历史暖永久锁存。',
 'policies_g1.py:18/20/29-34：G1_I进入/恢复要求E0有效、当前暖及(E0 entered或fresh_up)；i_target激活后沿E0与既有floor维持/抬升，只在E0失效或close<=旧floor时退出。仅X/IX额外采用cold退出；本两账用I。i_buy是fresh warm机会日，不是i_target同义词，也不一定新经济周期。',
 'refresh.py:47-65缓存g_grade/g_ready/g_fresh_up/g_acute_down；真实授权采用原账signal_day收盘行（旧历史模型cutoff15:10），不读成交日未来close、不前填缺失。Facts.packet把stock_up映射I；joint_v3.py:213/243将continuing buy_allowed换回market_buyable，因此mobile不要求fresh I。Q共同就绪源自stock/industry E0 ready，加I有效、行业E0有效、H1就绪等，没有current grade>=2。CP1.calculate只用原价量/segment/I有效及自身推进，不读G1。旧rotation的replacement_ok另有G1暖检查，非本两账的资金路径。',
 '', '实际confirmed mobile层：金额万元，闭合正/闭合负/未平为原含费分红账贡献；非全账户损失分母',
 '窗口/动作/当前G1 | 层数 | 新买款 | 闭合正 | 闭合负 | 未平']
 for s in ss:
  for action in ['all','first','add','reentry']:
   for group in ['still_warm','below_warm_known','unknown']:
    x=next(x for x in s['panels'] if x['field']=='current_stock_G1' and x['action']==action and x['group']==group)
    if group=='unknown' and action!='all':continue
    text.append(f"{s['window']}/{action}/{group} | {x['layers']} | {wan(x['buy_cash'])} | {wan(x['closed_positive'])} | {wan(x['closed_negative'])} | {wan(x['open_contribution'])}")
  d=s['below_warm_continuous'];text.append(f"{s['window']} 未暖层闭合负占本批负{f(D(s['below_warm_loss_share'])*100)}%；持续未暖中位/最大{d['median_observations']}/{d['max_observations']}个源价格观察，全部可追到此前暖日，左删失0。持续只数ready且grade已知的连续未暖行，unknown/segment断开，非自然日。")
 text+=['first/add/reentry沿此前已核真实股数/全清边界，分别为首次实际参与、已有股追加、真实全清后重入；不是信号首次，不改旧core保护，不把旧层后来损益归新层。同股多层相关，不是独立胜率。主分母576/602，当前未知0；129个I有效而grade未暖实际反例，证明两个谓词非同义。',
 '“当前grade未暖”还要分记忆：2022的67层中21层、正窗62层中17层，其当日proposal已>=2但promotion_blocked，不能说原始当日证据仍冷。GRADE_VS_PROPOSAL.json给完整金额分解；proposal只作原现成字段语义解释，未替换主分组或信号。',
 '反例：宏和科技2025-08-06追加，grade=-3、proposal=4、acute_down=false、已连续未暖2观察，因缺新G1凭据保留旧grade；新层买款20864.76、闭合净+8617.93元。正窗还有东方钽业7/1(+1111.09)和利欧股份7/15(+262.94)；三层均达原“净贡献/含费买款>=30%”事后尾部口径，共+9991.97元。2022未暖层没有此口径尾部。全部受影响尾部保留，非价格MFE。',
 '2022首次实际授权的宝通科技1/4：I有效、grade=-3、proposal=1、fresh_I=false，未暖已28观察（自2021-11-25，前暖11/24），后净-3093.36元；这是历史I继续有效的真实例，不是本轮认定应卖/不得小试。总体88.43%/89.06%本批闭合负仍来自grade>=2，主要损耗不支持归为G1已冷却却继续扩张。',
 '行业补充仅11/90有现成G1缓存且原价/E0完整前缀核同；其余79未生成指标、保留unknown。对应层2022 暖50/未暖18/未知508；正窗80/28/494。原90行业Q只用E0事实，不能把11行业偏样本推广成全市场结论。完整首次/追加/重入金额面板亦另存。',
 '', '2023两关注股：真实两账/不猜整手',
 '两股原i_buy事件首日均1/3（中际56日、新易52日）；原fresh CP1分别24/27张，个股Q通过22/27张，原市场confirmed/expanded下13/16张。i_buy日数不是独立结构数。',
 '中际旭创300308：Bdiag/C1均0买、0权重/贡献。1/3 Q通过CP1被ACT暂停；1/20最早真实core路由最低100股毛额2897.45元，记录仅probe_risk拒。2/1首次市场confirmed下Q通过CP1，2/2实际mobile路由industry level1，confirmed_migration=false(raw unknown)，probe仍因probe_risk拒；不能把这一条未迁池猜成某项独占cap。后续有pool/sector共存及core最小单位/风险混合拒因，不把全年的未参与归成一手高价。',
 '新易盛300502：Bdiag未参与；首Q通过CP1 1/20，1/30实际mobile最低一手2594.30元、行业probe，probe_risk拒。C1后来4/7无core mobile首次入200股、4/10新凭据追加100股，合计含费20496.85元；日终峰值3.0132%在4/20，4/28按原mobile保护实卖300股，全清净-1020.64元，未平0。5/31新CP1→6/1路由行业新attempt为probe，probe风险/行业资本/行业风险共同拒，未再参与；无白名单或新规则。',
 '', '2023原90行业全年价格涨幅前三（12/30/2022至12/29/2023原同源close；事后评价，不回流选股）',
 '行业/年涨幅/全年价格峰日 | 政策 首买日/累计新买万元/日终最大真实权重/权重峰日']
 rank=read(O/'2023/ALL90_PRICE_RANK.json');
 for sector in rank[:3]:
  for ref in ['Bdiag','C1']:
   x=next(x for x in read(O/'2023'/f'{ref}_TOP3_INDUSTRIES.json') if x['sector']==sector['sector']);date=x['first_actual_new_buy']['at'][:10] if x['first_actual_new_buy'] else '无'
   text.append(f"{sector['name']}/{f(sector['year_return_pct'])}%/{sector['peak_day']} | {ref} {date}/{wan(x['cumulative_new_buy_cash'])}/{f(x['peak_daily_actual_weight_pct'])}%/{x['peak_day']}")
 text+=['权重来自实际日终股数×原raw mark/各自NAV，全242日库存复算核同；盘中最大值未知，涨价被动增重不叫主动扩张。Bdiag通信/计算机各有盈利贡献，不能因未买中际/新易便说完全未捕获主线；消费电子权重峰远早于年底价格峰，C1峰值也仅约2%。行业全90排名、各行业首5成交、资金/闭合正负/未平及两股完整交易和拒因全部留存。',
 '', 'latest旧准备回传（未重做）',
 'july-extension-readiness-20261101仅确认runtime receipt/H1候选数据端到2026-10-30，发布15:51:45+08；研究原market钟仍止6/30，两个代表研究facts也止6/30。原始10/30不是已冻结安全共同终点：全1709/90研究前缀、后续CP1/receipts、held缺行/权息尚未核齐。没有启动latest账户或大缓存；2026/6/30未平兑现继续未决。',
 '', '执行与证据边界',
 '本轮0账户回放、0新指标、0买入门/参数变化。G1连接1178层15.96秒；2023只读行为9.16秒。641股原IX来源SHA与完整暖机manifest核同，1178行grade/ready/fresh/acute与原IX缓存逐值同，原G1源码SHA等于原冻结值。既有层损益/首次追加重入分类来自此前已核账，不冒充本轮新策略收益或独立结果审计。',
 '当前snapshot非PIT/历史全部消费/原日线执行与权息时点代理均不变。只结束当前G1门作为主要修复解释的方向；不据这些后验分组启用过滤、改排序/预算/退出。结果等待主审，未自动扩研究。']
 (O/'READOUT.txt').write_text('\n'.join(text)+'\n')
 paths={
 'grade':(R/'b5-g1-20261025/code/grade.py',9,63),
 'I_project':(R/'b5-g1-20261025/code/policies_g1.py',6,35),
 'pace_scale_acute':(R/'pv-strength-b4-20261025/code/model.py',158,185),
 'current_fields':(Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/desk/refresh.py'),47,65),
 'continuing_Q':(W/'case-stage-ledger-20261031/v3/joint_v3.py',213,219),
 'mobile_roles':(W/'case-stage-ledger-20261031/v3/joint_v3.py',241,256),
 'Q_checks':(Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/desk/admission.py'),185,223),
 'common_E0_readiness':(R/'rs-h1-execution-20261025/code/current_pool_bridge.py',336,366),
 'CP1_own_conditions':(R/'continuous-protection-lines-20261028/code/model.py',26,68)}
 chunks=[];index={}
 for name,(p,a,b) in paths.items():
  lines=p.read_text().splitlines();chunks.append(f'EXCERPT {name}: {p}:{a}-{b}\n'+'\n'.join(f'{i+1}: {lines[i]}' for i in range(a-1,min(b,len(lines)))));index[name]=dict(path=str(p),start=a,end=b,SHA256=hashlib.sha256(p.read_bytes()).hexdigest())
 (O/'SOURCE_EXCERPTS.txt').write_text('\n\n'.join(chunks)+'\n');(O/'SOURCE_INDEX.json').write_text(json.dumps(index,ensure_ascii=False,indent=2)+'\n')
 passed=True
 for s in ss:
  allgroups=[x for x in s['panels'] if x['field']=='current_stock_G1' and x['action']=='all'];assert sum(x['layers'] for x in allgroups)==s['total']['layers']
  for k in ['buy_cash','closed_positive','closed_negative','open_contribution']:assert abs(sum(D(x[k]) for x in allgroups)-D(s['total'][k]))<D('.0000000001')
 final=dict(passed=True,current_G1_predicate_distinct_from_I=True,current_grade_has_promotion_memory=True,cohort_layers=1178,primary_losses_remain_current_warm=True,new_policy_enabled=False,new_accounts=0,new_indicators=0,industry_G1_unavailable=79,behavior2023_complete=True,latest_safe_common_end_not_yet_frozen=True,execution_blockers=[])
 (O/'FINAL_STATUS.json').write_text(json.dumps(final,ensure_ascii=False,indent=2)+'\n')
 # Account and field sources used by both read-only joins remain explicit.
 src=read(O/'SOURCE_SHA256.json')
 for ref in ['Bdiag','C1']:
  root=W/'recovery-2023-readiness-20261101/runs'/ref/'pair'
  for file in ['B.json.gz','daily.jsonl.gz','opportunities.jsonl.gz','funding.jsonl.gz','capacity-checks.jsonl.gz']:src[str(root/file)]=hashlib.sha256((root/file).read_bytes()).hexdigest()
 src[str(W/'july-extension-readiness-20261101/READONLY_CHECKPOINT.json')]=hashlib.sha256((W/'july-extension-readiness-20261101/READONLY_CHECKPOINT.json').read_bytes()).hexdigest();(O/'ALL_SOURCE_SHA256.json').write_text(json.dumps(src,indent=2)+'\n')
 manifest={str(p.relative_to(O)):hashlib.sha256(p.read_bytes()).hexdigest() for p in O.rglob('*') if p.is_file() and p.name!='DELIVERABLE_SHA256.json'};(O/'DELIVERABLE_SHA256.json').write_text(json.dumps(manifest,indent=2)+'\n');print('PUBLISHED',manifest['READOUT.txt'])
if __name__=='__main__':main()
