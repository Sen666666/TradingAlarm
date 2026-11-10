"""Descriptive pre-entry overlap and terminal price extension, no account runs."""
from pathlib import Path
from collections import defaultdict
import pandas as pd,numpy as np,json,gzip,hashlib,gc
O=Path(__file__).resolve().parent;F=json.loads((O/'FREEZE.json').read_text());S=Path(F['source_root']);SF=json.loads((O/'SUPPLEMENT_FREEZE.json').read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
original={p.name:sha(p) for p in O.iterdir() if p.is_file()}
r=pd.read_csv(O/'ALL_ROUND_ATTRIBUTION.csv',keep_default_na=False);d=pd.read_csv(O/'DAILY_HELD_PATH.csv');paths={k:g.sort_values('day') for k,g in d.groupby(['account','round_id'])};cal=pd.read_parquet(F['price_source_by_sid']['000001.SZ'],columns=[]).index
cal=cal[cal<=pd.Timestamp('2026-05-15')];days=sorted(d.day.unique());acct=sorted(set(pd.read_csv(S/'analysis/DAILY_RISK.csv').day));assert list(cal[cal>=pd.Timestamp('2022-01-01')].strftime('%Y-%m-%d'))==acct
ci={str(t.date()):i for i,t in enumerate(cal)};buys={};ends={};splits=defaultdict(list)
for arm in ['PVR','NOACT']:
 with gzip.open(S/f'run/pair/{arm}.json.gz','rt') as f:a=json.load(f)
 for t in a['trades']:
  if t['side']=='buy':buys[(arm,int(t['layer']))]=t
  else:
   for p in t['parts']:ends[(arm,int(p['layer']))]=t
 for t in a['journal']:
  if t['kind']=='actual_split':splits[(arm,t['sid'])].append(t)
 del a;gc.collect()
features=[];give=[];mainlayers=pd.read_csv(S/'analysis/LAYER_ATTRIBUTION.csv');roundlayers={k:g.id.tolist() for k,g in mainlayers.groupby(['account','round_id'])}
names=['log_return_1','log_return_5','log_return_21','amount_ratio_prev21','log_distance_signal_floor']
for sid,g in r.groupby('sid'):
 b=pd.read_parquet(F['price_source_by_sid'][sid],columns=['close','amount','price_eligible','observed_bar','source_invalid','synthetic_event_bar','source_kind','source_path','segment_id']).reindex(cal)
 valid=b.price_eligible.eq(True)&b.observed_bar.eq(True)&b.source_invalid.eq(False)&b.synthetic_event_bar.eq(False)&np.isfinite(b.close)&b.close.gt(0)
 def good(w):
  return bool(len(w) and valid.loc[w.index].all() and w[['source_kind','source_path','segment_id']].notna().all().all() and w[['source_kind','source_path','segment_id']].nunique(dropna=False).eq(1).all())
 for z in g.to_dict('records'):
  key=(z['account'],int(z['round_id']));buy=buys[(z['account'],int(z['initial_layer']))];sd=buy['signal_at'][:10];assert buy['signal_at']<buy['at'] and buy['at']==z['opened']
  row=dict(account=z['account'],round_id=z['round_id'],sid=sid,entry_year=str(z['entry_year']),signal_at=buy['signal_at'],opened=z['opened'],initial_kind=z['initial_kind'],initial_pool=z['initial_pool'],round_status=z['round_status'],initial_status=z['initial_status'],round_pnl=z['round_pnl'],initial_pnl=z['initial_pnl'],round_return=z['round_return'],initial_return=z['initial_return'],initial_first5_session=z['initial_first5_session'],initial_progress20=z['initial_progress20'],initial_close_mfe=z['initial_close_mfe'],initial_close_mae=z['initial_close_mae'],round_progress20=z['round_progress20'],has_followup_add=z['has_followup_add'],round_held_closes=z['round_held_closes'],round_capital_days=z['round_capital_days'])
  row['group']='STALLED20_FINAL_LOSS' if z['round_status']=='CLOSED' and z['round_pnl']<0 and z['round_progress20']=='STALLED20' else 'BIG_WINNER30' if z['round_status']=='CLOSED' and z['round_return']>=.30 else 'OPEN_RETAINED' if z['round_status']=='OPEN' else 'OTHER_CLOSED_RETAINED'
  i=ci.get(sd)
  for n in names:row[n]=np.nan;row[n+'_status']='UNKNOWN'
  row['signal_floor']=float(buy['floor']) if buy.get('floor') is not None else np.nan
  if i is not None:
   for k in [1,5,21]:
    n='log_return_'+str(k);w=b.iloc[i-k:i+1] if i>=k else b.iloc[:0]
    if len(w)==k+1 and good(w):row[n]=float(np.log(w.close.iloc[-1]/w.close.iloc[0]));row[n+'_status']='KNOWN'
   w=b.iloc[i-21:i+1] if i>=21 else b.iloc[:0]
   if len(w)==22 and good(w) and np.isfinite(w.amount).all() and w.amount.gt(0).all():
    row['amount_ratio_prev21']=float(w.amount.iloc[-1]/w.amount.iloc[:-1].median());row['amount_ratio_prev21_status']='KNOWN'
   w=b.iloc[i:i+1]
   if good(w) and np.isfinite(row['signal_floor']) and row['signal_floor']>0:
    row['log_distance_signal_floor']=float(np.log(w.close.iloc[0]/row['signal_floor']));row['log_distance_signal_floor_status']='KNOWN'
  features.append(row)
  pp=paths[key];out=dict(account=z['account'],round_id=z['round_id'],sid=sid,entry_year=z['entry_year'])
  for pref in ['initial','round']:
   p=pp[pp.initial_layer_live.eq(True)] if pref=='initial' else pp
   v=p.close_price_return.dropna();peak=float(v.max()) if len(v) else np.nan;terminal=np.nan;basis=''
   if z[pref+'_status']=='CLOSED':
    k0=int(z['initial_layer'])
    e=ends[(z['account'],k0)] if pref=='initial' else max((ends[(z['account'],int(k))] for k in roundlayers[key]),key=lambda t:t['at'])
    sf=np.prod([float(t['ratio']) for t in splits[(z['account'],sid)] if z['opened']<t['at']<=e['at']])
    terminal=float(e['price'])*sf/float(buy['price'])-1;basis='ACTUAL_LAST_SELL_FILL';lastday=e['at'][:10]
   else:
    terminal=float(p.iloc[-1].close_price_return);basis='OBSERVED_LAST_HELD_CLOSE_OR_UNKNOWN';lastday=p.iloc[-1].day
   out.update({pref+'_terminal_price_return':terminal,pref+'_terminal_basis':basis,pref+'_terminal_day':lastday,pref+'_observed_peak_minus_terminal_pp':peak-terminal,pref+'_observed_peak_to_terminal_drawdown':(1+terminal)/(1+peak)-1,pref+'_last_held_close_return':float(p.iloc[-1].close_price_return),pref+'_terminal_below_observed_peak':bool(terminal<peak-1e-10) if np.isfinite(terminal) and np.isfinite(peak) else None,pref+'_observed_peak_day':str(p.loc[p.close_price_return.idxmax(),'day']) if len(v) else '',pref+'_observed_trough_day':str(p.loc[p.close_price_return.idxmin(),'day']) if len(v) else ''})
  give.append(out)
f=pd.DataFrame(features);f.to_csv(O/'PREENTRY_FEATURES_ALL.csv',index=False);gv=pd.DataFrame(give);gv.to_csv(O/'TERMINAL_PRICE_GIVEBACK.csv',index=False)
summary=[];overlap=[];outcomes=[]
for arm in ['PVR','NOACT']:
 for y in ['ALL','2022','2024']:
  a=f[f.account.eq(arm)&(True if y=='ALL' else f.entry_year.eq(y))]
  for group in ['STALLED20_FINAL_LOSS','BIG_WINNER30']:
   z=a[a.group.eq(group)]
   outcomes.append(dict(account=arm,entry_year=y,group=group,n=len(z),initial_losses=int(z.initial_pnl.lt(0).sum()),initial_positive=int(z.initial_pnl.gt(0).sum()),initial_median_return=pd.to_numeric(z.initial_return).median(),round_net=z.round_pnl.sum(),initial_net=z.initial_pnl.sum(),first5_median=pd.to_numeric(z.initial_first5_session,errors='coerce').median(),initial_STALLED20=int(z.initial_progress20.eq('STALLED20').sum()),with_ADD=int(z.has_followup_add.eq(True).sum()),median_hold=z.round_held_closes.median(),capital_days=z.round_capital_days.sum()))
   for feat in names:
    v=z[feat].dropna();summary.append(dict(account=arm,entry_year=y,group=group,feature=feat,n=len(z),known=len(v),unknown=len(z)-len(v),p10=v.quantile(.1),p25=v.quantile(.25),p50=v.quantile(.5),p75=v.quantile(.75),p90=v.quantile(.9)))
  l=a[a.group.eq('STALLED20_FINAL_LOSS')];w=a[a.group.eq('BIG_WINNER30')]
  for feat in names:
   lv=l[feat].dropna();wv=w[feat].dropna()
   if len(lv) and len(wv):
    lo=max(lv.quantile(.25),wv.quantile(.25));hi=min(lv.quantile(.75),wv.quantile(.75));union=max(lv.quantile(.75),wv.quantile(.75))-min(lv.quantile(.25),wv.quantile(.25))
    overlap.append(dict(account=arm,entry_year=y,feature=feat,stalled_loss_known=len(lv),big_winner_known=len(wv),stalled_loss_within_winner_p10_p90=float(lv.between(wv.quantile(.1),wv.quantile(.9)).mean()),winner_within_stalled_loss_p10_p90=float(wv.between(lv.quantile(.1),lv.quantile(.9)).mean()),IQR_intersection_over_union=max(0.,hi-lo)/union if union else np.nan))
pd.DataFrame(summary).to_csv(O/'PREENTRY_DISTRIBUTIONS.csv',index=False);pd.DataFrame(overlap).to_csv(O/'PREENTRY_OVERLAP.csv',index=False);pd.DataFrame(outcomes).to_csv(O/'PREENTRY_GROUP_OUTCOMES.csv',index=False)
for n,h in original.items():assert sha(O/n)==h,('primary changed',n)
for p,h in F['source_hashes'].items():assert sha(p)==h,('source changed',p)
(O/'SUPPLEMENT_CHECKS.json').write_text(json.dumps(dict(status='PASS',account_runs=0,full_feature_rows=len(f),full_giveback_rows=len(gv),original_1534_sources_unchanged=True,all_primary_files_unchanged=True,all_signal_times_before_buy=True,prehistory_calendar_matches_original1054=True,definitions_sha256=sha(O/'SUPPLEMENT_FREEZE.json')),indent=2))
print(pd.DataFrame(outcomes).to_string(index=False));print(pd.DataFrame(overlap).to_string(index=False))
