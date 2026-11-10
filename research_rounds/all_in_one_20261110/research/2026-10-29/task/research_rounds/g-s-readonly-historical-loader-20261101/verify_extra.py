"""Affected clock/source guards only; reuse the passed 13 mapping tests."""
from loader import *
from verify import ROOT,packet_digest
import shutil,subprocess,time,os

def main(out=None):
 out=Path(out) if out else O/'validation-extra-002';out.mkdir(exist_ok=False);t=time.monotonic();results=[]
 for k in ('2022','2025_26'):
  src=ROOT/k;original=HistoricalInputs(src/'MANIFEST.json');base=packet_digest(src/'MANIFEST.json')
  dst=out/(k+'-first-session-physical');shutil.copytree(src,dst);m=read(dst/'MANIFEST.json');first=m['days'][0];m['days']=[first]
  for name,r in m['files'].items():
   p=dst/r['path']
   if p.suffix=='.parquet':
    f=pd.read_parquet(p);f=f[f.day<=first];f.to_parquet(p,index=False)
   elif name in ('receipts','actions'):
    rows=read(p);field='confirmed_day' if name=='receipts' else 'effective_date';write(p,[r for r in rows if r[field]<=first])
   r['sha256']=sha(p)
  write(dst/'MANIFEST.json',m)
  target=out/(k+'-first-session-worker.json')
  subprocess.run([sys.executable,'-B',str(O/'verify.py'),'worker',str(dst/'MANIFEST.json'),str(target)],check=True)
  z=read(target);assert z['events']==base['events'][:4] and z['priority']==base['priority'][:1] and z['bootstrap']==base['bootstrap']
  assert z['pid']!=os.getpid()
  results.append(dict(check='first-session physical cutoff and new-process output',window=k,passed=True,pid=z['pid']))
  # Current-day indicator close changes must not change opening inputs. Keep
  # current deterministic ex-date factor intact; raw daily proxy unchanged.
  dst=out/(k+'-same-day-indicator-poison');shutil.copytree(src,dst);m=read(dst/'MANIFEST.json');last=m['days'][-1]
  p=dst/'facts.parquet';f=pd.read_parquet(p);mask=f.day==last
  for col in ['close','raw_close','i_floor','e0_floor','g_grade']:f.loc[mask,col]=123456789
  for col in ['i_target','e0_target','i_buy']:f.loc[mask,col]=(~f.loc[mask,col].astype(bool)).astype(f[col].dtype)
  f.to_parquet(p,index=False);m['files']['facts']['sha256']=sha(p);write(dst/'MANIFEST.json',m)
  poison=HistoricalInputs(dst/'MANIFEST.json');assert digest(poison.event(last,'OPEN'))==digest(original.event(last,'OPEN'))
  assert digest(poison.event(last,'CLOSE'))!=digest(original.event(last,'CLOSE'))
  results.append(dict(check='same-day close signal poison excluded from OPEN',window=k,passed=True))
  # Input identity is a real guard, not disabled for diagnostics.
  bad=out/(k+'-wrong-binding');bad.mkdir();badm=read(src/'MANIFEST.json')
  for r in badm['files'].values():r['path']=str((src/r['path']).resolve())
  badm['files']['metadata']['sha256']='0'*64;write(bad/'MANIFEST.json',badm)
  try:HistoricalInputs(bad/'MANIFEST.json')
  except ValueError as e:assert 'input hash changed metadata' in str(e)
  else:raise AssertionError('wrong source binding accepted')
  results.append(dict(check='wrong input hash rejected',window=k,passed=True))
 # Independent original-file fixtures cover exact raw/facts/CP1/PVR values,
 # canonical identity, missing identity, source-specific factor event.
 inventory={r['symbol']:r for r in read(B/'g-s-minimal-input-readiness/STOCK_INPUT_INVENTORY.json')}
 samples=[]
 for k in ('2022','2025_26'):
  x=HistoricalInputs(ROOT/k/'MANIFEST.json')
  for sid in ('000001.SZ','300308.SZ','688608.SH'):
   refs=inventory[sid]['refs'];full={n:pd.read_parquet(refs[p]) for n,p in [('facts','facts'),('cp','CP1'),('pvr','PVR')]}
   for d in x.days:
    s=x.stock(sid,d,'CLOSE')
    for name,f in full.items():
     row=x.rows(name,sid,d,True);orig=clean(f.loc[pd.Timestamp(d)].to_dict()) if pd.Timestamp(d) in f.index else None
     assert (None if row is None else {a:b for a,b in row.items() if a!='observed_day'})==orig,(k,sid,d,name)
    samples.append(dict(window=k,sid=sid,day=d,original_facts_cp_pvr_exact=True))
 results.append(dict(check='independent original parquet fixture equality',passed=True,samples=samples))
 write(out/'VERIFICATION.json',dict(passed=True,checks=results,check_count=len(results),seconds=time.monotonic()-t,
   financial_events=0,intents_created=0,accounts_created=0,unchanged_13_tests_reused=True))
 print(canonical(read(out/'VERIFICATION.json')))
if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path);a=p.parse_args();main(a.out)
