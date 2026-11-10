"""Descriptive post-seal readout of all finalized research-domain priority cycles."""
from pathlib import Path
import json,hashlib
import numpy as np,pandas as pd
R=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1')
O=Path(__file__).resolve().parent
F=R/'all_priority_sector_m3_detection_v1'
C=R/'major_trends_2025_2026_review_v1/industry_specific_cycles'
START=pd.Timestamp('2024-06-01');END=pd.Timestamp('2026-10-22')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def fmt(x):return str(pd.Timestamp(x).date()) if pd.notna(x) else None
def out(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
seal=json.loads((F/'SIGNAL_SEAL.json').read_text())
for n,h in seal['outputs'].items():assert sha(F/n)==h
cycles=pd.read_csv(F/'FIXED_PRIORITY_66.csv');assert len(cycles)==66
d=pd.read_parquet(F/'SECTOR_DAILY.parquet').sort_values(['sector','day'])
old=pd.read_parquet(R/'momentum_persistence_breadth_v1/canonical_mu3_comparison_v2/COMMON_K_COMPARISON.parquet')
old.day=pd.to_datetime(old.day)
imfile=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/INDUSTRY_MANIFEST.json')
im={x['series']:x for x in json.loads(imfile.read_text())}
src={str(p):sha(p) for p in [Path(__file__),O/'PROTOCOL.json',F/'FIXED_PRIORITY_66.csv',F/'SIGNAL_SEAL.json',F/'SECTOR_DAILY.parquet',imfile,C/'SIX_INDEPENDENT_PHASES.csv']}
px={}
for sec in cycles.sector:
 x=im[sec];p=Path(next(p for p in x['source_sha256'] if p.endswith('/signal.parquet')));assert sha(p)==x['source_sha256'][str(p)];src[str(p)]=sha(p)
 a=pd.read_parquet(p);assert a.index.is_unique and a.index.is_monotonic_increasing
 np.testing.assert_array_equal(a.close,a.raw_close)
 px[sec]=a.close.loc[:END]
trans=[];runs=[];rows=[]
pan={}
for c in cycles.itertuples():
 sec=c.sector;s=px[sec];x=d[d.sector.eq(sec)].set_index('day').copy()
 pre=old[(old.sector.eq(sec))&old.day.lt(START)].sort_values('day').tail(1)
 prev=x.M3_candidate.shift();prev.iloc[0]=int(pre.M3_candidate.iloc[0]) if len(pre) else np.nan
 x['previous_state']=prev
 x['close']=s.reindex(x.index);assert x.close.notna().all()
 for day,r in x[x.M3_candidate.ne(prev)].iterrows():
  trans.append(dict(sector=sec,name=c.name,day=fmt(day),previous_state=r.previous_state,state=int(r.M3_candidate),n=int(r.n),K=int(r.K),N=int(r.N),U=int(r.U),entered=int(r.entered3),left=int(r.left3),close=r.close,raw_A_sector_birth=r.M3_candidate==1 and r.previous_state==0))
 grp=x.M3_candidate.ne(prev).cumsum()
 for _,g in x.groupby(grp):
  a=g.iloc[0];b=g.iloc[-1];runs.append(dict(sector=sec,name=c.name,state=int(a.M3_candidate),start=fmt(g.index[0]),end=fmt(g.index[-1]),days=len(g),previous_state=a.previous_state,start_n=int(a.n),start_K=int(a.K),N=int(a.N),source_left_censored=g.index[0]==x.index[0],right_censored=g.index[-1]==x.index[-1],start_close=a.close,end_close=b.close))
 a=pd.Timestamp(c.start);b=pd.Timestamp(c.end);research_a=max(a,START)
 z=x.loc[research_a:b];t=z[z.M3_candidate.eq(1)]
 first=t.index[0] if len(t) else None;fr=t.iloc[0] if len(t) else None
 fresh=z[z.M3_candidate.eq(1)&z.previous_state.eq(0)];uf=z[z.M3_candidate.eq(1)&z.previous_state.eq(-1)]
 after=x[x.index>b];nf=after[after.M3_candidate.ne(1)];ff=after[after.M3_candidate.eq(0)]
 rr=dict(record_id=c.record_id,sector=sec,name=c.name,original_cycle_start=c.start,original_cycle_peak=c.end,carry_in=a<START,study_cycle_start=fmt(z.index[0]),study_cycle_days=len(z),N=int(x.N.iloc[0]),true_days=int(z.M3_candidate.eq(1).sum()),false_days=int(z.M3_candidate.eq(0).sum()),unknown_days=int(z.M3_candidate.eq(-1).sum()),true_share=float(z.M3_candidate.eq(1).mean()),false_to_true=int(len(fresh)),unknown_to_true=int(len(uf)),state_at_study_cycle_start=int(z.M3_candidate.iloc[0]),first_true=fmt(first),first_true_previous_state=fr.previous_state if fr is not None else None,first_true_n=int(fr.n) if fr is not None else None,first_true_K=int(fr.K) if fr is not None else None,first_true_U=int(fr.U) if fr is not None else None,signal_close=float(s[first]) if first is not None else None,earliest_next_common_open=fmt(s.index[s.index.get_loc(first)+1]) if first is not None and s.index.get_loc(first)+1<len(s) else None,delay_from_original_start_sessions=len(s.loc[a:first])-1 if first is not None and a>=START else None,already_up_from_original_start_pct=100*(s[first]/s[a]-1) if first is not None and a>=START else None,remaining_to_original_peak_pct=100*(s[b]/s[first]-1) if first is not None else None,study_first_observation_to_peak_pct=100*(s[b]/s[z.index[0]]-1),whole_original_cycle_pct=float(c.industry_return_pct),state_on_peak=int(x.loc[b,'M3_candidate']) if b in x.index else None,first_nontrue_after_peak=fmt(nf.index[0]) if len(nf) else None,peak_to_first_nontrue_pct=100*(s[nf.index[0]]/s[b]-1) if len(nf) else None,first_false_after_peak=fmt(ff.index[0]) if len(ff) else None,peak_to_first_false_pct=100*(s[ff.index[0]]/s[b]-1) if len(ff) else None,current_all_members=c.current_all_members,current_pool_members=c.research_pool_members,cycle_breadth_known_members=c.known_members,cycle_member_median_pct=c.member_median_pct)
 rows.append(rr);pan[sec]=x
res=pd.DataFrame(rows);res.to_csv(O/'ALL_66_CYCLE_DETECTION.csv',index=False)
pd.DataFrame(trans).to_csv(O/'ALL_RESEARCH_STATE_TRANSITIONS.csv',index=False);pd.DataFrame(runs).to_csv(O/'ALL_RESEARCH_STATE_RUNS.csv',index=False)
ph=pd.read_csv(C/'SIX_INDEPENDENT_PHASES.csv');phase=[]
for r in ph[ph.sid.isin(cycles.sector)&ph.start.ge('2024-06-01')].itertuples():
 x=pan[r.sid];s=px[r.sid];z=x.loc[r.start:r.end];seek=1 if r.return_pct>0 else 0;t=z[z.M3_candidate.eq(seek)];first=t.index[0] if len(t) else None
 phase.append(dict(sector=r.sid,name=r.name,phase=r.phase,description=r.description,start=r.start,end=r.end,phase_return_pct=r.return_pct,days=len(z),true_days=int(z.M3_candidate.eq(1).sum()),false_days=int(z.M3_candidate.eq(0).sum()),unknown_days=int(z.M3_candidate.eq(-1).sum()),target_state=seek,first_target=fmt(first),previous_state=t.iloc[0].previous_state if len(t) else None,n=int(t.iloc[0].n) if len(t) else None,K=int(t.iloc[0].K) if len(t) else None,N=int(z.N.iloc[0]),delay_sessions=len(s.loc[r.start:first])-1 if first is not None else None,price_change_before_first_target_pct=100*(s[first]/s[r.start]-1) if first is not None else None,remaining_to_phase_end_pct=100*(s[r.end]/s[first]-1) if first is not None else None,not_portfolio_exit=True))
pd.DataFrame(phase).to_csv(O/'FIVE_PRIORITY_PHASE_DETECTION.csv',index=False)
new=res[~res.carry_in]
stats=dict(priority_records=len(res),sectors=res.sector.nunique(),carry_in=int(res.carry_in.sum()),new_cycle_starts=len(new),first_true_found_new=int(new.first_true.notna().sum()),no_true_before_original_peak_new=new[new.first_true.isna()][['record_id','name']].to_dict('records'),new_delay_median=float(new.delay_from_original_start_sessions.median()),new_delay_max=float(new.delay_from_original_start_sessions.max()),new_already_up_median=float(new.already_up_from_original_start_pct.median()),new_remaining_space_median=float(new.remaining_to_original_peak_pct.median()),all_cycle_days=int(res.study_cycle_days.sum()),true_days=int(res.true_days.sum()),false_days=int(res.false_days.sum()),unknown_days=int(res.unknown_days.sum()),false_to_true=int(res.false_to_true.sum()),unknown_to_true=int(res.unknown_to_true.sum()),not_detection_precision=True,not_strategy_returns=True,postselection='Only preexisting hindsight priority cycles; no nonpriority control, no clean OOS')
out('SUMMARY.json',stats)
lines=['66个已封存重点行业：原M3板块识别时间线','研究域2024/6/1至2026/10/22。沿用最终90行业全景中的66条相交重点记录，未重新挑行情或更改算法。17条周期早于研究起点，保留原生日并标承接；其余49条可在研究域核起势后的识别。','这里先研究板块何时被识别。TRUE不等于已经买入，FALSE/UNKNOWN不等于账户卖出。原A票要求前一共同日FALSE→TRUE；UNKNOWN→TRUE当天不发A票，后续个股新生B仍另行判断。','行业信号只用当天已知日线。低点、峰值及中段划分来自已看过历史的原报告，只作后视误差标尺；剩余空间不是当时已知收益，也不是可保证成交收益。研究池及行业归属NON-PIT，K为M3与PVR3共同known，N是固定研究池人数，不是全历史行业成员。','']
lines += [f"覆盖：66行业×579共同日=38214行业日，1555成员；原行情存在866978/900345成员日，缺33367，未填充。33,198旧行业日及全部1555成员旧重叠状态精确复现，132物理截断断言通过；本次仅状态，没有新账户。",f"新起势49条中{stats['first_true_found_new']}条在各自原峰前出现TRUE；识别延迟中位{stats['new_delay_median']:.1f}个共同日，最慢{stats['new_delay_max']:.0f}日。这个分母是已知重点，不能推成全市场成功率，也不能从第一次TRUE推断之后一直参与。",f"所有原周期在研究域共有{stats['all_cycle_days']}行业日：TRUE {stats['true_days']}，FALSE {stats['false_days']}，UNKNOWN {stats['unknown_days']}；FALSE→TRUE {stats['false_to_true']}次，UNKNOWN→TRUE {stats['unknown_to_true']}次。反复与未知必须连同识别日期看。",'']
for r in res.itertuples():
 lines += [f"{r.name}（{r.record_id}）：原独立周期{r.original_cycle_start}→{r.original_cycle_peak}，行业全段{r.whole_original_cycle_pct:+.2f}%。"]
 if r.carry_in:lines.append(f"  研究起点承接旧周期，不计算整轮初识别延迟。研究域首个TRUE：{r.first_true}；此时至原峰的后视空间{r.remaining_to_original_peak_pct:+.2f}%。")
 else:lines.append(f"  起势后首个TRUE：{r.first_true}，相隔{r.delay_from_original_start_sessions:.0f}个共同日，行业此前已变动{r.already_up_from_original_start_pct:+.2f}%，此后到原峰尚有后视空间{r.remaining_to_original_peak_pct:+.2f}%。")
 lines.append(f"  首识别n/K/N={r.first_true_n}/{r.first_true_K}/{r.N}，U={r.first_true_U}，此前状态{r.first_true_previous_state}（0假、1真、-1未知）；最早仅可考察次共同开盘{r.earliest_next_common_open}，本表未生成订单。")
 lines.append(f"  周期研究范围{r.study_cycle_days}日：TRUE {r.true_days}、FALSE {r.false_days}、UNKNOWN {r.unknown_days}；0→1共{r.false_to_true}次，未知→1共{r.unknown_to_true}次。")
 lines.append(f"  原峰当日M3状态{r.state_on_peak}；峰后首次非TRUE {r.first_nontrue_after_peak}，相对峰价{r.peak_to_first_nontrue_pct:+.2f}%；首次FALSE {r.first_false_after_peak}，相对峰价{r.peak_to_first_false_pct:+.2f}%。这些不是账户卖点。")
 lines.append('')
(O/'66重点行业原M3识别复核.txt').write_text('\n'.join(lines)+'\n')
out('SOURCE_HASHES.json',src);out('OUTPUT_SEAL.json',dict(outputs={p.name:sha(p) for p in O.iterdir() if p.is_file() and p.suffix in ['.csv','.txt','.json'] and p.name!='OUTPUT_SEAL.json'},sources_unchanged=all(sha(p)==h for p,h in src.items()),account_runs=0))
print(json.dumps(stats,ensure_ascii=False,indent=2))
print('SLOWEST',new.sort_values('delay_from_original_start_sessions',ascending=False)[['name','original_cycle_start','first_true','delay_from_original_start_sessions','already_up_from_original_start_pct','remaining_to_original_peak_pct']].head(8).to_string(index=False))
