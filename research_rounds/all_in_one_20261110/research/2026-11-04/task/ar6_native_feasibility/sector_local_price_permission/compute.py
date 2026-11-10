from pathlib import Path
from collections import deque,Counter
import json,math,hashlib,gzip,time
import pandas as pd
O=Path(__file__).resolve().parent
M=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/INDUSTRY_MANIFEST.json')
END='2026-06-30'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def main():
 start=time.monotonic();assert not(O/'RESULTS.json').exists(),'no automatic repeat'
 freeze=json.loads((O/'SOURCE_FREEZE.json').read_text())
 for p,h in freeze.items():assert sha(p)==h,p
 manifest=json.loads(M.read_text());assert len(manifest)==90 and len({x['series']for x in manifest})==90
 index=[];total=0
 with gzip.open(O/'DAILY.jsonl.gz','wt',compresslevel=1)as output:
  for entry in manifest:
   sid=entry['series'];p=Path(entry['refs']['CP1_input']);source_hash=sha(p)
   assert entry['status']=='complete'and source_hash==entry['output_sha256'][str(p)]
   f=pd.read_parquet(p,columns=['close','segment_id']).loc[:END]
   assert f.index.is_unique and f.index.is_monotonic_increasing and f.index.normalize().is_unique
   assert f.segment_id.notna().all(),'unknown source unit cannot bridge'
   blocks=f.segment_id[f.segment_id.ne(f.segment_id.shift())];assert not blocks.duplicated().any(),'source must be contiguous'
   state='UNESTABLISHED';segment=None;history=deque(maxlen=20);counts=Counter();events=Counter();first=last=None
   for day,c,seg in zip(f.index,f.close,f.segment_id):
    seg=str(seg);reset=seg!=segment
    if reset:state='UNESTABLISHED';history.clear();segment=seg
    before=state;current_known=math.isfinite(float(c))and float(c)>0
    prior_known=len(history)==20 and all(x is not None for x in history)
    H=max(history)if prior_known else None;L=min(history)if prior_known else None
    known=bool(current_known and prior_known);event='source_reset'if reset else'none'
    if known:
     if float(c)>H:
      state='LOCAL_ON';event='enter_ON'if before!=state else'new_high_keep_ON'
     elif float(c)<L:
      state='LOCAL_OFF';event='enter_OFF'if before!=state else'new_low_keep_OFF'
    status=('KNOWN_ON'if state=='LOCAL_ON'else'KNOWN_OFF'if state=='LOCAL_OFF'else'KNOWN_UNESTABLISHED')if known else'UNKNOWN_NO_NEW_PERMISSION'
    d=str(day.date());r=dict(sector=sid,industry_sid=sid,day=d,decision_close=d+' 15:10:00+08:00',source_segment=seg,source_SHA256=source_hash,
     current_close=float(c)if current_known else None,current_known=bool(current_known),prior20_known=bool(prior_known),known=known,
     H20=H,L20=L,state_before=before,local_state=state,local_permission_status=status,local_new_risk_permission=bool(known and state=='LOCAL_ON'),event=event,
     old_inventory_macro_action='NO_LOCAL_FORCED_SELL_USE_ORIGINAL_I_CP1_EXIT',ON_is_mature_or_full_risk=False,original_I_CP1_Q_H_still_required=True)
    output.write(json.dumps(r,ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n');total+=1
    counts[status]+=1;events[event]+=1;first=first or d;last=d
    history.append(float(c)if current_known else None)
   index.append(dict(sector=sid,input_path=str(p),input_SHA256=source_hash,rows=len(f),first=first,last=last,source_segments=len(blocks),counts=dict(counts),events=dict(events)))
 save('SERIES_INDEX.json',index)
 for p,h in freeze.items():assert sha(p)==h,p
 save('RESULTS.json',dict(passed=True,seconds=time.monotonic()-start,sectors=len(index),rows=total,end=END,new_accounts=0,new_quantity_models=0,new_Stage=False,no_new_loader=True,all_input_hashes_exact_to_manifest=True,all_old_positions_keep_original_exits=True,no_automatic_followup=True))
 print(json.dumps(dict(sectors=len(index),rows=total,seconds=time.monotonic()-start),ensure_ascii=False))
if __name__=='__main__':main()
