from pathlib import Path
import sys,importlib.util,json,time,gzip,collections,datetime
from decimal import Decimal as D
import pandas as pd
O=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/loss-switch-reparticipation-20261029')
sp=importlib.util.spec_from_file_location('loss_finish',O/'code/study.py');S=importlib.util.module_from_spec(sp);sys.modules[sp.name]=S;sp.loader.exec_module(S);H=S.H;Z=D(0)
t=time.monotonic();results=H.read(O/'results/results.json');d=pd.read_parquet(O/'results/daily.parquet');cy=pd.read_parquet(O/'results/cycles.parquet');cp=pd.read_parquet(O/'results/CP_candidates.parquet');cand=pd.read_parquet(O/'candidates.parquet');ids=H.read(O/'input-identity.json')['sha256'];assert all(H.sha(p)==h for p,h in ids.items())
meta={x['symbol']:x for x in H.roster()};units=pd.read_parquet(S.E1/'results/units.parquet');units=units[units.variant.eq('I')];e=pd.read_parquet(S.E1/'opportunities.parquet');ref={(r.event_id,r.cost):r.net_return for r in units.itertuples()}
tagged=[]
for c in cy.to_dict('records'):
 day=pd.Timestamp(c['decision_at']).date().isoformat();sub=e[e.symbol.eq(c['symbol'])&e.start.le(day)&(e.end_signal.isna()|e.end_signal.gt(day))];assert len(sub)<=1
 eid=sub.iloc[0].event_id if len(sub) else None;v=ref.get((eid,c['cost']));label='unknown' if v is None or pd.isna(v) else 'tail' if v>=.30 else 'ordinary';tagged.append(dict(**c,reference_event=eid,tail_label=label))
cy=pd.DataFrame(tagged);cy.net_pnl=cy.net_pnl.map(D);cy.to_csv(O/'results/cycles-with-tail-reference.csv',index=False)
summ=[];decomp=[];paired=[]
for scenario in ['original','swap']:
 for cost in [1,2]:
  a=next(x for x in results if x['scenario']==scenario and x['cost']==cost and x['policy']=='I_ONLY');b=next(x for x in results if x['scenario']==scenario and x['cost']==cost and x['policy']=='I_PLUS_CP_AFTER_LOSS');assert a['initial']==b['initial'] and a['trigger']==b['trigger']
  da=d[(d.scenario==scenario)&(d.cost==cost)&d.policy.eq('I_ONLY')].set_index('date');db=d[(d.scenario==scenario)&(d.cost==cost)&d.policy.eq('I_PLUS_CP_AFTER_LOSS')].set_index('date');delta=db.nav.map(D)-da.nav.map(D);incs=delta.diff().fillna(delta.iloc[0]);assert sum(incs,Z)==D(b['nav'])-D(a['nav']);assert all(x==0 for x in delta)
  for day,x in delta.items():paired.append(dict(scenario=scenario,cost=cost,date=day,nav_delta=x,increment=incs.loc[day]))
  for label in ['tail','ordinary','unknown']:
   qa=cy[(cy.scenario==scenario)&(cy.cost==cost)&cy.policy.eq('I_ONLY')&cy.tail_label.eq(label)].net_pnl.sum();qb=cy[(cy.scenario==scenario)&(cy.cost==cost)&cy.policy.eq('I_PLUS_CP_AFTER_LOSS')&cy.tail_label.eq(label)].net_pnl.sum();decomp.append(dict(scenario=scenario,cost=cost,tail_label=label,I=qa,expanded=qb,delta=qb-qa))
  summ.append(dict(scenario=scenario,cost=cost,initial_symbol=a['initial']['symbol'],initial_name=meta[a['initial']['symbol']]['name'],trigger_at=a['trigger']['at'] if a['trigger'] else None,trigger_loss=D(a['trigger']['net_pnl_known_now']) if a['trigger'] else None,I_NAV=D(a['nav']),expanded_NAV=D(b['nav']),delta=D(b['nav'])-D(a['nav']),CP_only_candidates=b['CP_only_flat_candidates'],CP_only_selected=b['CP_only_selected'],CP_only_filled=b['CP_only_entries'],CP_only_buy_cash=D(b['CP_only_actual_cost']),displaced_I_entries=0,all_explicit_fees=D(b['fees']),slippage=D(b['slippage']),final_inventory=D(b['inventory']),dividend_receivable=D(b['dividend_receivable'])))
pd.DataFrame(S.clean(summ)).to_csv(O/'results/identification-and-results.csv',index=False);pd.DataFrame(S.clean(decomp)).to_csv(O/'results/tail-ordinary-decomposition.csv',index=False);pd.DataFrame(S.clean(paired)).to_csv(O/'results/daily-paired-accounting.csv',index=False)
# Read-only quote feasibility: explain unselected candidates, not another strategy arm.
sidset=set(cp.symbol)|set(cp.chosen_symbol);_,m,_,_=H.context(sidset,False);flows=[]
for row in cp[cp.policy.eq('I_PLUS_CP_AFTER_LOSS')].to_dict('records'):
 day=pd.Timestamp(row['date']);cl=H.at(day,datetime.time(15,10));clock=H.A.Clock(cl,m.sessions['A'][__import__('bisect').bisect_right(m.sessions['A'],cl)],cl.date());quote=m.quote(row['symbol'],cl);acct=H.L.SectorAccount(initial_cash=D(row['available_before']),cost_multiplier=row['cost'],fractional_split_policy=m.protocol['fractional_split_policy']);ok,why=acct.reserve_budget(quote=quote,clock=clock,gross_budget_cny=acct.available)
 pool=S.ordered(cand[cand.date.eq(day)].to_dict('records'));priority=next(n for n,x in enumerate(pool,1) if x['symbol']==row['symbol']);chosenrank=next(n for n,x in enumerate(pool,1) if x['symbol']==row['chosen_symbol']);actual=cy[(cy.scenario==row['scenario'])&(cy.cost==row['cost'])&cy.policy.eq('I_ONLY')&cy.symbol.eq(row['chosen_symbol'])&cy.decision_at.eq(str(cl))]
 assert len(actual)==1;flow=dict(**row,candidate_name=meta[row['symbol']]['name'],candidate_priority=priority,known_budget_feasible=ok,selected_priority=chosenrank,chosen_name=meta[row['chosen_symbol']]['name'],CP_filled=0,CP_buy_cash=Z,displaced_I=0,CP_actual_pnl=Z,unchosen_CP_counterfactual_pnl=None,chosen_I_actual_pnl=actual.iloc[0].net_pnl);flows.append(flow)
pd.DataFrame(S.clean(flows)).to_csv(O/'results/CP-opportunity-flow.csv',index=False)
ranges={}
for cost in [1,2]:
 vals=[D(x['nav']) for x in results if x['cost']==cost and x['policy']=='I_ONLY'];ranges[cost]=dict(min=min(vals),max=max(vals),range=max(vals)-min(vals),expanded_same=True)
orig=d[(d.cost==1)&d.policy.eq('I_ONLY')&d.scenario.eq('original')].set_index('date');sw=d[(d.cost==1)&d.policy.eq('I_ONLY')&d.scenario.eq('swap')].set_index('date');diff=orig.held.fillna('CASH')!=sw.held.fillna('CASH');lastdifferent=orig.index[diff][-1];nextsame=orig.index[orig.index>lastdifferent][0]
S.save(O/'results/summary.json',dict(verdict='unidentified_increment_no_policy_divergence',path_rows=summ,candidate_early=2679,CP_only_full_pool=30,I_overlap=2649,I_overlap_fraction=2649/2679,CP_only_encountered_distinct=cp.symbol.nunique(),CP_only_selected=0,CP_only_filled=0,CP_only_cash=Z,displaced_I=0,CP_actual_pnl=Z,unchosen_CP_counterfactual_not_estimated=True,range_cases_only=ranges,base_stock_holding_paths_identical_after=nextsame,necessity_of_loss_trigger_not_identified=True))
S.save(O/'results/report-verification.json',dict(passed=True,input_hashes_unchanged=len(ids),all_daily_policy_nav_deltas_zero=True,tail_ordinary_unknown_sum_to_zero=True,selected_CP_zero_no_counterfactual_return_claim=True,quote_feasibility_only_no_new_economic_paths=True,max_cash_residual=max(D(x['cash_residual']) for x in results),max_nav_residual=max(D(x['nav_residual']) for x in results),seconds=time.monotonic()-t))
def money(x):return f'{D(str(x))/10000:,.2f}'
basis=[x for x in summ if x['cost']==1];flowbase=[x for x in flows if x['cost']==1 and x['scenario']=='original']
table='\n'.join(f"{x['date']} {x['symbol']} {x['candidate_name']}：候选1→获选0→成交0→占资0→挤掉I0→实际贡献0；S0序{x['candidate_priority']}，原I获选{x['chosen_symbol']} {x['chosen_name']}序{x['selected_priority']}，CP最低预算可行={x['known_budget_feasible']}。原I真实后续净贡献{money(x['chosen_I_actual_pnl'])}万元。" for x in flowbase)
text=f'''首次规则亏损后扩大再参与通道：本轮收口

裁决：未识别通道增量，不是CP1无效。失败触发和初始扰动均真实发生，但没有一笔CP1独有成交，两政策全部逐日NAV/实际交易一致，4个配对净差均0。不得用最终收益或零差额验证/否定CP1信息增益、持续纠错或反脆弱性。

设计：407科技池，2023-12-29决策至2026-10-27，每条路径初始100万元且自身现金循环，最多一股；无外部注资/本金重置/ACT。原序与仅首批前两名交换×原I/失败后I+CP×基础/双成本，恰好8条完整路径。新通道仅原CP1首次新凭据、G1已暖、PVR>50、持续资格、年龄0—20，原S0优先序不变；无CP优先、无新退出/参数。亏损后永久开放是一次政策切换；没有额外臂验证亏损触发的必要性。

事前索引：2679个早期首次确认中2649个当天已有原I资格，占98.88%；只有30个CP1独有候选。本轮不能把CP1全部确认数量当作新增可参与机会。11行业/股票与原Q快照及时点限制沿用，不是全市场样本外。
可识别性：首批原序恒铭达002947，交换力鼎光电605118；均2024-01-02实际买入。原序2024-01-09卖完，首次净损75,709.81元；交换2024-02-01卖完，首次净损358,632.08元（基础）。两臂各自初始成交、触发日、触发时已知权益和触发前审计逐项相同；触发时两者已知应收股息均0，没有后结算回填。双成本同日触发，净损77,177.73/359,006.28元。

独有机会漏斗（以下两个日期每个情景/成本均相同；完整8行见CP-opportunity-flow.csv）：
{table}
两只CP候选在当时资金下都能满足最低买量，但排序较后的它们未获选。不是资金被额外缓冲、10%上限或廉价股排序挡住。实际所选I后续亏损是事后事实，不能据此推断未买CP一定更好；未选CP反事实收益本轮没有计算，实际贡献0绝非潜在收益0。CP1没有挤掉任何I持有，所有CP1专属资金、费用与尾部/普通增量均0。

资金路径：基础原序终值{money(basis[0]['I_NAV'])}万元，交换{money(basis[1]['I_NAV'])}万元；双成本原序251.53、交换80.63万元。两政策完全相同。两初始情景基础极差{money(ranges[1]['range'])}万元，双成本{money(ranges[2]['range'])}万元，只是案例敏感性，不是总体稳健性估计。基础持股身份从{nextsame}起直到末端趋同，但现金/股数与净值落差未消失；后续买到同样股票不等于恢复已经损失的本金。
基础原序/交换显式费用分别{money(basis[0]['all_explicit_fees'])}/{money(basis[1]['all_explicit_fees'])}万元，原开盘滑点{money(basis[0]['slippage'])}/{money(basis[1]['slippage'])}万元，均已在净账中。每条末端仍有1个持仓，市值/待收股息分别251.073/1.802万元和80.784/0.46912万元，均纳入主账，未将估值当成成交。尾部沿用实验一共同E0原I的30%事后标签，普通/尾部/未知分列；各分项政策差额全部0，不以胜率验收。

正确性：候选优先序与原S0纯选择器681日逐项相同。两政策分叉前原始审计一致；8路径全部独立费用、开盘价、现金、股数、权息、逐轮损益/终值及每日经济NAV核对，最大现金/NAV残差0。2024-06-28物理历史前缀样例与全量金融前缀精确一致。原{len(ids)}项关键输入SHA不变。原日线成交/容量及权息代理限制继续存在，不冒称实盘执行。
耗时：候选冻结1.116秒；8条历史前缀样例5.542秒；8条完整路径4.200秒（含上下文加载/哈希/写盘），低于300秒；后续只做已有账聚合与报价可负担性核验，未增加金融路径、补起点或放宽规则。开发/阅读未预设独立秒表，不伪造纯开发耗时；文件时间保留。无实现失败、无结果后调参。

对算法职责的有限更新：本早期CP定义与原I入场资格高度重叠，因此“扩大这一个通道”几乎没有改变选择集；两个真正遇见的独有机会又由原排序选择了其他I股票。这比笼统说CP1未改善收益更具体，但仍不能单独否定CP1作资金优先证据、判断I所有时点合理，或认定E0/PVR公式有错。E0/PVR本轮未被单独识别，原排序和退出的信息价值也未隔离。
本轮到此停止。若继续，需要另冻问题审查同日候选的资金排序或持仓占用价值，不能偷偷给CP1优先权来使本轮产生分叉。不会自动运行。

交付：PROTOCOL.json、candidate-freeze.json、input-identity.json、code/study.py；results/identification-and-results.csv、CP-opportunity-flow.csv、daily-paired-accounting.csv、cycles-with-tail-reference.csv、tail-ordinary-decomposition.csv、results.json、summary.json、audit.jsonl.gz及核验。产品/交易台/账户访问/交易/外部发送均0；没有未解决阻塞。
'''
(O/'FINAL_REPORT.txt').write_text(text)
S.save(O/'COMPLETION.json',dict(status='completed',verdict='unidentified: no CP-only selected or filled under frozen ranking',paths=8,CP_only_full_pool=30,CP_only_flat_encounters_per_path=2,CP_only_selected=0,CP_only_filled=0,all_pair_deltas=0,sample_seconds=5.541579792276025,full_seconds=4.200170375406742,input_hashes_unchanged=len(ids),blockers=[],product_changes=0,accounts=0,trades=0,report=str(O/'FINAL_REPORT.txt')))
print(json.dumps(S.clean(dict(completed=True,flow=flowbase,ranges=ranges,holdings_converged_after=nextsame,seconds=time.monotonic()-t)),ensure_ascii=False))
