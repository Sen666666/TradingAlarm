"""Pure saved-JSON G/Q arithmetic and anchor-change decomposition; no policy gates."""
from pathlib import Path
import csv,hashlib,json,math

OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[1]
CONTEXT=ROOT/'cp_two_scale_v1/yingxin/ORIGINAL_PRICE_AND_CP_Z_CONTEXT.json'
EVENTS=ROOT/'cp_two_scale_v1/yingxin/CONFIRMED_ANCHORS_AND_PREVIOUS_EVENT_CONTEXT.json'
ORIGINAL=ROOT/'cp_formula_redesign_v1/yingxin/ORIGINAL_21_DAILY_RAW_RECORDS.json'
FORMULA=ROOT/'cp_two_scale_v1/FROZEN_TWO_SCALE_PERMISSION_HYPOTHESIS.txt'
START='2022-01-19';END='2022-01-25';SID='000620.SZ'
context=json.loads(CONTEXT.read_text());by={r['day']:r for r in context};days=sorted(by)
events=json.loads(EVENTS.read_text());original={r['day']:r for r in json.loads(ORIGINAL.read_text())}
def save(n,x):(OUT/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def anchor_at(day,axis):
    sign=1 if axis=='s'else-1
    known=[r for r in events if r['event_sign']==sign and r['confirm_day']<=day and r['source_segment']==by[day]['original_CP_input']['segment_id']]
    assert known
    return max(known,key=lambda r:r['confirm_day'])
def measure(anchor,day):
    ds=[d for d in days if anchor['pivot_day']<=d<=day]
    assert ds and ds[0]==anchor['pivot_day']
    p=[math.log(by[d]['original_CP_input']['close'])for d in ds]
    assert all(by[d]['original_CP_input']['segment_id']==anchor['source_segment']for d in ds)
    A=p[-1]-math.log(anchor['pivot_price_a']);L=math.fsum(abs(b-a)for a,b in zip(p[:-1],p[1:]))
    ER=A/L if L else None;G=A*abs(ER)if ER is not None else None
    sigma=anchor['sigma_frozen_from_CP_z_at_confirm'];normalizer=math.sqrt(5)*sigma
    return dict(A=A,L=L,ER=ER,DD=max(p)-p[-1],G=G,sigma=sigma,normalizer=normalizer,Q=G/normalizer if G is not None else None,
                path_observations_after_pivot=len(ds)-1)
rows=[];raw=[]
for day in [d for d in days if START<=d<=END]:
    prev=days[days.index(day)-1];o=original[day]
    row=dict(sid=SID,day=day,original_CLOSE_clock=day+' 15:10:00+08:00',previous_observation_day=prev,
             close_a=by[day]['original_CP_input']['close'],close_raw=by[day]['original_facts']['raw_close'],
             original_CP_receipt=o['original_CP1_output']['receipt'],
             original_CP_reset_reason=o['original_CP1_output']['reset_reason'],
             original_E0_event=o['original_native_event']['event'],
             original_E0_pivot_day=o['original_native_event']['confirmed_pivot_date'],
             original_E0_pivot_price_a=o['original_native_event']['confirmed_pivot_price'])
    detail=dict(day=day,previous_observation_day=prev,scales={})
    for axis in ['s','l']:
        current=anchor_at(day,axis);yesterday=anchor_at(prev,axis)
        m=measure(current,day);p=measure(yesterday,prev);old_today=measure(yesterday,day)
        raw_delta=m['Q']-p['Q'];comparable=old_today['Q']-p['Q'];rebase=m['Q']-old_today['Q']
        residual=raw_delta-comparable-rebase
        assert abs(residual)<1e-14
        for k,v in m.items():row[k+'_'+axis]=v
        row.update({
            'anchor_confirm_day_'+axis:current['confirm_day'],
            'anchor_pivot_day_'+axis:current['pivot_day'],
            'anchor_price_a_'+axis:current['pivot_price_a'],
            'anchor_raw_current_units_'+axis:current['pivot_price_a']/by[day]['original_facts']['factor'],
            'anchor_source_row_key_'+axis:current['source_row_key_NOT_canonical_event_id'],
            'previous_anchor_confirm_day_'+axis:yesterday['confirm_day'],
            'previous_anchor_pivot_day_'+axis:yesterday['pivot_day'],
            'Q_yesterday_'+axis:p['Q'],
            'Q_old_anchor_at_today_'+axis:old_today['Q'],
            'delta_Q_raw_'+axis:raw_delta,
            'delta_Q_comparable_old_anchor_'+axis:comparable,
            'Q_rebase_component_'+axis:rebase,
            'raw_minus_comparable_minus_rebase_'+axis:residual,
            'anchor_changed_today_'+axis:current['source_row_key_NOT_canonical_event_id']!=yesterday['source_row_key_NOT_canonical_event_id']})
        detail['scales'][axis]=dict(current_anchor=current,yesterday_anchor=yesterday,
                                   current_metrics=m,yesterday_metrics=p,today_under_yesterday_anchor_and_sigma=old_today,
                                   delta_Q_raw=raw_delta,delta_Q_comparable=comparable,rebase_component=rebase,identity_residual=residual)
    rows.append(row);raw.append(detail)
assert len(rows)==5
save('JAN19_25_Q_AND_ANCHOR_DECOMPOSITION.json',rows)
with(OUT/'JAN19_25_Q_AND_ANCHOR_DECOMPOSITION.csv').open('w',newline='')as h:
    w=csv.DictWriter(h,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
save('EXACT_ANCHOR_AND_PATH_CALCULATION_RECORDS.json',raw)
save('SCOPE_AND_IDENTITY.json',dict(
    dates=[r['day']for r in rows],predecessor_used_for_Jan19=rows[0]['previous_observation_day'],
    math='G=A*abs(ER)=A*abs(A)/L; Q=G/(sqrt5*confirmation-day frozen CP z), signed, L0 undefined',
    raw='Q_t under current anchor - Q_yesterday under yesterday anchor',
    comparable='Recompute Q at today using yesterday pivot and yesterday frozen sigma, minus yesterday Q; include entire pivot-to-today path',
    rebase='Q_t under current anchor/sigma - Q_t under yesterday anchor/sigma; combines allowed anchor and sigma reference change, not new price evidence',
    identity='delta_raw=delta_comparable+rebase',
    old_permission_hard_gate_not_executed=True,no_Q_ge_1_permission=True,
    no_softplus_or_coefficient_selected=True,new_CP_or_G_state_machine=False,
    new_account=0,new_order=0,new_backtest=0,new_funding_or_return=0,
    sigma_and_source='Reuse saved confirmed E0 event context and full required original price path; no price feature recomputation',
    row_key_warning='Source row key is not a canonical original event ID; original events did not export such ID'))
save('SOURCE_SHA256.json',[dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest())for p in[CONTEXT,EVENTS,ORIGINAL,FORMULA,Path(__file__)]])
print(json.dumps([{k:r[k]for k in ['day','Q_s','Q_l','delta_Q_raw_s','delta_Q_comparable_old_anchor_s','Q_rebase_component_s','delta_Q_raw_l','delta_Q_comparable_old_anchor_l','Q_rebase_component_l','original_E0_event','original_CP_receipt']}for r in rows],ensure_ascii=False))
