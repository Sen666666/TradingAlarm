"""Read saved path JSON and substitute fixed lambda0/.5/1; no model/state/account."""
from pathlib import Path
import csv,hashlib,json,math

OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[1]
SOURCE=ROOT/'cp_continuous_weight_v1/yingxin/EXACT_ANCHOR_AND_PATH_CALCULATION_RECORDS.json'
LINK=ROOT/'cp_continuous_weight_v1/yingxin/JAN19_25_Q_AND_ANCHOR_DECOMPOSITION.json'
record=json.loads(SOURCE.read_text());links={r['day']:r for r in json.loads(LINK.read_text())}
LAMBDAS=[0.,.5,1.]
def save(n,x):(OUT/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def csvsave(n,x):
    with(OUT/n).open('w',newline='')as h:
        w=csv.DictWriter(h,fieldnames=list(x[0]));w.writeheader();w.writerows(x)
def measure(m,lam):
    A,L,sigma=m['A'],m['L'],m['sigma'];V=L-abs(A);N=A-lam*V
    assert V>=-1e-14
    return dict(A=A,L=L,excess_path_V=V,numerator_N=N,sigma=sigma,normalizer=math.sqrt(5)*sigma,
                Q_lambda=N/(math.sqrt(5)*sigma))
rows=[];wide=[];max_residual=0.
for r in record:
    link=links[r['day']]
    w=dict(day=r['day'],close_raw=link['close_raw'],original_E0_event=link['original_E0_event'],
           original_CP_receipt=link['original_CP_receipt'])
    for axis in ['s','l']:
        v=r['scales'][axis]
        for lam in LAMBDAS:
            t=measure(v['current_metrics'],lam);y=measure(v['yesterday_metrics'],lam)
            o=measure(v['today_under_yesterday_anchor_and_sigma'],lam)
            raw=t['Q_lambda']-y['Q_lambda'];comp=o['Q_lambda']-y['Q_lambda'];rebase=t['Q_lambda']-o['Q_lambda']
            residual=raw-comp-rebase;max_residual=max(max_residual,abs(residual));assert abs(residual)<1e-13
            q=dict(day=r['day'],previous_observation_day=r['previous_observation_day'],sid=link['sid'],axis=axis,lambda_sensitivity=lam,
                   current_anchor_confirm_day=v['current_anchor']['confirm_day'],current_anchor_pivot_day=v['current_anchor']['pivot_day'],
                   yesterday_anchor_confirm_day=v['yesterday_anchor']['confirm_day'],yesterday_anchor_pivot_day=v['yesterday_anchor']['pivot_day'],
                   original_E0_event=link['original_E0_event'],original_CP_receipt=link['original_CP_receipt'],
                   **t,Q_yesterday=y['Q_lambda'],Q_today_with_yesterday_anchor_and_sigma=o['Q_lambda'],
                   delta_Q_raw=raw,delta_Q_comparable=comp,Q_rebase_component=rebase,
                   raw_minus_comparable_minus_rebase=residual,
                   anchor_changed_today=link['anchor_changed_today_'+axis],
                   no_threshold_funding_or_return_decision=True)
            rows.append(q)
            suffix=axis+'_lambda_'+str(lam).replace('.','p')
            for key,value in [('Q',t['Q_lambda']),('delta_raw',raw),('delta_comparable',comp),('rebase',rebase)]:w[key+'_'+suffix]=value
    wide.append(w)
assert len(rows)==30 and len(wide)==5
csvsave('ALL30_AXIS_LAMBDA_VALUES_AND_DECOMPOSITION.csv',rows)
save('ALL30_AXIS_LAMBDA_VALUES_AND_DECOMPOSITION.json',rows)
csvsave('FIVE_DAYS_SIX_Q_AND_DELTA_WIDE.csv',wide)
save('FIVE_DAYS_SIX_Q_AND_DELTA_WIDE.json',wide)
save('FROZEN_SUBSTITUTION_SCOPE.json',dict(
    formula='Q_lambda=(A-lambda*(L-abs(A)))/(sqrt5*confirmation-day frozen CP z)',
    fixed_lambdas=LAMBDAS,lambda_choice='Sensitivity only; no best lambda selected',
    raw='today current-anchor Qlambda minus yesterday original-anchor Qlambda',
    comparable='today under yesterday anchor and yesterday frozen sigma minus yesterday Qlambda',
    rebase='today new-anchor Qlambda minus today under yesterday anchor and sigma',
    identity_max_abs_residual=max_residual,
    predecessor='Original Jan18 metrics already stored in source; Jan19 first output includes its original previous observation',
    monotonicity_note='For fixed anchor/sigma, while A<0 and a positive return r does not cross A0, delta numerator=(1-2lambda)*r. lambda=.5 is flat; lambda1 decreases on that rebound. Name does not prove every sensitivity is monotone.',
    after_reclaim_note='For A>0 and further up return, L-A remains unchanged and delta numerator equals r for each fixed lambda',
    no_future_price_or_outcome_used=True,no_post_Jan25_data_used=True,
    new_CP_or_G_state_machine=0,new_feature=0,new_account=0,new_order=0,new_backtest=0,new_profit_or_funding=0,
    softplus_calls=0,Q_ge_1_gate_calls=0))
save('SOURCE_SHA256.json',[dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest())for p in[SOURCE,LINK,Path(__file__)]])
print(json.dumps(wide,ensure_ascii=False))
