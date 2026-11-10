
"""Four-case right-confirmed higher-low price-event audit; no strategy replay."""
from pathlib import Path
import json,math
import pandas as pd,numpy as np
O=Path(__file__).resolve().parent;B=O.parent
U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
manifest={r['symbol']:r for r in json.loads((U/'STOCK_MANIFEST.json').read_text())}
CASES=[('002385.SZ','2022-03-04'),('300182.SZ','2022-01-04'),('600606.SH','2022-03-22'),('688582.SH','2024-07-29')]
band=pd.read_csv(B/'SIGNAL_SUMMARY.csv')
freeze=dict(hypothesis='REPAIR can rebuild on a newly right-confirmed higher-low plus breakout above the intervening confirmed close high; price rebuild is not an order. Current fresh original CP is still mandatory for a new order.',pivot_definition='No amplitude/window threshold. UP run high is confirmed only on first later lower close; DOWN run low only on first later higher close. Equal-close plateaus keep the latest equal extreme. Store extreme day and confirmation day separately. Same source segment only.',pattern='Two consecutive confirmed lows L1,L2 with the intervening confirmed high H. L2>L1. Confirming close may already break H; otherwise wait for a later actual close>H. Cancel unbroken pattern if C<L2. Emit at most once per pattern.',rebuild='After a known structural breach, require L1 extreme at/after breach. Actual price pattern breakout sets base=L2; later C<base invalidates; a new completed higher-low breakout can rebuild again. Never revive expired CP. No order at price breakout unless that day has its own fresh original CP. Existing I/industry/account eligibility unchanged.',CP_diagnostic='Count original receipts separately on L1->H and L2->break. These counts do not change the price event definition. Check whether demanding proof on both legs would also exclude real early reversals; do not tune counts.',case_set=CASES,not_validation='Fixed-case structure evidence only. Close pivots are minimal price turns, not claimed noise-resistant macro swings. No full candidate/account test or parameter search.')
(O/'FORMULA_AND_CLOCK.json').write_text(json.dumps(freeze,ensure_ascii=False,indent=2))
def derive(f,cp):
 piv=[];events=[];daily=[];seg=None;direction=0;ei=None;lastlow=None;lasthigh=None;pattern=None;bid=0
 for i,(day,row)in enumerate(f.iterrows()):
  p=float(row.close)
  if seg is None or row.segment_id!=seg:
   seg=row.segment_id;direction=0;ei=i;lastlow=lasthigh=pattern=None
  confirmed=None
  if i>0 and f.segment_id.iloc[i-1]==seg:
   e=float(f.close.iloc[ei])
   if direction==0:
    if p>e:direction=1;ei=i
    elif p<e:direction=-1;ei=i
    else:ei=i
   elif direction==1:
    if p>=e:ei=i
    else:confirmed=('HIGH',ei);direction=-1;ei=i
   else:
    if p<=e:ei=i
    else:confirmed=('LOW',ei);direction=1;ei=i
  if confirmed:
   typ,j=confirmed;x=dict(sid=None,pivot_type=typ,pivot_day=str(f.index[j].date()),confirmed_day=str(day.date()),pivot_close=float(f.close.iloc[j]),pivot_raw=float(f.raw_close.iloc[j]),index=j,confirmation_index=i)
   piv.append(x)
   if typ=='HIGH':lasthigh=x
   else:
    if lastlow is not None and lasthigh is not None and lastlow['index']<lasthigh['index']<j:
     pattern=dict(L1=lastlow,H=lasthigh,L2=x,higher=x['pivot_close']>lastlow['pivot_close'],broken=False,invalid=False,id=bid);bid+=1
    lastlow=x
  if pattern is not None:
   if p<pattern['L2']['pivot_close']:pattern['invalid']=True
   if pattern['higher']and not pattern['broken']and not pattern['invalid']and p>pattern['H']['pivot_close']:
    pattern['broken']=True
    L1,H,L2=pattern['L1'],pattern['H'],pattern['L2']
    c1=cp.receipt.iloc[L1['index']+1:H['index']+1];c2=cp.receipt.iloc[L2['index']+1:i+1]
    e=dict(break_day=str(day.date()),break_close=p,break_raw=float(row.raw_close),L1_day=L1['pivot_day'],L1_confirmed=L1['confirmed_day'],L1_close=L1['pivot_close'],L1_raw=L1['pivot_raw'],H_day=H['pivot_day'],H_confirmed=H['confirmed_day'],H_close=H['pivot_close'],H_raw=H['pivot_raw'],L2_day=L2['pivot_day'],L2_confirmed=L2['confirmed_day'],L2_close=L2['pivot_close'],L2_raw=L2['pivot_raw'],first_leg_CP_receipts=int(c1.sum()),second_leg_CP_receipts=int(c2.sum()),current_original_CP=bool(cp.receipt.iloc[i]),both_legs_have_CP=bool(c1.any()and c2.any()),source_i_buy=bool(row.i_buy))
    events.append(e)
  q=dict(day=str(day.date()),raw_close=float(row.raw_close),fresh_CP=bool(cp.receipt.iloc[i]),native_I=bool(row.i_target),new_pivot_type=confirmed[0]if confirmed else None)
  if pattern is not None:
   for k in ['L1','H','L2']:q[k+'_day']=pattern[k]['pivot_day'];q[k+'_confirmed']=pattern[k]['confirmed_day'];q[k+'_raw']=pattern[k]['pivot_raw']
   q.update(latest_pair_higher_low=pattern['higher'],latest_pattern_broken=pattern['broken'],latest_pattern_invalid=pattern['invalid'])
  daily.append(q)
 return pd.DataFrame(piv),pd.DataFrame(events),pd.DataFrame(daily)
pivs=[];evs=[];days=[];results=[];prefix=[]
for sid,signal in CASES:
 f=pd.read_parquet(manifest[sid]['refs']['facts']);cp=pd.read_parquet(manifest[sid]['refs']['CP1']);assert f.index.equals(cp.index)
 p,e,d=derive(f,cp);t=f.index.get_loc(pd.Timestamp(signal))
 for stop in [t,t+1]:
  pp,ee,dd=derive(f.iloc[:stop],cp.iloc[:stop])
  pd.testing.assert_frame_equal(pp,p[p.confirmation_index<stop].reset_index(drop=True),check_dtype=False)
  pd.testing.assert_frame_equal(ee,e[e.break_day<=(str(f.index[stop-1].date()))].reset_index(drop=True),check_dtype=False)
  pd.testing.assert_frame_equal(dd,d.iloc[:stop].reset_index(drop=True),check_dtype=False)
  prefix.append(dict(sid=sid,signal_day=signal,cutoff=str(f.index[stop-1].date()),passed=True))
 p['sid']=sid;e['sid']=sid;d['sid']=sid;pivs.append(p);evs.append(e);days.append(d.iloc[max(0,t-20):t+11].copy())
 original=band[band.sid.eq(sid)&band.signal_day.eq(signal)].iloc[0]
 summary=dict(sid=sid,signal_day=signal,original_band_state=original.state_after_floor_check,original_CP=bool(cp.receipt.iloc[t]))
 summary.update(d.iloc[t].to_dict())
 if original.state_after_floor_check=='REPAIR':
  start=pd.Timestamp(original.last_breach_day);state='REPAIR';base=math.nan;base_day=None;rebuilt=None;count=0;last_invalid=None
  eligible=e[(e.break_day>=str(start.date()))&(e.L1_day>=str(start.date()))&(e.break_day<=signal)].set_index('break_day')
  for dd in f.loc[start:pd.Timestamp(signal)].itertuples():
   day=str(dd.Index.date());price=float(dd.close)
   if state=='REBUILT'and price<base:state='REPAIR';last_invalid=day
   if day in eligible.index:
    z=eligible.loc[day];state='REBUILT';base=float(z.L2_close);base_day=z.L2_day;rebuilt=day;count+=1
  summary.update(original_repair_from=str(start.date()),price_rebuild_state_at_signal=state,price_rebuild_events_since_breach=count,last_price_rebuild_day=rebuilt,active_base_day=base_day if state=='REBUILT'else None,active_base_native=base if state=='REBUILT'else None,last_rebuild_invalidation=last_invalid)
 else:summary.update(price_rebuild_state_at_signal='NOT_APPLICABLE_ORIGINAL_EXPAND')
 results.append(summary)
pd.concat(pivs,ignore_index=True).to_csv(O/'RIGHT_CONFIRMED_PRICE_PIVOTS.csv',index=False)
pd.concat(evs,ignore_index=True).to_csv(O/'HIGHER_LOW_BREAKOUT_EVENTS.csv',index=False)
pd.concat(days,ignore_index=True).to_csv(O/'FOUR_CASES_DAILY.csv',index=False)
pd.DataFrame(results).to_csv(O/'SIGNAL_AND_REBUILD_SUMMARY.csv',index=False)
pd.DataFrame(prefix).to_csv(O/'PREFIX_CHECKS.csv',index=False)
print(pd.DataFrame(results).to_string(index=False))
for sid,signal in CASES:
 z=pd.concat(evs);z=z[(z.sid==sid)&(z.break_day<=signal)]
 print('LATEST_EVENT',sid,signal);print(z.tail(1).to_string(index=False))
print('ALL',len(prefix),'PREFIX CHECKS PASSED')
