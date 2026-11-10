"""Read frozen signal coordinates and saved financial layers; no strategy execution."""
from pathlib import Path
from decimal import Decimal as D
import sys,json,gzip,time,hashlib,collections
import numpy as np
import pandas as pd
O=Path(__file__).resolve().parent;W=O.parent;PRIOR=W/'stage-progress-R-diagnostic-20261031'
sys.path.insert(0,str(W/'q2-normal-continuation-20261031'));import continuation as E
J,L=E.J,E.L;Z=D(0)
def read(p):return json.loads(Path(p).read_text())
def obj(p):
 with gzip.open(p,'rt') as f:return json.load(f)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(n,x):E.IO.write_json(O/n,J.T.norm(J.W.canon(J.T.norm(x))))
def sign(x):return 'N/A' if x is None else '+' if x>0 else '-' if x<0 else '0'
def dist(v):
 s=pd.Series(v,dtype=float).dropna();return {'n':len(s),**{str(q):float(s.quantile(q)) for q in [0,.25,.5,.75,1]}} if len(s) else {'n':0}
def main():
 start=time.monotonic();sm={r['symbol']:r for r in read(L.U/'STOCK_MANIFEST.json')};allentries=[];files={};facts={};returns={}
 # npz is compressed: materialize each required original array exactly once.
 with np.load(J.M.P/'h1.npz') as archive:h={k:archive[k] for k in ['dates','symbols','score','raw','h','nref']}
 hd=pd.DatetimeIndex(h['dates']);hi={str(s):i for i,s in enumerate(h['symbols'])};ht={str(d.date()):i for i,d in enumerate(hd)}
 def series(sid):
  if sid not in facts:
   path=J.M.O/'industry-facts'/f'{sid}.parquet' if sid.startswith('URFI') else Path(sm[sid]['refs']['facts']);f=pd.read_parquet(path);facts[sid]=f;files[str(path)]=sha(path)
   for k in [21,63,126]:returns[sid,k]=f.close/f.close.groupby(f.segment_id,sort=False).shift(k)-1
  return facts[sid]
 def snapshot(sid,date):
  f=series(sid);d=pd.Timestamp(date)
  if d not in f.index:return dict(unknown='no_exact_authorization_observation',returns={str(k):None for k in [21,63,126]})
  r=f.loc[d];out=dict(close=float(r.close),segment=r.segment_id,returns={str(k):float(returns[sid,k].loc[d]) if pd.notna(returns[sid,k].loc[d]) else None for k in [21,63,126]},unknown=None)
  if not sid.startswith('URFI'):
   # Verify the used coordinate is the saved rights-adjusted signal, not raw across splits.
   assert abs(float(r.raw_close)*float(r.factor)-float(r.close))<=1e-9*max(1.,abs(float(r.close)))
   out.update(factor=float(r.factor),raw_close=float(r.raw_close),I_target=bool(r.i_target),I_buy=bool(r.i_buy),G1_grade=float(r.g_grade) if pd.notna(r.g_grade) else None)
  else:out['E0_target']=bool(r.e0_target)
  t,j=ht.get(date),hi.get(sid)
  for key in ['score','raw','h','nref']:
   value=h[key][t,j] if t is not None and j is not None and key in h else None;out['H1_'+key]=float(value) if value is not None and np.isfinite(value) else None
  return out
 summaries=[];tail_counter=[];score_unknown=[]
 for win in ['2022','2025_26']:
  for ref in ['B3','B_diag']:
   path=PRIOR/win/ref/'ENTRIES.json';entries=read(path);files[str(path)]=sha(path);bookpath=(W/'2022-normal-reference-20261031' if win=='2022' else W/'q2-normal-continuation-20261031')/'runs'/ref/'pair/B.json.gz';b=obj(bookpath);files[str(bookpath)]=sha(bookpath)
   original_scores={(str(d['at'])[:10],i['sid']):i['score'] for d in b['decisions'] for i in d['intents'] if i['role']=='mobile'};enhanced=[]
   for r in entries:
    sid=r['sid'];date=r['signal_day'];stock=snapshot(sid,date);sector=snapshot(r['sector'],date);rank=original_scores.get((date,sid));cached=stock.get('H1_score')
    if rank is None or cached is None:score_unknown.append(dict(window=win,ref=ref,layer=r['layer']))
    else:assert abs(float(rank)-cached)<1e-10,(win,ref,sid,date,'H1 score mismatch')
    sr=stock['returns']['63'];gr=sector['returns']['63'];key='industry'+sign(gr)+'_stock'+sign(sr)
    a=dict(**r,stock_at_authorization=stock,industry_at_authorization=sector,direction63_group=key,actual_decision_H1_score=rank);enhanced.append(a);allentries.append(a)
    if win=='2025_26' and gr is not None and gr<0 and r['tail_layer']:tail_counter.append(a)
   groups=[]
   keys=sorted({r['direction63_group'] for r in enhanced}|{'industry+_stock+','industry+_stock-','industry-_stock+','industry-_stock-'})
   for key in keys:
    z=[r for r in enhanced if r['direction63_group']==key];amount=lambda pred:sum((D(r['net_contribution']) for r in z if pred(r)),Z)
    groups.append(dict(group=key,layers=len(z),receipts=len({r['canonical_stock_receipt'] for r in z}),buy_cash=sum((D(r['actual_buy_cash']) for r in z),Z),closed_positive=amount(lambda r:r['closed'] and D(r['net_contribution'])>=0),closed_negative=amount(lambda r:r['closed'] and D(r['net_contribution'])<0),open_net=amount(lambda r:not r['closed']),actions=dict(collections.Counter(r['entry_action'] for r in z)),industry21_context_pct=dist([r['industry_at_authorization']['returns']['21']*100 for r in z if r['industry_at_authorization']['returns']['21'] is not None]),industry126_context_pct=dist([r['industry_at_authorization']['returns']['126']*100 for r in z if r['industry_at_authorization']['returns']['126'] is not None]),stock21_context_pct=dist([r['stock_at_authorization']['returns']['21']*100 for r in z if r['stock_at_authorization']['returns']['21'] is not None]),stock126_context_pct=dist([r['stock_at_authorization']['returns']['126']*100 for r in z if r['stock_at_authorization']['returns']['126'] is not None]),stock_H1_rank=dist([r['stock_at_authorization']['H1_score'] for r in z]),industry_H1_rank=dist([r['industry_at_authorization']['H1_score'] for r in z])))
   prior=read(PRIOR/win/ref/'SUMMARY.json');assert sum(g['layers'] for g in groups)==prior['new_confirmed_mobile_layers'];assert abs(sum((g['closed_positive']+g['closed_negative']+g['open_net'] for g in groups),Z)-D(prior['selected_layer_net']))<D('.00000001')
   unavailable={f'{kind}{k}':sum(r[kind+'_at_authorization']['returns'][str(k)] is None for r in enhanced) for kind in ['stock','industry'] for k in [21,63,126]}
   result=dict(window=win,reference=ref,layers=len(enhanced),groups=groups,return_NA=unavailable,selected_net=D(prior['selected_layer_net']),other_roles_or_probe_net=D(prior['excluded_other_roles_or_probe_net']),whole_account_net=D(prior['whole_NAV_net']),stock_current_G1_below_warm=sum(r['stock_at_authorization'].get('G1_grade') is not None and r['stock_at_authorization']['G1_grade']<2 for r in enhanced),stock_I_false=sum(r['stock_at_authorization'].get('I_target') is False for r in enhanced),industry_E0_false=sum(r['industry_at_authorization'].get('E0_target') is False for r in enhanced))
   save(Path(win)/ref/'ENTRIES.json',enhanced);save(Path(win)/ref/'SUMMARY.json',result);summaries.append(result);print('GROUPS',win,ref,J.W.canon([{k:g[k] for k in ['group','layers','buy_cash','closed_positive','closed_negative','open_net']} for g in groups]),'NA',unavailable,flush=True)
 files[str(J.M.P/'h1.npz')]=sha(J.M.P/'h1.npz');save('SUMMARY.json',summaries);save('NEGATIVE_INDUSTRY_POSITIVE_WINDOW_TAIL_LAYERS.json',tail_counter);save('H1_SCORE_UNKNOWN.json',score_unknown);save('COMPLETION.json',dict(seconds=time.monotonic()-start,new_account_paths=0,new_indicators_or_policy=0,source_SHA256=files,actual_new_confirmed_mobile_layers=len(allentries),H1_actual_decision_score_unknown=len(score_unknown),H1_actual_score_mismatches=0));print('READONLY_DONE',round(time.monotonic()-start,2),flush=True)
if __name__=='__main__':
 try:main()
 except BaseException as e:save('ERROR.json',dict(type=type(e).__name__,reason=str(e)));raise
