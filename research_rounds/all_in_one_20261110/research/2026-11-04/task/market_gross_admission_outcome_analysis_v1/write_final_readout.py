"""Render saved evidence only; never runs an account or changes sources."""
from pathlib import Path
from decimal import Decimal as D
import csv,json,hashlib
O=Path(__file__).resolve().parent;T=O.parent
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,r):p.write_text(json.dumps(r,ensure_ascii=False,indent=2,default=str)+'\n')
def f(v,d=2):return f'{D(str(v)):.{d}f}'
windows={w:read(O/f'full_{w}_v1/SUMMARY.json') for w in ['long','strong']};long=O/'full_long_v1';periods=read(long/'ALL_PERIODS_VS_ARCHIVED_B.json');phase=read(long/'FIXED_PHASE_WEALTH.json');act=read(long/'OWN_ACT_RECOVERY_WAIT_PATH.json');segs=read(long/'ALL_PREDECLARED_OPEN_SEGMENTS_VS_ARCHIVED_B.json')
lines=['D_GROSS10冻结版本：结果与主要失败点','',
'三年仍亏28.13579%、2024自身再亏16.33490%，绝对结果仍差；不能因好于原No60或DD31.10678%低于35%而晋升。本轮不调10参数。减少D下新增资金确实改变了自身风险路径，但没有解决NOT_DOWN下的损耗与自身ACT恢复等待。',
'',
'范围：long2022Jan4–2024Dec31，726CLOSE自身连续、初始1m；strong2025Jul1–2026Jun30，242CLOSE独立fresh1m。不是完整25/26自然年，不合成连续2022—26账户。B只引用ARCHIVED_B_CONTROL_BINDING归档金本和旧已审结果，没有新B运行、合并book或views。现有1709A股开发快照、非PIT/OOS/HK/120万元实盘证明。',
'',
'全窗口（ret% / global CLOSE DD% / 全日历实际费用元 / 平均lag市值暴露% / 原native平均CLOSE mark-floor名义风险%）：']
matrix=[]
for win in ['long','strong']:
 for arm in ['D_GROSS10','ARCHIVED_B']:
  a=windows[win][arm];m=a['account_metrics'];p=a['whole_calendar'];r=dict(window=win,arm=arm,return_pct=m['return_pct'],CLOSE_global_DD_pct=m['global_DD']['percent'],actual_fees=m['fees'],mean_lag_market_exposure_pct=p['mean_lag_exposure_pct'],mean_close_nominal_mark_floor_risk_pct=p['mean_close_nominal_risk_pct'],buy_fills=m['buy_fills'],sell_fills=m['sell_fills'],paused_CLOSE_days=m['paused_closes']);matrix.append(r)
  lines.append(f"{win} {arm}: "+' / '.join(f(r[k],4) for k in ['return_pct','CLOSE_global_DD_pct','actual_fees','mean_lag_market_exposure_pct','mean_close_nominal_mark_floor_risk_pct']))
lines+=['市值暴露、mark-floor名义风险与实际损失风险分别理解，不称同风险或止损保证。', '', '长期逐年：own年初→期末元 / 年净元 / own年度收益%：']
for year in ['2022','2023','2024']:
 r=next(r for r in periods if r['grain']=='year' and r['period']==year)
 for arm in ['D_GROSS10','ARCHIVED_B']:
  a=r[arm];lines.append(f"{year} {arm}: {f(a['initial_own_NAV'])}→{f(a['end_NAV'])} / {f(a['wealth_change'])} / {f(a['return_pct'],4)}%")
r=next(r for r in periods if r['grain']=='year' and r['period']=='2023');lines.append('2022—23累计D/B：'+f((D(r['D_GROSS10']['end_NAV'])/D(1000000)-1)*100,4)+'% / '+f((D(r['ARCHIVED_B']['end_NAV'])/D(1000000)-1)*100,4)+'%。2023正收益没有填回2022损失。')
lines+=['', '自身ACT路径：规则仍是原ACT20/BREAK63，旧B日历只作对照，不当D输入。']
for arm in ['D_GROSS10','ARCHIVED_B']:
 a=act[arm];lines.append(f"{arm}: paused OPEN/CLOSE {a['own_paused_OPEN_days']}/{a['own_paused_CLOSE_days']}，市场NOT_DOWN但own ACT仍暂停{a['NOT_DOWN_but_own_ACT_paused_OPEN_days']}个OPEN。")
 for e in windows['long'][arm]['account_metrics']['ACT_events']:lines.append(f"  实际{e['at']} {e['event']}，原NAV{f(e['nav'])}，源episode DD{f(D(e['episode_drawdown'])*100,4)}%，源peak{f(e['peak'])}。")
lines+=['D在2022—23没有自己的ACT pause；2024Jun11首次因自身episode DD20.3781%触发，Sep27 CLOSE flat/fast/breakout均真才恢复。减少新增流量后没有触发原B那两次历史pause，是已观察路径；并不等于改变了恢复公式或证明所有避免pause都更好。D在2024Sep24–27依旧空仓/暂停，随后Sep30才有49个buyfill、679728.34元，收盘仓位从0到82.9025%。',
'', '固定924与之后，按各自真实期初NAV：']
for name in ['924_six_closes','post924']:
 x=phase[name];d=x['own_NAV_account_period'];b=x['ARCHIVED_B_phase']['account_own_NAV_period'] if 'account_own_NAV_period' in x['ARCHIVED_B_phase'] else None
 # Older archived phase retains interval wealth, while own-NAV period can be
 # read from the already bound B daily flows below without a new account.
 if b is None:
  br=read(T/'capacity_cost_guard_analysis_v1/full_long_v1/B_DAILY_WEALTH.json');rr=[r for r in br if d['start']<=r['day']<=d['end']];b=dict(return_pct=(D(rr[-1]['NAV_end'])/D(rr[0]['NAV_begin'])-1)*100,wealth_change=sum((D(r['wealth_change']) for r in rr),D(0)),mean_lag_exposure_pct=sum((D(r['lag_exposure_pct']) for r in rr),D(0))/len(rr))
 lines.append(f"{name}: D/B自身收益{f(d['return_pct'],4)}%/{f(b['return_pct'],4)}%，财富变化{f(d['wealth_change'])}/{f(b['wealth_change'])}元，平均lag市值暴露{f(d['mean_lag_exposure_pct'],4)}%/{f(b['mean_lag_exposure_pct'],4)}%；D暂停OPEN{d['paused_OPEN_days']}。")
g=phase['post924_old_new_D']['groups'];lines.append(f"D post净−186615.50元＝Oct8真实持有{g['actually_held_at_boundary']['layers']}层{f(g['actually_held_at_boundary']['wealth'])}＋之后新增{g['new_fill_after_boundary']['layers']}层{f(g['new_fill_after_boundary']['wealth'])}元；已闭层0。不同起始财富不能仅凭元差宣传省损。")
ls=read(long/'analysis/long/D_GROSS10/LAYERS.json');new=[r for r in ls if r['opened'][:10]>'2024-10-08'];roles=[]
for role in ['core','mobile']:
 rr=[r for r in new if r['role']==role];row=dict(role=role,layers=len(rr),actual_buy_cash=sum((D(r['cost']) for r in rr),D(0)),original_path_contribution=sum((D(r['net']) for r in rr),D(0)),positive_layer_contribution=sum((D(r['net']) for r in rr if D(r['net'])>0),D(0)),negative_layer_contribution=sum((D(r['net']) for r in rr if D(r['net'])<0),D(0)));roles.append(row);lines.append(f"新增{role}: {len(rr)}层、买款{f(row['actual_buy_cash'])}元、原路径贡献{f(row['original_path_contribution'])}元（正层{f(row['positive_layer_contribution'])}/负层{f(row['negative_layer_contribution'])}）。")
postdays=[r for r in segs if r['definition']['start']<='2024-10-09'<=r['definition']['end']];assert len(postdays)==1 and postdays[0]['definition']['state']=='NOT_DOWN' and postdays[0]['definition']['end']=='2024-12-31'
lines+=['post全部NOT_DOWN，10%额外准入本来就关闭，未覆盖主要失败。2024Nov平均lag市值暴露D87.0016%，月亏14.1566%；Dec再亏6.2528%。D2024比B更差，不能用2022较少亏掩盖。',
'', '完整预定分段与旧边界：']
for state in ['DOWN','NOT_DOWN']:
 rr=[r for r in segs if r['definition']['state']==state];changes=[D(r['D_GROSS10']['wealth_change']) for r in rr];lines.append(f"{state}: {len(rr)}连续段，D期间财富正/负/零段数{sum(v>0 for v in changes)}/{sum(v<0 for v in changes)}/{sum(v==0 for v in changes)}；全部保留。")
lines+=['全long12D+13ND逐段账户财富/回报/费用/暴露与归档B并列保存在ALL_PREDECLARED_OPEN_SEGMENTS_VS_ARCHIVED_B.json。旧9段仅到2023Dec29，逐日prefix exact；第9段新full继续至2024Feb19，不能混成同一区间。旧9的D carry/new同已审边界表保留所有正/负/零；新2024段不造B层财富管线。',
'旧9中值得同时看正反：D DOWN01的carry−46860.79/new−24658.75；DOWN04 carry+53786.50/new0，保留独立强势赢家且抑制新增试错；DOWN05/06仍旧carry分别−33999.89/−28274.30，说明减少新流量不处置已有风险。DOWN02 D−8866.86而B+34460.18，是门可能损害可执行反弹参与的反例，不能只看避损段。',
'', '恢复/首买正反路径（原实际行为，不是新规则）：']
dr=read(long/'D_DAILY_WEALTH.json');br=read(T/'capacity_cost_guard_analysis_v1/full_long_v1/B_DAILY_WEALTH.json');firstrows=[]
for label,lo,hi in [('June22_ND','2022-06-07','2022-06-30'),('MarApr23_ND','2023-03-22','2023-04-21'),('Feb24_ND','2024-02-20','2024-02-29'),('Sep24_ACT_resume','2024-09-30','2024-10-08')]:
 for arm,data in [('D_GROSS10',dr),('ARCHIVED_B',br)]:
  x=next((x for x in data if lo<=x['day']<=hi and int(x['buy_fills'])>0),None);firstrows.append(dict(context=label,arm=arm,lo=lo,hi=hi,first_actual_buy_day=x['day'] if x else None,actual_buy_cash=x['actual_buy_cash'] if x else None,buy_fills=x['buy_fills'] if x else None,lag_market_exposure_pct=x['lag_exposure_pct'] if x else None,close_market_exposure_pct=x['exposure_pct'] if x else None,own_ACT_at_OPEN=x['ACT_at_OPEN'] if x else None))
  if x:lines.append(f"{label} {arm}: {x['day']}首buy、{x['buy_fills']}fill/{f(x['actual_buy_cash'])}元，lag→CLOSE市值暴露{f(x['lag_exposure_pct'],4)}→{f(x['exposure_pct'],4)}%。")
  else:lines.append(f"{label} {arm}: 该窗口无新buy；不等于无既有持仓参与。")
lines+=['June22 D整月+3.9210%、Apr23+14.2307%、Feb24+2.5932%；因此一次恢复较多新资金并非自动错误，也不能只凭Sep24后损失提出慢加仓或更早卖。Sep30 D进入前已错过四个关键OPEN；恢复后又出现大量新的损耗，是两项独立问题。',
'', '下一最有量的具体切点：',
'先查非D/原ACT恢复后，mobile新增风险授权如何随真实持仓/试错反馈延续或收缩。post新mobile227层−107345.19元，占整个post净损耗约57.5%，是大于旧carry−61905.83元的现成规模；这是原路径关联，不是可实现省损。与并行个股买入质量线分工：本线关注组合/授权持续与资金投入顺序，不重做股票排名、量因子或B回带标签。先用Sep24、June22、Apr23、Feb24的同类原行为和赢家反例检验能否分离失败，再决定候选；当前不拟新阈值、不跑账户，不将更早恢复/慢加仓自动当解法。',
'', '强窗与控制：',
'strong四D段共14OPEN新增D买0，B同日91fill/198.50万元买款；有避损段，也有少赚的正段。两者全局DD11.6595%都在首次D之前的2025Dec4，不能据此证明回撤改善。两者ACT暂停均0。严格URFI881121/126成员H1半导体D期间贡献−19169.90元/B−16783.58元；电子化学品未混入。固定leader路径与全集股票差在strong文件，不以两条都盈利的微差代替long验收。',
'146个完整CLOSE的全ND前缀（至2026Jan30，首次D为Feb2 CLOSE）15项daily财务字段与1218个实际fill聚合D/归档B exact，0差异；只排除标签/RID/元数据。STRONG_ND_PREFIX_FINANCIAL_EXACT.json有源SHA。',
'', '审查状态：strong底层financial/PVR/atomic已独审PASS；long主审在途，新增月/期间/旧新/ACT派生表待独审，后续只append收据。原reader按真实qty/现金/AR/原rawmark核桥，0新账户/0新Bbook或views/0新金融引擎。执行仍daily-bar proxy，缺口和滑点不保证保本。']
(O/'READOUT.txt').write_text('\n'.join(lines)+'\n');save(long/'POST924_NEW_ROLE_CONTRIBUTION.json',dict(rows=roles,scope='Original actual new-fill cohort through fixed2024cutoff, not avoidable loss; actual core/mobile not a new buy-quality label',derived_review='PENDING'));save(long/'FIRST_BUY_RECOVERY_CONTEXT.json',dict(rows=firstrows,scope='Observed own states and original actual fills only; B xref not input',derived_review='PENDING'))
with (O/'PERFORMANCE_MATRIX.csv').open('w') as h:w=csv.DictWriter(h,fieldnames=list(matrix[0]));w.writeheader();w.writerows(matrix)
rp=T/'market_gross_admission_full_ledger_review_v1/STRONG_FINANCE_PVR_ATOMIC_REVIEW.json';save(O/'REVIEW_STATUS_APPENDIX.json',dict(strong_financial=dict(path=str(rp),sha256=sha(rp),status=read(rp)['status']),strong_ND_prefix=dict(path=str(O/'STRONG_ND_PREFIX_FINANCIAL_EXACT.json'),sha256=sha(O/'STRONG_ND_PREFIX_FINANCIAL_EXACT.json')),long_financial='PENDING',derived_grouping='PENDING',historical_pending_fields_retained=True))
save(O/'FINAL_DELIVERABLE_BINDING.json',dict(files={str(p.relative_to(O)):sha(p) for p in [O/'READOUT.txt',O/'PERFORMANCE_MATRIX.csv',O/'REVIEW_STATUS_APPENDIX.json',O/'ALL_PREDECLARED_MARKET_STATE_SEGMENTS.json',long/'SOURCE_BINDING.json',O/'full_strong_v1/SOURCE_BINDING.json',long/'POST924_NEW_ROLE_CONTRIBUTION.json',long/'FIRST_BUY_RECOVERY_CONTEXT.json']},new_accounts=0,new_B_books_or_views=0,financial_or_signal_engine_created=0,main_claims_review='PENDING_LONG_FINANCIAL_AND_DERIVED'))
print('WROTE_FINAL_READOUT_PENDING_REVIEW',len(lines),flush=True)
