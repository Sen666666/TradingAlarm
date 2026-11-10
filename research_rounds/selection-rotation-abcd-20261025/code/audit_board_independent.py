"""Independent scalar endpoint, percentile and queue reconstruction."""
from common_abcd import *
import math

def main():
 z=dict(np.load(OLD/'h1/matrix.npz'));b=dict(np.load(HERE/'prepared/dual-board.npz'));meta=read(OLD/'inputs-v2/metadata.json');ids=[str(s) for s in z['symbols']];sec=[j for j,s in enumerate(ids) if s.startswith('URFI')];stocks=[j for j,s in enumerate(ids) if not s.startswith('URFI')];count=0
 for t in np.linspace(126,len(z['dates'])-1,23,dtype=int):
  r={}
  for h in [5,21,63,126]:
   r[h]=np.full(len(ids),np.nan)
   for j in range(len(ids)):
    a,c=z['close'][t,j],z['close'][t-h,j]
    if math.isfinite(a) and math.isfinite(c) and a>0 and c>0 and z['segment'][t,j]==z['segment'][t-h,j]:r[h][j]=a/c-1
   np.testing.assert_allclose(r[h],b[f'r{h}'][t],rtol=0,atol=1e-12,equal_nan=True)
  short=np.full(len(ids),np.nan)
  for group in [sec,stocks]:
   ps=[]
   for h in [21,63]:
    a=r[h][group];valid=a[np.isfinite(a)];pct=np.full(len(a),np.nan)
    if len(valid)>=20:
     for k,v in enumerate(a):
      if math.isfinite(v):pct[k]=100*(sum(x<v for x in valid)+.5*sum(x==v for x in valid))/len(valid)
    ps.append(pct)
   short[group]=(ps[0]+ps[1])/2
  np.testing.assert_allclose(short,b['short'][t],rtol=0,atol=1e-10,equal_nan=True)
  groups=[sec]+[[j for j in stocks if meta[ids[j]]['sector_id']==ids[k]] for k in sec]
  def channel(values,cond):return float(cond) if all(math.isfinite(v) for v in values) else math.nan
  fast=np.full(len(ids),np.nan);steady=fast.copy()
  for j in stocks:
   fast[j]=channel([r[5][j],short[j]],r[5][j]>0);steady[j]=channel([r[63][j],r[126][j],z['score'][t,j]],r[63][j]>0 and r[126][j]>0)
  for k,group in zip(sec,groups[1:]):
   bs={}
   for h in [21,63]:
    vals=[r[h][j] for j in group if math.isfinite(r[h][j])];bs[h]=sum(v>0 for v in vals)/len(vals) if vals else math.nan
    assert b[f'n{h}'][t,k]==len(vals);np.testing.assert_allclose(bs[h],b[f'breadth{h}'][t,k],equal_nan=True)
   fast[k]=channel([r[5][k],r[21][k],bs[21],short[k]],r[5][k]>0 and r[21][k]>0 and bs[21]>.5)
   steady[k]=channel([r[63][k],r[126][k],bs[63],z['score'][t,k]],r[63][k]>0 and r[126][k]>0 and bs[63]>.5)
  np.testing.assert_equal(fast,b['fast'][t]);np.testing.assert_equal(steady,b['steady'][t]);rank=np.full(len(ids),np.nan)
  for group in groups:
   q1=sorted([j for j in group if fast[j]==1],key=lambda j:(-round(short[j],12),ids[j]));q2=sorted([j for j in group if steady[j]==1],key=lambda j:(-round(z['score'][t,j],12),ids[j]))
   queues=[q2,q1] if group==sec else [q1,q2];pos=[0,0];result=[];seen=set();turn=0
   while pos[0]<len(queues[0]) or pos[1]<len(queues[1]):
    queue=queues[turn]
    while pos[turn]<len(queue) and queue[pos[turn]] in seen:pos[turn]+=1
    if pos[turn]<len(queue):v=queue[pos[turn]];pos[turn]+=1;result.append(v);seen.add(v)
    turn=1-turn
   for n,j in enumerate(result):rank[j]=100*(1-n/len(result))
  np.testing.assert_allclose(rank,b['rank'][t],rtol=0,atol=1e-10,equal_nan=True);count+=len(ids)
 write(HERE/'technical/independent-board.json',dict(recorded_at=now(),passed=True,independently_rebuilt_dates=23,symbol_date_rows=count,fields=['returns','same_day_percentiles','fast_steady_channels','breadth_denominators','interleaved_queues'],uses_future=False))
 print(dict(independent_board_passed=True,rows=count),flush=True)
if __name__=='__main__':main()
