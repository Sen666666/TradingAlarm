"""State population annotation only; original rank tables remain frozen."""
from analyze import O,OLD,read,save,sha,defaultdict
def main():
 rows=read(O/'RANKS_BEFORE_LABELS.json');by=defaultdict(list)
 for r in rows:by[r['case'],r['day']].append(r)
 logs={'2022Jan':read(O/'JAN_C10_SAVED_LOGS.json'),'2025Jul':read(OLD/'runs/2025_26-C10/2025-07-31-CLOSE.json')};result=[]
 for case,x in logs.items():
  for z in x['results']:
   if 'projection' not in z:continue
   day=z['at'][:10];q=z['projection']['C_rank_binding']['industry_order'];rs=by[case,day];lookup={r['sector']:r for r in rs}
   fullB=sorted(lookup,key=lambda s:(-lookup[s]['rank_improvement21'],s));queueB=sorted(q,key=lambda s:(-lookup[s]['rank_improvement21'],s))
   assert q==sorted(q,key=lambda s:lookup[s]['H1_rank90'])
   for s,r in lookup.items():result.append(dict(case=case,day=day,sector=s,industry=r['industry'],B_rank90=fullB.index(s)+1,original_C_queue_size=len(q),original_C_queue_A_rank=q.index(s)+1 if s in q else None,description_only_B_on_same_C_queue_rank=queueB.index(s)+1 if s in q else None,queue_population='original C comparison includes eligible incumbent mobile industries; separate from fresh opportunity industry subset'))
 save('GLOBAL_AND_ORIGINAL_QUEUE_RANK_ANNOTATIONS.json',result)
 print('ANNOTATED',len(result))
if __name__=='__main__':main()
