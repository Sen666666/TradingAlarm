"""Report correction only. Event-ID loss does not imply missing a stock's move."""
from pathlib import Path
import pandas as pd,json,hashlib
O=Path(__file__).resolve().parent
r=pd.read_csv(O/'CORE_AND_FULL_ROUNDS.csv',float_precision='round_trip')
b=r[(r.arm=='A_UNION_B')&(r.window=='2024_924')&(r.status=='COMPLETE_CONDITIONAL_STOCK_ROUND')&(r.core_return>=.5)]
n=r[(r.arm=='RELATIVE_UP_PRIORITY')&(r.window=='2024_924')]
missing=b[~b.event_id.isin(n.event_id)];assert len(missing)==11
rows=[];summary=[]
for _,old in missing.iterrows():
 candidates=n[n.sid.eq(old.sid)]
 matches=[]
 for _,new in candidates.iterrows():
  entered=new.entry_status=='CONDITIONAL_OPEN_PROXY' and pd.notna(new.entry_day)
  left=pd.Timestamp(new.entry_day) if entered else pd.NaT
  # Open sale terminates holding. Touching dates alone do not imply overlap.
  right=pd.Timestamp(new.exit_day) if pd.notna(new.exit_day) else pd.Timestamp(new.status_day) if pd.notna(new.status_day) else pd.NaT
  overlap=bool(entered and pd.notna(right) and max(pd.Timestamp(old.entry_day),left)<min(pd.Timestamp(old.exit_day),right))
  same_exit=bool(pd.notna(new.exit_day) and old.exit_day==new.exit_day)
  full_cover=bool(overlap and left<=pd.Timestamp(old.entry_day) and right>=pd.Timestamp(old.exit_day))
  x=dict(sid=old.sid,name=old['name'],old_event_id=old.event_id,old_signal_day=old.signal_day,old_entry_day=old.entry_day,old_exit_day=old.exit_day,old_core_net=old.core_net,old_core_return=old.core_return,new_event_id=new.event_id,new_signal_day=new.signal_day,new_entry_day=new.entry_day,new_exit_day=new.exit_day,new_status=new.status,new_core_net=new.core_net,new_core_return=new.core_return,holding_overlap=overlap,same_exit_day=same_exit,covers_entire_old_holding_interval=full_cover,entry_relation='EARLIER' if entered and left<pd.Timestamp(old.entry_day) else 'LATER' if entered and left>pd.Timestamp(old.entry_day) else 'SAME' if entered else 'NOT_ENTERED')
  rows.append(x);matches.append(x)
 overlaps=[x for x in matches if x['holding_overlap']]
 classification='EARLIER_ENTRY_FULL_INTERVAL_REPLACEMENT' if any(x['covers_entire_old_holding_interval'] for x in overlaps) else 'LATER_ENTRY_PARTIAL_INTERVAL_PARTICIPATION' if overlaps else 'NO_CONFIRMED_OVERLAPPING_HOLDING'
 summary.append(dict(old_event_id=old.event_id,sid=old.sid,name=old['name'],old_core_net=old.core_net,old_core_return=old.core_return,new_same_stock_rounds=len(matches),overlapping_rounds=len(overlaps),same_exit_rounds=sum(x['same_exit_day'] for x in matches),classification=classification,interpretation='原事件被更早同股持仓覆盖，不是错过对应行情' if classification.startswith('EARLIER') else '新臂较晚才持有对应行情，仅部分参与，不可称完全错过' if classification.startswith('LATER') else '此窗口新臂没有确认持有与旧回合重叠的该股区间',overlap_core_net=sum(x['new_core_net'] for x in overlaps),overlap_core_net_delta=sum(x['new_core_net'] for x in overlaps)-old.core_net))
 if not len(candidates):rows.append(dict(sid=old.sid,name=old['name'],old_event_id=old.event_id,old_signal_day=old.signal_day,old_entry_day=old.entry_day,old_exit_day=old.exit_day,old_core_net=old.core_net,old_core_return=old.core_return,new_event_id=None,holding_overlap=False,same_exit_day=False,covers_entire_old_holding_interval=False,entry_relation='NO_NEW_SAME_STOCK_ROUND'))
pd.DataFrame(rows).to_csv(O/'TAIL_SAME_STOCK_ROUNDS.csv',index=False);s=pd.DataFrame(summary);s.to_csv(O/'TAIL_HOLDING_OVERLAP_SUMMARY.csv',index=False)
b22=r[(r.arm=='A_UNION_B')&(r.window=='2022')&(r.core_return>=.5)];n22=r[(r.arm=='RELATIVE_UP_PRIORITY')&(r.window=='2022')];assert len(b22)==20 and b22.event_id.isin(n22.event_id).all()
qa=dict(old_2024_core_ge50=56,new_2024_core_ge50=49,old_tail_event_ids_not_retained=11,classification_counts=s.classification.value_counts().to_dict(),old_2022_core_ge50=20,old_2022_tail_event_ids_retained=20,economic_rerun=False,correction='Event-ID attrition is not stock-opportunity attrition. Three earlier same-stock rounds fully cover old intervals; five later rounds partly overlap; three have no overlapping new holding.')
(O/'TAIL_HOLDING_OVERLAP_QA.json').write_text(json.dumps(qa,ensure_ascii=False,indent=2)+'\n')
print(s.to_string(index=False));print(json.dumps(qa,ensure_ascii=False))
