"""Three parent-specified lambda sensitivities on saved paths; no new state."""
from pathlib import Path
import csv,hashlib,json,math
OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[1];H={}
def read(path):
 p=Path(path).resolve();H[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();return json.loads(p.read_text())
def save(n,v):(OUT/n).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
def score(path,lam):
 A,L=path['A'],path['L'];sigma=path['anchor']['sigma_CP_z_at_confirm']
 return(A-lam*(L-abs(A)))/(math.sqrt(5)*sigma)
def main():
 H[str(Path(__file__).resolve())]=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
 paths=read(ROOT/'cp_continuous_weight_v1/hytera/FULL_OLD_AND_NEW_ANCHOR_PATH_DETAILS.json')
 daily=read(ROOT/'cp_continuous_weight_v1/hytera/SEP23_OCT21_CONTINUOUS_Q_AND_DECOMPOSITION.json')
 meta={r['date']:r for r in daily};rows=[];rebase=[]
 for d in paths:
  m=meta[d['date']]
  for lam in[0.,.5,1.]:
   r={k:m[k]for k in['sid','date','previous_original_observation','known_at_native_protocol','raw_close','continuous_close','log_price_change','original_CP_receipt','original_CP_reset_reason','original_E0_event','original_E0_target','original_I_target']}
   r.update(lambda_value=lam,formula='(A-lambda*(L-abs(A)))/(sqrt5*frozen_sigma)',new_weight_or_permission_state=False)
   for axis in['s','l']:
    v=d['axes'][axis];now=v['today_on_current_confirmed_anchor'];old=v['today_on_yesterday_anchor_and_frozen_sigma'];y=v['yesterday_active_anchor_path']
    qn,qold,qy=score(now,lam),score(old,lam),score(y,lam)
    raw=qn-qy;market=qold-qy;rb=qn-qold;resid=raw-market-rb
    assert abs(resid)<1e-12
    for k in['A','L','ER','DD']:r[k+'_'+axis]=now[k]
    r['excess_path_'+axis]=now['L']-abs(now['A'])
    for key,val in {'Q':qn,'Q_yesterday':qy,'Q_today_oldanchor_sigma':qold,'raw_dQ':raw,'market_dQ':market,'rebase_dQ':rb,'bridge_residual':resid}.items():r[key+'_'+axis]=val
    for key in['anchor_changed','pivot_day','confirm_day','pivot_price_a','sigma','previous_pivot_day','previous_confirm_day','previous_pivot_price_a','previous_sigma','new_confirmed_anchor_kind']:
     r[key+'_'+axis]=m[key+'_'+axis]
    r['oldanchor_A_yesterday_'+axis]=y['A'];r['oldanchor_A_today_'+axis]=old['A']
    r['oldanchor_L_yesterday_'+axis]=y['L'];r['oldanchor_L_today_'+axis]=old['L']
    r['recovery_stays_negative_A_same_anchor_'+axis]=bool(old['A']>y['A']and old['A']<0 and y['A']<0)
    r['recovery_crosses_zero_A_same_anchor_'+axis]=bool(old['A']>y['A']and y['A']<0<=old['A'])
   rows.append(r)
   if r['anchor_changed_s']or r['anchor_changed_l']:rebase.append(r)
 assert len(rows)==48
 save('ALL16_DAYS_THREE_LAMBDAS_Q_AND_DELTAS.json',rows)
 with(OUT/'ALL16_DAYS_THREE_LAMBDAS_Q_AND_DELTAS.csv').open('w',newline='')as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 save('ANCHOR_CONFIRMATION_REBASE_DAYS.json',rebase)
 save('KEY_0930_1011.json',[r for r in rows if r['date']in['2024-09-30','2024-10-11']])
 negative_recoveries=[r for r in rows if r['lambda_value']==0 and(r['recovery_stays_negative_A_same_anchor_s']or r['recovery_stays_negative_A_same_anchor_l'])]
 cross=[r for r in rows if r['lambda_value']==0 and(r['recovery_crosses_zero_A_same_anchor_s']or r['recovery_crosses_zero_A_same_anchor_l'])]
 save('RECOVERY_SIGN_CASES_AND_SCOPE.json',dict(
  fixed_formula='Qlambda=(A-lambda*(L-abs(A)))/(sqrt5*confirmation_day_frozen_sigma)',
  lambda_values=[0,.5,1],selection_or_optimization=False,original_observations=16,sensitivity_rows=48,
  same_anchor_negative_to_still_negative_price_recovery_observations=negative_recoveries,
  same_anchor_negative_to_nonnegative_price_recovery_observations=cross,
  analytic_fixed_anchor_negative_A_recovery='IfA<0 throughout a positive log stepd, deltaQlambda=(1-2lambda)*d/(sqrt5*sigma). Lambda.5 stagnates;lambda1 decreases. This is algebra, not an invented observed day.',
  analytic_fixed_anchor_positive_A_rise='IfA>0 throughout a positive log stepd,excess path L-absA is unchanged and everylambda deltaQ=d/(sqrt5*sigma).',
  observed_boundary='This16-day window has no negative-A-to-still-negative-A positive recovery observation;9/30and10/11 long recoveries crosszero. Do not label them as the pure stagnation case.',
  rebase_boundary='Changing pivot/sigma can erase accumulated excess path; raw delta is separated from the old-anchor market delta. Old path retained in source details, never counted as market progress.',
  floating_point_policy='LiteralL-absA copied, noepsilon floor or silent clip; tiny roundoff is not a new path/weight rule.',
  maximum_delta_bridge_residual=max(abs(r['bridge_residual_'+a])for r in rows for a in['s','l']),
  new_G_or_CP_states=0,new_accounts=0,new_returns=0,new_weight_coefficients=0,new_thresholds=0))
 save('SOURCE_SHA256.json',H)
if __name__=='__main__':main()
