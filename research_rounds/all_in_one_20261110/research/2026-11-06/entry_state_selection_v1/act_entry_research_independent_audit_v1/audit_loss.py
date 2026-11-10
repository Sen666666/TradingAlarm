import json,gzip,hashlib,collections,pathlib,decimal
import pandas as pd,numpy as np
R=pathlib.Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1'); S=R/'act_only_ablation_continuous_v1'; N=R/'act_entry_loss_attribution_v1'; O=R/'act_entry_research_independent_audit_v1'; D=decimal.Decimal
summary={'method':'Independent raw trade/split replay and fresh-price reconstruction; no author imports, account runs, or signal recomputation.','account_runs':0,'arms':{}}
new=pd.read_csv(N/'ALL_ROUND_ATTRIBUTION.csv'); paths=pd.read_csv(N/'DAILY_HELD_PATH.csv'); freeze=json.loads((N/'FREEZE.json').read_text())
# Load only price-source columns. Source SHA verified separately below.
px={}
for sid,p in freeze['price_source_by_sid'].items():
 f=pd.read_parquet(p); f.index=pd.to_datetime(f.index).strftime('%Y-%m-%d')
 px[sid]=f
snaps=collections.defaultdict(dict)
for line in gzip.open(S/'run/pair/daily.jsonl.gz','rt'):
 d=json.loads(line);snaps[d['account']][d['at'][:10]]=d
for arm in ['PVR','NOACT']:
 a=json.load(gzip.open(S/f'run/pair/{arm}.json.gz','rt')); rr=new[new.account.eq(arm)].set_index('initial_layer'); checked=paths[paths.account.eq(arm)].set_index(['round_id','day']);
 events=collections.defaultdict(list)
 for i,t in enumerate(a['trades']):events[t['at'][:10]].append((t['at'],1,i,t))
 for i,t in enumerate(a['journal']):
  if t['kind']=='actual_split':events[t['at'][:10]].append((t['at'],0,i,t))
 live={}; layer={}; rounds={}; roundpaths=collections.defaultdict(list); initial_for_sid={}; maxcosterr=0.; daily_cost_sum=D(0); splits=0; partials=0
 for day,snap in snaps[arm].items():
  for _,kind,_,t in sorted(events[day]):
   sid=t['sid'] if kind==0 else t['security_id']
   if kind==0:
    ids=[k for k in live if layer[k]['sid']==sid]; before=sum(live[k] for k in ids); target=int(D(before)*D(t['ratio'])); bases={k:int(D(live[k])*D(t['ratio'])) for k in ids}
    for k in ids[:target-sum(bases.values())]:bases[k]+=1
    assert sum(bases.values())==target
    for k in ids:live[k]=bases[k]
    if ids: rounds[initial_for_sid[sid]]['split_factor']*=D(t['ratio']);splits+=1
   elif t['side']=='buy':
    k=int(t['layer']); q=int(t['shares']); cost=D(t['gross_cny'])+D(t['fees_cny']);
    if sid not in initial_for_sid:
     initial_for_sid[sid]=k; rounds[k]={'sid':sid,'open':t['at'],'closed':'','layers':[],'buy_cost':D(0),'cash':D(0),'split_factor':D(1),'price':float(t['price'])}
    first=initial_for_sid[sid];layer[k]={'sid':sid,'first':first,'cost':cost,'cash':-cost,'div':D(0),'kind':t['kind']};live[k]=q;rounds[first]['layers'].append(k);rounds[first]['buy_cost']+=cost;rounds[first]['cash']-=cost
   else:
    first=initial_for_sid[sid]; prior=sum(live[k] for k in live if layer[k]['sid']==sid)
    for p in t['parts']:
     k=int(p['layer']); q=int(p['shares']);assert 0<q<=live[k]; layer[k]['cost']*=D(live[k]-q)/D(live[k]);layer[k]['cash']+=D(p['net_cash']);rounds[first]['cash']+=D(p['net_cash']);live[k]-=q
     if not live[k]:del live[k]
    if any(layer[k]['sid']==sid for k in live):partials+=1
    else:rounds[first]['closed']=t['at'];del initial_for_sid[sid]
  expected={int(z['id']):int(z['qty']) for z in snap['layers']}; assert live==expected,(arm,day,'quantity replay')
  for z in snap['layers']:
   k=int(z['id']);layer[k]['div']=D(z['dividend']);assert abs(layer[k]['cash']-D(z['cash']))<D('1e-7')
  daily_cost_sum+=sum((layer[k]['cost'] for k in live),D(0))
  for sid,k0 in initial_for_sid.items():
   r=rounds[k0]; idx=int(rr.loc[k0,'round_id']); ids=[k for k in live if layer[k]['first']==k0]; costs=sum((layer[k]['cost'] for k in ids),D(0)); initial_cost=layer[k0]['cost'] if k0 in live else D(0)
   source=px[sid];bar=source.loc[day] if day in source.index else None
   valid=bar is not None and bool(bar.get('price_eligible',False)) and bool(bar.get('observed_bar',False)) and not bool(bar.get('source_invalid',True)) and not bool(bar.get('synthetic_event_bar',True)) and np.isfinite(float(bar['raw_close'])) and float(bar['raw_close'])>0
   val=float(bar['raw_close'])*float(r['split_factor'])/r['price']-1 if valid else np.nan
   observed=checked.loc[(idx,day)]; assert bool(observed.valid_fresh_close)==valid
   if valid:assert abs(observed.close_price_return-val)<1e-10
   assert observed.round_quantity==sum(live[k] for k in ids) and observed.initial_quantity==live.get(k0,0)
   for f,v in [('round_remaining_cost',costs),('initial_remaining_cost',initial_cost)]:maxcosterr=max(maxcosterr,abs(float(observed[f])-float(v)))
   roundpaths[k0].append({'day':day,'value':val,'round_cost':float(costs),'initial_cost':float(initial_cost),'initial_live':k0 in live})
 # Author initial layer and round must match independent 0-to-0 cycles, all BUY costs and later ADD identity.
 assert set(rounds)==set(rr.index)
 for k0,r in rounds.items():
  x=rr.loc[k0]; assert r['open']==x.opened and r['sid']==x.sid and (r['closed'] or '')==('' if pd.isna(x.closed) else x.closed)
  assert abs(float(r['buy_cost'])-x.round_buy_cost)<1e-7
  assert len(r['layers'])-1==x.followup_buy_count and sum(layer[k]['kind']=='add' for k in r['layers'][1:])==x.followup_add_count
  assert abs(sum(float(z['round_cost']) for z in roundpaths[k0])-x.round_capital_days)<1e-6
  assert abs(sum(float(z['initial_cost']) for z in roundpaths[k0])-x.initial_capital_days)<1e-6
  assert abs(x.initial_pnl/x.initial_buy_cost-x.initial_return)<1e-12 and abs(x.round_pnl/x.round_buy_cost-x.round_return)<1e-12
  for pref in ['round','initial']:
   pp=roundpaths[k0] if pref=='round' else [z for z in roundpaths[k0] if z['initial_live']]; vs=np.array([z['value'] for z in pp]); finite=np.isfinite(vs); hit=np.flatnonzero(vs>=.05); complete=finite.all(); status=x[pref+'_status']
   space='OBSERVED_GE5' if len(hit) else ('UNKNOWN' if not complete else ('CLOSE_NO_UPSIDE' if max(vs)<=0 else 'CLOSE_UP_LT5'))
   prog='PROMOTED_BY_20' if np.any(vs[:20]>=.05) else ('UNKNOWN' if not finite[:20].all() else ('STALLED20' if len(pp)>=20 else ('EXIT_BEFORE20' if status=='CLOSED' else 'OPEN_CENSORED_BEFORE20')))
   assert len(pp)==x[pref+'_held_closes'] and int((~finite).sum())==x[pref+'_missing_closes'];assert space==x[pref+'_space_bucket'] and prog==x[pref+'_progress20'],(arm,k0,pref,space,prog,x[pref+'_progress20'])
   assert bool(x[pref+'_first5_time_known'])==(bool(finite[:hit[0]+1].all()) if len(hit) else complete)
   if complete:assert abs(max(vs)-x[pref+'_close_mfe'])<1e-10 and abs(min(vs)-x[pref+'_close_mae'])<1e-10
   else:assert pd.isna(x[pref+'_close_mfe']) and pd.isna(x[pref+'_close_mae'])
   assert abs(sum(z[pref+'_cost'] for z in pp[19:])-x[pref+'_capital_days_from20'])<1e-6
 assert maxcosterr<1e-7
 # Final PnL reconciles all layer terminal cash/dividends and original marked NAV.
 final_layer={int(t['id']):t for t in a['layers']}; last=snaps[arm][list(snaps[arm])[-1]]
 for k0,r in rounds.items():
  x=rr.loc[k0]; div=sum(D(final_layer[k]['dividend']) for k in r['layers']); cash=sum(D(final_layer[k]['cash']) for k in r['layers']); inventory=0.
  if r['closed']=='':
   source=px[r['sid']];vv=source['raw_close'].where(source['price_eligible'].eq(True) & source['observed_bar'].eq(True) & ~source['source_invalid'].eq(True) & ~source['synthetic_event_bar'].eq(True));mark=float(vv.loc[:'2026-05-15'].dropna().iloc[-1]);inventory=sum(live.get(k,0) for k in r['layers'])*mark
  assert abs(float(cash+div)+inventory-x.round_pnl)<1e-6
 closed=rr.round_status.eq('CLOSED'); assert int((~closed).sum())==67
 summary['arms'][arm]={'rounds':len(rr),'closed':int(closed.sum()),'open':int((~closed).sum()),'daily_held_paths':len(checked),'splits_replayed':splits,'partial_sells_replayed':partials,'capital_days':float(daily_cost_sum),'initial_capital_days':float(rr.initial_capital_days.sum()),'max_cost_difference':maxcosterr,'price_unknown_rounds':int(rr.round_path_status.eq('UNKNOWN').sum()),'closed_net':float(rr.loc[closed,'round_pnl'].sum()),'closed_wins':int((closed & rr.round_pnl.gt(0)).sum()),'open_mark':float(rr.loc[~closed,'round_pnl'].sum())}
# Verify displayed partitions from detail, denominator rather than authors metrics.
claims=[]
for arm,g in new.groupby('account'):
 for level in ['initial','round']:
  losses=g[g[level+'_status'].eq('CLOSED') & g[level+'_pnl'].lt(0)]; denom=-losses[level+'_pnl'].sum()
  for kind,col,cats in [('space',level+'_space_bucket',['CLOSE_NO_UPSIDE','CLOSE_UP_LT5']),('progress',level+'_progress20',['STALLED20','EXIT_BEFORE20'])]:
   for cat in cats:
    selected=g[g[col].eq(cat)];claims.append({'account':arm,'level':level,'bucket':cat,'n':len(selected),'closed_gross_loss_share':float(-losses.loc[losses[col].eq(cat),level+'_pnl'].sum()/denom),'capital_days_share':float(selected[level+'_capital_days'].sum()/g[level+'_capital_days'].sum()),'median_held_closes':float(selected[level+'_held_closes'].median())})
summary['claims']=claims
bad=[]
for p,h in freeze['source_hashes'].items():
 if hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()!=h:bad.append(p)
assert not bad
summary['frozen_original_sources_verified']=len(freeze['source_hashes']);summary['all_original_sources_unchanged']=True;summary['status']='PASS'
(O/'LOSS_AUDIT.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2));print(json.dumps(summary,ensure_ascii=False,indent=2))
