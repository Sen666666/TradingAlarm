"""Two exact signal-day native scalar proofs, no routes or financial objects."""
from pathlib import Path
import gzip,hashlib,json,sys,time
import pandas as pd
O=Path(__file__).resolve().parent;ROOT=O.parent.parent
sys.path.insert(0,str(ROOT/'core_confirmed_v1/funding'))
import confirmed_adapter as C
EXPECTED='66ac96d10722ae49c0910c08a11e22cdd567159cf1e2b63c6b6142fbf5f025bd'
assert C.sha(C.__file__)==EXPECTED
start=time.monotonic();SHA={};DATES=('2026-02-11','2026-06-30')
def read(p):
 p=Path(p);SHA[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();return json.loads(p.read_text())
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
prepared=read(O/'PREPARATION.json');assert prepared['passed']and prepared['route_executed']is False
sm={r['symbol']:r for r in read('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')}
batches={d:read(O/('PREVIEWS_'+d+'.json'))for d in DATES}
lookups={d:read(O/('CORE_CP_LOOKUP_'+d+'.json'))for d in DATES}
wanted={'strong|'+x['clock']['session_date']+'|'+x['sid']+'|core'for xs in batches.values()for x in xs if x['role']=='core'}
path=ROOT/'core_confirmed_v1/coverage/ALL_CORE_OPEN_ORIGINAL_MOTHER.jsonl.gz';SHA[str(path)]=C.sha(path);contexts={}
with gzip.open(path,'rt')as f:
 for line in f:
  r=json.loads(line)
  if r['key']in wanted:contexts[r['key']]=r
assert len(contexts)==len(wanted)
cache={};checks=[]
for od,xs in batches.items():
 proofs={}
 for i in xs:
  if i['role']!='core':continue
  if time.monotonic()-start+prepared['seconds']>=20:raise TimeoutError('Two-batch total input/proof preparation20seconds')
  sid=i['sid'];day=i['clock']['session_date'];k='strong|'+day+'|'+sid+'|core';ctx=contexts[k]
  if sid not in cache:
   p=Path(sm[sid]['refs']['facts']);SHA[str(p)]=C.sha(p);assert SHA[str(p)]==sm[sid]['output_sha256'][str(p)]
   cache[sid]=pd.read_parquet(p,columns=['segment_id','i_target','i_buy','e0_target','g_ready','g_grade'])
  z=cache[sid].loc[day];industry=ctx['industry_financial_at_signal'];cp=lookups[od][sid]['trace']
  assert ctx['original_opportunity']['core_Q']is True and ctx['original_opportunity']['held']is False and not ctx['original_opportunity']['barriers']
  assert all(bool(z[c])for c in ['i_target','i_buy','e0_target','g_ready'])and z.g_grade>=2
  if cp:assert cp['receipt_id']==ctx['original_opportunity']['CP1_id']
  frozen=dict(policy=C.POLICY,account=ctx['original_opportunity']['account'],sid=sid,signal_day=day,epoch=i['epoch'],sector=ctx['original_opportunity']['sector'],
    industry_episode=industry['episode'],industry_attempt=industry['attempt'],industry_level=industry['financial_level'],source_segment=int(z.segment_id),
    i_target=bool(z.i_target),i_buy=bool(z.i_buy),e0_target=bool(z.e0_target),G1_ready=bool(z.g_ready),G1_grade=float(z.g_grade),ACT_on=True,canonical_receipt=cp)
  # ACT_on is not guessed: native raw CORE opportunity/intent exists only when
  # ACT_on; bind and check the original signal decision scalar via coverage.
  assert ctx['original_opportunity']['barriers']==[]
  frozen['receipt_sha256']=C.digest(cp)if cp is not None else None
  frozen['proof_sha256']=C.digest(frozen);proofs[sid]=frozen
 save('FROZEN_CORE_PROOFS_'+od+'.json',proofs)
 checks.append(dict(OPEN=od,CORE_proofs=len(proofs),same_day_CP=sum(p['canonical_receipt']is not None for p in proofs.values()),no_CP=sum(p['canonical_receipt']is None for p in proofs.values())))
SHA[str(Path(__file__))]=C.sha(__file__);SHA[str(Path(C.__file__))]=EXPECTED
save('PROOF_SOURCE_SHA256.json',SHA)
save('PROOF_PREPARATION.json',dict(passed=True,seconds=time.monotonic()-start,earlier_input_preparation_seconds=prepared['seconds'],total_preparation_seconds=prepared['seconds']+time.monotonic()-start,limit_seconds=20,unique_fact_files=len(cache),facts_columns=['segment_id','i_target','i_buy','e0_target','g_ready','g_grade'],batches=checks,industry_source='original signal-CLOSE industry financial event in saved full mother, not OPEN rebinding',ACT_source='native original CORE opportunity/intent after ACT gate, barriers empty',route_executed=False,new_Account=0,new_Runner=0,new_marks=0))
save('PROOF_FREEZE.json',{str(p.resolve()):C.sha(p)for p in sorted(O.iterdir())if p.is_file()and p.name not in ['PROOF_FREEZE.json']})
print(json.dumps(dict(seconds=time.monotonic()-start,unique_fact_files=len(cache),batches=checks,route_executed=False),ensure_ascii=False,indent=2))
