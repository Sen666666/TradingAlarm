"""Saved E0-pivot confirmation joins and pure log-path arithmetic. No signal/account model."""
from pathlib import Path
import csv,hashlib,json,math
import pandas as pd

OUT=Path(__file__).resolve().parent
MANIFEST=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')
SID='000620.SZ';START='2022-01-20';END='2022-01-25'
def clean(x):
    if isinstance(x,dict):return{k:clean(v)for k,v in x.items()}
    if isinstance(x,list):return[clean(v)for v in x]
    if x is pd.NA or x is pd.NaT:return None
    if hasattr(x,'item'):return clean(x.item())
    if isinstance(x,float)and not math.isfinite(x):return None
    return x
def save(n,x):(OUT/n).write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
rec=next(r for r in json.loads(MANIFEST.read_text())if r['symbol']==SID)
ip=Path(rec['refs']['CP1_input']);zp=Path(rec['refs']['CP1']);fp=Path(rec['refs']['facts'])
ep=Path(next(p for p in rec['source_sha256']if p.endswith('/events.parquet')))
for p in [ip,zp,fp]:assert hashlib.sha256(p.read_bytes()).hexdigest()==rec['output_sha256'][str(p)]
assert hashlib.sha256(ep.read_bytes()).hexdigest()==rec['source_sha256'][str(ep)]
f=pd.read_parquet(ip).loc[:END];z=pd.read_parquet(zp).reindex(f.index)
facts=pd.read_parquet(fp,columns=['close','raw_close','factor','segment_id']).loc[:END]
events=pd.read_parquet(ep).loc[:END]
assert not any('event_id'==c or 'canonical_event_id'==c for c in events.columns)
confirmed=[]
for dt,e in events.iterrows():
    if not pd.notna(e.event)or e.event not in[-1,1]:continue
    confirm=str(dt.date());pivot=str(pd.Timestamp(e.confirmed_pivot_date).date())
    assert pivot<=confirm
    sigma=z.loc[dt,'z']if dt in z.index else float('nan')
    key=f'{SID}|segment:{int(e.segment_id)}|E0:{int(e.event):+d}|confirm:{confirm}|pivot:{pivot}'
    confirmed.append(dict(confirm_day=confirm,confirm_at=confirm+' 15:10:00+08:00',pivot_day=pivot,
                          event_sign=int(e.event),source_segment=int(e.segment_id),
                          pivot_price_a=float(e.confirmed_pivot_price),
                          pivot_raw_at_pivot_date=float(facts.loc[pd.Timestamp(pivot),'raw_close']),
                          sigma_frozen_from_CP_z_at_confirm=float(sigma)if math.isfinite(float(sigma))else None,
                          original_event_id='NOT_EXPORTED_BY_ORIGINAL_EVENTS_PARQUET',
                          source_row_key_NOT_canonical_event_id=key,
                          original_confirmation_row=clean(e.to_dict())))

def path(anchor,through):
    pivot=anchor['pivot_day'];a=float(anchor['pivot_price_a'])
    g=f.loc[pivot:through]
    assert len(g)and str(g.index[0].date())==pivot
    assert g.segment_id.eq(anchor['source_segment']).all()
    assert abs(float(g.iloc[0].close)-a)<1e-12
    p=[math.log(float(c))for c in g.close]
    A=p[-1]-math.log(a);L=math.fsum(abs(b-a0)for a0,b in zip(p[:-1],p[1:]));DD=max(p)-p[-1]
    sigma=anchor['sigma_frozen_from_CP_z_at_confirm']
    return dict(A=A,L=L,ER=A/L if L else None,DD=DD,
                A_over_frozen_sigma=A/sigma if sigma else None,
                L_over_frozen_sigma=L/sigma if sigma else None,
                DD_over_frozen_sigma=DD/sigma if sigma else None,
                observations_after_pivot=len(g)-1,known_peak_price_a=math.exp(max(p)))

targets=[];used=set()
for dt,r in f.loc[START:END].iterrows():
    day=str(dt.date());segment=int(r.segment_id);factor=float(facts.loc[dt,'factor'])
    known=[e for e in confirmed if e['source_segment']==segment and e['confirm_day']<=day]
    low=next(e for e in reversed(known)if e['event_sign']==1)
    high=next(e for e in reversed(known)if e['event_sign']==-1)
    sm=path(low,day);lm=path(high,day)
    row=dict(day=day,original_CLOSE_at=day+' 15:10:00+08:00',sid=SID,source_segment=segment,
             close_a=float(r.close),close_raw=float(facts.loc[dt,'raw_close']),factor=factor,
             original_CP_receipt=bool(z.loc[dt,'receipt']),
             low_confirm_at=low['confirm_at'],low_pivot_day=low['pivot_day'],low_pivot_price_a=low['pivot_price_a'],
             low_pivot_raw_in_today_units=low['pivot_price_a']/factor,
             low_source_row_key=low['source_row_key_NOT_canonical_event_id'],low_original_event_id=low['original_event_id'],
             sigma_s=low['sigma_frozen_from_CP_z_at_confirm'],
             high_confirm_at=high['confirm_at'],high_pivot_day=high['pivot_day'],high_pivot_price_a=high['pivot_price_a'],
             high_pivot_raw_in_today_units=high['pivot_price_a']/factor,
             high_source_row_key=high['source_row_key_NOT_canonical_event_id'],high_original_event_id=high['original_event_id'],
             sigma_l=high['sigma_frozen_from_CP_z_at_confirm'],
             **{k+'_s':v for k,v in sm.items()},**{k+'_l':v for k,v in lm.items()},
             anchors_do_not_reset_on_CP_receipt_or_SEEK=True,
             historical_pivot_path_became_available_only_at_confirmation=True,
             no_threshold_or_signal_decision=True)
    targets.append(row);used.update([low['source_row_key_NOT_canonical_event_id'],high['source_row_key_NOT_canonical_event_id']])
assert len(targets)==4
save('TWO_SCALE_FOUR_CLOSES.json',targets)
with(OUT/'TWO_SCALE_FOUR_CLOSES.csv').open('w',newline='')as h:
    w=csv.DictWriter(h,fieldnames=list(targets[0]));w.writeheader();w.writerows(clean(targets))
used_events=[e for e in confirmed if e['source_row_key_NOT_canonical_event_id']in used]
context={e['source_row_key_NOT_canonical_event_id']:e for e in used_events};archives=[]
for new in used_events:
    prior=[e for e in confirmed if e['source_segment']==new['source_segment']and e['event_sign']==new['event_sign']and e['confirm_day']<new['confirm_day']]
    if not prior:continue
    old=prior[-1];context[old['source_row_key_NOT_canonical_event_id']]=old
    archives.append(dict(axis='short_low'if new['event_sign']==1 else'long_high',
                         original_old_anchor=old,new_confirmed_anchor=new,
                         old_anchor_path_archive_as_known_on_replacement=path(old,new['confirm_day']),
                         archived_at=new['confirm_at'],archive_is_not_a_trade_or_reset_on_CP=True))
save('CONFIRMED_ANCHORS_AND_PREVIOUS_EVENT_CONTEXT.json',sorted(context.values(),key=lambda e:e['confirm_day']))
save('REPLACED_ANCHOR_PATH_ARCHIVES.json',archives)
needed_start=min(e['pivot_day']for e in context.values())
save('ORIGINAL_PRICE_AND_CP_Z_CONTEXT.json',[
    dict(day=str(dt.date()),original_CP_input=clean(r.to_dict()),
         original_facts=clean(facts.loc[dt].to_dict()),
         original_CP_z=clean(z.loc[dt,'z']),original_receipt=bool(z.loc[dt,'receipt']))
    for dt,r in f.loc[needed_start:END].iterrows()])
save('SCOPE_AND_MISSING_FIELDS.json',dict(sid=SID,target_days=[t['day']for t in targets],
    no_future_event_after_END_used=True,original_events_columns=list(events),
    original_canonical_E0_event_id='NOT_EXPORTED; source row key is separately labelled and is not a fabricated canonical id',
    known_at='Original protocol CLOSE on confirmation row; vendor received_at not certified',
    short='Latest event+1 confirmed by current CLOSE, same source segment; path starts at known historical pivot once confirmation is available',
    long='Latest event-1 confirmed by current CLOSE, same source segment; path starts at known historical pivot once confirmation is available',
    updates='Replace only that high/low axis on a new original confirmed pivot. Old defining segment archived as of its replacement confirmation; original CP receipts/down/SEEK do not clear these paths.',
    sigma='Frozen separately from saved CP z at each pivot CONFIRMATION day, not pivot day and not original local CP frozen scale. Normalized values descriptive, no gate.',
    Jan25_pivot_rule='Jan25 high is confirmed only Jan26 and therefore is not available in this output ending Jan25.',
    source_event_prices_vs_input_pivot_closes_checked=True,new_E0_or_CP_or_G_calculation_calls=0,
    new_account=0,new_order=0,new_backtest=0,new_threshold=0,new_funding_or_return=0))
save('SOURCE_SHA256.json',[dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest())for p in[MANIFEST,ip,zp,fp,ep,Path(__file__)]])
print(json.dumps(clean([dict(day=t['day'],A_s=t['A_s'],L_s=t['L_s'],ER_s=t['ER_s'],DD_s=t['DD_s'],A_l=t['A_l'],L_l=t['L_l'],ER_l=t['ER_l'],DD_l=t['DD_l'])for t in targets]),ensure_ascii=False))
