"""Current cached G1 at original authorization close. No model/execution calls."""
from pathlib import Path
from decimal import Decimal as D
import json,collections,time,hashlib,traceback,statistics
import pandas as pd,numpy as np
O=Path(__file__).resolve().parent;W=O.parent;R=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds');P=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared')
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(name,x):
 p=O/name;p.parent.mkdir(parents=True,exist_ok=True);t=p.with_name(p.name+'.tmp');t.write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n');t.replace(p)
def agg(rs):
 return dict(layers=len(rs),stocks=len({x['sid'] for x in rs}),receipts=len({x['receipt'] for x in rs}),buy_cash=sum((D(x['actual_buy_cash']) for x in rs),D(0)),closed_positive=sum((D(x['net_contribution']) for x in rs if x['closed'] and D(x['net_contribution'])>0),D(0)),closed_negative=sum((D(x['net_contribution']) for x in rs if x['closed'] and D(x['net_contribution'])<0),D(0)),open_contribution=sum((D(x['net_contribution']) for x in rs if not x['closed']),D(0)))
def state(f,at):
 t=pd.Timestamp(at)
 if t not in f.index:return dict(source_day=None,group='unknown',reason='no exact authorization-day observation')
 i=f.index.get_loc(t);r=f.iloc[i];known=bool(r.g_ready is True or r.g_ready==True) and pd.notna(r.g_grade)
 out=dict(source_day=at,grade=float(r.g_grade) if pd.notna(r.g_grade) else None,ready=bool(r.g_ready) if pd.notna(r.g_ready) else None,group='still_warm' if known and r.g_grade>=2 else 'below_warm_known' if known else 'unknown',fresh_up=bool(r.g_fresh_up),acute_down=bool(r.g_acute_down),I_valid=bool(r.i_target),fresh_I=bool(r.i_buy),E0_valid=bool(r.e0_target),segment=str(r.segment_id),continuous_below_warm_observations=None,first_continuous_below_warm_day=None,last_warm_day=None,duration_left_censored=None)
 if known and r.g_grade<2:
  j=i
  while j>=0:
   q=f.iloc[j]
   if q.segment_id!=r.segment_id or not (pd.notna(q.g_ready) and bool(q.g_ready) and pd.notna(q.g_grade) and q.g_grade<2):break
   j-=1
  out.update(continuous_below_warm_observations=i-j,first_continuous_below_warm_day=str(f.index[j+1].date()),duration_left_censored=not(j>=0 and f.iloc[j].segment_id==r.segment_id and bool(f.iloc[j].g_ready) and pd.notna(f.iloc[j].g_grade) and f.iloc[j].g_grade>=2),last_warm_day=str(f.index[j].date()) if j>=0 and f.iloc[j].segment_id==r.segment_id and bool(f.iloc[j].g_ready) and pd.notna(f.iloc[j].g_grade) and f.iloc[j].g_grade>=2 else None)
 return out
def main():
 begun=time.monotonic();sm={r['symbol']:r for r in read(W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json')};frames={};ix={};src={};rows=[];summary=[]
 industry_cache={s.name[:-8]:s for s in (P/'facts').glob('URFI*.parquet')};industry_frames={};industry_proof=[]
 im={r['series']:r for r in read(W/'universe-cp1-inputs-20261031/INDUSTRY_MANIFEST.json')}
 for sid,path in industry_cache.items():
  f=pd.read_parquet(path).loc[:'2026-06-30'];q=pd.read_parquet(im[sid]['refs']['CP1_input']).loc[:'2026-06-30'];common=q.index.intersection(f.index);same=True
  for a,b in [('close','close'),('segment_id','segment_id'),('e0_valid','e0_target'),('i_floor','e0_floor')]:
   try:np.testing.assert_allclose(q.loc[common,a].astype(float),f.loc[common,b].astype(float),rtol=0,atol=0,equal_nan=True)
   except AssertionError:same=False
  industry_proof.append(dict(sid=sid,cached_path=str(path),common_rows=len(common),full_original_input_prefix_equal=same and common.equals(q.index),original_contract_industry_G1_gate=False))
  if same and common.equals(q.index):industry_frames[sid]=f
  src[str(path)]=sha(path)
 for win in ['2022','2025_26']:
  path=W/'add-and-reentry-readonly-20261031'/win/'ENTRIES.json';entries=read(path);src[str(path)]=sha(path);out=[]
  for x in entries:
   sid=x['sid'];date=x['signal_day'];rec=sm[sid]
   if sid not in frames:
    fp=Path(rec['refs']['facts']);assert sha(fp)==rec['output_sha256'][str(fp)]
    frames[sid]=pd.read_parquet(fp,columns=['g_grade','g_ready','g_fresh_up','g_acute_down','i_target','i_buy','e0_target','segment_id']);src[str(fp)]=sha(fp)
    ip=R/'ix-a-share-entry-20261025/signals'/(sid+'.parquet');ix[sid]=pd.read_parquet(ip,columns=['grade','strength_ready','fresh_up','acute_down','proposal','phase','promotion_blocked','z5','z21']);src[str(ip)]=sha(ip)
   g=state(frames[sid],date);assert g['I_valid'] is True,(win,sid,date,'actual confirmed layer I not valid')
   z=ix[sid].loc[pd.Timestamp(date)]
   for a,b in [('g_grade','grade'),('g_ready','strength_ready'),('g_fresh_up','fresh_up'),('g_acute_down','acute_down')]:
    aa=frames[sid].loc[pd.Timestamp(date),a];bb=z[b];assert aa==bb or (pd.isna(aa) and pd.isna(bb)),(sid,date,a)
   g.update(proposal=float(z.proposal) if pd.notna(z.proposal) else None,phase=z.phase,promotion_blocked=bool(z.promotion_blocked),z5=float(z.z5) if pd.notna(z.z5) else None,z21=float(z.z21) if pd.notna(z.z21) else None)
   if g['fresh_I']:assert g['group']=='still_warm','fresh I must be current warm by source contract'
   sector=x['industry_attempt'].split(':')[0] if False else read(W/'stage-progress-R-diagnostic-20261031'/win/'B_diag/ENTRIES.json')[0].get('industry') if False else None
   # Original frozen metadata gives the same fixed industry mapping used by Q.
   # Resolve from the stock manifest's original metadata below, not future outcomes.
   meta=metadata[sid];sector=meta['sector_id'];ig=state(industry_frames[sector],date) if sector in industry_frames else dict(group='unknown',reason='no complete same-source cached current G1 for this industry; no indicator generated')
   r=dict(x,current_stock_G1=g,current_industry_G1=ig,sector=sector);out.append(r)
  assert len(out)==(576 if win=='2022' else 602)
  panels=[]
  for field in ['current_stock_G1','current_industry_G1']:
   for action in ['all','first','add','reentry']:
    for group in ['still_warm','below_warm_known','unknown']:
     use=[x for x in out if x[field]['group']==group and (action=='all' or x['actual_action']==action)];panels.append(dict(field=field,action=action,group=group,**agg(use)))
  cold=[r for r in out if r['current_stock_G1']['group']=='below_warm_known'];dur=[r['current_stock_G1']['continuous_below_warm_observations'] for r in cold if not r['current_stock_G1']['duration_left_censored']]
  tails=[r for r in out if D(r['net_contribution'])>=D('.3')*D(r['actual_buy_cash'])]
  summary.append(dict(window=win,total=agg(out),panels=panels,grade_counts=dict(collections.Counter(str(r['current_stock_G1']['grade']) for r in out)),below_warm_continuous=dict(layers=len(cold),full_duration_known=len(dur),left_censored=sum(r['current_stock_G1']['duration_left_censored'] for r in cold),median_observations=statistics.median(dur) if dur else None,max_observations=max(dur) if dur else None,proposal_warm_but_grade_below_and_promotion_blocked=sum(r['current_stock_G1']['proposal'] is not None and r['current_stock_G1']['proposal']>=2 and r['current_stock_G1']['promotion_blocked'] for r in cold)),tail_all=agg(tails),tail_below_warm=agg([r for r in tails if r['current_stock_G1']['group']=='below_warm_known']),below_warm_loss_share=abs(agg(cold)['closed_negative']/agg(out)['closed_negative']) if agg(out)['closed_negative'] else None))
  save(win+'/ENTRIES.json',out);save(win+'/PANELS.json',panels);save(win+'/TAILS_ALL.json',tails);save(win+'/TAILS_BELOW_WARM.json',[r for r in tails if r['current_stock_G1']['group']=='below_warm_known']);rows+=out
  print('G1_RESULT',win,json.dumps(summary[-1],ensure_ascii=False,default=str),flush=True)
 code=[R/'b5-g1-20261025/code/grade.py',R/'b5-g1-20261025/code/policies_g1.py',R/'pv-strength-b4-20261025/code/model.py',R/'pv-strength-b5-20261025/code/evidence.py',R/'continuous-protection-lines-20261028/code/model.py',W/'case-stage-ledger-20261031/v3/joint_v3.py',Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/desk/admission.py'),Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/desk/refresh.py')]
 for p in code:src[str(p)]=sha(p)
 save('SUMMARY.json',summary);save('INDUSTRY_COVERAGE.json',dict(fixed_industries=90,cached_current_G1=len(industry_cache),same_input_complete_prefix=len(industry_frames),unknown_no_new_indicator=90-len(industry_frames),proof=industry_proof));save('SOURCE_SHA256.json',src);save('COMPLETION.json',dict(passed=True,rows=len(rows),windows=2,new_accounts=0,new_indicators=0,seconds=time.monotonic()-begun,current_state_exact_to_original_IX_grade=True,fresh_I_implies_warm_all_rows=True))
 print('DONE',round(time.monotonic()-begun,3),flush=True)
metadata=read(R/'a-share-selection-e0-20261024/inputs-v2/metadata.json')
if __name__=='__main__':
 try:main()
 except BaseException as e:save('ERROR.json',dict(reason=str(e),traceback=traceback.format_exc(),new_accounts=0));raise
