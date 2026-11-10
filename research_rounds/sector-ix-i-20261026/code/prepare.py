"""Restore the unchanged I policy from cached B5/G1 public market evidence."""
from sec_common import *
import gzip,time,collections
sys.path.append(str(G1/'code'));from policies_g1 import project

def original_inputs(f):
 e=f[['segment_id','close']].copy();e['valid_price_observation']=True;b=f[['e0_target','e0_floor','e0_entered','e0_entry_kind']].rename(columns=lambda c:c[3:]);g=f[['grade','fresh_up','acute_down']].copy();g['ready']=f.strength_ready
 return e,b,g

def restore(f):
 e,b,g=original_inputs(f);n=len(f);target=np.zeros(n,int);entered=np.zeros(n,int);exited=np.zeros(n,int);buy=np.zeros(n,bool);floors=np.full(n,np.nan);active=False;floor=math.nan;segment=None
 seg=e.segment_id.to_numpy();close=e.close.to_numpy(float);shadow=b.target.to_numpy(bool);bf=b.floor.to_numpy(float);be=b.entered.to_numpy(bool);ready=g.ready.to_numpy(bool);grade=g.grade.to_numpy(float);fresh=g.fresh_up.to_numpy(bool)
 for i in range(n):
  if seg[i]!=segment:active=False;floor=math.nan;segment=seg[i]
  if active:
   if not shadow[i] or close[i]<=floor:active=False;exited[i]=1
   elif np.isfinite(bf[i]):floor=max(floor,bf[i])
  opp=shadow[i] and ready[i] and grade[i]>=2 and (be[i] or fresh[i])
  if not active and not exited[i] and opp:active=True;entered[i]=1;floor=bf[i]
  target[i]=active;buy[i]=active and opp
  if active or exited[i]:floors[i]=floor
 return pd.DataFrame(dict(i_target=target,i_entered=entered,i_exited=exited,i_buy=buy,i_floor=floors),index=f.index)

def main():
 t=time.time();meta=read(OLD/'inputs-v2/metadata.json');lines=read(OLD/'inputs-v2/selection.json')['lines'];eligible={x['security_id'] for x in lines if x.get('company_cap_cny') is not None and float(x['company_cap_cny'])>1e10 and x['market']=='A'}
 xls=HERE/'sources/931152cons.xls';df=pd.read_excel(xls,dtype=str);assert len(df)==50 and set(df.iloc[:,1])=={'931152'};codes=set(df.iloc[:,4]);drug={s for s in eligible if meta[s]['code'] in codes};groups={k:sorted(drug if k=='DRUG' else {s for s in eligible if meta[s]['sector_id']==sid}) for k,(_,sid) in GROUPS.items()};ids=sorted(set().union(*map(set,groups.values())))
 assert all(groups.values()) and sum(map(len,groups.values()))==len(ids)
 membership=[]
 for _,r in df.iterrows():
  matches=[s for s,v in meta.items() if v['code']==r.iloc[4]];membership.append(dict(code=r.iloc[4],name=r.iloc[5],source_date=r.iloc[0],included=bool(set(matches)&drug),matched=matches,exclusion=None if set(matches)&drug else 'not_in_original_qualified_pool'))
 write(HERE/'scope.json',dict(recorded_at=now(),start=START,end=END,groups=groups,counts={k:len(v) for k,v in groups.items()},meta={s:meta[s] for s in ids},innovation_source=dict(url='https://oss-ch.csindex.com.cn/static/html/csindex/public/uploads/file/autofile/cons/931152cons.xls',sha256=sha(xls),source_date=sorted(set(df.iloc[:,0])),all_members=membership),snapshot_bias=True))
 rows=[dict(group=k,group_name=GROUPS[k][0],symbol=s,**meta[s]) for k,v in groups.items() for s in v];pd.DataFrame(rows).to_csv(HERE/'scope.csv',index=False)
 out=HERE/'signals';out.mkdir(exist_ok=False);checks=[];difference=0;manifest=[];deterministic=set(ids[::max(1,len(ids)//8)])|{'688256.SH','300308.SZ','300502.SZ'}
 for n,sid in enumerate(ids):
  p=IX/'signals'/f'{sid}.parquet';f=pd.read_parquet(p);i=restore(f);difference+=int((i.i_buy!=f.IX).sum())
  if sid in deterministic:
   e,b,g=original_inputs(f)
   for kind,ref in [('G1_I',i),('G1_IX',f)]:
    r=project(e,b,g,kind)
    for c in ['target','entered','exited','floor']:
     np.testing.assert_array_equal(r[c].to_numpy(float),ref[('i_' if kind=='G1_I' else 'ix_')+c].to_numpy(float),err_msg=sid+kind+c)
    np.testing.assert_array_equal(r.buy_event.to_numpy(bool),ref.i_buy.to_numpy(bool) if kind=='G1_I' else ref.IX.to_numpy(bool));checks.append(dict(symbol=sid,kind=kind,rows=len(f)))
  i.to_parquet(out/f'{sid}.parquet');manifest.append(dict(symbol=sid,rows=len(i),source=dict(path=str(p.relative_to(ROOT)),sha256=sha(p)),output_sha256=sha(out/f'{sid}.parquet')))
 write(out/'manifest.json',dict(recorded_at=now(),series=manifest,I_IX_buy_event_differences=difference,original_projection_checks=checks,seconds=time.time()-t));print(dict(groups={k:len(v) for k,v in groups.items()},buy_differences=difference,projection_checks=len(checks),seconds=time.time()-t),flush=True)
 # Original saved pure q is independent of occupied positions and uses the
 # identical S0/S1 qualification function; save only known true event dates.
 events=collections.defaultdict(list)
 with gzip.open(ABCD/'technical/A-controls/decisions.jsonl.gz','rt') as stream:
  for l in stream:
   row=json.loads(l)
   if row['account']!='A__S0_base' or not START<=row['at'][:10]<=END:continue
   for r in row['event_eligibility']:
    if r['symbol'] in ids and r['q'] is True:events[r['symbol']].append(row['at'][:10])
 write(HERE/'pure-q-events.json',dict(events=events,source=str((ABCD/'technical/A-controls/decisions.jsonl.gz').relative_to(ROOT)),source_sha256=sha(ABCD/'technical/A-controls/decisions.jsonl.gz'),S0_S1_qualification_identical=True));print(dict(qualified_events=sum(map(len,events.values())),seconds=time.time()-t),flush=True)
if __name__=='__main__':main()
