import pathlib,json,hashlib,pandas as pd
O=pathlib.Path(__file__).parent;P=O.parent
m=pd.read_csv(O/'MANUAL_CYCLES.csv');old=pd.read_csv(P/'MANUAL_RECORDS.csv');old=old[old.sector.isin(m.sector)].copy();assert len(old)==40
rr=[]
for i,r in m.iterrows():
 overlap=old[(old.sector==r.sector)&(old.start<r.end)&(old.end>r.start)];fs=overlap[overlap.priority.str.contains('重点')];same=overlap[(overlap.start==r.start)&(overlap.end==r.end)]
 if not len(overlap):rel='完全遗漏新增'
 elif len(same)==1 and len(overlap)==1:rel='原边界保留'
 elif len(fs)>1:rel='合并多个旧重点'
 elif len(fs):rel='旧重点延伸或归并'
 elif r.priority_code=='F':rel='旧非重点延伸上调'
 else:rel='原非重点边界或归属调整'
 m.loc[i,'old_manual_ids']=';'.join(overlap.record_id);m.loc[i,'old_priority_ids']=';'.join(fs.record_id);m.loc[i,'relation_to_old']=rel
 m.loc[i,'new_priority_class']='完全遗漏新增重点' if not len(overlap) and r.priority_code=='F' else ('原非重点延伸上调' if not len(fs) and len(overlap) and r.priority_code=='F' else ('保留或合并原重点' if r.priority_code=='F' else '非重点'))
 m.loc[i,'note']=r.boundary_rationale;m.loc[i,'auxiliary_ids']=r.aux_ids.replace(' ',';');m.loc[i,'sessions_after_start']=r.sessions;m.loc[i,'outside_pool']=r.current_all_members-r.research_pool_members
for r in old.itertuples():
 o=m[(m.sector==r.sector)&(m.start<r.end)&(m.end>r.start)];assert len(o)
 rr.append(dict(old_id=r.record_id,sector=r.sector,name=r.name,old_start=r.start,old_end=r.end,old_priority=r.priority,canonical_ids=';'.join(o.record_id),canonical_grades=';'.join(o.priority),reconciliation='原包络拆开两次未持续创新高的普通反弹' if len(o)>1 else ('原记录边界和级别保留' if o.start.iloc[0]==r.start and o.end.iloc[0]==r.end and ('重点' in o.priority.iloc[0])==('重点' in r.priority) else '归入完整人工周期；原时段与指标保留供追溯，不另计独立周期'),reasons=' / '.join(o.boundary_rationale)))
m.to_csv(O/'MANUAL_CYCLES.csv',index=False);pd.DataFrame(rr).to_csv(O/'OLD_MANUAL_RECONCILIATION.csv',index=False)
l=pd.read_csv(O/'ALL_AUXILIARY_DISPOSITIONS.csv').rename(columns={'aux_id':'auxiliary_id','manual_record_id':'manual_cycle_id','rationale':'review_reason','role':'review_decision'});l.to_csv(O/'AUXILIARY_REVIEW_LEDGER.csv',index=False)
q=json.loads((O/'QA.json').read_text());q.update(old_manual_records=40,old_manual_each_accounted=True,priority_classes=m.new_priority_class.value_counts().to_dict(),canonical_nonoverlap=all(g.sort_values('start').end.shift().fillna('0000') .lt(g.sort_values('start').start).all() for _,g in m.groupby('sector')))
(O/'QA.json').write_text(json.dumps(q,ensure_ascii=False,indent=2)+'\n');s=json.loads((O/'SOURCE_HASHES.json').read_text());s[str(P/'MANUAL_RECORDS.csv')]=hashlib.sha256((P/'MANUAL_RECORDS.csv').read_bytes()).hexdigest();(O/'SOURCE_HASHES.json').write_text(json.dumps(s,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(q,ensure_ascii=False));print(m[m.priority_code=='F'][['record_id','name','start','end','industry_return_pct','member_median_pct','old_manual_ids','new_priority_class']].round(2).to_string(index=False))
