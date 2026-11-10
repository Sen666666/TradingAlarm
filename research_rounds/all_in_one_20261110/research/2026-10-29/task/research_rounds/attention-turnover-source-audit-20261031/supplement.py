"""Write original membership identities/qualification components already used."""
import audit as A
import time,numpy as np,pandas as pd
def main():
 t=time.monotonic();g=A.read(A.O/'GROUPS.json');e=A.read(A.O/'EXIT_EVENTS.json');z=np.load(A.SRC/'AMOUNT_INPUT.npz');dates=pd.DatetimeIndex(z['dates']);sids=np.array([str(s) for s in z['symbols']]);amount=z['amount'];matrix=pd.read_parquet(A.SRC/'FEATURE_MATRIX_90.parquet').set_index(['day','sector']);root=A.W/'mainline-absolute-Q4-20261031/industry-facts';facts={p.stem:pd.read_parquet(p,columns=['e0_ready','e0_target']) for p in root.glob('*.parquet')};qchecks=0
 for r in A.read(A.W/'mainline-attention-top3-Q4-20261031/TARGETS.json'):
  for q in r['industry_inputs']:
   d=r['day'];sec=q['sector'];f=facts[sec].loc[d];derived=bool(f.e0_ready and f.e0_target and np.isfinite(matrix.loc[d,sec].H1_original));assert derived==q['qualified'];qchecks+=1
 for r in g:
  masks=[]
  for d in [r['previous_day'],r['day']]:
   j=dates.get_loc(pd.Timestamp(d));x=amount[j-25:j+1];masks.append(np.isfinite(x).all(axis=0)&(x>=0).all(axis=0))
  r.update(original_complete_n0=int(masks[0].sum()),original_complete_n1=int(masks[1].sum()),added_complete_members=sids[masks[1]&~masks[0]].tolist(),removed_complete_members=sids[masks[0]&~masks[1]].tolist())
 qloss=[]
 for r in e:
  if not r['own_qualification_lost']:continue
  sec=r['sector'];f0,f1=(facts[sec].loc[d] for d in [r['previous_day'],r['day']]);qloss.append(dict(group_id=r['group_id'],day=r['day'],sector=sec,industry=r['industry'],ready0=bool(f0.e0_ready),ready1=bool(f1.e0_ready),E0_target0=bool(f0.e0_target),E0_target1=bool(f1.e0_target),H1_RS_known0=bool(np.isfinite(matrix.loc[r['previous_day'],sec].H1_original)),H1_RS_known1=bool(np.isfinite(matrix.loc[r['day'],sec].H1_original))))
 A.save('GROUP_MEMBERSHIP_IDENTITIES',g);A.save('QUALIFICATION_LOSS_COMPONENTS',qloss);A.save('INPUT_RECEIPTS',dict(qualification_exact_Q4_cells=qchecks,seconds=time.monotonic()-t,hashes={str(p):A.sha(p) for p in list(root.glob('*.parquet'))+[A.O/'supplement.py',A.ROOT/'research_rounds/a-share-selection-e0-20261024/inputs-v2/metadata.json']}));print('SUPPLEMENT',qchecks,len(qloss),time.monotonic()-t)
if __name__=='__main__':main()
