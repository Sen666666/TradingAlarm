import pathlib,json,hashlib,pandas as pd,numpy as np
R=pathlib.Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1')
O=R/'sector_clock_924_financials_v1';O.mkdir(exist_ok=True)
kp=R/'momentum_persistence_breadth_v1/canonical_mu3_comparison_v2/COMMON_K_COMPARISON.parquet'
mp=R/'industry_panorama_2019_2026_v1/full90_final_integration_v1/FINAL_CANONICAL_CYCLES_90.csv'
hp=R/'account_comparison_continuous_v1/inputs/H1_MANIFEST.json'
master=pathlib.Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/current-pool-20261022/audit-snapshot/current-stock-master.industry-resolved.csv')
K=pd.read_parquet(kp);K.day=pd.to_datetime(K.day)
H={r['sid']:r for r in json.load(open(hp))};M=pd.read_csv(master);F=pd.read_csv(mp)
sources={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [kp,mp,hp,master]}
rows=[];daily=[];changes=[];runs=[];prices=[]
for sid in ['URFI881157','URFI881155','URFI881156','URFI881283']:
 p=next(p for p in H[sid]['source_identity'] if p.endswith('/signal.parquet'))
 sources[p]=hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest();assert sources[p]==H[sid]['source_identity'][p]
 q=pd.read_parquet(p);valid=q.observed_bar.fillna(False)&q.price_eligible.fillna(False)&~q.source_invalid.fillna(True)&~q.synthetic_event_bar.fillna(True)&np.isfinite(q.close)&q.close.gt(0)
 assert valid.loc['2024-09-02':'2024-12-31'].all()
 assert np.allclose(q.close.dropna(),q.raw_close.loc[q.close.notna()],rtol=0,atol=0)
 c=q.close.where(valid)
 s=K[K.sector==sid].set_index('day').sort_index().copy()
 assert s.index.is_unique and len(s)==1085
 s['previous_state']=s.M3_candidate.shift();s['previous_day']=s.index.to_series().shift()
 s['industry_close']=c.reindex(s.index)
 d=s.loc['2024-09-02':'2024-12-31'].copy()
 d['date']=d.index.strftime('%Y-%m-%d')
 daily.append(d[['date','sector','sector_name','previous_day','previous_state','M3_candidate','N','K','U','M3_n','M3_delta3','industry_close']])
 changes.append(d[d.M3_candidate.ne(d.previous_state)][['date','sector','sector_name','previous_day','previous_state','M3_candidate','N','K','U','M3_n','M3_delta3','industry_close']])
 grp=s.M3_candidate.ne(s.M3_candidate.shift()).cumsum()
 for key,g in s.groupby(grp):
  if g.index[-1]<pd.Timestamp('2024-09-02') or g.index[0]>pd.Timestamp('2024-12-31'):continue
  a=g.index[0];z=g.index[-1];i=s.index.get_loc(z);nextday=s.index[i+1] if i+1<len(s) else None
  runs.append({'sector':sid,'industry':g.sector_name.iloc[0],'state':int(g.M3_candidate.iloc[0]),'previous_state':g.previous_state.iloc[0],'start':str(a.date()),'last_same_state':str(z.date()),'sessions':len(g),'next_day':str(nextday.date()) if nextday is not None else '', 'start_n':int(g.M3_n.iloc[0]),'start_K':int(g.K.iloc[0]),'N':int(g.N.iloc[0]),'start_U':int(g.U.iloc[0]),'start_close':c.get(a,np.nan),'last_close':c.get(z,np.nan),'last_return_pct':100*(c.get(z,np.nan)/c.get(a,np.nan)-1),'state_end_not_sell_rule':True})
 t=pd.Timestamp('2024-09-24');loc=s.index.get_loc(t);assert s.iloc[loc].M3_candidate==1
 l=loc;z=loc
 while l>0 and s.iloc[l-1].M3_candidate==1:l-=1
 while z+1<len(s) and s.iloc[z+1].M3_candidate==1:z+=1
 a=s.index[l];end=s.index[z];out=s.index[z+1]
 peak=c.loc['2024-09-24':'2024-12-31'].idxmax()
 f=F[(F.sector==sid)&(F.start<='2024-09-24')&(F.end>='2024-10-08')]
 assert len(f)==1;f=f.iloc[0]
 prior=s.loc['2024-09-02':a].iloc[:-1]
 earlier=prior[(prior.M3_candidate==1)&prior.M3_candidate.ne(prior.previous_state)]
 r={'sector':sid,'industry':s.sector_name.iloc[0],'research_N':int(s.iloc[l].N),'current_all_member_n':int((M.industry_index_symbol==sid).sum()),'true_run_covering_924_start':str(a.date()),'previous_state':int(s.iloc[l].previous_state),'start_n':int(s.iloc[l].M3_n),'start_K':int(s.iloc[l].K),'start_U':int(s.iloc[l].U),'start_diffusion3':float(s.iloc[l].M3_delta3),'start_close':c.at[a],'on_924_n':int(s.loc[t,'M3_n']),'on_924_K':int(s.loc[t,'K']),'on_924_U':int(s.loc[t,'U']),'on_924_close':c.at[t],'true_last':str(end.date()),'true_session_count':z-l+1,'first_nontrue':str(out.date()),'first_nontrue_state':int(s.loc[out,'M3_candidate']),'first_nontrue_n':int(s.loc[out,'M3_n']),'first_nontrue_K':int(s.loc[out,'K']),'first_nontrue_close':c.at[out],'prior_september_true_starts':'|'.join(x.strftime('%Y-%m-%d') for x in earlier.index),'sep23_close':c.at[pd.Timestamp('2024-09-23')],'oct8_close':c.at[pd.Timestamp('2024-10-08')],'sep23_oct8_return_pct':100*(c.at[pd.Timestamp('2024-10-08')]/c.at[pd.Timestamp('2024-09-23')]-1),'autumn_peak_day':str(peak.date()),'autumn_peak_close':c.at[peak],'sep23_autumn_peak_return_pct':100*(c.at[peak]/c.at[pd.Timestamp('2024-09-23')]-1),'state_start_autumn_peak_return_pct':100*(c.at[peak]/c.at[a]-1),'fixed_cycle_id':f.record_id,'fixed_cycle_start':f.start,'fixed_cycle_peak':f.end,'fixed_cycle_return_pct':float(f.industry_return_pct),'fixed_cycle_known_members':int(f.known_members),'fixed_cycle_positive_members':int(f.positive_members),'fixed_cycle_member_median_pct':float(f.member_median_pct),'cycle_boundary_rationale':f.boundary_rationale}
 # Map source boundaries independently match the exact same frozen index series.
 assert abs(r['fixed_cycle_return_pct']-100*(c.at[pd.Timestamp(f.end)]/c.at[pd.Timestamp(f.start)]-1))<1e-8
 rows.append(r)
 prices.append(pd.DataFrame({'date':c.loc['2024-07-01':'2026-10-22'].index.strftime('%Y-%m-%d'),'sector':sid,'close':c.loc['2024-07-01':'2026-10-22'].values}))
S=pd.DataFrame(rows);D=pd.concat(daily,ignore_index=True);C=pd.concat(changes,ignore_index=True);B=pd.DataFrame(runs);P=pd.concat(prices,ignore_index=True)
assert (D.K+D.U==D.N).all();assert (D.M3_n<=D.K).all();assert len(D)==4*len(D[D.sector=='URFI881157'])
S.to_csv(O/'FOUR_FINANCIALS_SUMMARY.csv',index=False)
D.to_csv(O/'DAILY_M3_20240902_20241231.csv',index=False)
C.to_csv(O/'ALL_STATE_CHANGES_20240902_20241231.csv',index=False)
B.to_csv(O/'STATE_RUNS_OVERLAPPING_AUTUMN.csv',index=False)
P.to_csv(O/'FOUR_RAW_INDEX_CLOSES.csv',index=False)
json.dump(sources,open(O/'SOURCE_HASHES.json','w'),ensure_ascii=False,indent=2)
for p,h in sources.items():assert hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()==h
json.dump({'source_unchanged':True,'source_price_hash_matches_frozen_manifest':True,'all_four_index_close_equals_raw':True,'same_calendar_daily_rows':len(D),'all_N_equals_K_plus_U':True,'all_n_at_most_K':True,'four_cycle_price_returns_rechecked':True,'stock_or_economic_work':False,'live_signal_claim':False,'scope':'original stored common-known M3 daily classifier, current membership NON-PIT; future index prices descriptive only'},open(O/'QA.json','w'),ensure_ascii=False,indent=2)
print(S[['industry','true_run_covering_924_start','start_n','start_K','research_N','current_all_member_n','true_last','true_session_count','first_nontrue','sep23_oct8_return_pct','autumn_peak_day','sep23_autumn_peak_return_pct','state_start_autumn_peak_return_pct','fixed_cycle_start','fixed_cycle_peak','fixed_cycle_return_pct']].to_string(index=False))
lines=['924金融板块的行业状态与行情核对','',
'本表先看行业，不从几只暴涨股倒推板块。采用原共同known口径M3行业日状态，未更换公式；不是新B0/B1运行或交易盈亏。',
'“识别日”指覆盖2024/9/24的那一段TRUE实际开始日，不是历史首次、不预知后来涨幅。信号为当日收盘数据，仅可能用于此后的执行。状态转FALSE/UNKNOWN是行业状态改变，不等于持仓卖出指令。',
'n为M3为真且共同known的研究成员数，K为M3和PVR3共同known，N为固定研究池行业总数，U=N-K。原规则可以在至少三只、达到N的三分之一且扩散为正时识别，并非必须多数；另一分支是至少一半。当前成员映射NON-PIT。',
'9/23→10/8用于统一比较924首波；9/24→12/31最高仅为秋季描述窗口。各行业更大周期独立列出，绝不把12/31当实际行情结束。后续空间只作复盘，不回灌识别和买入许可。','']
for x in rows:
 lines += [x['industry'],f"覆盖924的TRUE段：{x['true_run_covering_924_start']}由{x['previous_state']}转1，n/K/N={x['start_n']}/{x['start_K']}/{x['research_N']}，U={x['start_U']}，三日同成员扩散{x['start_diffusion3']:.6f}，行业收盘{x['start_close']:.3f}。9/24为{x['on_924_n']}/{x['on_924_K']}/{x['research_N']}，已在持续中。",f"该段一直到{x['true_last']}，共{x['true_session_count']}个收盘为TRUE；{x['first_nontrue']}首次转为{x['first_nontrue_state']}，当日n/K={x['first_nontrue_n']}/{x['first_nontrue_K']}。此前9月另有TRUE段起点：{x['prior_september_true_starts'] or '没有'}。",f"9/23→10/8行业收盘变化{x['sep23_oct8_return_pct']:+.2f}%；秋季窗口最高{x['autumn_peak_day']}，较9/23{x['sep23_autumn_peak_return_pct']:+.2f}%，较上述真实状态识别日{x['state_start_autumn_peak_return_pct']:+.2f}%。这些不是次开可实现收益。",f"既有人工独立周期：{x['fixed_cycle_start']}→{x['fixed_cycle_peak']}，行业{x['fixed_cycle_return_pct']:+.2f}%；同日起止可比成员{x['fixed_cycle_positive_members']}/{x['fixed_cycle_known_members']}上涨，中位{x['fixed_cycle_member_median_pct']:+.2f}%。{x['cycle_boundary_rationale']}",f"覆盖：当前固定研究池{x['research_N']}，现有全行业名单{x['current_all_member_n']}。不是历史PIT成分全量。",'']
lines += ['四行业的逐日状态及全部变化已单列，含TRUE退出与恢复，不能只挑识别后上涨的单段。没有在本核查中选股票、重算S、运行账户或修改源。',
'行业日状态旧源至2026/6/30，价格至2026/10/22；本924核查不受后段状态缺口影响，但更大周期后段是否被继续识别不能凭旧末值补齐。']
(O/'READOUT.txt').write_text('\n'.join(lines),encoding='utf-8')
