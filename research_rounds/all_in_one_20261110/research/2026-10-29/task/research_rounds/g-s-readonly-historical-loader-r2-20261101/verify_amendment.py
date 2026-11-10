"""Only the two affected mechanisms and full input-packet causal regressions.
No accounts, signals recalculated, order intents, or financial event progression.
"""
from loader import *
from prepare import filtered,structure_observations
import importlib.util, shutil, subprocess, time, os, argparse
OLD=W/'g-s-readonly-historical-loader-20261101';ROOT=O/'input-v1'

def packet_hashes(path,days=None):
 x=HistoricalInputs(path);days=days or x.days
 return dict(events=[digest(x.event(d,p)) for d in days for p in ('ACTION','PAYMENT','OPEN','CLOSE')],
  priority=[digest(x.priority(d)) for d in days],bootstrap=digest(x.bootstrap()),pid=os.getpid())
def rebind(dst,name,value=None,frame=None):
 m=read(dst/'MANIFEST.json');p=dst/m['files'][name]['path']
 if value is not None:write(p,value)
 if frame is not None:frame.to_parquet(p,index=False)
 m['files'][name]['sha256']=sha(p);write(dst/'MANIFEST.json',m)
def projection(ev):
 ev=copy.deepcopy(ev)
 for s in ev.get('stocks',[]):
  s.pop('structure',None)
  if s.get('canonical_receipt'):s['canonical_receipt'].pop('structure',None)
 for r in ev.get('market_observations',[]):r.pop('original_F1_scope',None)
 return ev

def main(out):
 out=Path(out);out.mkdir(exist_ok=False);started=time.monotonic();checks=[]
 spec=importlib.util.spec_from_file_location('original_readonly_loader_frozen',OLD/'loader.py');old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
 assert sha(OLD/'loader.py')=='ffd54547982e12cd1a6682531887a720246017d32b60ccf6c0b86a75cd5dee44'
 inv={r['symbol']:r for r in read(B/'g-s-minimal-input-readiness/STOCK_INPUT_INVENTORY.json')}
 for k in ('2022','2025_26'):
  src=ROOT/k;x=HistoricalInputs(src/'MANIFEST.json');previous=old.HistoricalInputs(OLD/'input-v2'/k/'MANIFEST.json');warm=x.m['warm_through'];first,last=x.days
  # The complete prior input package is immutable. Every output difference
  # must be exactly structure or F1 original scope, never other eligibility,
  # prices, receipt IDs, NA or priority semantics.
  structure_changes=[];scope_changes=[]
  for day in x.days:
   for phase in ('ACTION','PAYMENT','OPEN','CLOSE'):
    a=previous.event(day,phase);b=x.event(day,phase)
    assert canonical(projection(a))==canonical(projection(b)),(k,day,phase,'unapproved output difference')
    for aa,bb in zip(a.get('stocks',[]),b.get('stocks',[])):
     if aa['structure']!=bb['structure']:structure_changes.append(dict(sid=aa['sid'],day=day,phase=phase,old=aa['structure'],new=bb['structure'],facts_day=bb['facts']['observed_day'] if bb['facts'] else None))
    for aa,bb in zip(a.get('market_observations',[]),b.get('market_observations',[])):
     if aa['original_F1_scope']!=bb['original_F1_scope']:scope_changes.append(dict(node=aa['node_id'],day=day,old=aa['original_F1_scope'],new=bb['original_F1_scope']))
  assert previous.bootstrap()==x.bootstrap()
  assert previous.priority(first)==x.priority(first) and previous.priority(last)==x.priority(last)
  checks.append(dict(window=k,check='complete packets unchanged outside two audited fields',passed=True,structure_changes=structure_changes,scope_changes=scope_changes))
  # All retained real observation rows must have a matching structure lookup.
  for sid in x.ids:
   for r in x.meta[sid]['structure_observations']:
    ff=x.rows('facts',sid,r['observed_day'],True);assert ff is not None
    assert x.structure_at_observation(sid,ff)==r['identity']
  observations=[r for d in x.days for r in x.market_observations(d)]
  assert len(observations)==182
  assert all(r['original_F1_scope']==x.seeds[r['node_id']]['original_F1_scope']==x.seeds[r['node_id']]['f1_checkpoint']['state']['scope'] for r in observations)
  checks.append(dict(window=k,check='all actual observation structure rows and 182 F1 seed scope identities',passed=True))

  # Strong counterexample: rebuild metadata from REAL full saved E0 states,
  # not merely edit leaf signal values. Compare full OPEN packets, all stocks.
  poison=out/(k+'-future-derived-metadata');shutil.copytree(src,poison)
  meta=read(poison/'metadata.json');facts=pd.read_parquet(poison/'facts.parquet')
  witness=['002683.SZ','688608.SH']
  witnesses=[]
  for sid in witness:
   p=Path(inv[sid]['refs']['facts']);assert sha(p)==read(ROOT/'SOURCE_BINDINGS.json')[str(p)]
   full=filtered(p,last);future=full.index>=pd.Timestamp(first)
   mutated=full.copy();mutated.loc[future,'e0_target']=0
   source_before=full.loc[:warm];source_after=mutated.loc[:warm]
   pd.testing.assert_frame_equal(source_before,source_after,check_exact=True)
   rows=facts[facts.sid==sid].day.tolist()
   meta[sid]['structure_observations']=structure_observations(sid,mutated,rows)
   mask=(facts.sid==sid)&facts.day.ge(first);facts.loc[mask,'e0_target']=0
   knownrows=[d for d in rows if d<=warm]
   known=structure_observations(sid,source_before,knownrows)
   original_known=[r for r in x.meta[sid]['structure_observations'] if r['observed_day']<=warm]
   assert known==original_known
   witnesses.append(dict(sid=sid,known_observations=known,future_E0_changed_days=[str(t.date()) for t in full.index[future]],metadata_rebuilt_from_original_states=True))
  rebind(poison,'metadata',value=meta);rebind(poison,'facts',frame=facts)
  p=HistoricalInputs(poison/'MANIFEST.json')
  assert canonical(x.event(first,'OPEN'))==canonical(p.event(first,'OPEN'))
  firststock=x.stock('002683.SZ',first,'OPEN')
  if k=='2022':
   assert firststock['facts']['observed_day']=='2021-12-17';assert firststock['structure']=='002683.SZ|0|2021-10-22'
  checks.append(dict(window=k,check='future E0 plus recomputed derived metadata leaves whole OPEN identical',passed=True,witnesses=witnesses,problem_stock_open=firststock['structure']))

  # Truly physical first-session files, excluding second-session rows, with
  # metadata recomputed for the actual source witnesses and causal snapshots
  # retained for all identities. New process reads only these branch files.
  physical=out/(k+'-first-session-physical');shutil.copytree(src,physical)
  m=read(physical/'MANIFEST.json');m['days']=[first];write(physical/'MANIFEST.json',m)
  for name,r in m['files'].items():
   fp=physical/r['path']
   if fp.suffix=='.parquet':
    f=pd.read_parquet(fp);rebind(physical,name,frame=f[f.day<=first])
   elif name in ('receipts','actions'):
    field='confirmed_day' if name=='receipts' else 'effective_date';rebind(physical,name,value=[r for r in read(fp) if r[field]<=first])
  pm=read(physical/'metadata.json')
  for sid in x.ids:pm[sid]['structure_observations']=[r for r in pm[sid]['structure_observations'] if r['observed_day']<=first]
  for sid in witness:
   full=filtered(inv[sid]['refs']['facts'],first);obs=[r['observed_day'] for r in pm[sid]['structure_observations']]
   pm[sid]['structure_observations']=structure_observations(sid,full,obs)
  rebind(physical,'metadata',value=pm)
  target=out/(k+'-physical-worker.json');subprocess.run([sys.executable,'-B',str(Path(__file__)),'worker',str(physical/'MANIFEST.json'),str(target)],check=True)
  physical_result=read(target);base=packet_hashes(src/'MANIFEST.json',[first]);assert physical_result['pid']!=base['pid']
  assert {k:v for k,v in physical_result.items() if k!='pid'}=={k:v for k,v in base.items() if k!='pid'}
  checks.append(dict(window=k,check='complete first-session physical cutoff/rebuilt metadata/new process identical',passed=True,pid=physical_result['pid']))

  # A valid SHA on a semantically wrong scope must not bypass identity checks.
  bad=out/(k+'-invalid-scope');shutil.copytree(src,bad);f=pd.read_parquet(bad/'f1_observations.parquet')
  i=f.index[f.policy_scope=='URFI881121'][0];f.at[i,'original_F1_scope']='NATIVE1709_industry_URFI881121';rebind(bad,'f1_observations',frame=f)
  try:HistoricalInputs(bad/'MANIFEST.json')
  except ValueError as e:assert 'F1 observation scope identity mismatch' in str(e)
  else:raise AssertionError('wrong scope accepted with a new valid SHA')
  checks.append(dict(window=k,check='semantic scope mismatch rejected even with rebound valid hash',passed=True))
 # Source metadata builder must be prefix-invariant, including inactive rows,
 # source-segment restarts and missing-calendar-observation gaps.
 f=pd.DataFrame(dict(e0_target=[0,1,1,0,1,1],segment_id=[0,0,0,0,1,1]),index=pd.to_datetime(['2021-01-01','2021-01-05','2021-01-12','2021-02-01','2021-02-02','2021-02-03']))
 cut='2021-01-20';days=[str(t.date()) for t in f.loc[:cut].index]
 a=structure_observations('FIXTURE',f,days);b=structure_observations('FIXTURE',f.loc[:cut],days);assert a==b and a[0]['identity'] is None and a[-1]['identity']=='FIXTURE|0|2021-01-05'
 checks.append(dict(check='causal structural builder common-prefix inactive/restart/gap fixtures',passed=True))
 write(out/'VERIFICATION.json',dict(passed=True,checks=checks,check_count=len(checks),seconds=time.monotonic()-started,
   accounts_created=0,financial_events=0,intents_created=0,models_recomputed=0,unmodified_baseline_tests_reused=True))
 print(canonical(dict(passed=True,checks=len(checks),seconds=time.monotonic()-started,financial_events=0)),flush=True)
if __name__=='__main__':
 if len(sys.argv)>1 and sys.argv[1]=='worker':write(sys.argv[3],packet_hashes(sys.argv[2]))
 else:
  p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();main(a.out)
