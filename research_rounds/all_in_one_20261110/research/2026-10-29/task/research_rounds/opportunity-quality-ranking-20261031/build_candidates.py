"""Freeze common original opportunities and actual allocation flags before labels."""
from pathlib import Path
from decimal import Decimal as D
import sys,json,gzip,time,collections
import numpy as np,pandas as pd
O=Path(__file__).resolve().parent;W=O.parent;sys.path.insert(0,str(W/'q2-normal-continuation-20261031'));import continuation as E
J,L,IO=E.J,E.L,E.IO
WINDOWS={'2022':('2022-01-01','2022-12-30'),'2025_26':('2025-07-01','2026-06-30')}
def read(p):return json.loads(Path(p).read_text())
def stream(p):
 with gzip.open(p,'rt') as f:
  for x in f:yield json.loads(x)
def obj(p):
 with gzip.open(p,'rt') as f:return json.load(f)
def save(p,x):IO.write_json(p,J.T.norm(J.W.canon(J.T.norm(x))))
def main():
 t=time.monotonic();im=read(L.U/'INDUSTRY_MANIFEST.json');sm=read(L.U/'STOCK_MANIFEST.json');states={};probe={};source={str(O/'PROTOCOL.txt'):L.sha(O/'PROTOCOL.txt'),str(Path(__file__)):L.sha(__file__)}
 for r in im:
  f=pd.read_parquet(r['refs']['state']);states[r['series']]={a['day']:a for a in J.T.norm(f.to_dict('records')) if any(lo<=a['day']<=hi for lo,hi in WINDOWS.values())};probe.update({a['attempt_id']:a['day'] for a in J.T.norm(f.to_dict('records')) if a['action']=='probe'});source[r['refs']['state']]=L.sha(r['refs']['state'])
 with np.load(J.M.P/'h1.npz') as z:dates=pd.DatetimeIndex(z['dates']);cols={str(s):i for i,s in enumerate(z['symbols'])};score=z['score']
 hdate={str(d.date()):i for i,d in enumerate(dates)};source[str(J.M.P/'h1.npz')]=L.sha(J.M.P/'h1.npz');summary=[]
 for win,(lo,hi) in WINDOWS.items():
  base=W/'2022-normal-reference-20261031' if win=='2022' else W/'q2-normal-continuation-20261031';original={};allocation={};on={};freshcounts={}
  canonical={}
  for r in sm:
   path=(W/'2022-normal-reference-20261031/inputs/stock-receipts'/(r['symbol']+'.json')) if win=='2022' else Path(r['refs']['receipts'])
   for x in read(path):
    if lo<=x['confirmed_day']<=hi:canonical[r['symbol'],x['confirmed_day'],x['receipt_id']]=True
  for ref in ['B3','B_diag']:
   root=base/'runs'/ref/'pair';p=root/'opportunities.jsonl.gz';source[str(p)]=L.sha(p);fresh={}
   for r in stream(p):
    if r['CP1_id']:
     k=r['sid'],r['day'],r['CP1_id'];assert k not in fresh;assert k in canonical,(win,ref,k,'not original canonical');fresh[k]=r
   assert set(fresh)==set(canonical),(win,ref,'canonical day coverage mismatch',len(fresh),len(canonical));original[ref]=fresh;freshcounts[ref]=len(fresh)
   on[ref]={r['at'][:10]:r['on'] for r in stream(root/'daily.jsonl.gz')};a=obj(root/'B.json.gz');selected=read(W/'stage-progress-R-diagnostic-20261031'/win/ref/'ENTRIES.json');fund={}
   for x in selected:
    k=x['sid'],x['signal_day'],x['canonical_stock_receipt'];fund.setdefault(k,dict(layers=0,cash=D(0)));fund[k]['layers']+=1;fund[k]['cash']+=D(x['actual_buy_cash'])
   probe_mobile=set();core=set()
   for j in a['journal']:
    if j['kind']!='real_buy_fill':continue
    if j['role']=='core':core.add((j['sid'],j['signal_at'][:10]))
    elif j['pool']=='probe':probe_mobile.add((j['sid'],j['signal_at'][:10],j['CP1_id']))
   allocation[ref]=dict(confirmed=fund,probe=probe_mobile,core=core)
  assert original['B3'].keys()==original['B_diag'].keys()
  for k,r in original['B3'].items():
   rr=original['B_diag'][k];assert all(r[x]==rr[x] for x in ['sector','rank','core_Q','mobile_Q']),('market facts differ',k)
  rows=[];exclusion=collections.Counter()
  for key,r in original['B3'].items():
   if r['mobile_Q'] is None:exclusion['Q_unknown']+=1;continue
   if r['mobile_Q'] is not True:exclusion['Q_false']+=1;continue
   st=states[r['sector']].get(r['day'])
   if not st or st['action']=='unknown':exclusion['industry_unknown']+=1;continue
   if not (st['E0_valid'] and st['stage_name'] in ['confirmed','expanded'] and st['authorization_usable'] and st['attempt_id']):exclusion['industry_not_confirmed_expanded_valid']+=1;continue
   i,j=hdate.get(r['day']),cols.get(r['sid']);h=score[i,j] if i is not None and j is not None else np.nan;assert np.isfinite(h),'Qtrue requires H1'
   z=dict(window=win,sid=r['sid'],day=r['day'],receipt=r['CP1_id'],sector=r['sector'],industry_attempt=st['attempt_id'],attempt_probe_day=probe[st['attempt_id']],industry_stage=st['stage_name'],H1=float(h),original_global_rank=r['rank'],attempt_inherited=probe[st['attempt_id']]<lo)
   for ref in ['B3','B_diag']:
    fund=allocation[ref]['confirmed'].get(key);z[ref]=dict(selected=bool(fund),selected_layers=fund['layers'] if fund else 0,selected_cash=str(fund['cash']) if fund else '0',ACT_paused=not on[ref][r['day']],probe_mobile_funded=key in allocation[ref]['probe'],same_stock_core_funded=(r['sid'],r['day']) in allocation[ref]['core'])
   rows.append(z)
  byday=collections.defaultdict(list)
  for r in rows:byday[r['day']].append(r)
  for date,rs in byday.items():
   rs.sort(key=lambda r:(-r['H1'],r['sid']));assert [r['original_global_rank'] for r in rs]==sorted(r['original_global_rank'] for r in rs),'original H1/tie order mismatch'
   for q,indices in enumerate(np.array_split(np.arange(len(rs)),5),1):
    for i in indices:rs[int(i)].update(quintile=q,daily_candidates=len(rs),candidate_rank=int(i)+1)
  seen=set()
  for r in sorted(rows,key=lambda r:(r['day'],r['sid'])):
   k=r['sid'],r['industry_attempt'];r['first_stock_attempt_in_window']=k not in seen;r['first_complete_attempt']=r['first_stock_attempt_in_window'] and not r['attempt_inherited'];seen.add(k)
  for ref in ['B3','B_diag']:
   selected=allocation[ref]['confirmed'];assert {(r['sid'],r['day'],r['receipt']) for r in rows if r[ref]['selected']}==set(selected),'real confirmed receipts missing from candidate set'
  path=O/win/'CANDIDATES.jsonl.gz';IO.write_gzip_jsonl(path,sorted(rows,key=lambda r:(r['day'],r['candidate_rank'])))
  d=dict(window=win,all_original_fresh_receipts=len(canonical),exclusion_counts=dict(exclusion),candidates=len(rows),unique_stocks=len({r['sid'] for r in rows}),candidate_dates=len(byday),first_stock_attempt_in_window=sum(r['first_stock_attempt_in_window'] for r in rows),first_complete_attempt=sum(r['first_complete_attempt'] for r in rows),first_inherited_left_censored=sum(r['first_stock_attempt_in_window'] and r['attempt_inherited'] for r in rows),selected={ref:dict(events=sum(r[ref]['selected'] for r in rows),layers=sum(r[ref]['selected_layers'] for r in rows),cash=sum((D(r[ref]['selected_cash']) for r in rows),D(0)),ACT_paused_candidate_events=sum(r[ref]['ACT_paused'] for r in rows),ACT_paused_candidate_dates=len({r['day'] for r in rows if r[ref]['ACT_paused']})) for ref in ['B3','B_diag']},candidate_file_SHA256=L.sha(path));save(O/win/'DENOMINATORS.json',d);summary.append(d);print('CANDIDATES_FROZEN',win,J.W.canon(d),flush=True)
 save(O/'CANDIDATE_FREEZE.json',dict(before_price_labels=True,sources_SHA256=source,windows=summary,seconds=time.monotonic()-t,new_account_paths=0));print('CANDIDATE_DONE',round(time.monotonic()-t,2),flush=True)
if __name__=='__main__':
 try:main()
 except BaseException as e:save(O/'CANDIDATE_ERROR.json',dict(type=type(e).__name__,reason=str(e)));raise
