from pathlib import Path
import json,math,hashlib,gzip,time
from collections import Counter
import pandas as pd
O=Path(__file__).resolve().parent;BASE=O.parent/'diagnostic_v2';T=O.parents[2]
REC=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/mainline-absolute-Q4-20261031/recovery.csv')
AR=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/pv-strength-b5-20261025/code/arithmetic.py')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def main():
 start=time.monotonic();assert not(O/'RESULTS.json').exists(),'no automatic repeat'
 freeze=json.loads((O/'SOURCE_FREEZE.json').read_text())
 for p,h in freeze['sources'].items():assert sha(p)==h,p
 ar={'__name__':'unchanged_E0_scalar_only'};exec(compile(AR.read_text(),str(AR),'exec'),ar);lr,cmp=ar['log_ratio'],ar['compare']
 f=pd.read_csv(REC,index_col=0,parse_dates=True);z=pd.read_csv(BASE/'FULL_ORIGINAL_INPUT_PLUS_STATIC20.csv',index_col=0,parse_dates=True)
 assert f.market.equals(z.market)and f.breadth.equals(z.breadth)
 assert f.index.is_unique and f.index.is_monotonic_increasing
 old={}
 for source in freeze['ACT_context_books']:
  with gzip.open(source,'rt')as h:b=json.load(h)
  for q in b['audit']:
   if q['kind']=='risk_checkpoint':
    d=q['at'][:10];assert d not in old
    old[d]={k:q.get(k)for k in ['on','flat','event']}
 M=f.market.to_numpy(float);known=z.price_known.to_numpy(bool);sigma=[None]*len(f)
 for i in range(64,len(f)):
  if all(known[i-64:i])and known[i]:
   r=[lr(float(M[j]),float(M[j-1]))for j in range(i-63,i)]
   sigma[i]=max(math.sqrt(math.fsum(x*x for x in r)/63),1e-8)
 state=None;S=anchor=sig=None;marker=False;rows=[];initial=None
 for i,(day,q)in enumerate(z.iterrows()):
  d=str(day.date());m=float(q.market);price_known=bool(q.price_known);B_known=pd.notna(q.breadth)
  ready=sigma[i]is not None and pd.notna(q.H20)and pd.notna(q.L20)
  before=state;sb=S;ab=anchor;vb=sig;mb=marker;ev='none';reason='no_qualifying_high';new=bool(q.new_high20)and price_known
  if state is None:
   if ready:state='D';initial=d;ev='initialize_D';reason='first_complete_prior64M_and20_window'
   else:reason='uninitialized_unknown_or_warm'
  elif state in ['P','C']and price_known and m<S:
   state='D';S=anchor=sig=None;marker=False;ev='support_break_D';reason='M_strictly_below_OLD_S_no_same_bar_reentry'
  elif not price_known or not B_known or not ready:
   marker=False;reason='unknown_breaks_continuity_no_new_state_or_weakness'
  elif float(q.breadth)<=.6:
   marker=False;reason='known_B_false_freezes_progression_no_sale'
  elif state=='D':
   if new:
    state='P';S=float(q.L20);anchor=m;sig=sigma[i];marker=True;ev='D_to_P';reason='strict_new20high_and_B_gt_.6'
  elif new:
   displacement=lr(m,anchor);passed=displacement>=0 and cmp(displacement,math.sqrt(5)*sig)>=0
   if passed:
    if not marker:marker=True;ev='rearm_marker';reason='first_qualifying_high_after_continuity_gap_NO_advance'
    else:
     state='C';S=max(S,float(q.L20));anchor=m;sig=sigma[i];ev='P_to_C'if before=='P'else'C_advance';reason='continuous_known_B_and_frozen_E0_displacement'
  row=dict(day=d,at=d+' 15:10:00+08:00',price_known=price_known,breadth_known=B_known,prior64_ready=ready,market=m,breadth=None if not B_known else float(q.breadth),H20=None if pd.isna(q.H20)else float(q.H20),L20=None if pd.isna(q.L20)else float(q.L20),new20high=new,old_BREAK63=bool(q.breakout),market_structural_state=state,requested_state=state,state_before=before,event=ev,reason=reason,S_before=sb,S_after=S,anchor_before=ab,anchor_after=anchor,sigma_before=vb,sigma_after=sig,marker_before=mb,marker_after=marker,old_ACT_context=old.get(d))
  rows.append(row)
 save('DAILY.json',rows);pd.DataFrame([{**r,'old_ACT_context':json.dumps(r['old_ACT_context'],ensure_ascii=False)}for r in rows]).to_csv(O/'DAILY.csv',index=False)
 save('EVENTS.json',[r for r in rows if r['event']!='none'])
 windows=[('L01','2022-01-04','2022-04-26'),('L02','2022-04-27','2022-07-04'),('L03','2022-07-05','2022-10-31'),('2023Q2_AI','2023-04-01','2023-06-30'),('2023Jul_false','2023-07-01','2023-09-29'),('2024spring','2024-02-01','2024-05-06'),('2024SepOct','2024-09-02','2024-10-31'),('strong','2025-07-01','2026-06-30')]
 ws=[]
 for label,lo,hi in windows:
  w=[r for r in rows if lo<=r['day']<=hi];e=[r for r in w if r['event']!='none'];ex=[r for r in e if r['event']=='support_break_D']
  record=dict(label=label,lo=lo,hi=hi,closes=len(w),state_counts=dict(Counter(r['market_structural_state']for r in w)),event_counts=dict(Counter(r['event']for r in e)),first_D_day=next((r['day']for r in w if r['market_structural_state']=='D'),None),first_support_break_D=ex[0]['day']if ex else None,events=e)
  for r in ex:
   remaining=[v for v in w if v['day']>=r['day']];p=r['market']
   r['DIAGNOSTIC_future_same_window']=dict(end=remaining[-1]['day'],min_M=min(v['market']for v in remaining),max_M=max(v['market']for v in remaining),end_M=remaining[-1]['market'],min_change=min(v['market']for v in remaining)/p-1,max_change=max(v['market']for v in remaining)/p-1,end_change=remaining[-1]['market']/p-1,not_trading_return=True)
  ws.append(record)
 save('WINDOWS.json',ws)
 for p,h in freeze['sources'].items():assert sha(p)==h,p
 save('RESULTS.json',dict(passed=True,seconds=time.monotonic()-start,rows=len(rows),initial_D=initial,states=dict(Counter(r['market_structural_state']for r in rows)),events=dict(Counter(r['event']for r in rows)),new_accounts=0,new_account_events=0,new_risk_ledger=False,no_ACT_on_output=True,M_recalculated=False,single_fixed_spec=True,no_automatic_followup=True))
 print(json.dumps(dict(initial=initial,windows=[{k:v for k,v in w.items()if k!='events'}for w in ws]),ensure_ascii=False,indent=2))
if __name__=='__main__':main()
