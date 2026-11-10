"""Saved lambda0 substitution + original-field joins and actual-r path counts only."""
from pathlib import Path
import csv,hashlib,json,math

OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[1]
LAMBDA=ROOT/'cp_monotone_path_v1/yingxin/ALL30_AXIS_LAMBDA_VALUES_AND_DECOMPOSITION.json'
PATHS=ROOT/'cp_continuous_weight_v1/yingxin/EXACT_ANCHOR_AND_PATH_CALCULATION_RECORDS.json'
CP=ROOT/'cp_formula_redesign_v1/yingxin/ORIGINAL_21_DAILY_RAW_RECORDS.json'
ACTUAL=ROOT/'mobile_allocation_audit_v1/yingxin/EXACT_SELECTED_ORIGINAL_LAYERS.json'
data=json.loads(LAMBDA.read_text());paths={r['day']:r for r in json.loads(PATHS.read_text())}
orig={r['day']:r for r in json.loads(CP.read_text())}
old=[r for r in data if r['lambda_sensitivity']==0]
def save(n,x):(OUT/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
rows=[];negative_records=[]
for day in sorted(paths):
    s=next(r for r in old if r['day']==day and r['axis']=='s')
    l=next(r for r in old if r['day']==day and r['axis']=='l')
    assert s['Q_lambda']==s['A']/(math.sqrt(5)*s['sigma'])
    assert l['Q_lambda']==l['A']/(math.sqrt(5)*l['sigma'])
    r=orig[day];f=r['original_stock_facts'];c=r['original_CP1_output'];e=r['original_native_event']
    canonical=r['original_canonical_receipt']
    high=paths[day]['scales']['l']['current_anchor'];low=paths[day]['scales']['s']['current_anchor']
    # Count real saved daily returns after high pivot, not from A/L aggregates.
    rs=[dict(day=d,original_CP_cached_r=orig[d]['original_CP1_output']['r'])for d in sorted(orig)if high['pivot_day']<d<=day]
    assert rs and rs[0]['day']=='2022-01-17'
    signs=[1 if x['original_CP_cached_r']>0 else-1 for x in rs if x['original_CP_cached_r']!=0]
    down=sum(x['original_CP_cached_r']<0 for x in rs)
    turns=sum(a!=b for a,b in zip(signs[:-1],signs[1:]))
    Ddown=math.fsum(-x['original_CP_cached_r']for x in rs if x['original_CP_cached_r']<0)
    DfromAL=(l['L']-l['A'])/2
    assert abs(Ddown-DfromAL)<1e-14
    negative_records.append(dict(day=day,long_anchor=high,actual_saved_r_after_high_pivot=rs,
                                 negative_log_path_sum=Ddown,n_down=down,n_turn_zero_returns_removed=turns,
                                 aggregate_identity_from_A_L=DfromAL,identity_residual=Ddown-DfromAL))
    row=dict(day=day,sid='000620.SZ',original_CLOSE=day+' 15:10:00+08:00',
             close_a=f['close'],close_raw=f['raw_close'],factor=f['factor'],
             R_low_displacement_normalized=s['Q_lambda'],B_prior_confirmed_high_displacement_normalized=l['Q_lambda'],
             low_confirm_at=low['confirm_at'],low_pivot_day=low['pivot_day'],low_pivot_a=low['pivot_price_a'],sigma_low=s['sigma'],
             low_source_row_key_NOT_canonical_event_ID=low['source_row_key_NOT_canonical_event_id'],
             prior_high_confirm_at=high['confirm_at'],prior_high_pivot_day=high['pivot_day'],prior_high_pivot_a=high['pivot_price_a'],sigma_high=l['sigma'],
             prior_high_source_row_key_NOT_canonical_event_ID=high['source_row_key_NOT_canonical_event_id'],
             prior_high_definition='Last original event-1 already confirmed by CLOSE; all target high confirmations strictly precede today, so < and <= agree here',
             A_short=s['A'],L_short=s['L'],A_long=l['A'],L_long=l['L'],
             D_down_long=(l['L']-l['A'])/2,n_down_long=down,n_turn_long_excluding_zero=turns,
             original_CP_receipt=c['receipt'],original_CP_phase=c['phase'],original_CP_reset_reason=c['reset_reason'],
             original_CP_frontier_log=c['frontier'],original_CP_frontier_a=math.exp(c['frontier'])if c['frontier']is not None else None,
             original_CP_delta_frontier=c['delta_frontier'],original_CP_new_frontier=c['delta_frontier']>0,
             original_E0_event=e['event'],original_E0_pivot_day=e['confirmed_pivot_date'],original_E0_pivot_a=e['confirmed_pivot_price'],
             original_E0_target=f['e0_target'],original_E0_native_entered=e['entered'],original_E0_native_exited=e['exited'],
             original_I_target=f['i_target'],original_I_buy=f['i_buy'],original_I_floor_a=f['i_floor'],
             original_I_floor_raw=f['i_floor']/f['factor']if f['i_floor']is not None else None,
             original_canonical_CP_receipt_ID=canonical['receipt_id']if isinstance(canonical,dict)else None,
             original_E0_episode_ID_from_canonical_CP=canonical['original_E0_episode_id']if isinstance(canonical,dict)else 'NO_CP_CANONICAL_THIS_DAY',
             original_CP_e0_valid_means_I_target=c['e0_valid'],
             original_live_I_watch_epochs=json.dumps(sorted({json.dumps(l0['saved_native_layer']['epoch'])for l0 in r['original_live_layers']})),
             original_CORE_qty=sum(l0['qty']for l0 in r['original_live_layers']if l0['role']=='core'),
             original_MOBILE_qty=sum(l0['qty']for l0 in r['original_live_layers']if l0['role']=='mobile'),
             numeric_R_at_least_1_not_new_permission=s['Q_lambda']>=1,
             numeric_B_nonnegative_not_new_permission=l['Q_lambda']>=0,
             loss_and_turn_fields_are_separate_not_subtracted_from_R_B=True)
    rows.append(row)
save('JAN19_25_PARALLEL_R_B_AND_ORIGINAL_FIELDS.json',rows)
with(OUT/'JAN19_25_PARALLEL_R_B_AND_ORIGINAL_FIELDS.csv').open('w',newline='')as h:
    w=csv.DictWriter(h,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
save('LONG_ANCHOR_DOWN_PATH_AND_TURNS_FROM_ACTUAL_R.json',negative_records)
save('REVERSAL_VS_DOMAIN_ORIGINAL_CONTEXT.json',[
    dict(day=d,original_E0_event=orig[d]['original_native_event']['event'],
         original_E0_pivot_day=orig[d]['original_native_event']['confirmed_pivot_date'],
         original_E0_target=orig[d]['original_stock_facts']['e0_target'],
         original_I_target=orig[d]['original_stock_facts']['i_target'],
         original_CP_e0_valid=orig[d]['original_CP1_output']['e0_valid'],
         original_CP_reset_reason=orig[d]['original_CP1_output']['reset_reason'])
    for d in ['2022-01-17','2022-01-20','2022-01-26','2022-02-07']])
actual=json.loads(ACTUAL.read_text())
layer122=next(x for x in actual if x['native']['id']==122)
save('JAN24_POSITIVE_B_LATER_ORIGINAL_FAILURE_LABEL_ONLY.json',dict(
    signal_day_values=next(r for r in rows if r['day']=='2022-01-24'),
    original_layer122=layer122,
    meaning='Jan24 B already nonnegative before later original layer122 loss; raw fields do not identify that failure',
    boundary='Original path label only. No claim new rule would receive same fill/quantity/resources, no candidate PnL calculated.'))
save('SCOPE.json',dict(
    formulas='R=A_short/(sqrt5*sigma_low); B=A_long/(sqrt5*sigma_high), exactly fixed lambda0 short/long',
    days=[r['day']for r in rows],
    high_definition_boundary='No target day has a high confirmation, so prior(<t) and latest-known(<=t) coincide. Lower-high/current-high handling beyond this window remains a rule-definition issue, not resolved by this table.',
    downside='D_down=(L_long-A_long)/2 also independently summed from actual negative cached r; n_down and n_turn use full saved daily r, not A/L inference',
    original_event_minus1='Original confirmed high turning event; not equivalent to original E0_target or I_target invalidation. Source/I-domain invalidation is separate.',
    candidate_status='Numeric predicates and logical review only; no one-use evidence consumption, new maturity/repair state or permit implemented',
    new_CP_E0_G_model_calls=0,new_account=0,new_order=0,new_backtest=0,new_funding_or_return=0))
save('SOURCE_SHA256.json',[dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest())for p in[LAMBDA,PATHS,CP,ACTUAL,Path(__file__)]])
print(json.dumps([{k:r[k]for k in ['day','R_low_displacement_normalized','B_prior_confirmed_high_displacement_normalized','D_down_long','n_down_long','n_turn_long_excluding_zero','original_CP_new_frontier','original_E0_event','original_I_target']}for r in rows],ensure_ascii=False))
