from common_abcd import *
import pandas as pd
from board_abcd import build

def main():
 out=HERE/'review';out.mkdir(exist_ok=False);z=np.load(HERE/'prepared/dual-board.npz');data={k:z[k] for k in z.files};dates=pd.DatetimeIndex(data['dates']);ids=[str(s) for s in data['symbols']];idx={s:j for j,s in enumerate(ids)};meta=read(OLD/'inputs-v2/metadata.json');rows=[]
 for day in ['2015-12-31','2018-12-28','2021-12-31','2023-03-13','2023-12-29','2025-08-13','2026-10-22']:
  i=dates.get_loc(day);sectors=sorted([s for s in ids if s.startswith('URFI') and np.isfinite(data['rank'][i,idx[s]])],key=lambda s:-data['rank'][i,idx[s]])[:10]
  for sid in sectors+['688256.SH','300308.SZ','300502.SZ']:
   if sid not in idx:continue
   j=idx[sid];rows.append(dict(date=day,symbol=sid,name=meta[sid]['name'] if sid in meta else sid,**{k:float(data[k][i,j]) for k in ['short','long','rank','gate','fast','steady','r5','r21','r63','r126','breadth21','breadth63']}))
 write(out/'fixed-date-board-review.json',rows);pd.DataFrame(rows).to_csv(out/'fixed-date-board-review.csv',index=False)
 # Full actual board versus physical truncation: no future rows can affect any
 # past cross-sectional rank, breadth, segment gate or interleaved queue.
 source=dict(np.load(OLD/'h1/matrix.npz'));receipts=[]
 for cutoff in ['2018-12-28','2023-12-29']:
  n=dates.searchsorted(pd.Timestamp(cutoff),side='right');p=build({k:v if k=='symbols' else v[:n] for k,v in source.items()},meta)
  for k,v in p.items():np.testing.assert_equal(v,data[k] if k=='symbols' else data[k][:n])
  receipts.append(dict(cutoff=cutoff,rows=n,all_fields_exact=True))
 write(out/'board-prefix.json',dict(passed=True,recorded_at=now(),details=receipts))
 print(dict(review=True,prefixes=len(receipts)),flush=True)
if __name__=='__main__':main()
