"""Exact actual PVR/rank source audit before plan deletions; no A/B/m model."""
from pathlib import Path
from collections import defaultdict,Counter
import argparse,gzip,json,math,hashlib
import pandas as pd
O=Path(__file__).resolve().parent;ROOT=O.parents[1];W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
PATHS={'2022':W/'pvr-slot1-native-readiness-20261101/SCORES_MANIFEST.json','2023':W/'pvr-slot1-native-readiness-20261101/continuation-2023-readiness/SCORES_MANIFEST.json','2024':ROOT/'ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full/SCORES_MANIFEST.json'}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):
 with gzip.open(p,'rt')as f:return json.load(f)
def rows(p):
 with gzip.open(p,'rt')as f:return[json.loads(s)for s in f]
def main():
 ap=argparse.ArgumentParser();ap.add_argument('run',type=Path);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=False);source={};req=defaultdict(lambda:defaultdict(set));logp=a.run/'pair/rank-policy.jsonl.gz';logs=rows(logp);source[str(logp.resolve())]=sha(logp)
 for r in logs:req[r['day'][:4]][r['sid']].add(r['day'])
 expected={}
 for year,sids in req.items():
  mp=PATHS['2022']if year>'2024'else PATHS[year];m=json.loads(mp.read_text());source[str(mp)]=sha(mp);entries={r['symbol']:r for r in m['entries']}
  for sid,days in sids.items():
   p=mp.parent/'scores'/f'{sid}.parquet';assert sha(p)==entries[sid]['output_sha256'];source[str(p)]=sha(p);f=pd.read_parquet(p,columns=['score']);values={str(t.date()):float(v)for t,v in f.score.items()}
   for day in days:v=values.get(day);expected[day,sid]=v if v is not None and math.isfinite(v)else None
 groups=defaultdict(list);bykey={};counts=Counter()
 for r in logs:
  k=r['account'],r['day'],r['sid'];assert k not in bykey;bykey[k]=r;v=expected[r['day'],r['sid']];assert r['PVR']==v and r['PVR_ready']==(v is not None),(k,r['PVR'],v);groups[k[:2]].append(r);counts['actual_before_modifier_rank_values_exact']+=1
 for key,rs in groups.items():
  old=sorted(rs,key=lambda r:r['original_slot']);assert [r['original_slot']for r in old]==list(range(len(old)))
  ready=[r for r in old if r['PVR_ready']];ready.sort(key=lambda r:(-round(r['PVR'],12),r['original_slot']));it=iter(ready);new=[r if not r['PVR_ready']else next(it)for r in old]
  for slot,r in enumerate(new):assert r['final_slot']==slot and r['priority_rank']==old[slot]['original_H1_rank'],(key,r)
  counts['complete_before_modifier_stock_maps_exact']+=1
 arms=[]
 for p in sorted((a.run/'pair').glob('*.json.gz')):
  b=load(p)
  if not isinstance(b,dict)or'decisions'not in b:continue
  arm=p.name.split('.')[0];arms.append(arm);source[str(p.resolve())]=sha(p)
  for d in b['decisions']:
   day=str(d['at'])[:10]
   for i in d['intents']:
    v=expected[day,i['sid']];r=bykey[arm,day,i['sid']];assert i['PVR_score']==v and i['PVR_ready']==(v is not None);assert i['rank']==i['priority_rank']==r['priority_rank'];assert i['original_H1_rank']==r['original_H1_rank'];counts['actual_surviving_intent_values_and_frozen_slots_exact']+=1
 binding=a.run/'SCORE_BINDING_REFERENCE.json';ref=json.loads(binding.read_text());p=Path(ref['path']);assert sha(p)==ref['sha256'];z=json.loads(p.read_text());assert all(sha(p)==v for p,v in z['source_sha256'].items());source[str(p)]=sha(p);source[str(binding.resolve())]=sha(binding)
 if max(req)<='2024':assert z['per_original_year_manifest_dispatch']==['2022','2023','2024']
 x={'status':'PASS_EXACT_ACTUAL_PVR_SOURCE_FULL_RANK_GROUP_AND_SURVIVING_FROZEN_SLOTS','actual_decision_years':sorted(req),'arms':arms,'counts':dict(counts),'no_score_tolerance_fallback_or_recalculation':True,'before_modifier_full_group_used_not_survivor_reranking':True,'source_sha256':source,'checker_sha256':sha(__file__),'A_B_m_price_feature_recomputation':False}
 (a.out/'AUDIT.json').write_text(json.dumps(x,indent=2)+'\n');print(json.dumps({k:v for k,v in x.items()if k!='source_sha256'}))
if __name__=='__main__':main()
