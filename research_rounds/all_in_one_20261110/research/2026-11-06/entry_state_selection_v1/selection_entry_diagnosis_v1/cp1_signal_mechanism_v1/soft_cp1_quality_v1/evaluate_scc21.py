"""Frozen SCC21 case arithmetic. Never imports or reruns an original model/account."""
from pathlib import Path
import hashlib,json,math
from datetime import datetime,timezone
import numpy as np
import pandas as pd
O=Path(__file__).resolve().parent
B=O.parent
MANIFEST=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')
LAM=20/21
ALPHA=1/21
CASES=[
 ('002385.SZ','2022-03-04','primary_failure'),
 ('300182.SZ','2022-01-04','primary_failure'),
 ('688582.SH','2024-07-29','primary_book_winner'),
 ('000506.SZ','2024-10-15','primary_book_winner_execution_unverified'),
 ('600606.SH','2022-03-22','existing_reversal_winner'),
 ('600056.SH','2022-03-30','existing_terminal_failure'),
 ('601607.SH','2022-03-24','existing_failure'),
]
freeze=dict(name='沿原CP m的21期连续加权涨跌比',lambda_=LAM,alpha=ALPHA,formula='U=lambda*U_prev+(1-lambda)*m*max(r,0); D=lambda*D_prev+(1-lambda)*m*max(-r,0); score=100*U/(U+D), zero denominator=50',reset='source segment change or unavailable r/m only; never E0/I/native-down/lower_anchor/receipt',scope='Original legal same-day fresh MOBILE candidates only. Sort score descending, exact ties original PVR order. No gate, no wait, no account replay.',inputs='Only original cached CP1.r and CP1.m plus facts.segment_id. Entire available prior history, no resetting at case-window start.',cases=CASES,precalculation_design_history='SQ1 price-high multiplier and exp(-1/21) proposals were discussed and withdrawn before any new-score case calculation. Neither was executed or compared.',not_validation='Fixed known-outcome mechanism examples, not prediction/strategy validation. Cross-date scores are not same-day portfolio ranks.')
(O/'FORMULA_FREEZE.json').write_text(json.dumps(freeze,ensure_ascii=False,indent=2))
refs={x['symbol']:x['refs'] for x in json.loads(MANIFEST.read_text())}
hashes={}
def track(path):
 path=Path(path);hashes[str(path)]=hashlib.sha256(path.read_bytes()).hexdigest()
for path in [MANIFEST,B/'false_i_buy_case_comparison/FROZEN_CASES.csv',B/'FIRST_ENTRY_SIGNAL_FEATURES.csv',B/'false_i_buy_case_comparison/DAILY_20_BEFORE_10_AFTER.csv',B/'FOUR_STOCKS_DAILY.csv']:
 track(path)
original=pd.read_csv(B/'false_i_buy_case_comparison/FROZEN_CASES.csv')
extra=pd.read_csv(B/'FIRST_ENTRY_SIGNAL_FEATURES.csv')
origdaily=pd.read_csv(B/'false_i_buy_case_comparison/DAILY_20_BEFORE_10_AFTER.csv',parse_dates=['day'])
extradaily=pd.read_csv(B/'FOUR_STOCKS_DAILY.csv',parse_dates=['day'])

def score_frame(f,cp):
 U=D=0.;seg=None;last_score=math.nan;run=0;rows=[]
 for day in f.index:
  segment=f.at[day,'segment_id'];r=float(cp.at[day,'r']);m=float(cp.at[day,'m']);why=''
  if seg is None or segment!=seg:
   U=D=0.;last_score=math.nan;run=0;why='source_segment';seg=segment
  beforeU,beforeD=U,D
  if not (math.isfinite(r) and math.isfinite(m) and m>0):
   U=D=0.;last_score=math.nan;run=0
   rows.append(dict(day=day,U_before=beforeU,D_before=beforeD,U=U,D=D,signed_balance=0.,total_flow=0.,score=math.nan,score_change=math.nan,up_increment=math.nan,down_increment=math.nan,weighted_return=math.nan,score_reset='unavailable_r_or_m',continuous_valid_observations=run));continue
  up=ALPHA*m*max(r,0);down=ALPHA*m*max(-r,0)
  U=LAM*U+up;D=LAM*D+down
  score=100*(U/(U+D)) if U+D>0 else 50.
  change=score-last_score if math.isfinite(last_score) else math.nan
  run+=1
  rows.append(dict(day=day,U_before=beforeU,D_before=beforeD,U=U,D=D,signed_balance=U-D,total_flow=U+D,score=score,score_change=change,up_increment=up,down_increment=down,weighted_return=r*m,score_reset=why,continuous_valid_observations=run))
  last_score=score
 return pd.DataFrame(rows).set_index('day')

def check_units():
 # Algebraic recurrence, no alternative parameter or outcome fitting.
 U,D=.02,.01;old=100*U/(U+D)
 upU,upD=LAM*U+ALPHA*.015,LAM*D
 dnU,dnD=LAM*U,LAM*D+ALPHA*.015
 assert 100*upU/(upU+upD)>old>100*dnU/(dnU+dnD)
 assert abs(100*(LAM*U)/(LAM*(U+D))-old)<1e-12
 for scale in [.01,100.]:
  assert abs(100*(scale*U)/(scale*(U+D))-old)<1e-12
 assert abs((2*old/100-1)-(U-D)/(U+D))<1e-12
check_units()
pieces=[];summaries=[];checks=[];daily_notes=[]
for sid,signal,kind in CASES:
 for key in ['facts','CP1','CP1_input']:track(refs[sid][key])
 f=pd.read_parquet(refs[sid]['facts']);cp=pd.read_parquet(refs[sid]['CP1']);inp=pd.read_parquet(refs[sid]['CP1_input']).reindex(f.index)
 assert f.index.equals(cp.index) and f.index.is_unique and f.index.is_monotonic_increasing
 t=f.index.get_loc(pd.Timestamp(signal));end=min(t+11,len(f))
 sf_full=score_frame(f,cp)
 f=f.iloc[:end];cp=cp.iloc[:end];inp=inp.iloc[:end]
 sf=sf_full.iloc[:end]
 prefix=score_frame(f.iloc[:t+1],cp.iloc[:t+1])
 assert prefix.equals(sf_full.iloc[:t+1]),'Full-cache future append changed signal prefix'
 prefix_previous=score_frame(f.iloc[:t],cp.iloc[:t])
 assert prefix_previous.equals(sf_full.iloc[:t]),'Full-cache future append changed pre-signal prefix'
 assert sf.score.dropna().between(0,100).all()
 # Independently reconstruct exponentially weighted history at the signal date.
 last_reset=np.flatnonzero(sf.score_reset.iloc[:t+1].ne('').to_numpy())[-1]
 start=last_reset if math.isfinite(sf.score.iloc[last_reset]) else last_reset+1
 rr=cp.r.iloc[start:t+1].to_numpy();mm=cp.m.iloc[start:t+1].to_numpy()
 weights=ALPHA*LAM**np.arange(len(rr)-1,-1,-1)
 closedU=float(np.sum(weights*mm*np.maximum(rr,0)))
 closedD=float(np.sum(weights*mm*np.maximum(-rr,0)))
 assert abs(closedU-sf.U.iloc[t])<1e-14 and abs(closedD-sf.D.iloc[t])<1e-14
 # Rows after original CP resets must obey the same continuous recurrence, not a local warm start.
 original_reset=cp.reset_reason.fillna('').isin(['E0_down_reset','lower_anchor','receipt_consumed','E0_invalid','start']) & sf.score.notna() & sf.score_reset.eq('')
 assert np.allclose(sf.U[original_reset],LAM*sf.U_before[original_reset]+sf.up_increment[original_reset],rtol=1e-13,atol=1e-15)
 assert np.allclose(sf.D[original_reset],LAM*sf.D_before[original_reset]+sf.down_increment[original_reset],rtol=1e-13,atol=1e-15)
 z=f.copy()
 for col in cp:z['cp_'+col]=cp[col]
 z=z.join(sf);z['native_down']=inp.e0_down;z['amount']=inp.amount
 z['ret1']=np.expm1(cp.r);z['relative_observation']=np.arange(len(z))-t;z['sid']=sid;z['case_kind']=kind;z['signal_day']=signal
 z['credit_threshold_ratio']=cp.credit/(math.sqrt(5)*cp.scale);z['displacement_threshold_ratio']=cp.displacement/(math.sqrt(5)*cp.scale)
 sample=z.iloc[t-20:t+11].copy()
 prior=(origdaily if kind.startswith('primary') else extradaily)
 prior=prior[prior.sid.eq(sid)].set_index('day')
 common=sample.index.intersection(prior.index)
 for col in ['close','raw_close','cp_r','cp_m','cp_credit']:
  assert np.allclose(sample.loc[common,col],prior.loc[common,col],equal_nan=True,rtol=1e-12,atol=1e-14),(sid,col)
 ann=[]
 for day,row in sample.iterrows():
  flags=[]
  if row.cp_reset_reason is not None and pd.notna(row.cp_reset_reason):flags.append(str(row.cp_reset_reason))
  if bool(row.cp_receipt):flags.append('原CP1新证')
  flags.append('SCC不清零' if row.score_reset=='' else 'SCC重置:'+row.score_reset)
  if row.relative_observation>0:flags.append('事后展示，不参与信号分数')
  ann.append('；'.join(flags))
  daily_notes.append(f"{sid} {day.date()} ({int(row.relative_observation):+d}): 原价 {row.raw_close:.2f}，r={row.cp_r:+.8f}，m={row.cp_m:.6f}，原credit={row.cp_credit:.8f}，U={row.U:.8f}，D={row.D:.8f}，SCC21={row.score:.4f}，日变动={row.score_change:+.4f}；{ann[-1]}。")
 sample['annotation']=ann;pieces.append(sample)
 a=t
 while a>0 and cp.anchor.iloc[a-1]==cp.anchor.iloc[t]:a-=1
 case=(original[(original.sid==sid)&(original.signal_day==signal)] if kind.startswith('primary') else extra[(extra.sid==sid)&(extra.signal_day==signal)]).iloc[0]
 summaries.append(dict(sid=sid,signal_day=signal,case_kind=kind,original_round_pnl=float(case.round_pnl),original_PVR=float(case.get('original_PVR',case.get('PVR_decision'))),signal_raw_close=float(f.raw_close.iloc[t]),original_i_buy=bool(f.i_buy.iloc[t]),original_cp_phase=cp.phase.iloc[t],original_receipt=bool(cp.receipt.iloc[t]),original_credit=float(cp.credit.iloc[t]),credit_threshold_ratio=float(z.credit_threshold_ratio.iloc[t]),displacement_threshold_ratio=float(z.displacement_threshold_ratio.iloc[t]),original_anchor_day=str(f.index[a].date()),anchor_raw_close=float(f.raw_close.iloc[a]),anchor_score=float(sf.score.iloc[a]),signal_U=float(sf.U.iloc[t]),signal_D=float(sf.D.iloc[t]),signal_score=float(sf.score.iloc[t]),signal_signed_efficiency=float(2*sf.score.iloc[t]/100-1),score_prev=float(sf.score.iloc[t-1]),score_change=float(sf.score_change.iloc[t]),continuous_valid_observations=int(sf.continuous_valid_observations.iloc[t]),first_score_day=str(sf.score.first_valid_index().date()),post10_raw_close=float(f.raw_close.iloc[t+10]) if t+10<len(f) else None,post10_return=float(f.close.iloc[t+10]/f.close.iloc[t]-1) if t+10<len(f) else None,execution_caveat='ST resumed one-price limit-up; original first fill not demonstrated' if sid=='000506.SZ' else 'No new execution audit in this task'))
 checks.append(dict(sid=sid,signal_day=signal,prefix_invariance=True,prefix_cutoffs=[str(f.index[t-1].date()),str(f.index[t].date())],full_cache_observations=len(sf_full),closed_form_recurrence=True,score_range=True,original_reset_rows_continuous=int(original_reset.sum()),original_case_rows_matched=len(common),source_r_m_used_without_recomputation=True))
summary=pd.DataFrame(summaries)
pd.concat(pieces).to_csv(O/'DAILY_20_BEFORE_10_AFTER.csv',index_label='day')
summary.to_csv(O/'SIGNAL_SUMMARY.csv',index=False)
(O/'DAILY_EXPLANATIONS.txt').write_text('\n'.join(daily_notes),encoding='utf-8')
# Independent integrity reread: all original files stayed byte-for-byte unchanged.
assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in hashes.items())
(O/'SOURCE_HASHES.json').write_text(json.dumps(hashes,indent=2))
(O/'CHECKS.json').write_text(json.dumps(dict(checked_at_utc=datetime.now(timezone.utc).isoformat(),formula_units=True,source_unchanged=True,parameter_scan=False,account_replay=False,recalculated_original_indicators=False,checks=checks),indent=2))
print(summary[['sid','signal_day','case_kind','original_round_pnl','original_anchor_day','anchor_score','signal_score','score_change']].to_string(index=False))
print('Checks passed; 7 fixed cases, 217 daily rows. No new strategy/account run.')
