"""Saved lambda0 R/B and original frontier audit; no new permission state."""
from pathlib import Path
import csv,hashlib,json,math
import pandas as pd
OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[1];H={}
def bind(p):
 p=Path(p).resolve();H[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();return p
def read(p):return json.loads(bind(p).read_text())
def save(n,x):(OUT/n).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def main():
 bind(__file__)
 scores=[r for r in read(ROOT/'cp_monotone_path_v1/hytera/ALL16_DAYS_THREE_LAMBDAS_Q_AND_DELTAS.json')if r['lambda_value']==0]
 cps={r['date']:r for r in read(ROOT/'cp_formula_redesign_v1/hytera_924/002583.SZ_ORIGINAL_CP_DAILY.json')}
 pivots={r['date']:r for r in read(ROOT/'cp_two_scale_v1/hytera/ALL43_CONFIRMED_E0_TWO_SCALE_PATHS.json')}
 sm=next(r for r in read('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')if r['symbol']=='002583.SZ')
 frames={}
 for key in['CP1_input','CP1']:
  p=bind(sm['refs'][key]);assert H[str(p)]==sm['output_sha256'][str(p)];frames[key]=pd.read_parquet(p).loc[:'2024-10-21']
 f=frames['CP1_input'];cp=frames['CP1'];dates=list(f.index);ix={str(t.date()):i for i,t in enumerate(dates)}
 rows=[];vectors=[]
 for s in scores:
  d=s['date'];c=cps[d];p=pivots[d];a=p['long']['anchor'];j=ix[a['pivot_day']];i=ix[d]
  # Counts come from original cached r, not inferred from A/L. Exact zero is skipped.
  original_r=[float(cp.loc[t,'r'])for t in dates[j+1:i+1]]
  assert all(math.isfinite(v)for v in original_r)
  signs=[1 if v>0 else-1 for v in original_r if v!=0]
  n_down=sum(v<0 for v in original_r);n_turn=sum(x!=y for x,y in zip(signs,signs[1:]))
  dd=(s['L_l']-s['A_l'])/2
  assert math.isclose(dd,math.fsum(-v for v in original_r if v<0),abs_tol=1e-12)
  frontier=c['delta_frontier']>0;R=s['Q_s'];B=s['Q_l'];rawtrial=bool(frontier and R>=1);rawmature=bool(rawtrial and B>=0)
  r=dict(sid='002583.SZ',date=d,raw_close=s['raw_close'],R=R,B=B,
   R_definition='lnC_over_last_confirmed_low/(sqrt5*sigma_low_at_confirmation)',
   B_definition='lnC_over_latest_high_confirmed_by_this_CLOSE/(sqrt5*sigma_high_at_confirmation)',
   B_on_yesterday_confirmed_high_reference=s['Q_today_oldanchor_sigma_l'],
   sigma_low=s['sigma_s'],sigma_high=s['sigma_l'],low_pivot_day=s['pivot_day_s'],low_confirm_day=s['confirm_day_s'],high_pivot_day=s['pivot_day_l'],high_confirm_day=s['confirm_day_l'],
   original_CP_new_frontier=frontier,original_CP_delta_frontier=c['delta_frontier'],original_CP_receipt=c['receipt'],original_CP_phase=c['phase'],original_CP_reset_reason=c['reset_reason'],
   original_E0_event=s['original_E0_event'],original_E0_target=s['original_E0_target'],original_I_target=s['original_I_target'],
   static_frontier_and_R_ge1=rawtrial,static_frontier_R_ge1_and_B_ge0=rawmature,
   static_condition_true_does_not_emit_new_permission=True,once_consumption_identity='NOT_DEFINED_NOT_SIMULATED',
   D_down_l=dd,n_down_l=n_down,n_turn_l=n_turn,return_count=len(original_r),zero_return_count=sum(v==0 for v in original_r),
   down_and_chop_have_no_eligibility_mapping=True,
   event_minus1_is_full_domain_off=bool(s['original_E0_event']==-1 and not s['original_E0_target']),
   latest_high_includes_today_confirmation_causally=True,
   raw_dR=s['raw_dQ_s'],market_dR=s['market_dQ_s'],rebase_dR=s['rebase_dQ_s'],raw_dB=s['raw_dQ_l'],market_dB=s['market_dQ_l'],rebase_dB=s['rebase_dQ_l'])
  rows.append(r);vectors.append(dict(date=d,long_pivot_day=a['pivot_day'],long_confirm_day=a['confirm_day'],
   original_cached_return_rows=[dict(date=str(t.date()),r=v)for t,v in zip(dates[j+1:i+1],original_r)],D_down_from_A_L=dd,sum_original_negative_r_magnitude=math.fsum(-v for v in original_r if v<0),n_down=n_down,n_turn_ignoring_exact_zero=n_turn))
 save('ALL16_DAILY_R_B_AND_ORIGINAL_EVENTS.json',rows)
 with(OUT/'ALL16_DAILY_R_B_AND_ORIGINAL_EVENTS.csv').open('w',newline='')as g:
  w=csv.DictWriter(g,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 save('ORIGINAL_RETURN_VECTORS_FOR_DOWN_TURN_COUNTS.json',vectors)
 loss_rebases=[]
 for s in scores:
  if not s['anchor_changed_l']:continue
  d=s['date'];j=ix[s['previous_pivot_day_l']];i=ix[d]
  old_r=[float(cp.loc[t,'r'])for t in dates[j+1:i+1]]
  signs=[1 if v>0 else-1 for v in old_r if v!=0]
  now=next(r for r in rows if r['date']==d)
  loss_rebases.append(dict(date=d,original_high_confirmation=pivots[d]['original_E0_event'],
   prior_high_pivot_day=s['previous_pivot_day_l'],prior_high_confirm_day=s['previous_confirm_day_l'],
   old_anchor_path_extended_to_today=dict(A=s['oldanchor_A_today_l'],L=s['oldanchor_L_today_l'],D_down=(s['oldanchor_L_today_l']-s['oldanchor_A_today_l'])/2,n_down=sum(v<0 for v in old_r),n_turn=sum(a!=b for a,b in zip(signs,signs[1:]))),
   current_new_high_pivot_day=s['pivot_day_l'],current_new_high_confirm_day=s['confirm_day_l'],
   current_rebased_path=dict(A=s['A_l'],L=s['L_l'],D_down=now['D_down_l'],n_down=now['n_down_l'],n_turn=now['n_turn_l']),
   rebase_is_not_market_loss_erasure=True))
 save('LOSS_AND_TURN_REBASE_ARCHIVE.json',loss_rebases)
 # Finite warm-up boundary, not a new first-use/consumption simulation.
 a0=pivots['2024-09-23'];warm=[]
 for day in['2024-09-19','2024-09-20']:
  t=pd.Timestamp(day);close=float(f.loc[t,'close']);c=cp.loc[t];v={}
  for label,key in[('R','short'),('B','long')]:
   a=a0[key]['anchor'];assert a['confirm_day']<=day
   v[label]=math.log(close/a['pivot_price_a_saved'])/(math.sqrt(5)*a['sigma_CP_z_at_confirm'])
  warm.append(dict(date=day,continuous_close=close,**v,original_CP_delta_frontier=float(c.delta_frontier),original_CP_receipt=bool(c.receipt),
   static_frontier_and_R_ge1=bool(c.delta_frontier>0 and v['R']>=1),low_identity=dict(pivot_day=a0['short']['anchor']['pivot_day'],confirm_day=a0['short']['anchor']['confirm_day']),
   does_not_prove_actual_consumption_or_order=True))
 save('WARM_WINDOW_FIRST_USE_WARNING.json',warm)
 save('STATIC_CONDITION_COVERAGE_NOT_NEW_TRADES.json',dict(
  original_observations=16,original_CP_frontier_days=sum(r['original_CP_new_frontier']for r in rows),original_CP_receipt_days=sum(r['original_CP_receipt']for r in rows),
  static_trial_condition_days=sum(r['static_frontier_and_R_ge1']for r in rows),static_trial_and_B_nonnegative_days=sum(r['static_frontier_R_ge1_and_B_ge0']for r in rows),
  frontier_R_true_but_original_receipt_false=[r for r in rows if r['static_frontier_and_R_ge1']and not r['original_CP_receipt']],
  B_negative_days=[r for r in rows if r['B']<0],
  original_local_high_confirmations_with_domain_still_on=[r for r in rows if r['original_E0_event']==-1 and r['original_E0_target']and r['original_I_target']],
  full_E0_or_I_domain_off_observations=[r for r in rows if not r['original_E0_target']or not r['original_I_target']],
  state_boundary='Once, mature increase and revoke are not simulated. Same-day statically true conditions are not actual grants, trades or risk budgets.',
  prior_high_boundary='MainB uses the latest original high confirmed by currentCLOSE, including today if event-1; alternative on yesterday high is separately recorded. Neither uses unconfirmed forming highs.',
  new_CP_G_or_permission_states=0,new_accounts=0,new_returns=0,new_features=0))
 save('SOURCE_SHA256.json',H)
if __name__=='__main__':main()
