"""Actual decision-domain exact PVR source checks; no model/account imports."""
from pathlib import Path
from collections import defaultdict,Counter
import argparse,gzip,json,math,hashlib
import pandas as pd

ROOT=Path(__file__).resolve().parents[2]
W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
PATHS={'2022':W/'pvr-slot1-native-readiness-20261101/SCORES_MANIFEST.json',
 '2023':W/'pvr-slot1-native-readiness-20261101/continuation-2023-readiness/SCORES_MANIFEST.json',
 '2024':ROOT/'ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full/SCORES_MANIFEST.json'}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 ap=argparse.ArgumentParser();ap.add_argument('run',type=Path);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=False)
 source={};books={};requests=defaultdict(lambda:defaultdict(set));counts=Counter();strong=False
 for p in sorted((a.run/'pair').glob('*.json.gz')):
  with gzip.open(p,'rt')as f:b=json.load(f)
  if not isinstance(b,dict)or'decisions'not in b:continue
  source[str(p.resolve())]=sha(p);books[p.stem.split('.')[0]]=b
  for d in b['decisions']:
   day=str(d['at'])[:10];year=day[:4];strong|=year>'2024'
   for i in d['intents']:requests[year][i['sid']].add(day)
 expected={}
 for year,sids in requests.items():
  path=PATHS['2022']if year>'2024'else PATHS[year]
  m=json.loads(path.read_text());source[str(path)]=sha(path);entries={r['symbol']:r for r in m['entries']}
  for sid,days in sids.items():
   p=path.parent/'scores'/f'{sid}.parquet';assert sha(p)==entries[sid]['output_sha256'];source[str(p)]=sha(p)
   f=pd.read_parquet(p,columns=['score']);rows={str(t.date()):float(v)for t,v in f.score.items()}
   for day in days:
    v=rows.get(day);expected[day,sid]=v if v is not None and math.isfinite(v)else None
 for arm,b in books.items():
  for d in b['decisions']:
   day=str(d['at'])[:10];unique={}
   for i in d['intents']:
    sid=i['sid'];v=expected[day,sid]
    assert i['PVR_score']==v,(arm,day,sid,i['PVR_score'],v)
    assert i['PVR_ready']==(v is not None)
    assert i['rank']==i['priority_rank']
    if sid in unique:assert unique[sid]['original_H1_rank']==i['original_H1_rank']
    unique[sid]=i;counts['intent_values_exact']+=1;counts['known_values'if v is not None else'unavailable_values']+=1
   old=sorted(unique,key=lambda s:unique[s]['original_H1_rank']);oldpos={s:i for i,s in enumerate(old)}
   ready=[s for s in old if expected[day,s]is not None]
   # Twelve-place tie handling is the ORIGINAL frozen PVR_SLOT1 sort contract,
   # not a tolerance used to accept a changed score input.
   ready.sort(key=lambda s:(-round(expected[day,s],12),oldpos[s]))
   it=iter(ready);final=[s if expected[day,s]is None else next(it)for s in old]
   slots=[unique[s]['original_H1_rank']for s in old]
   for k,sid in enumerate(final):assert unique[sid]['priority_rank']==slots[k]
   counts['decision_stock_priority_maps_exact']+=bool(old);counts['unique_stock_values_exact']+=len(old)
 binding=a.run/'SCORE_BINDING_REFERENCE.json'
 if binding.exists():
  ref=json.loads(binding.read_text());p=Path(ref['path']);assert sha(p)==ref['sha256'];z=json.loads(p.read_text())
  assert all(sha(p)==v for p,v in z['source_sha256'].items())
  if not strong:assert z['per_original_year_manifest_dispatch']==['2022','2023','2024']
  source[str(binding.resolve())]=sha(binding);source[str(p)]=sha(p)
 result=dict(status='PASS_EXACT_ACTUAL_DECISION_SOURCE_AND_ORIGINAL_PRIORITY_CONTRACT',
   actual_decision_years=sorted(requests),counts=dict(counts),arms=sorted(books),
   no_score_tolerance_or_recalculation=True,unknowns_preserve_original_slots=True,
   source_sha256=source,checker_sha256=sha(__file__),financial_events=0,
   scope='actual native decision intents only; unused exported history is not a live signal source')
 (a.out/'AUDIT.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps({k:v for k,v in result.items()if k!='source_sha256'},indent=2))
if __name__=='__main__':main()
