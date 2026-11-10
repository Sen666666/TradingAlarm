import pathlib,json,hashlib,pandas as pd,numpy as np
O=pathlib.Path(__file__).parent;P=O.parent
U=pathlib.Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031');B=pathlib.Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024')
a=pd.read_csv(P/'AUXILIARY_20PCT_WAVES.csv').set_index('record_id');d=pd.read_csv(O/'DAILY_PATHS_20.csv',parse_dates=['date']);prices={s:z.set_index('date').close for s,z in d.groupby('sector')}
merges=[['A0371','A0372','A0373'],['A0055','A0056','A0057'],['A0061','A0062'],['A0505','A0506'],['A0513','A0514'],['A0517','A0518'],['A0494','A0495'],['A0045','A0046'],['A0266','A0267'],['A0476','A0477','A0478'],['A0005','A0006']]
meta=json.loads((B/'inputs-v2/metadata.json').read_text());mapping=json.loads((B/'audit/industry-repair-v2/mapping.json').read_text());full={};group={}
for x in mapping:
 if x['index']:full.setdefault(x['index'],[]).append(x['symbol'])
stockm=json.loads((U/'STOCK_MANIFEST.json').read_text());ss={};src=json.loads((O/'SOURCE_HASHES.json').read_text());wanted={a.loc[x[0]].sector for x in merges}
for m in stockm:
 sid=m['symbol'];sec=meta[sid]['sector_id']
 if sec not in wanted:continue
 p,h=next((p,h) for p,h in m['source_sha256'].items() if p.endswith('/signal.parquet') and '/a-share-selection-e0-' in p);assert hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()==h;src[p]=h
 z=pd.read_parquet(p,columns=['close','observed_bar','price_eligible','source_invalid','synthetic_event_bar','symbol']);good=z.observed_bar.astype(bool)&z.price_eligible.astype(bool)&~z.source_invalid.astype(bool)&~z.synthetic_event_bar.astype(bool)&z.close.gt(0)&np.isfinite(z.close);ss[sid]=z.close[good].loc[:'2026-10-22'].astype(float);group.setdefault(sec,[]).append(sid)
rows=[];members=[]
for i,ids in enumerate(merges):
 r=a.loc[ids[0]];t=a.loc[ids[-1]];sec=r.sector;start=r.start;end=t.end;p=prices[sec];q=p.loc[start:end];dd=q/q.cummax()-1;dn=dd.idxmin();up=q.loc[:dn].idxmax();tail=p.loc[end:]; vals=[];unknown=[];fully=0
 mid='RM'+str(i+1).zfill(2)
 for sid in group[sec]:
  sp=ss[sid];known=pd.Timestamp(start) in sp.index and pd.Timestamp(end) in sp.index;v=float((sp[end]/sp[start]-1)*100) if known else None;fp=known and not len(q.index.difference(sp.index));fully+=int(fp);members.append(dict(record_id=mid,sector=sec,symbol=sid,start=start,end=end,known=known,full_path=fp,return_pct=v))
  if known:vals.append(v)
  else:unknown.append(sid)
 x=np.array(vals);pos=np.sort(np.maximum(x,0));F=len(full[sec]);N=len(group[sec])
 rows.append(dict(record_id=mid,sector=sec,name=r['name'],start=start,end=end,auxiliary_ids=';'.join(ids),industry_return_pct=float((q.iloc[-1]/q.iloc[0]-1)*100),mdd_pct=float(dd.min()*100),mdd_peak=str(up.date()),mdd_trough=str(dn.date()),sessions_after_start=len(q)-1,calendar_days=(pd.Timestamp(end)-pd.Timestamp(start)).days,peak_following_low=str(tail.idxmin().date()),peak_to_observed_low_pct=float((tail.min()/q.iloc[-1]-1)*100),at_cutoff_vs_peak_pct=float((tail.iloc[-1]/q.iloc[-1]-1)*100),observation_end='2026-10-22',current_all_members=F,research_pool_members=N,known_members=len(x),unknown_members=N-len(x),outside_pool=F-N,full_path_members=fully,unknown_symbols=','.join(unknown),positive_members=int(sum(x>0)),above30_members=int(sum(x>=30)),above50_members=int(sum(x>=50)),member_p25_pct=float(np.quantile(x,.25)),member_median_pct=float(np.median(x)),member_p75_pct=float(np.quantile(x,.75)),member_mean_pct=float(x.mean()),top3_positive_share_pct=float(pos[-3:].sum()/pos.sum()*100) if pos.sum()>0 else None,mean_without_top3_pct=float(np.sort(x)[:-3].mean()) if len(x)>3 else None))
pd.DataFrame(rows).to_csv(O/'MERGED_CYCLES_RECOMPUTED.csv',index=False);pd.DataFrame(members).to_csv(O/'MERGED_MEMBER_RETURNS.csv',index=False);(O/'SOURCE_HASHES.json').write_text(json.dumps(src,ensure_ascii=False,indent=2));print(pd.DataFrame(rows)[['record_id','name','start','end','auxiliary_ids','industry_return_pct','mdd_pct','positive_members','known_members','research_pool_members','current_all_members','full_path_members','member_median_pct','top3_positive_share_pct','mean_without_top3_pct']].round(2).to_string(index=False));print('read_stock_sources',len(ss))
