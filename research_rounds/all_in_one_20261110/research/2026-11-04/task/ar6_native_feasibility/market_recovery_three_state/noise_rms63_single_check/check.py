from pathlib import Path
import json,math,hashlib,time
import pandas as pd
O=Path(__file__).resolve().parent;BASE=O.parent/'diagnostic_v2'
REC=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/mainline-absolute-Q4-20261031/recovery.csv')
AR=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/pv-strength-b5-20261025/code/arithmetic.py')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def main():
 t=time.monotonic();assert not (O/'RESULTS.json').exists(),'no repeat'
 freeze=json.loads((O/'SOURCE_FREEZE.json').read_text())
 for p,h in freeze.items():assert sha(p)==h,p
 ar={'__name__':'frozen_e0_arithmetic_geometry_only'};exec(compile(AR.read_text(),str(AR),'exec'),ar)
 # Source module contains pure scalar functions only; no I/O, model or account.
 compare,log_ratio=ar['compare'],ar['log_ratio']
 f=pd.read_csv(REC,index_col=0,parse_dates=True)
 z=pd.read_csv(BASE/'FULL_ORIGINAL_INPUT_PLUS_STATIC20.csv',index_col=0,parse_dates=True)
 assert f.market.equals(z.market)and f.breadth.equals(z.breadth)
 assert f.index.is_unique and f.index.is_monotonic_increasing
 assert z.loc['2022':'2026','price_known'].all()
 cases=[]
 for r in json.loads((BASE/'ALL_ORIGINAL_PAUSE_CYCLES.json').read_text()):
  cases.append(dict(kind='original_pause_anchor',id=r['policy']+'_'+r['pause_day'],P=r['first_trigger20'],end=r['resume_day']or'2024-12-31',old63=r['resume_day']))
 for r in json.loads((BASE/'CONTEXT_SUMMARY.json').read_text()):
  cases.append(dict(kind='fixed_context',id=r['label'],P=r['all_trigger20_days'][0]if r['all_trigger20_days']else None,end=r['hi'],old63=r['all_BREAK63_days'][0]if r['all_BREAK63_days']else None))
 cases.append(dict(kind='same_old_pause_subcontext',id='2024_spring_Feb26',P='2024-02-26',end='2024-05-06',old63='2024-05-06'))
 out=[]
 for c in cases:
  r=dict(c);P=c['P']
  if P is None:r.update(status='NO_P_WITHIN_ORIGINAL_OBSERVATION',sigma_raw=None,sigma_effective=None,threshold=None,first_geometric_C=None,first_valid_before_S_breach=None);out.append(r);continue
  d=pd.Timestamp(P);p=float(f.loc[d,'market']);s=float(z.loc[d,'L20']);past=f.loc[f.index<d].market.tail(64)
  assert len(past)==64 and z.loc[past.index,'price_known'].all()
  rets=[log_ratio(float(past.iloc[i]),float(past.iloc[i-1]))for i in range(1,64)]
  raw=math.sqrt(math.fsum(x*x for x in rets)/63);sig=max(raw,1e-8);h=math.sqrt(5)*sig;threshold=p*math.exp(h)
  w=z.loc[d:c['end']].iloc[1:];sbreach=w.index[w.market.le(s)];breach=None if len(sbreach)==0 else sbreach[0]
  eligible=[x for x in w.index if bool(w.loc[x,'trigger20'])and log_ratio(float(w.loc[x,'market']),p)>=0 and compare(log_ratio(float(w.loc[x,'market']),p),h)>=0]
  hit=eligible[0]if eligible else None;valid=hit is not None and(breach is None or hit<breach)
  old=pd.Timestamp(c['old63'])if c['old63']else None
  def nd(x):return None if x is None else str(x.date())
  r.update(status='PASS_STATIC_GEOMETRY_NOT_MATURITY',P_market=p,S0=s,box_width=(p-s)/p,
   prior64_begin=nd(past.index[0]),prior64_end=nd(past.index[-1]),prior63_returns=63,trigger_return_excluded=True,
   sigma_raw=raw,sigma_effective=sig,numeric_floor_active=raw<1e-8,log_unit=h,threshold=threshold,threshold_advance_fraction=math.expm1(h),
   first_geometric_C=nd(hit),first_geometric_C_M=None if hit is None else float(w.loc[hit,'market']),
   first_S_breach=nd(breach),first_valid_before_S_breach=nd(hit)if valid else None,
   geometric_after_S_failure=hit is not None and not valid,
   first_geometric_vs_old63_closes=None if old is None or hit is None else int(f.index.get_loc(hit)-f.index.get_loc(old)),
   first_geometric_vs_P_closes=None if hit is None else int(f.index.get_loc(hit)-f.index.get_loc(d)),
   right_censored_no_geometric_hit=hit is None,observed_last=str(w.index[-1].date())if len(w)else P,
   old63_is_future_historical_context_only=True)
  out.append(r)
 save('ALL_CASES.json',out);pd.DataFrame(out).to_csv(O/'ALL_CASES.csv',index=False)
 for p,hsh in freeze.items():assert sha(p)==hsh,p
 save('RESULTS.json',dict(passed=True,seconds=time.monotonic()-t,cases=len(out),new_account_events=0,new_models=0,
  M_recalculated=False,scale_formula='rawRMS prior63; effective=max(raw,1e-8), old E0 numeric floor',
  no_state_machine=True,no_risklevel=True,no_automatic_followup=True))
 print(json.dumps(out,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
