import pathlib,json,hashlib,pandas as pd,numpy as np
O=pathlib.Path(__file__).parent;P=O.parent
U=pathlib.Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031');B=pathlib.Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024')
S={};sha=lambda p:hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def loadj(p):S[str(p)]=sha(p);return json.loads(p.read_text())
def readprice(m):
 p,h=next((p,h) for p,h in m['source_sha256'].items() if p.endswith('/signal.parquet') and '/a-share-selection-e0-' in p);assert sha(p)==h;S[p]=h;d=pd.read_parquet(p,columns=['close','observed_bar','price_eligible','source_invalid','synthetic_event_bar','symbol']);sid=m.get('series',m.get('symbol'));assert set(d.symbol.dropna())=={sid};assert d.index.is_unique and d.index.is_monotonic_increasing
 ok=d.observed_bar.astype(bool)&d.price_eligible.astype(bool)&~d.source_invalid.astype(bool)&~d.synthetic_event_bar.astype(bool)&d.close.gt(0)&np.isfinite(d.close);return d.close[ok].loc[:'2026-10-22']
spec=loadj(O/'MANUAL_SPEC.json');A=pd.read_csv(P/'AUXILIARY_20PCT_WAVES.csv').set_index('record_id');S[str(P/'AUXILIARY_20PCT_WAVES.csv')]=sha(P/'AUXILIARY_20PCT_WAVES.csv');ids=[x for g in spec['groups'] for x in g[0].split()];assert len(ids)==90 and len(set(ids))==90;secs=set(A.loc[ids].sector);assert len(secs)==12
S[str(P/'COVERAGE_90.csv')]=sha(P/'COVERAGE_90.csv');C=pd.read_csv(P/'COVERAGE_90.csv').set_index('sector');assert C.loc[list(secs)].manual_records.gt(0).all();assert set(ids)==set(A[A.sector.isin(secs)].index)
inds={m['series']:readprice(m) for m in loadj(U/'INDUSTRY_MANIFEST.json') if m['series'] in secs};meta=loadj(B/'inputs-v2/metadata.json');stocks={};groups={}
for m in loadj(U/'STOCK_MANIFEST.json'):
 sec=meta[m['symbol']]['sector_id']
 if sec in secs:stocks[m['symbol']]=readprice(m);groups.setdefault(sec,[]).append(m['symbol'])
manual=[];members=[];auxrows=[];checks=[]
for i,(ss,pr,note) in enumerate(spec['groups'],1):
 xx=ss.split();aa=A.loc[xx];assert aa.sector.nunique()==1;sec=aa.sector.iloc[0];name=aa.name.iloc[0];start=aa.start.min();end=aa.end.max();p=inds[sec];q=p.loc[start:end];assert q.index[0]==pd.Timestamp(start) and q.index[-1]==pd.Timestamp(end)
 dd=q/q.cummax()-1;dt=dd.idxmin();dp=q.loc[:dt].idxmax();rid=f'H{i:03d}';vals=[];full=0
 for sid in groups[sec]:
  t=stocks[sid];known=pd.Timestamp(start) in t.index and pd.Timestamp(end) in t.index;v=float((t.loc[end]/t.loc[start]-1)*100) if known else None;ff=known and len(q.index.difference(t.index))==0;full+=int(ff)
  reason=None if known else ('start_missing' if pd.Timestamp(start) not in t.index else 'end_missing');members.append(dict(record_id=rid,sector=sec,symbol=sid,start=start,end=end,known=known,full_path=ff,return_pct=v,unknown_reason=reason))
  if known:vals.append(v)
 x=np.array(vals);pos=np.sort(np.maximum(x,0));r=dict(record_id=rid,sector=sec,name=name,start=start,end=end,priority=spec['priorities'][pr],priority_code=pr,boundary_rationale=note,aux_ids=ss,aux_count=len(xx),industry_return_pct=float((q.iloc[-1]/q.iloc[0]-1)*100),mdd_pct=float(dd.min()*100),mdd_peak=str(dp.date()),mdd_trough=str(dt.date()),sessions=len(q)-1,calendar_days=(q.index[-1]-q.index[0]).days,current_all_members=int(C.loc[sec].current_all_members),research_pool_members=len(groups[sec]),known_members=len(x),unknown_members=len(groups[sec])-len(x),full_path_members=full,positive_members=int(sum(x>0)),above30_members=int(sum(x>=30)),above50_members=int(sum(x>=50)),member_median_pct=float(np.median(x)),member_p25_pct=float(np.quantile(x,.25)),member_p75_pct=float(np.quantile(x,.75)),member_mean_pct=float(x.mean()),top3_positive_share_pct=float(pos[-3:].sum()/pos.sum()*100) if pos.sum()>0 else None,mean_without_top3_pct=float(np.sort(x)[:-3].mean()) if len(x)>3 else None,period_peak_is_highest=bool(q.iloc[-1]==q.max()))
 assert r['period_peak_is_highest']
 if len(xx)==1:
  a=aa.iloc[0];checks.append(dict(record_id=rid,aux_id=xx[0],return_error=abs(r['industry_return_pct']-a.industry_return_pct),mdd_error=abs(r['mdd_pct']-a.mdd_pct),median_error=abs(r['member_median_pct']-a.member_median_pct),K_match=r['known_members']==a.known_members,n_match=r['positive_members']==a.positive_members))
 for aid in xx:auxrows.append(dict(aux_id=aid,sector=sec,name=name,manual_record_id=rid,role='跨年主周期内部子段' if len(xx)>1 else '人工保留独立段',priority=r['priority'],rationale=note))
 manual.append(r)
for r in manual:
 starts=[t['start'] for t in manual if t['sector']==r['sector'] and t['start']>r['end']];cut=min(starts) if starts else '2026-10-22';p=inds[r['sector']];tail=p.loc[r['end']:cut];r.update(observation_end=cut,post_peak_low_date=str(tail.idxmin().date()),post_peak_low_pct=float((tail.min()/p.loc[r['end']]-1)*100),cutoff_vs_peak_pct=float((tail.iloc[-1]/p.loc[r['end']]-1)*100),end_status='截至下轮起点（含）观察' if starts else '截至2026-10-22，不声明行情永久终结')
M=pd.DataFrame(manual);M.to_csv(O/'MANUAL_CYCLES.csv',index=False);pd.DataFrame(members).to_csv(O/'MEMBER_RETURNS.csv',index=False);pd.DataFrame(auxrows).to_csv(O/'ALL_AUXILIARY_DISPOSITIONS.csv',index=False);pd.DataFrame(checks).to_csv(O/'REUSED_BOUNDARY_RECHECK.csv',index=False)
assert all(sha(p)==h for p,h in S.items());assert all(c['K_match'] and c['n_match'] and max(c['return_error'],c['mdd_error'],c['median_error'])<1e-9 for c in checks)
qa=dict(industries=len(secs),manual_records=len(M),priority_counts=M.priority.value_counts().to_dict(),auxiliary_candidates=len(ids),auxiliary_each_mapped_once=True,merged_records=int(M.aux_count.gt(1).sum()),stock_sources=len(stocks),member_rows=len(members),reused_boundary_rechecks=len(checks),sources=len(S),all_sources_unchanged=True,all_manual_peaks_within_span_highest=True,independent_review=False,no_backtest=True)
(O/'SOURCE_HASHES.json').write_text(json.dumps(S,ensure_ascii=False,indent=2)+'\n');(O/'QA.json').write_text(json.dumps(qa,ensure_ascii=False,indent=2)+'\n');print(json.dumps(qa,ensure_ascii=False));print(M[M.priority_code=='F'][['record_id','name','start','end','industry_return_pct','mdd_pct','positive_members','known_members','research_pool_members','current_all_members','member_median_pct','top3_positive_share_pct']].round(2).to_string(index=False))
