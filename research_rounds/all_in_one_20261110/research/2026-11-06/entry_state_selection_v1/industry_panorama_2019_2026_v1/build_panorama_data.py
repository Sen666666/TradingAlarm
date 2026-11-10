import pathlib,json,hashlib,math,pandas as pd,numpy as np
R=pathlib.Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1');O=pathlib.Path(__file__).parent
U=pathlib.Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031');B=pathlib.Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024')
START=pd.Timestamp('2019-01-01');END=pd.Timestamp('2026-10-22');T=.20;sources={};sha=lambda p:hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def readj(p):sources[str(p)]=sha(p);return json.loads(p.read_text())
def readc(p):sources[str(p)]=sha(p);return pd.read_csv(p)
protocol={'scope':'2019 through 2026-10-22; prior history used to preserve cross-year origins','main_layer':'Merge saved retrospective manual industry records; exact duplicate sector/start/end removed; overlapping long cycles and subwaves explicitly nested, never added','auxiliary_layer':'One fixed 20% close-reversal hysteresis from earliest available history; ascent confirmed only after 20% rise from running trough; peak confirmed only after 20% decline; no threshold search; these are mechanical subwave candidates, not manual campaign endpoints, alpha or fat-tail classifications','members':'Original current 1709 surviving approx>=10bn CNY company-cap pool, 2026-10 snapshot, repaired current industry mapping, NON-PIT; exact observed eligible adjusted-close endpoints shared by all stocks in a row; no forwardfill','units':'all percent fields in percentage points; MDD negative','concentration':'top3 sum max(r,0) / all sum max(r,0), equal initial notional, not index weight contribution','quality':'known endpoint != full path; report n/K/P/F separately; full current membership does not equal historic membership','no_accounts':True}
(O/'PROTOCOL.json').write_text(json.dumps(protocol,ensure_ascii=False,indent=2)+'\n')
sm=readj(U/'STOCK_MANIFEST.json');im=readj(U/'INDUSTRY_MANIFEST.json');mapping=readj(B/'audit/industry-repair-v2/mapping.json');meta=readj(B/'inputs-v2/metadata.json');lookup={x['symbol']:x for x in mapping}
full={};names={}
for x in mapping:
 if x['index']:
  full.setdefault(x['index'],[]).append(x['symbol']);names[x['index']]=x['name']
prices={};quality=[]
def signal(m):
 p,h=next((p,h) for p,h in m['source_sha256'].items() if p.endswith('/signal.parquet') and '/a-share-selection-e0-' in p);assert sha(p)==h;sources[p]=h
 d=pd.read_parquet(p,columns=['close','observed_bar','price_eligible','source_invalid','synthetic_event_bar','symbol']);assert d.index.is_unique and d.index.is_monotonic_increasing
 sid=m.get('series',m.get('symbol'));assert set(d.symbol.dropna())=={sid}
 good=d.observed_bar.astype(bool)&d.price_eligible.astype(bool)&~d.source_invalid.astype(bool)&~d.synthetic_event_bar.astype(bool)&d.close.gt(0)&np.isfinite(d.close)
 return d.close[good].loc[:END].astype(float)
for m in im:prices[m['series']]=signal(m)
cal=pd.DatetimeIndex(sorted(set().union(*(set(p.loc[START:END].index) for p in prices.values()))))
for sid,p in prices.items():
 q=p.loc[START:END];quality.append(dict(sector=sid,name=names[sid],first_valid=str(p.index.min().date()),last_valid=str(p.index.max().date()),period_valid=len(q),period_expected=len(cal),period_missing=len(cal.difference(q.index))))
# Normalize existing human-reviewed industry records. No selected-stock examples enter.
old=readc(R/'market_regime_2019_2022_v1/sector_campaigns_v2/USER_REVIEW_CAMPAIGNS.csv');manual=[]
for _,r in old.iterrows():manual.append(dict(sector=r.sector,start=r.start,end=r.end,priority={'重点':'重点肥尾候选','次级':'普通或次级波段','待讨论':'等级待讨论'}[r.priority],note=r.note,origin='2019_2022_manual',expected_ret_pct=r.ret*100,expected_mdd_pct=r.MDD*100,expected_K=int(r.K),expected_n=int(r.n),expected_member_median_pct=r.member_median*100))
ep=readc(R/'market_regime_2023_2024_review_v1/INDEPENDENT_EPISODES.csv');seen={(r['sector'],r['start'],r['end']) for r in manual};duplicates=[]
for _,r in ep[ep.sid.str.startswith('URFI')].iterrows():
 k=(r.sid,r.low_day,r.peak_day)
 if k in seen:duplicates.append(dict(sector=r.sid,start=r.low_day,end=r.peak_day,removed_origin='2023_2024_duplicate'));continue
 priority='重点肥尾候选' if r.sid in ['URFI881129','URFI881275','URFI881164','URFI881272','URFI881168','URFI881169','URFI881121','URFI881157'] else '普通或次级波段'
 if r.sid in ['URFI881158','URFI881279','URFI881281','URFI881273','URFI881142']:priority='等级待讨论'
 if r.sid=='URFI881169' and r.low_day<'2024':priority='普通或次级波段'
 manual.append(dict(sector=r.sid,start=r.low_day,end=r.peak_day,priority=priority,note=r.episode,origin='2023_2024_manual',expected_ret_pct=r.low_to_peak_pct,expected_mdd_pct=r.ascent_max_drawdown_pct));seen.add(k)
late=readc(R/'major_trends_2025_2026_review_v1/industry_specific_cycles/SIX_INDEPENDENT_CYCLES.csv');lateph=readc(R/'major_trends_2025_2026_review_v1/industry_specific_cycles/SIX_INDEPENDENT_PHASES.csv');latemem=readc(R/'major_trends_2025_2026_review_v1/industry_specific_cycles/member_participation/WINDOW_PARTICIPATION.csv')
for _,r in late[late.sid.str.startswith('URFI')].iterrows():
 q=latemem[(latemem.sector==r.sid)&(latemem.window=='二次底部至行业峰值')].iloc[0]
 manual.append(dict(sector=r.sid,start=r.secondary_base,end=r.main_peak,priority='重点肥尾候选',note='2024二次底部后跨2025至2026主段；2024局部峰与中途回撤不视为整轮终点',origin='2025_2026_manual',background_start=r.background_base,expected_ret_pct=r.secondary_to_peak_pct,expected_K=int(q.known_endpoint_n),expected_n=int(q.positive_n),expected_member_median_pct=q.median_pct))
def pathstats(sid,a,b):
 p=prices[sid];q=p.loc[a:b];assert pd.Timestamp(a) in p.index and pd.Timestamp(b) in p.index
 dd=q/q.cummax()-1;low=dd.idxmin();high=q.loc[:low].idxmax();tail=p.loc[pd.Timestamp(b):END];tlow=tail.idxmin()
 return dict(industry_return_pct=float((q.iloc[-1]/q.iloc[0]-1)*100),mdd_pct=float(dd.min()*100),mdd_peak=str(high.date()),mdd_trough=str(low.date()),sessions_after_start=len(q)-1,calendar_days=(pd.Timestamp(b)-pd.Timestamp(a)).days,peak_following_low=str(tlow.date()),peak_to_observed_low_pct=float((tail.min()/q.iloc[-1]-1)*100),at_cutoff_vs_peak_pct=float((tail.iloc[-1]/q.iloc[-1]-1)*100),observation_end=str(END.date()))
for i,r in enumerate(manual):
 r['record_id']=f'M{i+1:03d}';r['name']=names[r['sector']];r.update(pathstats(r['sector'],r['start'],r['end']));r['nested_in']=';'.join(t['origin']+':'+t['start']+'/'+t['end'] for t in manual if t is not r and t['sector']==r['sector'] and t['start']<=r['start'] and t['end']>=r['end'] and (t['start'],t['end'])!=(r['start'],r['end']))
 assert abs(r['industry_return_pct']-r['expected_ret_pct'])<1e-7
 if 'expected_mdd_pct' in r:assert abs(r['mdd_pct']-r['expected_mdd_pct'])<1e-7
# One unoptimized auxiliary wave extractor; data cutoff is not an economic exit.
def waves(p):
 out=[];state=None;lo=hi=p.index[0];peak=lo;start=None;up_confirm=None
 for d,v in p.items():
  if state is None:
   if v<p[lo]:lo=d
   if v>p[hi]:hi=d
   if v>=p[lo]*(1+T):state='up';start=lo;peak=d;up_confirm=d
   elif v<=p[hi]*(1-T):state='down';lo=d
  elif state=='down':
   if v<p[lo]:lo=d
   if v>=p[lo]*(1+T):state='up';start=lo;peak=d;up_confirm=d
  else:
   if v>p[peak]:peak=d
   if v<=p[peak]*(1-T):out.append(dict(start=str(start.date()),end=str(peak.date()),up_confirm=str(up_confirm.date()),down_confirm=str(d.date()),status='20pct_down_confirmed'));state='down';lo=d
 if state=='up':out.append(dict(start=str(start.date()),end=str(peak.date()),up_confirm=str(up_confirm.date()),down_confirm=None,status='open_no_20pct_down_confirmation'))
 return out
# Small exact synthetic checks of sequencing, not economic tests.
p=lambda v:pd.Series(v,index=pd.date_range('2000-01-01',periods=len(v)))
w=waves(p([100,80,100,120,95,70,84,90]));assert len(w)==2 and w[0]['start']=='2000-01-02' and w[0]['end']=='2000-01-04' and w[0]['down_confirm']=='2000-01-05' and w[1]['status'].startswith('open')
assert len(waves(p([100,90,95,99,85])))==0
aux=[]
for sid,p in prices.items():
 for w in waves(p):
  if pd.Timestamp(w['end'])<START and (w['down_confirm'] is None or pd.Timestamp(w['down_confirm'])<START):continue
  w.update(sector=sid,name=names[sid],record_id=f'A{len(aux)+1:04d}');w.update(pathstats(sid,w['start'],w['end']));aux.append(w)
print('INDUSTRY',len(prices),'MANUAL',len(manual),'UNIQUE_MANUAL_SECTORS',len({r['sector'] for r in manual}),'DUPLICATE_REMOVED',len(duplicates),'AUX',len(aux),flush=True)
# All original selected stocks, one source read each. No broker/account model.
stocks={};group={}
for i,m in enumerate(sm):
 sid=m['symbol'];sec=meta[sid]['sector_id'];assert lookup[sid]['index']==sec
 stocks[sid]=signal(m);group.setdefault(sec,[]).append(sid)
 if (i+1)%400==0:print('STOCK_READ',i+1,flush=True)
memberrows=[]
def memberstats(r):
 sec=r['sector'];a=pd.Timestamp(r['start']);b=pd.Timestamp(r['end']);vals=[];unknown=[];inside=prices[sec].loc[a:b].index;fully=0
 for sid in group.get(sec,[]):
  p=stocks[sid];ok=a in p.index and b in p.index;v=float((p[b]/p[a]-1)*100) if ok else None
  rec=dict(record_id=r['record_id'],sector=sec,symbol=sid,start=r['start'],end=r['end'],known=ok,return_pct=v)
  if ok:
   vals.append(v);f=len(inside.difference(p.index))==0;fully+=int(f);rec['full_path']=f
  else:unknown.append(sid);rec['full_path']=False
  memberrows.append(rec)
 x=np.array(vals);pos=np.sort(np.maximum(x,0));N=len(group.get(sec,[]));F=len(full.get(sec,[]));z=dict(current_all_members=F,research_pool_members=N,known_members=len(x),unknown_members=N-len(x),outside_pool=F-N,full_path_members=fully,unknown_symbols=','.join(unknown))
 if len(x):z.update(positive_members=int(sum(x>0)),above30_members=int(sum(x>=30)),above50_members=int(sum(x>=50)),member_p25_pct=float(np.quantile(x,.25)),member_median_pct=float(np.median(x)),member_p75_pct=float(np.quantile(x,.75)),member_mean_pct=float(x.mean()),top3_positive_share_pct=float(pos[-3:].sum()/pos.sum()*100) if pos.sum()>0 else None,mean_without_top3_pct=float(np.sort(x)[:-3].mean()) if len(x)>3 else None)
 return z
for r in manual+aux:r.update(memberstats(r))
recheck=[]
for r in manual:
 if 'expected_K' in r:
  recheck.append(dict(record_id=r['record_id'],K_equal=r['known_members']==r['expected_K'],n_equal=r['positive_members']==r['expected_n'],median_abs_error=abs(r['member_median_pct']-r['expected_member_median_pct'])))
# Differences are disclosed, not silently corrected.
pd.DataFrame(recheck).to_csv(O/'PREVIOUS_MEMBER_RECHECK.csv',index=False)
coverage=[]
for q in quality:
 sid=q['sector'];mr=[x for x in manual if x['sector']==sid];ar=[x for x in aux if x['sector']==sid];big=max(ar,key=lambda x:x['industry_return_pct']) if ar else None
 coverage.append(dict(**q,manual_records=len(mr),manual_origins=';'.join(sorted({x['origin'] for x in mr})),auxiliary_records=len(ar),research_pool_members=len(group.get(sid,[])),current_all_members=len(full.get(sid,[])),review_status='有重点区段人工复盘 不是全时段已人工覆盖' if mr else '仅机械候选及成员描述 人工定级待核',largest_aux_id=big['record_id'] if big else None))
for filename,records in [('MANUAL_RECORDS.csv',manual),('AUXILIARY_20PCT_WAVES.csv',aux),('MEMBER_RETURNS_ALL.csv',memberrows),('COVERAGE_90.csv',coverage),('EXACT_DUPLICATES_REMOVED.csv',duplicates)]:pd.DataFrame(records).to_csv(O/filename,index=False)
(O/'SOURCE_HASHES.json').write_text(json.dumps(sources,ensure_ascii=False,indent=2)+'\n')
assert all(sha(p)==h for p,h in sources.items())
qa=dict(industry_n=len(prices),industry_missing_cells=sum(q['period_missing'] for q in quality),common_sessions=len(cal),manual_records=len(manual),manual_industries=len({r['sector'] for r in manual}),exact_duplicates_removed=len(duplicates),auxiliary_records=len(aux),auxiliary_industries=len({r['sector'] for r in aux}),stock_sources=len(stocks),member_record_n=len(memberrows),member_recheck_n=len(recheck),previous_K_mismatches=sum(not x['K_equal'] for x in recheck),previous_n_mismatches=sum(not x['n_equal'] for x in recheck),previous_median_max_abs_error=max(x['median_abs_error'] for x in recheck),source_count=len(sources),source_unchanged=True,synthetic_wave_checks=True,no_account_runs=True)
(O/'QA.json').write_text(json.dumps(qa,ensure_ascii=False,indent=2)+'\n');print(json.dumps(qa,ensure_ascii=False),flush=True)
