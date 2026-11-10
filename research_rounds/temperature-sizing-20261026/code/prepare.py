from common import *
def main():
 rules=read(OLD/'inputs-v2/market-rules.json');dates=[x[:10] for x in rules['decision_cutoffs'] if '2015-01-01'<=x[:10]<='2026-10-22'];assert len(dates)==len(set(dates))==2866
 lines=read(OLD/'inputs-v2/selection.json')['lines'];ids=[x['security_id'] for x in lines];assert len(ids)==1711
 col={s:j for j,s in enumerate(ids)};ix={d:i for i,d in enumerate(dates)};shape=(len(dates),len(ids));q=np.zeros(shape,bool);up=np.full(shape,-1,np.int8);grade=np.full(shape,-99,np.int8);fresh=np.zeros(shape,bool);acute=np.zeros(shape,bool);price=np.full(shape,np.nan)
 n=0
 for r in rows(PREV/'accounts-v1/decisions.jsonl.gz'):
  if r['account']!='E0__S0_base':continue
  i=ix[r['at'][:10]]
  for sid in r['eligible']:q[i,col[sid]]=True
  n+=1
 assert n==len(dates)
 sources=[];dt=pd.DatetimeIndex(dates)
 for sid,j in col.items():
  p=IX/'signals'/f'{sid}.parquet';f=pd.read_parquet(p,columns=['e0_ready','e0_target','grade','strength_ready','fresh_up','acute_down','close'])
  pos=f.index.searchsorted(dt,side='right')-1;known=pos>=0;ii=np.flatnonzero(known);pp=pos[known];rr=f.e0_ready.to_numpy(bool)[pp];up[ii[rr],j]=f.e0_target.to_numpy(np.int8)[pp[rr]]
  current=np.zeros(len(dates),bool);current[ii]=f.index[pp]==dt[ii];valid=current.copy();valid[ii]&=f.strength_ready.to_numpy(bool)[pp]
  kk=np.flatnonzero(valid);ss=pos[valid];grade[kk,j]=f.grade.to_numpy(float)[ss].astype(np.int8);fresh[kk,j]=f.fresh_up.to_numpy(bool)[ss];acute[kk,j]=f.acute_down.to_numpy(bool)[ss]
  price[ii,j]=f.close.to_numpy(float)[pp];sources.append(dict(symbol=sid,sha256=sha(p),rows=len(f)))
 out=HERE/'prepared';out.mkdir(exist_ok=False);np.savez_compressed(out/'facts.npz',dates=np.array(dates),symbols=np.array(ids),eligible=q,up=up,grade=grade,fresh=fresh,acute=acute,signal_price=price)
 write(out/'manifest.json',dict(recorded_at=now(),shape=shape,pure_eligibility_days=n,source_decisions=dict(path=str((PREV/'accounts-v1/decisions.jsonl.gz').relative_to(ROOT)),sha256=sha(PREV/'accounts-v1/decisions.jsonl.gz')),signals=sources,output_sha256=sha(out/'facts.npz'),causality='reuse prior verified E0/G1 pure market qualification; no old actual buy/sell list used as new orders'))
 print(dict(prepared=True,shape=shape,qualified_stock_days=int(q.sum())),flush=True)
if __name__=='__main__':main()
