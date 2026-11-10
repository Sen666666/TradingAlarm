import pathlib,json,hashlib,sys
import pandas as pd,numpy as np
sys.dont_write_bytecode=True
from manual_decisions import DECISIONS
O=pathlib.Path(__file__).parent;P=O.parent
U=pathlib.Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
B=pathlib.Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024')
NAMES=['半导体','消费电子','通信设备','电子化学品','元件','软件开发','文化传媒','游戏','汽车整车']; END=pd.Timestamp('2026-10-22'); sources={}
sha=lambda p:hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def readc(p):sources[str(p)]=sha(p);return pd.read_csv(p)
def readj(p):sources[str(p)]=sha(p);return json.loads(pathlib.Path(p).read_text())
allold=readc(P/'MANUAL_RECORDS.csv');old=allold[allold.name.isin(NAMES)].copy(); allaux=readc(P/'AUXILIARY_20PCT_WAVES.csv');aux=allaux[allaux.name.isin(NAMES)].copy(); coverage=readc(P/'COVERAGE_90.csv')
sm=readj(U/'STOCK_MANIFEST.json');im=readj(U/'INDUSTRY_MANIFEST.json');mapping=readj(B/'audit/industry-repair-v2/mapping.json');meta=readj(B/'inputs-v2/metadata.json')
sources[str(P/'build_panorama_data.py')]=sha(P/'build_panorama_data.py')
sids=set(aux.sector);prices={}; stocks={};group={};full={};symbols={x['symbol']:x for x in mapping}
for x in mapping:
 if x['index'] in sids:full.setdefault(x['index'],[]).append(x['symbol'])
def signal(m):
 p,h=next((p,h) for p,h in m['source_sha256'].items() if p.endswith('/signal.parquet') and '/a-share-selection-e0-' in p);assert sha(p)==h;sources[p]=h
 d=pd.read_parquet(p,columns=['close','observed_bar','price_eligible','source_invalid','synthetic_event_bar','symbol']);assert d.index.is_unique and d.index.is_monotonic_increasing
 assert set(d.symbol.dropna())=={m.get('series',m.get('symbol'))}
 g=d.observed_bar.astype(bool)&d.price_eligible.astype(bool)&~d.source_invalid.astype(bool)&~d.synthetic_event_bar.astype(bool)&d.close.gt(0)&np.isfinite(d.close)
 return d.close[g].loc[:END].astype(float)
for m in im:
 if m['series'] in sids:prices[m['series']]=signal(m)
for m in sm:
 sec=meta[m['symbol']]['sector_id']
 if sec not in sids:continue
 assert symbols[m['symbol']]['index']==sec
 stocks[m['symbol']]=signal(m);group.setdefault(sec,[]).append(m['symbol'])
print('Loaded',len(prices),'industry',len(stocks),'stock signals',flush=True)
def stats(sid,a,b):
 p=prices[sid];a=pd.Timestamp(a);b=pd.Timestamp(b);assert a in p.index and b in p.index;q=p.loc[a:b];dd=q/q.cummax()-1;lo=dd.idxmin();hi=q.loc[:lo].idxmax();tail=p.loc[b:]
 return dict(industry_return_pct=float((p[b]/p[a]-1)*100),mdd_pct=float(dd.min()*100),mdd_peak=str(hi.date()),mdd_trough=str(lo.date()),sessions_after_start=len(q)-1,sessions=len(q),calendar_days=(b-a).days,period_peak_is_highest=bool(p[b]>=q.max()-1e-8),period_start_is_lowest=bool(p[a]<=q.min()+1e-8),period_true_low=str(q.idxmin().date()),period_true_high=str(q.idxmax().date()),peak_following_low=str(tail.idxmin().date()),peak_to_observed_low_pct=float((tail.min()/p[b]-1)*100),at_cutoff_vs_peak_pct=float((tail.iloc[-1]/p[b]-1)*100),observation_end=str(END.date()))
def members(r,detail=True):
 a=pd.Timestamp(r['start']);b=pd.Timestamp(r['end']);sec=r['sector'];inside=prices[sec].loc[a:b].index;vals=[];unknown=[];rows=[];fp=0
 for sid in group[sec]:
  p=stocks[sid];known=a in p.index and b in p.index;v=float((p[b]/p[a]-1)*100) if known else None;f=bool(known and len(inside.difference(p.index))==0)
  if known:vals.append(v);fp+=int(f)
  else:unknown.append(sid)
  if detail:rows.append(dict(record_id=r['record_id'],sector=sec,name=r['name'],symbol=sid,start=r['start'],end=r['end'],known=known,return_pct=v,full_path=f))
 x=np.array(vals);positive=np.sort(np.maximum(x,0));K=len(x);PP=len(group[sec]);F=len(full[sec]);n=int(sum(x>0))
 z=dict(current_all_members=F,research_pool_members=PP,known_members=K,unknown_members=PP-K,outside_pool=F-PP,full_path_members=fp,unknown_symbols=','.join(unknown),positive_members=n,n=n,K=K,P=PP,F=F,full_path=fp,unknown=PP-K,above30_members=int(sum(x>=30)),above50_members=int(sum(x>=50)),member_p25_pct=float(np.quantile(x,.25)),member_median_pct=float(np.median(x)),member_p75_pct=float(np.quantile(x,.75)),member_mean_pct=float(x.mean()),top3_positive_share_pct=float(positive[-3:].sum()/positive.sum()*100) if positive.sum()>0 else None,mean_without_top3_pct=float(np.sort(x)[:-3].mean()) if K>3 else None)
 return z,rows
# Validate every original boundary against underlying series and stock endpoints.
checks=[]
for _,r in pd.concat([old,aux]).iterrows():
 z=stats(r.sector,r.start,r.end);m,_=members(r.to_dict(),False);checks.append(dict(record_id=r.record_id,industry_return_abs_error=abs(z['industry_return_pct']-r.industry_return_pct),mdd_abs_error=abs(z['mdd_pct']-r.mdd_pct),K_equal=m['K']==r.known_members,n_equal=m['n']==r.positive_members,P_equal=m['P']==r.research_pool_members,F_equal=m['F']==r.current_all_members,full_path_equal=m['full_path']==r.full_path_members,member_median_abs_error=abs(m['member_median_pct']-r.member_median_pct)))
assert all(c['industry_return_abs_error']<1e-8 and c['mdd_abs_error']<1e-8 and c['K_equal'] and c['n_equal'] and c['P_equal'] and c['F_equal'] and c['full_path_equal'] and c['member_median_abs_error']<1e-8 for c in checks)
canonical=[];ledger=[];memberrows=[];phases=[]; used=[]
priority={'K':'重点肥尾候选','O':'普通或次级波段','D':'等级待讨论'}
for i,decision in enumerate(DECISIONS,1):
 ids,grade,reason=decision[:3]; ids=ids.split();aa=aux.set_index('record_id').loc[ids].sort_values('start'); sec=aa.iloc[0].sector;name=aa.iloc[0]['name'];assert aa.sector.nunique()==1
 a=aa.iloc[0].start;b=aa.iloc[-1].end
 if len(decision)>3:a,b=decision[3:5]
 rid=f'TC{i:03d}';used+=ids
 overlap=old[(old.sector==sec)&(old.start<b)&(old.end>a)];oldfocus=overlap[overlap.priority=='重点肥尾候选'];eq=overlap[(overlap.start==a)&(overlap.end==b)];inold=old[(old.sector==sec)&(old.start<=a)&(old.end>=b)]
 if overlap.empty:relation='完全遗漏新增'
 elif grade=='K' and oldfocus.empty:relation='原普通或待讨论升级为重点'
 elif len(overlap)>1 and len(eq):relation='既有主线保留并去除嵌套重计'
 elif len(overlap)>1:relation='合并旧片段及延长'
 elif len(eq):relation='原记录原边界保留'
 else:relation='旧记录延长或边界修订'
 r=dict(record_id=rid,sector=sec,name=name,start=a,end=b,priority=priority[grade],priority_code=grade,note=reason,boundary_rationale=reason,origin='prior29_tech_manual_rereview',aux_ids=';'.join(ids),aux_count=len(ids),old_overlap_ids=';'.join(overlap.record_id),old_priority_overlap_ids=';'.join(oldfocus.record_id),exact_old_ids=';'.join(eq.record_id),old_containing_ids=';'.join(inold.record_id),relation_to_old=relation,fully_missing=bool(overlap.empty),new_priority_kind=relation if grade=='K' else '非重点',is_genuinely_new_priority=bool(grade=='K' and overlap.empty),nested_in='',selection_method='continuous daily and monthly path review; explicit manual endpoints and grading; no threshold/rank optimization',member_scope='2026 current surviving 1709-company approx>=10bn cap static research pool; NON-PIT',price_basis='source close already theoretical_ex_price adjusted; not official PIT or dividend-inclusive total return')
 r.update(stats(sec,a,b));r['last_aux_status']=aa.iloc[-1]['status'];r['last_aux_down_confirm']=aa.iloc[-1]['down_confirm'];r['observed_cycle_status']='截至观察日尚无20%峰后回撤确认' if str(aa.iloc[-1]['status']).startswith('open') else '截至观察日已有20%峰后回撤确认，非经济退出判据';m,mr=members(r);r.update(m);memberrows+=mr;canonical.append(r)
 for j,(_,ar) in enumerate(aa.iterrows()):
  ledger.append(dict(aux_id=ar.name,sector=sec,name=name,aux_start=ar.start,aux_end=ar.end,canonical_id=rid,canonical_start=a,canonical_end=b,disposition='单候选人工保留或修订' if len(ids)==1 else '合并为主周期的阶段/嵌套子段',manual_priority=r['priority'],old_overlap_ids=';'.join(old[(old.sector==sec)&(old.start<ar.end)&(old.end>ar.start)].record_id),canonical_relation_to_old=relation,reason=reason))
  z=stats(sec,ar.start,ar.end);phases.append(dict(canonical_id=rid,sector=sec,name=name,phase_type='上行阶段',source_aux_id=ar.name,start=ar.start,end=ar.end,**z))
  if j:
   pr=aa.iloc[j-1];z=stats(sec,pr.end,ar.start);phases.append(dict(canonical_id=rid,sector=sec,name=name,phase_type='中段停顿/回撤',source_aux_id=aa.index[j-1]+'->'+ar.name,start=pr.end,end=ar.start,**z))
assert len(used)==len(set(used))==len(aux)==87 and set(used)==set(aux.record_id)
recon=[]
for _,r in old.iterrows():
 cc=[c for c in canonical if c['sector']==r.sector and c['start']<r.end and c['end']>r.start];assert cc
 acts=[]
 for c in cc:
  if c['start']==r.start and c['end']==r.end:act='保留原边界'
  elif c['start']<=r.start and c['end']>=r.end:act='嵌套并入主周期' if r.record_id=='M091' else '延长起点/终点并并入主周期'
  else:act='修订真实低点/主峰；旧区间逐项披露'
  acts.append(act)
 extra=''
 if r.record_id=='M021':
  p=prices[r.sector];extra=f"旧终点2021-12-13较真正主峰2021-09-07低{(p['2021-12-13']/p['2021-09-07']-1)*100:.6f}%；旧3月起点晚于2月低点，旧条原收益仍保留在本对账表。"
 if r.record_id=='M063':extra='旧备注“非全周期新高”未说明比较基准；源日线2020-07-13高于2020-02-25，但这不等于全历史新高。本次明确基准，普通级不变。'
 if r.record_id=='M091':extra='完全嵌套于M098及TC008，2024子段不得再独立累计重点或收益。'
 recon.append(dict(old_id=r.record_id,sector=r.sector,name=r['name'],old_start=r.start,old_end=r.end,old_priority=r.priority,old_industry_return_pct=r.industry_return_pct,canonical_ids=';'.join(c['record_id'] for c in cc),actions=';'.join(acts),new_priorities=';'.join(c['priority'] for c in cc),extra_note=extra,reason=' | '.join(c['boundary_rationale'] for c in cc)))
assert len(recon)==34
C=pd.DataFrame(canonical);L=pd.DataFrame(ledger);RC=pd.DataFrame(recon)
# Canonical cycles never overlap in positive time inside one industry.
for sec,d in C.groupby('sector'):
 d=d.sort_values('start');assert all(x<=y for x,y in zip(d.end.iloc[:-1],d.start.iloc[1:]))
print(C[~C.period_start_is_lowest | ~C.period_peak_is_highest][["record_id","name","start","end","period_true_low","period_true_high"]].to_string(index=False),flush=True)
assert C.period_peak_is_highest.all();assert set(C[~C.period_start_is_lowest].record_id)=={"TC019"}
for name,d in [('GENUINELY_NEW_PRIORITIES.csv',C[C.is_genuinely_new_priority]),('MANUAL_CYCLES.csv',C),('AUXILIARY_REVIEW_LEDGER.csv',L),('OLD_MANUAL_RECONCILIATION.csv',RC),('MEMBER_RETURNS.csv',pd.DataFrame(memberrows)),('PHASES.csv',pd.DataFrame(phases).sort_values(['canonical_id','start','end'])),('ORIGINAL_RECOMPUTATION_CHECKS.csv',pd.DataFrame(checks))]:d.to_csv(O/name,index=False)
summary=C.groupby('name').agg(canonical_cycles=('record_id','size'),priority_cycles=('priority_code',lambda x:int((x=='K').sum())),fully_missing_priority_cycles=('is_genuinely_new_priority','sum'),assigned_auxiliary=('aux_count','sum')).reset_index();summary.to_csv(O/'INDUSTRY_SUMMARY.csv',index=False)
qa=dict(industry_n=9,auxiliary_n=87,old_manual_n=34,canonical_n=len(C),priority_counts=C.priority.value_counts().to_dict(),genuinely_new_priority_count=int(C.is_genuinely_new_priority.sum()),priority_relation_counts=C[C.priority_code=='K'].relation_to_old.value_counts().to_dict(),all_87_unique_assignments=True,all_34_old_records_reconciled=True,all_original_recomputations_match=True,original_recomputed_rows=len(checks),max_original_return_error=max(x['industry_return_abs_error'] for x in checks),max_original_member_median_error=max(x['member_median_abs_error'] for x in checks),canonical_no_positive_overlap=True,all_canonical_ends_observed_high=True,canonical_true_low_start_count=int(C.period_start_is_lowest.sum()),non_trough_start_exceptions="TC019: 2019-07 broad trial/restart campaign; 2020-02-04 later low 1.4205% lower, explicitly disclosed",stock_sources=len(stocks),member_rows=len(memberrows),source_count=len(sources),source_unchanged=all(sha(p)==h for p,h in sources.items()),no_threshold_sweep=True,no_account_or_strategy_run=True,scope_limitation='All 87 existing fixed-20pct auxiliary candidates reviewed and reconciled, not proof all sub-20pct oscillations since 2019 are exhausted; NON-PIT static surviving member pool; subjective manual grades not a measured fat-tail probability.')
assert qa['source_unchanged'];(O/'QA.json').write_text(json.dumps(qa,ensure_ascii=False,indent=2)+'\n');(O/'SOURCE_HASHES.json').write_text(json.dumps(sources,ensure_ascii=False,indent=2)+'\n')
text=['9行业人工独立周期复审','范围：半导体、消费电子、通信设备、电子化学品、元件、软件开发、文化传媒、游戏、汽车整车。','87条原辅助候选逐条唯一归属；34条旧人工记录逐条对账。连续日线及月度低高点观察覆盖2018至2026-10-22。',f'形成{len(C)}条互不重叠人工周期，其中{int((C.priority_code=="K").sum())}条重点候选；与全部旧人工区间无正时间重叠的真正新增重点为{int(C.is_genuinely_new_priority.sum())}条。','重点关系分开计数：'+json.dumps(qa['priority_relation_counts'],ensure_ascii=False),'这仅代表已给87候选全部人工复审，不代表未触发20%的微小波动已穷尽。所有定级均人工结合持续性、回撤、恢复前高、成员广度及集中度作判断；20%只提供原候选，不是肥尾认定规则。','收益单位均为百分点。n为上涨成员，K为两端可知成员，P为2026静态研究池行业成员，F为2026当前全行业成员，full_path为行业窗口每个交易日均有可用价格的成员。K可知不代表全路径完整。unknown=P-K。Top3是等初始本金正收益和份额，不是行业指数权重贡献。','成员来源是2026静态1709现时大市值存续池，NON-PIT；不能推广到历史全体成员。close已沿用theoretical_ex_price调整，不称官方PIT或含息总收益。','新旧边界均重新从原行业和成员日线实算。旧源文件未修改，没有重跑build_panorama_data.py，没有账户回测。','']
for name in NAMES:
 text.append('【'+name+'】')
 for _,r in C[C.name==name].sort_values('start').iterrows():
  text.append(f"{r.record_id} {r.start}—{r.end} | {r.priority} | 行业{r.industry_return_pct:.2f}% / 途中MDD {r.mdd_pct:.2f}%（{r.mdd_peak}至{r.mdd_trough}） | n/K/P/F={r.n}/{r.K}/{r.P}/{r.F} full_path={r.full_path} unknown={r.unknown} | 成员中位{r.member_median_pct:.2f}% / Top3正收益份额{r.top3_positive_share_pct:.2f}% | {r.relation_to_old} | 旧重叠：{r.old_overlap_ids or '无'} | 原辅助：{r.aux_ids}")
  text.append(r.boundary_rationale)
  pp=pd.DataFrame(phases);pp=pp[(pp.canonical_id==r.record_id)&(pp.phase_type=='中段停顿/回撤')]
  for _,ph in pp.iterrows():text.append(f"  中段停顿/回撤：{ph.start}至{ph.end}，端点变化{ph.industry_return_pct:.2f}%，自然日{ph.calendar_days}。")
 text.append('')
text+=['重要旧账修正：','半导体2021终点由7月延至11月；元件2024起点由9月前移至4月；软件2024主线延至2026-01。均不是独立遗漏。','汽车整车M021真实前低2020-02-04、真实主峰2021-09-07；原2021-12-13是较低后峰，对账表保留旧收益与修订理由。','软件M063原备注“非全周期新高”口径含混：2020-07已超过2月峰，但不等于更长期全历史新高；本次明确基准，未自动升级。','2024半导体M091为M098的完整嵌套子段，保留来源对账但不再独立累计。','所有主峰是截至2026-10-22的已观测主峰，不是实时可预知卖点；未完成行情仍有右删失。']
(O/'REVIEW_REPORT.txt').write_text('\n'.join(text)+'\n')
print(json.dumps(qa,ensure_ascii=False,indent=2));print('\nNEW PRIORITY\n',C[C.is_genuinely_new_priority][['record_id','name','start','end','industry_return_pct','mdd_pct','n','K','P','F','full_path','unknown','member_median_pct','top3_positive_share_pct']].to_string(index=False));print('\nSUMMARY\n',summary.to_string(index=False))
