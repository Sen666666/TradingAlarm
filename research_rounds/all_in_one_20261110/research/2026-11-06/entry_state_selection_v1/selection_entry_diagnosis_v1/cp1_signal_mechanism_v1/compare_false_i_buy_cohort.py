
from pathlib import Path
import json
import pandas as pd,numpy as np
O=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1/selection_entry_diagnosis_v1/cp1_signal_mechanism_v1')
U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
sm={r['symbol']:r for r in json.loads((U/'STOCK_MANIFEST.json').read_text())}
a=pd.read_csv(O/'ACTUAL_FIRST_MOBILE_GATE_ATTRIBUTION.csv');a=a[(a.account=='PVR')&~a.accepted].copy()
out=[]
for sid,g in a.groupby('sid'):
 f=pd.read_parquet(sm[sid]['refs']['facts']);cp=pd.read_parquet(sm[sid]['refs']['CP1']);inp=pd.read_parquet(sm[sid]['refs']['CP1_input'])
 for z in g.to_dict('records'):
  d=pd.Timestamp(z['signal_day']);ix=f.index.get_loc(d);cur=f.iloc[ix];p=f.iloc[:ix+1];p=p[p.segment_id==cur.segment_id];l=np.log(p.close);base=float(cp.at[d,'anchor']);cp_p=cp.reindex(p.index);loc=np.flatnonzero(np.isclose(cp_p.next_anchor.to_numpy(dtype=float),base,rtol=0,atol=1e-10)&cp_p.reset_reason.isin(['start','lower_anchor','E0_down_reset','receipt_consumed']).to_numpy());bi=int(loc[-1])if len(loc)else None
  pre=l.iloc[max(0,len(l)-64):-1];prior20=l.iloc[max(0,len(l)-21):-1];gvals=p.g_grade;et=p.e0_target.eq(True);it=p.i_target.eq(True)
  def age(mask):
   idx=np.flatnonzero(mask);return len(p)-1-int(idx[-1])if len(idx)else np.nan
  rec=dict(z)
  rec.update(native_close=cur.close,cp_phase=cp.at[d,'phase'],cp_receipt=bool(cp.at[d,'receipt']),cp_anchor_native=np.exp(base),cp_anchor_age=len(p)-1-bi if bi is not None else np.nan,cp_displacement=float(cp.at[d,'displacement']),cp_scale=float(cp.at[d,'scale']),cp_credit=float(cp.at[d,'credit']),price_evidence=float(cp.at[d,'displacement'])/(np.sqrt(5)*cp.at[d,'scale']),credit_evidence=float(cp.at[d,'credit'])/(np.sqrt(5)*cp.at[d,'scale']),old20_gap_native=np.exp(l.iloc[-1]-prior20.max())-1,old63_gap_native=np.exp(l.iloc[-1]-pre.max())-1,amount_ratio_native=float(inp.at[d,'amount'])/inp.loc[p.index,'amount'].iloc[-22:-1].median(),e0_entry_age=age(et&~et.shift(1,fill_value=False)),i_entry_age=age(it&~it.shift(1,fill_value=False)),g_last_rise_age=age(gvals.gt(gvals.shift(1))),g_last_drop_age=age(gvals.lt(gvals.shift(1))),g_fresh_up_age=age(p.g_fresh_up.eq(True)),g_grade_change5=cur.g_grade-p.g_grade.iloc[-6] if len(p)>5 else np.nan)
  if bi is not None and bi>0:
   oldpeak=l.iloc[max(0,bi-63):bi].max();chain=l.iloc[bi:];absolute=chain.diff().abs().sum()
   rec.update(anchor_drawdown_from63=np.exp(base-oldpeak)-1,anchor_recovery_fraction=(l.iloc[-1]-base)/(oldpeak-base)if oldpeak>base else np.nan,anchor_path_efficiency=(l.iloc[-1]-base)/absolute if absolute>0 else np.nan)
  rm=(cp.r*cp.m).reindex(p.index);ab=(cp.r.abs()*cp.m).reindex(p.index)
  rec.update(net21_weighted=rm.iloc[-21:].sum(),eff21_weighted=rm.iloc[-21:].sum()/ab.iloc[-21:].sum())
  assert rec['cp_receipt'] and not bool(cur.i_buy)
  out.append(rec)
r=pd.DataFrame(out);r['outcome']=np.where(r.round_pnl.gt(0),'winner',np.where(r.round_pnl.lt(0),'loser','flat'))
r.to_csv(O/'FALSE_I_BUY_FIRST_MOBILE_FEATURES.csv',index=False)
cols=['old20_gap_native','old63_gap_native','amount_ratio_native','cp_anchor_age','anchor_drawdown_from63','anchor_recovery_fraction','anchor_path_efficiency','price_evidence','credit_evidence','g_grade_change5','g_last_rise_age','g_fresh_up_age','eff21_weighted','industry_breadth20','market_breadth20','ret5_forward','ret20_forward','entry_gap']
closed=r[r.closed_in_entry_year if False else r.closed].copy()
# 2022 uses original required year-end closed ledger; later years use observed closed.
closed=closed[(closed.year!=2022)|closed.closed_in_entry_year]
s=closed.groupby(['year','outcome']).agg(n=('sid','size'),pnl=('round_pnl','sum'),**{c:(c,'median')for c in cols}).reset_index()
s.to_csv(O/'FALSE_I_BUY_YEAR_MEDIANS.csv',index=False)
q=closed.groupby(['quarter','outcome']).agg(n=('sid','size'),pnl=('round_pnl','sum'),**{c:(c,'median')for c in cols}).reset_index();q.to_csv(O/'FALSE_I_BUY_QUARTER_MEDIANS.csv',index=False)
print(s[['year','outcome','n','pnl','old20_gap_native','old63_gap_native','amount_ratio_native','anchor_path_efficiency','g_grade_change5','industry_breadth20','market_breadth20','ret5_forward','ret20_forward']].round(5).to_string(index=False))
print('TOTAL false i_buy',len(r),'closed evaluated',len(closed))
