"""Explain actual frozen decisions and holdings, without running an account."""
from common import *
from cohort import environment
import pandas as pd
import gzip,collections

def source_rows(file,accounts):
 with gzip.open(file,'rt') as stream:
  for line in stream:
   head=line[:140]
   if not any('"at": "'+str(y)+'-' in head for y in range(2023,2027)):continue
   if not any('"account": "'+a+'"' in head for a in accounts):continue
   yield json.loads(line)

def main():
 out=HERE/'detail';out.mkdir(exist_ok=False)
 cal,score,h,cols,up,secrank=environment();datepos={d.date().isoformat():i for i,d in enumerate(cal)};meta=read(OLD/'inputs-v2/metadata.json');sf={sid:pd.read_parquet(SRC/'signals'/f'{sid}.parquet') for sid in IDS};accounts=[m+'__'+a+'_base' for m in MODES for a in ALLOCS]
 daily={(x['account'],x['at'][:10]):x for x in source_rows(SRC/'accounts/daily.jsonl.gz',accounts+['IX__S1_delay1'])}
 old_daily={(x['account'],x['at'][:10]):x for x in source_rows(OLD/'accounts-v2/daily.jsonl.gz',[a+'_base' for a in ALLOCS])}
 cached={};traces=[];snaps=[]
 def facts(sid,day,i):
  if sid not in cached:cached[sid]=pd.read_parquet(SRC/'signals'/f'{sid}.parquet',columns=['grade','e0_target','ix_target','z21','close','e0_floor'])
  f=cached[sid];at=f.index.searchsorted(pd.Timestamp(day),side='right')-1;row=f.iloc[at] if at>=0 else None
  return dict(symbol=sid,name=meta[sid]['name'],industry=meta[sid]['industry'],rs_h1=score[i,cols[sid]] if sid in cols else None,grade=row.grade if row is not None else None,ix_target=row.ix_target if row is not None else None,e0_target=row.e0_target if row is not None else None,z21=row.z21 if row is not None else None,observed_on_date=pd.Timestamp(day) in f.index,close_to_support=(row.close-row.e0_floor)/row.close if row is not None and pd.notna(row.e0_floor) else None)
 for d in source_rows(SRC/'accounts/decisions.jsonl.gz',accounts):
  aid,day=d['account'],d['at'][:10];mode,alloc=aid.split('__');alloc=alloc.split('_')[0];i=datepos[day];book=daily[aid,day];ee={e['symbol']:e for e in d['event_eligibility']};rejected=dict(d['first_rejected']);executor=dict(d['rejected']);occ={x['security_id']:x for x in d['occupancy']};considered=set(d['first_selected'])|set(rejected)
  for sid in IDS:
   f=sf[sid];row=f.loc[day] if pd.Timestamp(day) in f.index else None;event=bool(row[mode]) if row is not None else False;e=ee.get(sid);sector=meta[sid]['sector_id'];q=e['q'] if e else None;held=book['positions'].get(sid,0)>0;accepted=sid in d['accepted'];selreason=rejected.get(sid,executor.get(sid,''))
   if held:outcome='actual_holding'
   elif accepted:outcome='accepted_new_buy'
   elif not event:outcome='no_current_entry_event'
   elif q is None:outcome='qualification_unknown'
   elif q is False:outcome='qualification_false'
   elif selreason:outcome=selreason
   elif sid in occ:outcome='pending_buy_or_exit'
   else:outcome='eligible_not_allocated'
   peers=[s for s in considered if meta[s]['sector_id']==sector and s in cols and np.isfinite(score[i,cols[s]])];peers=sorted(peers,key=lambda s:(-score[i,cols[s]],s));sector_ids=sorted({meta[s]['sector_id'] for s in considered},key=lambda s:(-score[i,cols[s]] if np.isfinite(score[i,cols[s]]) else float('inf'),s))
   rank_in_sector=peers.index(sid)+1 if sid in peers else None;sr=sector_ids.index(sector)+1 if sector in sector_ids else None
   t=dict(account=aid,mode=mode,allocation=alloc,date=day,symbol=sid,name=meta[sid]['name'],industry=meta[sid]['industry'],event=event,raw_transition=bool(row['raw_'+mode]) if row is not None and mode!='IX' else event,grade=row.grade if row is not None else None,previous_grade=row.previous_grade if row is not None else None,e0_up=row.e0_target if row is not None else None,ix_up=row.ix_target if row is not None else None,z21=row.z21 if row is not None else None,stock_rs=score[i,cols[sid]],rs_horizon=h[i,cols[sid]],sector_rs=score[i,cols[sector]],sector_up=bool(up.iloc[i][sector]),sector_rank_all_up=secrank.iloc[i][sector],sector_rank_considered=sr,stock_rank_considered_sector=rank_in_sector,q=q,qualification_reasons=';'.join(e['reasons']) if e else '',held=held,pending=sid in occ and occ[sid]['pending_buy'],accepted=accepted,selected=sid in d['first_selected'],selection_reason=selreason,outcome=outcome,nav=float(book['nav']),available=float(book['available']),reserved=float(book['order_reserved']),inventory=float(book['inventory']),held_count=len(book['positions']),held_sectors=len({meta[s]['sector_id'] for s in book['positions']}),qualified_stock_count=len(d['eligible']))
   traces.append(t)
   if event and q is True and not held and not accepted and selreason:
    occupancy=[dict(**o,**facts(o['security_id'],day,i),selected_today=o['security_id'] in d['accepted']) for o in d['occupancy']]
    snaps.append(dict(**t,occupancy=occupancy,selected_today=[facts(s,day,i) for s in d['first_selected']],considered_sector_order=[dict(sector_id=s,industry=next((v['industry'] for v in meta.values() if v['sector_id']==s),s),rs=score[i,cols[s]]) for s in sector_ids]))
 df=pd.DataFrame(traces);df.to_parquet(out/'all-daily-traces.parquet',index=False);df.to_csv(out/'all-daily-traces.csv',index=False)
 write(out/'rejected-event-snapshots.json',snaps)
 event_summary=df.loc[df.event].groupby(['mode','allocation','symbol','outcome']).size().reset_index(name='event_days');event_summary.to_csv(out/'event-outcomes.csv',index=False)
 yearly=df.loc[df.event].assign(year=lambda a:a.date.str[:4]).groupby(['mode','allocation','symbol','year','outcome']).size().reset_index(name='event_days');yearly.to_csv(out/'event-outcomes-yearly.csv',index=False)
 cases=[]
 for sid in IDS:
  for year in range(2023,2027):
   matches=[s for s in snaps if s['account']=='IX__S0_base' and s['symbol']==sid and s['date'].startswith(str(year))]
   if matches:cases.append(matches[0])
 write(out/'first-missed-IX-S0-by-stock-year.json',cases)
 # Actual fills/campaigns are copied from the already-audited source, not simulated.
 c=pd.read_csv(SRC/'analysis/campaigns.csv');c=c.loc[c.symbol.isin(IDS)&c.account.isin(accounts+['IX__S1_delay1'])].copy();oc=pd.read_csv(OLD/'analysis-v2/campaigns.csv');oc=oc.loc[oc.symbol.isin(IDS)&oc.account.isin([a+'_base' for a in ALLOCS])].copy();oc.account='E0__'+oc.account;c=pd.concat([oc,c],ignore_index=True)
 profiles=pd.read_csv(SRC/'analysis/entry-profiles.csv');op=pd.read_csv(OLD/'entry-profiles/profiles.csv');op.account='E0__'+op.account;profiles=pd.concat([op,profiles],ignore_index=True);profs={(p.account,p.symbol,p.entry_at):p for _,p in profiles.iterrows()};objects={};actual=[]
 for _,camp in c.iterrows():
  aid,sid=camp.account,camp.symbol;isold=aid.startswith('E0__');srcaid=aid.split('__',1)[1] if isold else aid
  if aid not in objects:objects[aid]=read((OLD/'accounts-v2' if isold else SRC/'accounts')/f'{srcaid}.json')
  obj=objects[aid];reserves={x['order_id']:x['decision_at'] for x in obj['audit_log'] if x['kind']=='reserve'};exits={x['event_id']:x['at'] for x in obj['audit_log'] if x['kind']=='exit_request'}
  buyrow=next(x for x in obj['audit_log'] if x['kind']=='fill' and x['receipt']['side']=='buy' and x['receipt']['security_id']==sid and x['receipt']['at']==camp.entry_at);decision=reserves[buyrow['order_id']][:10];i=datepos.get(decision);book=(old_daily.get((srcaid,decision)) if isold else daily.get((aid,decision)));signal=sf[sid].loc[decision] if pd.Timestamp(decision) in sf[sid].index else None
  ex=None;exsig=None
  if camp.closed:
   sellrow=next(x for x in obj['audit_log'] if x['kind']=='fill' and x['receipt']['side']=='sell' and x['receipt']['security_id']==sid and x['receipt']['at']==camp.exit_at);ex=exits[sellrow['order_id']][:10];exsig=sf[sid].loc[ex] if pd.Timestamp(ex) in sf[sid].index else None
  record=camp.to_dict();record.update(decision_date=decision,decision_nav=float(book['nav']) if book else None,investment=float(camp.buy_gross+camp.buy_fees),investment_vs_initial=float((camp.buy_gross+camp.buy_fees)/1e6),investment_vs_decision_nav=float((camp.buy_gross+camp.buy_fees)/float(book['nav'])) if book else None,entry_grade=signal.grade if signal is not None else None,exit_signal_date=ex,exit_grade=exsig.grade if exsig is not None else None,e0_still_up_on_exit=bool(exsig.e0_target) if exsig is not None else None,exit_reason=exsig.ix_exit_reason if exsig is not None and not isold else 'E0_structure',entry_in_recent=camp.entry_at[:10]>=START)
  actual.append(record)
 af=pd.DataFrame(actual);af.to_csv(out/'actual-focus-campaigns.csv',index=False);write(out/'actual-focus-campaigns.json',actual)
 # Coverage describes saved states and actual holding days, not a new portfolio return.
 coverage=[];prices=[]
 for sid in IDS:
  f=sf[sid].loc[START:END];logchange=np.log(f.close).diff();positive=logchange.clip(lower=0);price_return=f.close.iloc[-1]/f.close.iloc[0]-1;maxdd=float(-(f.close/f.close.cummax()-1).min());prices.append(dict(symbol=sid,name=meta[sid]['name'],price_return=price_return,max_price_drawdown=maxdd,observations=len(f),**{m:int(f[m].sum()) for m in MODES}))
  for mode,col in [('E0','e0_target'),('IX','ix_target')]:
   prior=f[col].shift().fillna(0).eq(1);coverage.append(dict(symbol=sid,kind=mode+'_saved_state',qualified_days=int(f[col].eq(1).sum()),observations=len(f),qualified_fraction=float(f[col].eq(1).mean()),positive_log_gain_coverage=float(positive[prior].sum()/positive.sum())))
  for aid in accounts:
   a=df.loc[df.account.eq(aid)&df.symbol.eq(sid)];coverage.append(dict(symbol=sid,kind=aid,qualified_days=int(a.held.sum()),observations=len(a),qualified_fraction=float(a.held.mean()),positive_log_gain_coverage=None))
 pd.DataFrame(coverage).to_csv(out/'coverage.csv',index=False);write(out/'price-context.json',prices)
 write(out/'receipt.json',dict(recorded_at=now(),passed=True,base_account_traces=len(df),actual_copied_cycles=len(actual),rejected_event_snapshots=len(snaps),fixed_first_miss_cases=len(cases),new_accounts=0,ranking_basis='actual considered candidates, ranked before capacity constraints; actual outcomes from immutable logs',no_old_output_changes=True))
 print('S0 cases',[(x['date'],x['name'],x['outcome'],x['stock_rs'],x['sector_rank_all_up'],x['stock_rank_considered_sector']) for x in cases],flush=True)
 print(event_summary.query("allocation=='S0'").to_string(index=False),flush=True)
 print(af.loc[af.entry_at.str[:10].ge('2023-01-01'),['account','symbol','entry_at','exit_at','net_return','decision_nav','investment','exit_signal_date','exit_grade','e0_still_up_on_exit','exit_reason']].to_string(index=False),flush=True)
if __name__=='__main__':main()
