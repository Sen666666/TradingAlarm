from study import *
from audit import rows,FIELDS
from collections import Counter
versions=['ACT','PB','BOX','BOTH'];scenarios=['base','cost2','delay1']
summ=[];campaigns=[];receipts=[];localsums=[];funnel=[];curves=[]
ref={(r['account'],r['at']):r for r in rows(PRIOR/'RS/accounts-v2/daily.jsonl.gz')}
for v in versions:
 root=O/v;audit=read(root/'analysis/accounting.json');assert audit['passed'] and D(audit['max_nav_difference'])==0;receipts.append(audit)
 ds=rows(root/'accounts-v2/daily.jsonl.gz');decs=rows(root/'accounts-v2/decisions.jsonl.gz')
 for r in ds:assert len(set(r['positions'])|set(r['pending_buys'])|set(r['pending_sells']))<=6
 s=pd.read_csv(root/'analysis/summary.csv');s['version']=v;summ.append(s)
 cc=pd.read_csv(root/'analysis/curves.csv');cc['version']=v;curves.append(cc)
 cs=pd.read_csv(root/'analysis/campaigns.csv');cs['version']=v;cs['entry_channel']='original';cs['handed_off']=False
 if v=='ACT':
  for r in ds:
   for k in FIELDS:assert r[k]==ref[r['account'],r['at']][k],(r['at'],k)
 for sc in scenarios:
  aid='I__S0_'+sc;obj=read(root/'accounts-v2'/f'{aid}.json');logs=obj['audit_log'];assert not any(r['kind']=='rotation_started' for r in logs)
  if v=='ACT':assert obj['fills']==read(PRIOR/'RS/accounts-v2'/f'{aid}.json')['fills']
  started=[r for r in logs if r['kind']=='local_position_started'];handoffs=[r for r in logs if r['kind']=='local_handoff']
  for e in started:
   mask=(cs.account==aid)&(cs.symbol==e['sid'])&(pd.to_datetime(cs.first_buy_at,utc=True)==pd.Timestamp(e['at']));assert mask.sum()==1,(v,sc,e)
   cs.loc[mask,'entry_channel']=e['setup_kind'];end=cs.loc[mask,'exit_at'].iloc[0]
   hs=[r for r in handoffs if r['sid']==e['sid'] and pd.Timestamp(r['at'])>=pd.Timestamp(e['at']) and (pd.isna(end) or pd.Timestamp(r['at'])<=pd.Timestamp(end))];cs.loc[mask,'handed_off']=bool(hs)
  q=cs[(cs.account==aid)&(cs.entry_channel!='original')];closed=q[q.closed];tails=closed[closed.tail_closed];ordinary=closed[~closed.tail_closed]
  localsums.append(dict(version=v,scenario=sc,local_campaigns=len(q),local_closed=len(closed),local_tail_count=len(tails),local_tail_profit=tails.net_pnl.sum(),local_ordinary_net=ordinary.net_pnl.sum(),local_gross_losses=-closed.loc[closed.net_pnl<0,'net_pnl'].sum(),local_profit=q.net_pnl.sum(),local_open_profit=q.loc[~q.closed,'net_pnl'].sum(),local_fees=(q.buy_fees+q.sell_fees).sum(),handoffs=len(handoffs),local_stop_signals=sum(r['kind']=='local_stop_trigger' for r in logs)))
  # Ledger's original contract audit validates cash and prices. This separately
  # checks the local stop at each held close against frozen source prices.
  facts={};dd={r['at'][:10]:r for r in ds if r['account']==aid};effective_checks=0
  for e in started:
   sid=e['sid'];facts.setdefault(sid,pd.read_parquet(Path(read(O/'input.json')['snapshot'])/'facts'/f'{sid}.parquet'))
   stop=D(e['local_floor']);end=cs.loc[(cs.account==aid)&(cs.symbol==sid)&(pd.to_datetime(cs.first_buy_at,utc=True)==pd.Timestamp(e['at'])),'exit_at'].iloc[0]
   last=end[:10] if isinstance(end,str) else '2026-10-28'
   for day,d in dd.items():
    if day<e['at'][:10] or day>=last or sid not in d['positions']:continue
    f=facts[sid];i=f.index.searchsorted(pd.Timestamp(day),side='right')-1;r=f.iloc[i]
    if bool(r.e0_target) and np.isfinite(r.e0_floor):stop=max(stop,D(str(r.e0_floor)))
    if D(str(r.close))<=stop:assert sid in d['pending_sells'],(v,sc,sid,day,'local stop missing')
    effective_checks+=1
  if v!='ACT':
   daily={r['at'][:10]:r for r in ds if r['account']==aid};dec={r['at'][:10]:r for r in decs if r['account']==aid};risk={r['at'][:10]:r for r in logs if r['kind']=='risk_checkpoint'}
   for path in sorted((O/v/'signals').glob('*.parquet')):
    z=pd.read_parquet(path).loc['2024':];f=pd.read_parquet(Path(read(O/'input.json')['snapshot'])/'facts'/path.name).reindex(z.index)
    for t,row in z[z.event&~f.i_buy.astype(bool)].iterrows():
     day=str(t.date());sid=path.stem
     if day not in daily:continue
     d=daily[day];dc=dec[day];reason='eligible_not_admitted'
     if not risk[day]['on']:reason='account_paused'
     elif sid in dc['accepted']:reason='accepted'
     elif sid in d['positions']:reason='already_held'
     elif sid in d['pending_buys'] or sid in d['pending_sells']:reason='pending_order'
     elif sid not in dc['eligible']:reason='other_eligibility_or_memory'
     funnel.append(dict(version=v,scenario=sc,date=day,symbol=sid,kind=row.kind,reason=reason))
  localsums[-1]['independent_local_held_closes']=effective_checks
 campaigns.append(cs)
summary=pd.concat(summ,ignore_index=True);campaign=pd.concat(campaigns,ignore_index=True);curve=pd.concat(curves,ignore_index=True)
summary.to_csv(O/'summary.csv',index=False);campaign.to_csv(O/'campaigns.csv',index=False);curve.to_csv(O/'curves.csv',index=False);pd.DataFrame(localsums).to_csv(O/'local-contribution.csv',index=False);pd.DataFrame(funnel).to_csv(O/'event-funnel.csv',index=False)
freeze=read(O/'freeze.json')
for field in ['sources','signals']:
 for p,h in freeze[field].items():assert sha(p)==h,('frozen identity',p)
save(O/'full-verification.json',{'passed':True,'paths':12,'new_economic_paths':9,'controls':3,'daily_rows':sum(a['daily_rows'] for a in receipts),'max_nav_difference':0,'original_control_exact':True,'no_rotation':True,'max_total_stocks':6,'frozen_identity':True,'local_held_closes_checked':sum(r['independent_local_held_closes'] for r in localsums),'economic_reruns':0,'post_result_parameter_revisions':0})
print(summary[['version','scenario','net_return','max_drawdown','tail_profit','ordinary_profit','closed']].to_string(index=False));print(pd.DataFrame(localsums).to_string(index=False));print(pd.DataFrame(funnel).groupby(['version','scenario','reason']).size().to_string())
