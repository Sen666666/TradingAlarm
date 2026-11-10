"""Summarize existing preflight counts and correct supplemental case evidence only."""
from pathlib import Path
import json,hashlib,math
import pandas as pd,numpy as np
O=Path(__file__).resolve().parent;R=O.parent;H={}
def src(p):
 p=Path(p);H[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();return p
def clean(x):
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [clean(v) for v in x]
 if isinstance(x,np.generic):return clean(x.item())
 if x is pd.NA or x is pd.NaT:return None
 if isinstance(x,float) and not math.isfinite(x):return None
 return x
def dump(n,x):
 with (O/n).open('x') as f:json.dump(clean(x),f,ensure_ascii=False,indent=2,allow_nan=False)
src(__file__);e=pd.read_csv(src(O/'REGISTERED_ENTRY_PREFLIGHT.csv'),low_memory=False);m=pd.read_csv(src(O/'MARKET_RECEIPT_PREFLIGHT.csv'),low_memory=False);c=pd.read_csv(src(O/'FIXED_CASE_PREFLIGHT.csv'),low_memory=False)
def role(row):
 g=row['preflight_gate']
 if g=='KEEP_ORIGINAL_ROOT_BIRTH':return 'BIRTH_ORIGINAL_ELIGIBILITY'
 if g=='BYPASS_EXISTING_PROBE_PARENT':return 'EXISTING_PARENT_OUTSIDE_GATE'
 if g.startswith('UNKNOWN'):return 'UNKNOWN'
 return {'NO_CURRENT_USABLE_AUTHORIZATION':'LATE_NO_CURRENT_ACTIVE_AUTH','CURRENT_AUTH_NOT_STRICTLY_POST_BIRTH':'LATE_ACTIVE_AUTH_NOT_POST_BIRTH_PURE_INCREMENT','CURRENT_ACCEPTED_POST_BIRTH_AUTHORIZATION':'LATE_ACTIVE_POST_BIRTH_AUTH'}[row['sector_market_reason']]
for x in [e,m]:x['responsibility_group']=x.apply(role,axis=1)
def price_result(s):
 q=[x['result'] for x in json.loads(s) if x.get('lane')=='PRICE' and x.get('result')!='APPLICATION'];return q[-1] if q else 'ONLY_APPLICATION_SAVED'
m['original_PRICE_offer_result']=m.all_offer_results.map(price_result)
allcounts=[];long=[];groupcross=[]
groups=['BIRTH_ORIGINAL_ELIGIBILITY','EXISTING_PARENT_OUTSIDE_GATE','LATE_NO_CURRENT_ACTIVE_AUTH','LATE_ACTIVE_AUTH_NOT_POST_BIRTH_PURE_INCREMENT','LATE_ACTIVE_POST_BIRTH_AUTH','UNKNOWN']
for y in [2022,2024]:
 for sc in ['ALL','COMMON']:
  for den,df in [('MARKET_RECEIPTS',m),('ORIGINAL_PRICE_CLOSE_PASS',m[m.original_PRICE_offer_result.isin(['SELECTED_PENDING','PASS_NOT_TOP2'])]),('REGISTERED_ENTRIES',e),('ORIGINAL_PROXY_BUYS',e[e.actual_buy])]:
   g=df[df.year.eq(y)&(df.common if sc=='COMMON' else True)];v=g.responsibility_group.value_counts().to_dict();v={k:int(v.get(k,0)) for k in groups};assert sum(v.values())==len(g)
   n=len(g);late=sum(v[k] for k in groups if k.startswith('LATE'));pure=v['LATE_ACTIVE_AUTH_NOT_POST_BIRTH_PURE_INCREMENT'];bad=v['LATE_NO_CURRENT_ACTIVE_AUTH'];allcounts.append(dict(year=y,scope=sc,denominator=den,n=n,late_no_parent=late,**v,pure_increment_fraction_all=pure/n,pure_increment_fraction_late=pure/late if late else None,total_changed_count=bad+pure,total_changed_fraction_all=(bad+pure)/n))
   for col in ['ticket_fact','prewindow_root_fact','root_exit_relation_fact','window_participation_fact','native_sector_action','native_sector_new_receipt','M3_entry' if df is e else 'M3_candidate']:
    if col not in g:continue
    for key,z in g.groupby(['responsibility_group',col],dropna=False):groupcross.append(dict(year=y,scope=sc,denominator=den,grouping=col,responsibility_group=key[0],fact_value=key[1],n=len(z)))
  raw=m[m.year.eq(y)&(m.common if sc=='COMMON' else True)]
  for key,z in raw.groupby(['responsibility_group','original_PRICE_offer_result'],dropna=False):long.append(dict(year=y,scope=sc,responsibility_group=key[0],original_PRICE_offer_result=key[1],n_market_receipts=len(z)))
pd.DataFrame(allcounts).to_csv(O/'RESPONSIBILITY_FOUR_GROUP_COUNTS.csv',index=False,mode='x');dump('RESPONSIBILITY_FOUR_GROUP_COUNTS.json',allcounts);pd.DataFrame(groupcross).to_csv(O/'RESPONSIBILITY_FACT_CROSSES.csv',index=False,mode='x');pd.DataFrame(long).to_csv(O/'ORIGINAL_OFFER_FUNNEL_BY_RESPONSIBILITY.csv',index=False,mode='x')
# The original fixed daily source contains the two earlier stock receipts omitted by the window overlay.
fixed=pd.read_csv(src(R/'independent_channel_probe_preflight_v1/FIXED_DAILY.csv'))
corrections=[]
for d in ['2025-12-15','2025-12-17']:
 a=fixed[fixed.sid.eq('300666.SZ')&fixed.day.eq(d)];assert len(a)==1;idx=c.index[c.sid.eq('300666.SZ')&c.day.eq(d)][0];r=a.iloc[0]
 assert r.valid and r.receipt and r.new_frontier and not r.root_unknown
 for col in ['root_day','born','receipt','receipt_id','phase','confirmed_now','confirmed_at','C','Q','R','U','S_old','S_new','new_frontier','valid','root_unknown']:
  c.loc[idx,col]=r[col]
 c.loc[idx,'case_source_status']='EXACT_ORIGINAL_FIXED_DAILY_NO_ECONOMIC_WINDOW';c.loc[idx,'preflight_gate']='KEEP_ORIGINAL_ROOT_BIRTH' if r.born else 'UNKNOWN_EXECUTION_PARENT';c.loc[idx,'proxy_parent_before_signal']='UNKNOWN_NO_ECONOMIC_WINDOW';c.loc[idx,'stock_receipt_evidence_source']=str(R/'independent_channel_probe_preflight_v1/FIXED_DAILY.csv')
 corrections.append(dict(sid='300666.SZ',day=d,prior_summary_status='UNKNOWN_MISSING_SOURCE',corrected_source_status='EXACT_ORIGINAL_FIXED_DAILY_NO_ECONOMIC_WINDOW',born=bool(r.born),receipt=bool(r.receipt),receipt_id=r.receipt_id,root_day=r.root_day,execution_parent='UNKNOWN_NO_ECONOMIC_WINDOW'))
c['hypothetical_no_parent_signal_condition']=[('UNKNOWN_STOCK_SIGNAL' if str(a)=='UNKNOWN_MISSING_SOURCE' else 'KEEP_ORIGINAL_ROOT_BIRTH' if bool(b) else str(v)+'_LATE_SIGNAL_ONLY') for a,b,v in zip(c.case_source_status,c.born,c.sector_market_condition)]
# Preserve real execution uncertainty for all non-economic cases, even when signal condition is known.
c['real_order_ACK_fill_evidence']='UNKNOWN_NOT_PROVIDED';c['old_pnl_label']='ORIGINAL_FROZEN_PATH_ONLY_NOT_NEW_GATE_RETURN'
cols=['sid','name','day','case_source_status','sector','root_day','born','receipt','receipt_id','current20_high_break','contemporary_prior20_high','C','phase','confirmed_now','proxy_parent_before_signal','prior_proxy_round_id','prior_proxy_exit_day','root_exit_relation_fact','prewindow_root_fact','native_sector_E0_episode','native_sector_stage','native_sector_action','native_sector_receipt','native_sector_new_receipt','native_sector_receipt_ignored_same_observation','native_sector_authorization_usable','native_sector_authorization_id','native_sector_attempt_id','current_authorization_receipt_id','current_authorization_confirmed_day','current_authorization_formation_start','current_authorization_formation_end','current_authorization_accepted','current_authorization_same_native_episode','current_authorization_same_attempt','current_authorization_source_consistent','sector_market_condition','sector_market_reason','preflight_gate','hypothetical_no_parent_signal_condition','stock_receipt_evidence_source','selected_lane','all_offer_results','round_id','participation','status','entry_day','exit_day','actual_buy','full_closed','closed_total_pnl','PROBE_realized','ADD_realized','net80_income','common','real_order_ACK_fill_evidence','old_pnl_label']
c[[k for k in cols if k in c]].to_csv(O/'FIXED_CASE_PREFLIGHT_FINAL.csv',index=False,mode='x');dump('FIXED_CASE_SOURCE_CORRECTION.json',corrections)
# Original native-stage cancellation and next accepted event are observations, never a new fill path.
im=json.loads(src('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/INDUSTRY_MANIFEST.json').read_text());tr=pd.read_csv(src(O/'ORIGINAL_SECTOR_CP1_FULL_RECEIPTS.csv'),low_memory=False);trans=[]
for sid,sec in [('002583.SZ','URFI881129'),('688660.SH','URFI881280')]:
 rec=next(v for v in im if v['series']==sec);s=pd.read_parquet(src(rec['refs']['state']));cut='2024-09-25';bef=s[s.day.le(cut)&s.action.eq('end_attempt')].tail(1);aft=s[s.day.gt(cut)&s.new_receipt&s.authorization_usable&~s.receipt_ignored_same_observation].head(1)
 for label,g in [('PREVIOUS_ATTEMPT_END',bef),('NEXT_ACCEPTED_AUTHORIZATION',aft)]:
  for r in g.to_dict('records'):
   q=tr[tr.receipt_id.eq(r.get('authorization_id'))];r.update(sid=sid,sector=sec,observation=label,fixed_case_day=cut,potential_market_eligibility_only=True,no_queue_open_or_fill_inference=True,formation_start_exclusive=q.formation_start_exclusive.iloc[0] if len(q) else None);trans.append(r)
pd.DataFrame(trans).to_csv(O/'HYTERA_WIND_STAGE_TRANSITIONS.csv',index=False,mode='x')
# Readout contains no new gate-selected PnL sum.
lines=['# 旧根内首次未买续邀：只读事实预检','', '## 核心结论', '', '唯一新增职责不是行业 active 总门，而是 late 首次目标要求当前仍有效的行业授权确认日晚于本股原 root 出生日。2022 共同 BUY 的纯新增作用是 163/1779（9.16%）；2024 是 31/1083（2.86%）。它改变的是旧根内尚无 PROBE parent 的首次邀请，不能说修复了退出后复用同根新开仓。', '', '2022 共同原 BUY 中总影响210条，47条是当前行业授权本就不可用，163条才是postbirth比较纯新增；2024总影响144条，113条是前者、31条才是纯新增。不能把总数冒充新逻辑贡献。没有计算这些条目的删单收益或任何新账户结果。', '', '## 完整分母及职责', '', '|年/范围/分母|总数|原birth旁路|late无当前有效授权|late有效但不晚于root（纯新增）|late有效且晚于root|身份来源未知|', '|---|---:|---:|---:|---:|---:|---:|']
for a in allcounts:
 if a['denominator'] not in ['REGISTERED_ENTRIES','ORIGINAL_PROXY_BUYS']:continue
 lines.append('|'+ '/'.join(str(a[k]) for k in ['year','scope','denominator'])+'|'+ '|'.join(str(a[k]) for k in ['n','BIRTH_ORIGINAL_ELIGIBILITY','LATE_NO_CURRENT_ACTIVE_AUTH','LATE_ACTIVE_AUTH_NOT_POST_BIRTH_PURE_INCREMENT','LATE_ACTIVE_POST_BIRTH_AUTH','UNKNOWN'])+'|')
lines += ['', '市场票另列完整分母：2022全部24733张、共同16963张；2024全部12723张、共同11555张。其内尚无本root代理PROBE parent的late票为9937/6896及5230/4840，包含已经被原持仓、UNKNOWN责任、行业四真、AB优先、尺寸或PVR队列挡住的票，不能称可成交机会数。ORIGINAL_OFFER_FUNNEL_BY_RESPONSIBILITY.csv逐项保留原结果。', '', '## root、初仓与UNKNOWN边界', '', '- 3621个原登记signal CLOSE之前均无本root的代理PROBE parent；3593个发生原buy_core的回合才在次OPEN建立唯一parent。其余28个未买回合不是真实零填单。', '- PRICE q0为2022的3条、2024的9条，全部无自身parent/订单/BUY。后来同root新receipt可能首次建立parent，但不会倒推到此前q0时存在。真实零填、部分填、ACK和晚到成交的证据全为UNKNOWN_NOT_PROVIDED。', '- 本窗首全策略BUY的late票：2022全/共同461/307，2024为626/564；前次实际全卖后新root内的late首次BUY：237/184和22/19。两类不能混成退出前旧根复用。', '- 窗口前root：2022全/共同286/200；2024为162/138。2024原ENTRY_FACTS的prewindow_root列全空，本报告依据固定窗口起点2024-09-02和原root_day另建prewindow_root_fact，不改原表。', '- 机制身份/来源UNKNOWN为0只表示此批原票核验完备。旧账经济UNKNOWN仍为2022全353回合（已买340），2024全86（已买83）；共同样本均0。这些总盈亏未知从未填0。', '', '## native行业字段不是M3', '', 'ENTRY_FACTS的8个sector_E0/stage/action/receipt/authorization字段3621行全部与INDUSTRY_MANIFEST.refs.state逐字段一致。其路径是原native行业state → momentum_persistence_breadth_v1/SECTOR_DAILY → canonical_mu3的附带字段 → ENTRY_FACTS；M3/PVR3本身没有生成这些stage字段。ENTRY_FACTS缺行业authorization_id和receipt_id，本报告从原state回接，未拿股票PRICE receipt_id代替。', '', 'refs.receipts JSON只覆盖2025-07至2026-06，不能据它认定2022/24没有票。本次仅抽取原trace和Stage定义，使用90行业既存CP缓存重建25227张全史receipt，90行业state所有字段逐位exact，没有重算numeric CP。每张receipt核formation两端和全区间的source_kind/path/segment；原截止2026-06-30内真实切源0、trace_unknown0。不能外推未来跨source自动安全。', '', 'trace原E0 episode哈希与Stage episode哈希约定不同，已按原receipt/确认日的唯一state行建立对应关系；当前授权同时核当前attempt和Stage episode。当前失效授权不缓存；same-observation ignored票不算accepted。', '', '## 固定例（完整身份在FINAL CSV）', '', '- 浪潮1/5与同方1/4：当前计算机行业授权确认2021-12-30、formation从12-24，分别晚于原root10-26/12-17，late条件通过。没有因浪潮旧亏损改式。', '- 游族11/8：root11/2，当前有效行业授权11/7、formation11/1起；确认晚于root但形成起点早于root，按冻结式通过，不追加formation门。', '- 永和7/15、巨轮6/13、歌尔9/30、银轮12/25：原root生日旁路，原行业四真、AB优先和PVR队列仍适用；不禁止洗出后真新root首探。', '- 电气风电9/25和海能达9/25：均为late且当天无有效行业授权，不通过的是active部分，不是本轮postbirth纯新增。电气此前8/16因mobile_line撤权，后首accepted票9/27；海能达此前7/4因E0_invalid撤权，后首accepted票9/26。后日期只描述潜在市场资格，不代表同股新票、选中或OPEN成交。', '- 海能达9/20原born保留，但原行业false仍挡；9/23原AB优先事实不变；9/24和25均无当期行业授权。新机制不能把早先未成交的票补成成交。', '- 华电辽能10/28：root9/27，当前当天accepted授权10/28、formation10/22起，late条件通过。', '- 江丰12/15与17现有FIXED_DAILY明确receipt=true，root12/15、前者born/PROBE，后者continuing/首次CONFIRMED。12/15保持birth原资格；12/17当前行业授权仍12/12，假设无parent时late条件不通过。实际执行parent从未提供，因此不能推断真正初仓或续余量。1/5和15已有信号源且行业当前授权确认分别1/5和1/7，假设无parent时late条件通过；1/5票formation始12/12早于stockbirth亦不另加门。1/30、2/2、2/5股票市场源缺失仍UNKNOWN。', '', '## 运行与文件', '', 'CONTRACT.md在本轮新公式全量核值前保存；不是盲测，之前的案例和旧经济结果已知。未运行经济/consumer、参数搜索、filtered PnL、第二式或同日AND比较，原账/源码/授权/锁未改。原固定输入hash复核不变。', '', '- REGISTERED_ENTRY_BASE_FACTS.csv / MARKET_RECEIPT_BASE_FACTS.csv：未应用新式的完整原事实。', '- REGISTERED_ENTRY_PREFLIGHT.csv / MARKET_RECEIPT_PREFLIGHT.csv：同一唯一式逐条注释。', '- RESPONSIBILITY_FOUR_GROUP_COUNTS.csv及RESPONSIBILITY_FACT_CROSSES.csv：纯新增职责、rolling20High/首次重入/窗前根完整交叉，只有计数。', '- ORIGINAL_LABEL_DESCRIPTIVE_TABLES.csv：仅按原入场标签描述已冻旧路径金额。不同投影不可相加，不是新门收益。', '- ORIGINAL_SECTOR_CP1_FULL_RECEIPTS.csv：全史原票及形成/确认时钟、source、accepted身份。', '- FIXED_CASE_PREFLIGHT_FINAL.csv：最终固定案例；覆盖临时FIXED_CASE_PREFLIGHT.csv的江丰摘要缺源标记，源修复见FIXED_CASE_SOURCE_CORRECTION.json。', '- HYTERA_WIND_STAGE_TRANSITIONS.csv：两例原stage撤权及后续首accepted。', '- BASE/TRACE_PREFLIGHT/FINAL的QA与SOURCE_HASHES、OUTPUT_HASHES：完整复核。', '', '研究限制：固定1709股票与行业映射NON-PIT；两窗独立FLAT，不是连续共享账户；条件next-common OPEN全填代理不证明可成交；不由静态票身份推断动态替代机会或新收益。']
(O/'READOUT.md').write_text('\n'.join(lines)+'\n')
assert all(hashlib.sha256(Path(k).read_bytes()).hexdigest()==v for k,v in H.items())
dump('FINAL_SOURCE_HASHES.json',H);dump('FINAL_QA.json',dict(four_group_counts_conserved=True,formula_variants=1,no_economic_or_filtered_PnL=True,no_source_changes=True,case_source_corrections=corrections,preliminary_case_table_superseded='FIXED_CASE_PREFLIGHT_FINAL.csv',basefacts_preserved=True))
dump('OUTPUT_HASHES.json',{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(O.iterdir()) if p.is_file() and p.name!='OUTPUT_HASHES.json'})
print(pd.DataFrame(allcounts).to_string(index=False));print('FINAL_FILES_COMPLETE')
