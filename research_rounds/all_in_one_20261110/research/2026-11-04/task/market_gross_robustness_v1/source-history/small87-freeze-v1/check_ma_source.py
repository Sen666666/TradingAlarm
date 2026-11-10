"""Pure stored-X MA identity, no Account/data loader or economic result."""
from pathlib import Path
import json,hashlib,math,datetime
import pandas as pd
O=Path(__file__).resolve().parent;T=O.parent
PATHS={'long':T/'benchmark_2022_2023/continuation2024/inputs/510300_history.csv','strong':T/'capacity_cost_guard_analysis_v1/benchmark_B_2025_26/inputs/510300_history.csv'}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def state(x,ma,previous):
 k=all(z is not None and math.isfinite(z)and z>0 for z in(x,ma,previous))
 return'UNKNOWN'if not k else'DOWN'if x<ma and ma<previous else'NOT_DOWN'
def main():
 assert not(O/'MA63_RECOMPUTE_CHECK.json').exists(),'do not silently repeat checks'
 sources=[Path(__file__),O/'PROTOCOL.txt',O/'ma_provider.py']+list(PATHS.values())
 freeze=dict(before_new_rolling_or_accounts=True,at_UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),source_sha256={str(p):sha(p)for p in sources})
 (O/'PRE_MA_CHECK_FREEZE.json').write_text(json.dumps(freeze,indent=2)+'\n')
 out={}
 for window,path in PATHS.items():
  f=pd.read_csv(path,index_col='date',parse_dates=True);ma=f.signal_close.rolling(63,min_periods=63).mean();old=list(map(float,f.ma63));new=list(map(float,ma));x=list(map(float,f.signal_close));diff=[];mapping={}
  for k,t in enumerate(f.index):
   a=state(x[k],old[k],old[k-1]if k else None);b=state(x[k],new[k],new[k-1]if k else None);day=str(t.date());mapping[day]=(a,b)
   if a!=b:diff.append(dict(day=day,stored=a,recomputed=b,X=x[k],stored_MA63=old[k],recomputed_MA63=new[k],previous_stored=old[k-1]if k else None,previous_recomputed=new[k-1]if k else None))
  cal=json.loads((T/f'market_gross_admission_native_v1/prepared/{window}/EXPECTED_CLOSE_CALENDAR.json').read_text());days={c[:10]for c in cal['closes']};consumed=[r for r in diff if r['day']in days]
  out[window]=dict(history_rows=len(f),all_history_D_classification_exact=not diff,differences=diff,prescribed_full_calendar_and_warm_D_exact=not consumed,consumed_differences=consumed,source_path=str(path),source_sha256=sha(path),primary63_always_uses_stored_MA63=True)
 assert all(sha(p)==h for p,h in freeze['source_sha256'].items())
 z=dict(scope='PURE_MA_RECOMPUTE_IDENTITY_ONLY',windows=out,new_accounts=0,no_primary_source_replacement=True)
 (O/'MA63_RECOMPUTE_CHECK.json').write_text(json.dumps(z,indent=2,allow_nan=True)+'\n');print(json.dumps(z,indent=2,allow_nan=True))
if __name__=='__main__':main()
