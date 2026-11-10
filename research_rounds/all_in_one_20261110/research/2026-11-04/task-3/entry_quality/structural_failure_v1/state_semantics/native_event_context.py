"""Original negative event leg at actual decisions. No new indicator/filter/account."""
from pathlib import Path
import json,hashlib
from collections import defaultdict,Counter
import pandas as pd
import analyze as A
O=A.O;W=A.W;S={};sm=A.sm
requests=defaultdict(list)
for ref in ['2022_2024','strong']:
 for e in json.loads((O/(ref+'_ROWS.json')).read_text()):requests[e['sid']].append((ref,e))
out={r:[] for r in ['2022_2024','strong']}
for sid,requests_ in sorted(requests.items()):
 m=sm[sid];ep=next(Path(p) for p in m['source_sha256'] if p.endswith('/events.parquet'));s=A.sha(ep);assert s==m['source_sha256'][str(ep)];S[str(ep)]=s;ev=pd.read_parquet(ep);f=pd.read_parquet(m['refs']['facts']);joined=ev.reindex(f.index);native=joined['event'].fillna(0);times=pd.Series(f.index,index=f.index)
 lastneg=times.where(native.eq(-1)).ffill();lastpos=times.where(native.eq(1)).ffill();negpivot=joined.confirmed_pivot_price.where(native.eq(-1)).ffill();negconfirm=f.close.where(native.eq(-1)).ffill();negsegment=f.segment_id.where(native.eq(-1)).ffill();Istart=times.where(f.i_target.eq(1)&(f.i_target.shift(fill_value=0).ne(1)|f.segment_id.ne(f.segment_id.shift()))).ffill().where(f.i_target.eq(1))
 for ref,e in requests_:
  d=pd.Timestamp(e['decision_at'][:10]);p=joined.loc[d];ln=lastneg.loc[d];lp=lastpos.loc[d];is_=Istart.loc[d];same_negseg=pd.notna(negsegment.loc[d]) and negsegment.loc[d]==f.loc[d,'segment_id'];negative_leg=same_negseg and pd.notna(ln) and (pd.isna(lp) or ln>lp)
  e['native_E0_event_context']=dict(event=A.scalar(p.event),leg_direction=A.scalar(p.leg_direction),confirmation=A.scalar(p.confirmation),last_negative_event_day=None if pd.isna(ln) else str(ln.date()),last_positive_event_day=None if pd.isna(lp) else str(lp.date()),last_negative_event_confirmed_pivot=A.scalar(negpivot.loc[d]),last_negative_event_confirmation_close=A.scalar(negconfirm.loc[d]),current_I_true_start=None if pd.isna(is_) else str(is_.date()),negative_event_in_current_Iroot=bool(pd.notna(ln) and pd.notna(is_) and ln>=is_ and same_negseg),pending_negative_event_until_next_positive=bool(negative_leg),C_reclaimed_last_negative_pivot=None if pd.isna(negpivot.loc[d]) else float(f.loc[d,'close'])>float(negpivot.loc[d]),unknown_leg=pd.isna(p.leg_direction))
  e['native_negative_event_unreconfirmed']=bool(negative_leg);e['native_negative_event_unreconfirmed_in_Iroot']=bool(negative_leg and pd.notna(is_) and ln>=is_);e['native_below_last_negative_pivot']=None if pd.isna(negpivot.loc[d]) else float(f.loc[d,'close'])<=float(negpivot.loc[d]);out[ref].append(e)
for ref,rows in out.items():rows.sort(key=lambda x:x['layer']);A.save(ref+'_NATIVE_EVENT_ROWS.json',rows)
summary={}
for label,rows in [('2022_2024',out['2022_2024']),('2022_2023',[x for x in out['2022_2024'] if x['opened'][:4]<'2024']),('post_Oct8_303',[x for x in out['2022_2024'] if x['opened'][:10]>'2024-10-08']),('strong',out['strong'])]:
 m=[x for x in rows if x['role']=='mobile'];neg=[x for x in m if x['native_negative_event_unreconfirmed']];summary[label]=dict(all=A.agg(rows),mobile=A.agg(m),mobile_native_negative_leg=A.agg(neg),mobile_negative_leg_in_currentI=A.agg([x for x in m if x['native_negative_event_unreconfirmed_in_Iroot']]),negative_leg_by_action=A.grouped(neg,['action']),negative_leg_G1grade=A.grouped([{**x,'g':x['original_stock_state']['g_grade']} for x in neg],['g']),negative_leg_by_industry_stage=A.grouped(neg,['industry_stage']),unknown_leg=sum(x['native_E0_event_context']['unknown_leg'] for x in rows),below_old_negativepivot=A.agg([x for x in m if x['native_below_last_negative_pivot']]))
A.save('NATIVE_EVENT_RESULTS.json',summary);A.save('NATIVE_EVENT_SOURCES.json',dict(sources=S,script_sha256=A.sha(__file__),no_model_calls=True,no_new_accounts=True,clock='same original E0 event stream on existing prepared price/source dates; pending negative state means last event -1 until next +1, not original participation-memory reclaim'))
print(json.dumps(summary,ensure_ascii=False,default=str),flush=True)
