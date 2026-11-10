import pathlib,json,hashlib,math,pandas as pd,numpy as np
O=pathlib.Path(__file__).parent
B=pathlib.Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024');U=pathlib.Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
sha=lambda p:hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest();sources={}
def read(p):sources[str(p)]=sha(p);return json.loads(p.read_text())
mm=read(U/'STOCK_MANIFEST.json');meta=read(B/'inputs-v2/metadata.json');mapping=read(B/'audit/industry-repair-v2/mapping.json');selection=read(B/'inputs-v2/selection.json')
mapby={r['symbol']:r for r in mapping};assert len(mapby)==5576
specs=[
('通信第一轮','URFI881129','2022-10-10','2023-06-19','industry_own_episode'),
('游戏第一轮','URFI881275','2022-10-10','2023-06-20','industry_own_episode'),
('传媒第一轮','URFI881164','2022-10-10','2023-06-19','industry_own_episode'),
('软件第一轮','URFI881272','2022-10-10','2023-06-20','industry_own_episode'),
('通信2023上半年','URFI881129','2022-12-30','2023-06-30','fixed_half_year'),
('通信大类在CPO跨年时钟','URFI881129','2023-11-01','2024-07-10','representative_clock_not_CPO_members'),
('汽车整车在赛力斯时钟','URFI881125','2023-06-08','2023-11-06','representative_clock_not_Huawei_members'),
('消费电子在光弘时钟','URFI881124','2023-05-05','2023-11-08','representative_clock_not_Huawei_members'),
('传媒在短剧代表时钟','URFI881164','2023-10-23','2023-11-22','representative_clock_not_short_drama_members'),
('贵金属2024','URFI881169','2024-02-05','2024-04-12','industry_own_episode'),
('工业金属2024','URFI881168','2024-02-05','2024-05-20','industry_own_episode'),
('银行跨年','URFI881155','2023-12-26','2024-12-30','industry_own_episode'),
('汽车零部件在万丰时钟','URFI881126','2024-01-09','2024-05-20','representative_clock_not_low_altitude_members'),
('通用设备在宗申时钟','URFI881117','2024-07-08','2024-10-31','representative_clock_not_low_altitude_members'),
('924软件及后续','URFI881272','2024-08-22','2024-11-11','industry_own_episode'),
('924半导体及后续','URFI881121','2024-09-23','2024-11-11','industry_own_episode'),
('924证券及后续','URFI881157','2024-08-27','2024-11-07','industry_own_episode'),
('924软件共同起点','URFI881272','2024-09-23','2024-10-08','fixed_924_window'),
('924半导体共同起点','URFI881121','2024-09-23','2024-10-08','fixed_924_window'),
('924证券共同起点','URFI881157','2024-09-23','2024-10-08','fixed_924_window'),
('零售秋冬','URFI881158','2024-08-27','2024-12-16','industry_own_episode'),
('光伏924反弹','URFI881279','2024-08-23','2024-11-11','industry_own_episode'),
('电池924反弹','URFI881281','2024-08-23','2024-11-13','industry_own_episode')]
protocol=dict(purpose='Descriptive correction distinguishing group participation from selected winner anecdotes',source_pool='1709 surviving stocks selected by 2026-10 current market capitalization, not historical PIT; full current mapping denominator 5576',fixed_windows=specs,return_definition='same exact start and end adjusted CLOSE for every member; no member-specific trough or peak',eligibility='observed, eligible, noninvalid, nonsynthetic positive endpoint closes; no forward/back fill; internal gaps disclosed separately',top3_positive_share='sum top3 max(return,0) / sum max(return,0), equal initial notional; NOT actual cap-weighted index contribution',remove_top3='mean return after removing three largest returns, descriptive not strategy',thresholds='zero, +30%, +50% fixed descriptive bins only, no optimized classification',label_limits='Theme proxies are broad THS industries and do not prove Huawei/CPO/low-altitude/short-drama breadth; no new strategy or economic replay')
(O/'PROTOCOL.json').write_text(json.dumps(protocol,ensure_ascii=False,indent=2)+'\n')
sectors={s[1] for s in specs};frames={};selected={}
for m in mm:
 sid=m['symbol'];sec=meta[sid]['sector_id'];assert mapby[sid]['index']==sec
 if sec not in sectors:continue
 p,h=next((p,h) for p,h in m['source_sha256'].items() if p.endswith('/signal.parquet') and '/a-share-selection-e0-' in p);assert sha(p)==h;sources[p]=h
 d=pd.read_parquet(p);assert d.index.is_unique and set(d.symbol.dropna())=={sid}
 frames[sid]=d;selected.setdefault(sec,[]).append(sid)
rows=[];summaries=[]
for label,sec,start,end,clock in specs:
 known=[];all_current=[r for r in mapping if r['index']==sec]
 for sid in selected.get(sec,[]):
  d=frames[sid];valid=d.observed_bar.astype(bool)&d.price_eligible.astype(bool)&~d.source_invalid.astype(bool)&~d.synthetic_event_bar.astype(bool)&d.close.gt(0)&np.isfinite(d.close)
  good=d[valid];r=dict(episode=label,sector=sec,symbol=sid,name=meta[sid]['name'],start=start,end=end,clock_basis=clock,first_valid=str(good.index.min().date()) if len(good) else None,missing_or_invalid_observed_rows_inside=int((~valid.loc[start:end]).sum()))
  missing=[q for q in [start,end] if pd.Timestamp(q) not in good.index]
  if missing:r.update(status='UNKNOWN_ENDPOINT',missing_endpoints=','.join(missing),return_pct=None)
  else:
   v=float((good.loc[end,'close']/good.loc[start,'close']-1)*100);r.update(status='KNOWN',missing_endpoints='',return_pct=v);known.append(v)
  rows.append(r)
 x=np.array(known);pos=np.sort(np.maximum(x,0));k=math.ceil(len(x)*.1)
 q=dict(episode=label,sector=sec,start=start,end=end,clock_basis=clock,current_all_members=len(all_current),priced_selected_members=len(selected.get(sec,[])),known=len(x),unknown_endpoint=len(selected.get(sec,[]))-len(x),outside_priced_pool=len(all_current)-len(selected.get(sec,[])))
 if len(x):
  q.update(positive=int(sum(x>0)),above30=int(sum(x>=30)),above50=int(sum(x>=50)),median_pct=float(np.median(x)),p25_pct=float(np.quantile(x,.25)),p75_pct=float(np.quantile(x,.75)),equal_weight_mean_pct=float(np.mean(x)),top3_positive_share_pct=float(pos[-3:].sum()/pos.sum()*100) if pos.sum()>0 else None,top10pct_k=k,top10pct_positive_share_pct=float(pos[-k:].sum()/pos.sum()*100) if pos.sum()>0 else None,mean_without_top3_pct=float(np.sort(x)[:-3].mean()) if len(x)>3 else None,effective_positive_contributors=float(pos.sum()**2/(pos**2).sum()) if pos.sum()>0 else None)
 summaries.append(q)
pd.DataFrame(rows).to_csv(O/'MEMBER_RETURNS.csv',index=False);pd.DataFrame(summaries).to_csv(O/'SUMMARY.csv',index=False);(O/'SUMMARY.json').write_text(json.dumps(summaries,ensure_ascii=False,indent=2)+'\n');(O/'SOURCE_HASHES.json').write_text(json.dumps(sources,ensure_ascii=False,indent=2)+'\n')
assert all(sha(p)==h for p,h in sources.items())
print('SOURCES',len(sources),'STOCKS',len(frames),'MEMBER_EVENTS',len(rows));print(pd.DataFrame(summaries)[['episode','current_all_members','priced_selected_members','known','unknown_endpoint','positive','above30','above50','median_pct','equal_weight_mean_pct','top3_positive_share_pct','mean_without_top3_pct']].round(2).to_string(index=False))
