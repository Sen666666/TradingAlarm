"""Continuous saved-pivot Q diagnostics only, no weights/threshold/state/account."""
from pathlib import Path
import csv,hashlib,json,math
import pandas as pd
OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[1];H={}
def bind(p):
 p=Path(p).resolve();H[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();return p
def read(p):return json.loads(bind(p).read_text())
def save(n,x):(OUT/n).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def score(path):
 if path is None or path['ER']is None:return None
 sigma=path['anchor']['sigma_CP_z_at_confirm']
 if sigma is None or sigma<=0:return None
 return path['A']*abs(path['ER'])/(math.sqrt(5)*sigma)
def main():
 bind(__file__)
 rootrows=read(ROOT/'cp_two_scale_v1/hytera/ALL43_CONFIRMED_E0_TWO_SCALE_PATHS.json')
 bind(ROOT/'cp_two_scale_v1/calculate_point_scores.py')
 m=next(r for r in read('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')if r['symbol']=='002583.SZ')
 p=bind(m['refs']['CP1_input']);assert H[str(p)]==m['output_sha256'][str(p)]
 f=pd.read_parquet(p).loc[:'2024-10-21'];days=list(f.index);idx={str(d.date()):i for i,d in enumerate(days)};C=list(map(float,f.close));seg=list(f.segment_id)
 byday={r['date']:r for r in rootrows}
 def describe(anchor,i):
  j=idx[anchor['pivot_day']];assert j<=i
  assert all(int(seg[k])==anchor['source_segment']for k in range(j,i+1))
  A=math.log(C[i]/anchor['pivot_price_a_saved']);L=math.fsum(abs(math.log(C[k]/C[k-1]))for k in range(j+1,i+1))
  ER=A/L if L>0 else None;DD=math.log(max(C[j:i+1])/C[i])
  return dict(A=A,L=L,ER=ER,DD=DD,anchor=anchor)
 rows=[];full=[]
 for r in rootrows:
  d=r['date']
  if not'2024-09-23'<=d<='2024-10-21':continue
  i=idx[d];prev=str(days[i-1].date());pr=byday.get(prev)
  q=dict(sid='002583.SZ',date=d,previous_original_observation=prev,
   known_at_native_protocol=r['known_at_native_protocol'],raw_close=r['raw_close'],continuous_close=r['continuous_close'],
   log_price_change=math.log(C[i]/C[i-1]),original_CP_receipt=r['original_CP_receipt'],
   original_CP_reset_reason=r['original_CP_reset_reason'],original_E0_event=r['original_E0_event'],
   original_E0_target=r['original_E0_target'],original_I_target=r['original_I_target'],new_weight_or_permission_event=False)
  detail=dict(date=d,previous_original_observation=prev,axes={})
  for label,key in [('s','short'),('l','long')]:
   current=r[key];ca=current['anchor']
   if pr is None:
    #9/20 is before the requested output window. Both current anchors were
    #already confirmed by9/20, so that historical row needs no future anchor.
    assert ca['confirm_day']<=prev
    old_anchor=ca;previous=describe(old_anchor,i-1)
   else:old_anchor=pr[key]['anchor'];previous=pr[key]
   comparable=describe(old_anchor,i)
   nowq=score(current);prevq=score(previous);oldq=score(comparable)
   assert None not in [nowq,prevq,oldq]
   rawdelta=nowq-prevq;market=oldq-prevq;rebase=nowq-oldq
   assert math.isclose(rawdelta,market+rebase,rel_tol=1e-12,abs_tol=1e-12)
   ident=lambda a:(a['pivot_day'],a['confirm_day'],a['pivot_price_a_saved'],a['sigma_CP_z_at_confirm'],a['source_segment'])
   changed=ident(ca)!=ident(old_anchor)
   if not changed:assert abs(rebase)<1e-12
   for k in ['A','L','ER','DD']:q[k+'_'+label]=current[k]
   q.update({
    'Q_'+label:nowq,'Q_'+label+'_yesterday':prevq,
    'Q_'+label+'_today_old_anchor_and_sigma':oldq,
    'raw_dQ_'+label:rawdelta,'market_dQ_'+label:market,'rebase_dQ_'+label:rebase,
    'decomposition_residual_'+label:rawdelta-market-rebase,
    'anchor_changed_'+label:changed,
    'pivot_day_'+label:ca['pivot_day'],'confirm_day_'+label:ca['confirm_day'],
    'pivot_price_a_'+label:ca['pivot_price_a_saved'],
    'pivot_raw_in_current_units_'+label:current['pivot_a_div_current_factor'],
    'sigma_'+label:ca['sigma_CP_z_at_confirm'],
    'previous_pivot_day_'+label:old_anchor['pivot_day'],'previous_confirm_day_'+label:old_anchor['confirm_day'],
    'previous_pivot_price_a_'+label:old_anchor['pivot_price_a_saved'],
    'previous_sigma_'+label:old_anchor['sigma_CP_z_at_confirm'],
    'new_confirmed_anchor_kind_'+label:('E0_LOW_CONFIRMED'if label=='s'else'E0_HIGH_CONFIRMED')if changed else None,
   })
   detail['axes'][label]=dict(yesterday_active_anchor_path=previous,today_on_yesterday_anchor_and_frozen_sigma=comparable,today_on_current_confirmed_anchor=current,
    Q_yesterday=prevq,Q_today_oldanchor=oldq,Q_today_current=nowq,raw_delta=rawdelta,market_delta=market,rebase_delta=rebase,
    anchor_change_is_not_market_price_decline=changed)
  rows.append(q);full.append(detail)
 assert len(rows)==16
 save('SEP23_OCT21_CONTINUOUS_Q_AND_DECOMPOSITION.json',rows)
 with(OUT/'SEP23_OCT21_CONTINUOUS_Q_AND_DECOMPOSITION.csv').open('w',newline='')as g:
  w=csv.DictWriter(g,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 save('FULL_OLD_AND_NEW_ANCHOR_PATH_DETAILS.json',full)
 save('REBASE_CONFIRMATION_DAYS.json',[r for r in rows if r['anchor_changed_s']or r['anchor_changed_l']])
 save('SCOPE_AND_NUMERIC_DEFINITION.json',dict(window=['2024-09-23','2024-10-21'],observations=16,
  G='A*abs(ER)',Q='G/(sqrt5*confirmation-day frozen originalCP z)',
  raw_delta='Q_current_anchor(t)-Q_yesterday_anchor(t-1)',
  market_delta='Q_yesterday_anchor_and_sigma_extended_to_t-Q_yesterday_anchor(t-1)',
  rebase_delta='Q_current_anchor_and_sigma(t)-Q_yesterday_anchor_and_sigma_extended_to_t',
  first_day_previous_observation='2024-09-20; both saved anchors had already been confirmed, not9/23 backfill',
  boundary='No Q>=1 hard gate, no weight mapping/coefficient, no new receipt/permission/CP state, no cash/account/return.',
  numeric_formula_reference=str((ROOT/'cp_two_scale_v1/calculate_point_scores.py').resolve()),
  earlier_permission_hypothesis_not_applied=True,new_accounts=0,new_backtests=0,new_weight_coefficients=0))
 save('SOURCE_SHA256.json',H)
if __name__=='__main__':main()
