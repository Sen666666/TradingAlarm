"""Unified independent stock-round shadow arithmetic; never a financial account or live order."""
from pathlib import Path
import json,hashlib,sys,time,math
from decimal import Decimal as D
import pandas as pd,numpy as np
O=Path(__file__).resolve().parent;R=O.parent
U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
B=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025')
sys.path.insert(0,str(B/'code'))
from market_rules import version_on,market_identity_on,RuleUnavailable
from sector_account import QuantityRule,FeeComponent,FeeSchedule
NAV=D('1200000');INIT=NAV*D('.005');SLOT=NAV*D('.01');SLIP=D('.0005');END='2026-06-30'
WINDOWS=[('2022','2022-01-01','2022-12-31',None),('2024_924','2024-09-01','2024-12-31',None),('2026H1_SEMI','2026-01-01',END,'URFI881121')]
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
def fee(q,p,s,side,par):return sum(s.incremental(side,D(q)*p,{}, {},1,shares=q,par_value=par).values(),D(0))
started=time.monotonic()
assert not (O/'SELECTION_SEAL.json').exists(),'New output only; no implicit rerun'
protocol=dict(windows=WINDOWS,denominator='same day/same both-known stock members, fixed future 1709/90 research pool NON-PIT',event='FALSE->TRUE only for main study; UNKNOWN->TRUE and LEFT_CENSORED separately, never silently promoted. Full panel shifted before window filter.',selection='every same-industry both-known right3 stock; original I close state valid, e0/g ready, positive protection floor; first entry does not require fresh; record current-I start and most recent old I buy signal; mean previous20 observed amount through decision close descending then sid; top2 per event, no ex-post replacement',position='Independent slots, not a capital account. 1.2m reference NAV; initial max0.5%NAV per name, <=2 names/event; one add max0.5%NAV/name; slot capital max1%NAV; baseline fee-inclusive stop-reference loss cap0.125%NAV/slot; quantity sensitivity0.0625%,0.25% at identical entries. These are research choices, not user risk promises.',add='Only first unused original stock CP1 receipt, current I valid, industry current robust qualification TRUE, whole stock round net liquidation at close >0 after all fees, and rechecked at next open; no averaging down. One add maximum in this finite contract, no tuning.',exit='Core uses original I_structure_exit, next common open; add uses original CP1_add_protection with trailing max(I floor, fresh CP candidate). Industry decline only stops new buys/adds, never forced sell. Original account ACT/cash/global protection must also gate deployed strategy, but cannot be inferred for a new account from old account P&L.',execution='Signal known close, next common open +/-5bp; dated native commission/minimum5/levies/stamp/quantity rules; A-share T+1. Missing price, source switch/gap, corporate action/factor change => UNKNOWN (not dropped), right-censor => OPEN_CENSORED. Historical limit/suspension orderability UNKNOWN for every proxy fill.',resources='Original account next-open snapshot overlay is a separate necessary-condition rejection screen only, after its original reservations; does not prove positive admission nor reuse its trade P&L. Ends2026-05-15. Prices/indicators stop2026-06-30. All independent events may overlap and cannot be summed into NAV or claimed full-strategy win rate.',sample='All selected events and names, not first3 only; known-date case diagnostics kept separate; no threshold search; no full financial account run')
save('PROTOCOL.json',protocol)
md=R/'momentum_persistence_breadth_v1/canonical_mu3_comparison_v2';panel=pd.read_parquet(md/'COMMON_K_COMPARISON.parquet').sort_values(['sector','day']);cal=pd.DatetimeIndex(sorted(panel.day.unique()));dates={t:i for i,t in enumerate(cal)}
ps=pd.read_parquet(R/'pvr_persistence_breadth_v1/STOCK_DAILY.parquet');pr=ps.pivot(index='day',columns='sid',values='state');mk=pd.read_parquet(md/'KNOWN3.parquet');mr=pd.read_parquet(md/'RIGHT3.parquet');both=mk&pr.ge(0);rights={'M3':mr&both,'PVR3':pr.eq(1)&both}
roster=pd.read_csv(R/'pvr_persistence_breadth_v1/FIXED_MEMBERSHIP.csv');members=roster.groupby('sector_id').sid.apply(list).to_dict();sm={x['symbol']:x for x in read(U/'STOCK_MANIFEST.json')}
rules=read(B/'inputs-v2/market-rules.json');proxies=read(B/'inputs-v2/economic-protocol.json')['approved_proxy_ids'];names=rules['security_metadata'];hashes={str(p):sha(p) for p in [md/'COMMON_K_COMPARISON.parquet',md/'KNOWN3.parquet',md/'RIGHT3.parquet',R/'pvr_persistence_breadth_v1/STOCK_DAILY.parquet',U/'STOCK_MANIFEST.json',Path(__file__)]}
events=[]
for arm in rights:
 prev=panel.groupby('sector')[arm+'_candidate'].shift()
 for wn,lo,hi,sec in WINDOWS:
  z=panel.day.between(lo,hi)&panel[arm+'_candidate'].eq(1)&~prev.eq(1)
  if sec:z&=panel.sector.eq(sec)
  for idx,r in panel[z].iterrows():
   p=prev.loc[idx];typ='FALSE_TO_TRUE' if p==0 else 'UNKNOWN_TO_TRUE' if pd.notna(p) else 'LEFT_CENSORED'
   events.append(dict(event_id=f'{wn}|{arm}|{r.day.date()}|{r.sector}',window=wn,arm=arm,day=r.day,sector=r.sector,industry=r.sector_name,event_type=typ,N=r.N,K=r.K,n=r[arm+'_n'],share=r[arm+'_right_known'],diffusion=r[arm+'_delta3'],sector_action=r.sector_action,original_sector_permission=r.sector_authorization_usable))
e=pd.DataFrame(events).sort_values(['window','arm','day','sector']);e.to_csv(O/'ALL_EVENTS.csv',index=False)
print('EVENTS',e.groupby(['window','arm','event_type']).size().to_string(),flush=True)
facts={};cp={};liq={};istart={};lastbuy={};sources={}
for j,(sid,m) in enumerate(sm.items()):
 p=m['refs']['facts'];f=pd.read_parquet(p).loc[:END];q=pd.read_parquet(m['refs']['CP1_input']).loc[:END];facts[sid]=f;cp[sid]=pd.read_parquet(m['refs']['CP1']).loc[:END];liq[sid]=q.amount.where(q.amount.gt(0)).rolling(20,min_periods=20).mean();hashes[p]=sha(p);hashes[m['refs']['CP1']]=sha(m['refs']['CP1']);hashes[m['refs']['CP1_input']]=sha(m['refs']['CP1_input']);sources[sid]=next(p for p in m['source_sha256'] if p.endswith('/signal.parquet'))
 on=f.i_target.eq(1);start=on&(~on.shift(fill_value=False)|f.segment_id.ne(f.segment_id.shift()));ep=start.cumsum();dt=pd.Series(f.index,index=f.index);istart[sid]=dt.where(start).ffill().where(on);lastbuy[sid]=dt.where(f.i_buy.eq(True)&on).groupby(ep).ffill().where(on)
 if (j+1)%500==0:print('FACTS',j+1,round(time.monotonic()-started,1),flush=True)
rows=[]
for r in e.itertuples():
 ids=members[r.sector];rr=rights[r.arm].loc[r.day,ids];assert int(rr.sum())==r.n
 for sid in rr.index[rr]:
  f=facts[sid];d=r.day;fr=f.loc[d] if d in f.index else None;valid=bool(fr is not None and fr.i_target==1 and fr.e0_ready==1 and fr.g_ready==True and math.isfinite(fr.i_floor) and fr.i_floor>0);l=liq[sid].get(d,np.nan)
  rows.append(dict(event_id=r.event_id,window=r.window,arm=r.arm,day=d,sector=r.sector,industry=r.industry,event_type=r.event_type,sid=sid,name=names.get(sid,{}).get('name',''),right3=True,I_valid=valid,rank_amount20=l,rank_known=math.isfinite(l),I_start=istart[sid].get(d),last_I_buy=lastbuy[sid].get(d),I_buy_today=bool(fr.i_buy) if fr is not None else None,CP1_today=bool(cp[sid].loc[d,'receipt']) if d in cp[sid].index else None,I_floor=float(fr.i_floor) if valid else None))
c=pd.DataFrame(rows);c['selected']=False;c['rank']=np.nan
for _,g in c.groupby('event_id',sort=False):
 v=g[g.I_valid&g.rank_known].sort_values(['rank_amount20','sid'],ascending=[False,True]);c.loc[v.index,'rank']=range(1,len(v)+1);c.loc[v.head(2).index,'selected']=True
c.to_csv(O/'ALL_CANDIDATES.csv',index=False);sel=c[c.selected].copy();sel.to_csv(O/'SEALED_SELECTED.csv',index=False)
save('SELECTION_SEAL.json',dict(created=str(pd.Timestamp.now(tz='UTC')),hashes={str(O/n):sha(O/n) for n in ['PROTOCOL.json','ALL_EVENTS.csv','ALL_CANDIDATES.csv','SEALED_SELECTED.csv']},events=len(e),all_right_candidates=len(c),selected=len(sel),main_selected=int(sel.event_type.eq('FALSE_TO_TRUE').sum()),source_hashes=hashes))
print('SEALED',len(c),len(sel),round(time.monotonic()-started,1),flush=True)
# Forward evaluation starts only after the complete selection artifact is sealed.
raw={};meta={}
for sid in sel.sid.unique():
 p=sources[sid];raw[sid]=pd.read_parquet(p).loc[:END].reindex(cal);hashes[p]=sha(p)
 for day in []:pass
snap=read(R/'early_sector_probe_boundary_v1/ORIGINAL_OPEN_RESOURCES.json');snap={pd.Timestamp(x['day']):x for x in snap['rows']}
sectorstate={(arm,sec):g.set_index('day')[arm+'_candidate'] for arm in rights for sec,g in panel.groupby('sector')}
def getmeta(sid,d):
 key=(sid,str(d.date()))
 if key not in meta:
  s=str(d.date());identity=market_identity_on(rules,sid,s,proxies);v=version_on(rules['fee_versions'][identity['venue']],s,proxies)['schedule'];qr=QuantityRule(**version_on(rules['quantity_versions'][sid],s,proxies)['rule']);meta[key]=(qr,FeeSchedule(v['schedule_id'],tuple(FeeComponent(**x) for x in v['components'])),D(str(names[sid]['par_value'])))
 return meta[key]
def size(sid,d,price,floor,budget,riskmax,capacity):
 qr,fs,par=getmeta(sid,d);q=qr.buy_floor(min(int(budget/price),int(capacity)))
 while q>0:
  bf=fee(q,price,fs,'buy',par);sf=fee(q,floor*(1-SLIP),fs,'sell',par);risk=max(D(0),D(q)*(price-floor*(1-SLIP))+bf+sf)
  if D(q)*price+bf<=budget and risk<=riskmax:return q,bf,risk,fs,par
  q=qr.buy_floor(q-1)
 return 0,D(0),D(0),fs,par
def screen(r,d,q,p,bf,loss):
 s=snap.get(d)
 if not s:return 'UNKNOWN_AFTER_ACCOUNT_END',None
 nav=D(s['decision_NAV_exact']);bc=s['balance_components'];av=D(bc['available']);pending=D(s.get('original_pending_fees','0'));cap=D(q)*p;fee_nav=D(bc['nav'])-pending-bf;f=[]
 if cap+bf>av-nav*D('.1'):f.append('cash_or_original_10pct_reserve')
 if D(str(s['probe_capital']))+cap>fee_nav*D('.1'):f.append('probe_capital')
 if D(str(s['probe_risk']))+loss>fee_nav*D('.005'):f.append('probe_risk')
 ar=s.get('all_resources',[0,0,0]);sc=s.get('sector_resources',{}).get(r.sector,s.get('sectors',{}).get(r.sector,[0,0,0]));
 if D(str(ar[1]))+loss>fee_nav*D('.03'):f.append('account_risk')
 if D(str(sc[0]))+cap>fee_nav*D('.02'):f.append('new_probe_sector_2pct_cap')
 if D(str(sc[1]))+loss>fee_nav*D('.01'):f.append('sector_risk')
 if s.get('stock_quantities',{}).get(r.sid,0)>0:f.append('already_held_requires_add_contract')
 return '|'.join(f) if f else 'NECESSARY_SCREEN_ONLY_NOT_FULL_ADMISSION',float(av-nav*D('.1'))
def simulate(r):
 sid=r.sid;f=facts[sid];p=raw[sid];cps=cp[sid];t=dates[r.day];out=dict(event_id=r.event_id,window=r.window,arm=r.arm,event_type=r.event_type,day=r.day,sid=sid,name=r.name,industry=r.industry,selected_rank=r.rank,I_start=r.I_start,last_I_buy=r.last_I_buy,entry_status='UNKNOWN',historical_tradability='UNKNOWN',account_run=False)
 if t+1>=len(cal):return dict(out,status='NO_NEXT_OPEN')
 od=cal[t+1];out['entry_day']=od;rr=p.loc[od];prev=p.loc[r.day]
 if not np.isfinite(rr.raw_open) or rr.raw_open<=0:return dict(out,status='MISSING_NEXT_OPEN')
 if str(rr.source_kind)+'|'+str(rr.source_path)+'|'+str(rr.segment_id)!=str(prev.source_kind)+'|'+str(prev.source_path)+'|'+str(prev.segment_id):return dict(out,status='SOURCE_CHANGED_AT_ENTRY')
 fac=D(str(prev.adjustment_factor));
 if not np.isclose(rr.adjustment_factor,prev.adjustment_factor,rtol=1e-11):return dict(out,status='ACTION_OR_FACTOR_AT_ENTRY_UNKNOWN')
 px=D(str(rr.raw_open))*(1+SLIP);fl=D(str(r.I_floor))/fac
 if px<=fl:return dict(out,status='NEXT_OPEN_BELOW_PROTECTION')
 vv=p.loc[:r.day,'raw_volume'];vv=vv[vv.gt(0)]
 if len(vv)<20:return dict(out,status='PRIOR_VOLUME_UNKNOWN')
 capacity=int(vv.iloc[-20:].mean()*.01)
 try:q,bf,risk,fs,par=size(sid,od,px,fl,INIT,NAV*D('.00125'),capacity)
 except (RuleUnavailable,KeyError,ValueError) as ex:return dict(out,status='DATED_RULE_UNKNOWN',error=str(ex))
 out.update(raw_entry_open=float(rr.raw_open),entry_price=float(px),entry_q=q,entry_fee=float(bf),entry_risk=float(risk),floor_raw=float(fl),prior20_capacity=capacity)
 for cap in ['.000625','.0025']:
  qs,*_=size(sid,od,px,fl,INIT,NAV*D(cap),capacity);out['quantity_risk_'+cap]=qs
 if not q:return dict(out,status='MINIMUM_LOT_NOT_FUNDED')
 overlay,free=screen(r,od,q,px,bf,risk);out.update(original_resource_screen=overlay,original_after_reserve_cash=free,entry_status='CONDITIONAL_OPEN_PROXY')
 cashflow=-D(q)*px-bf;spent=-cashflow;totalfees=bf;core=q;add=0;addfloor=None;added=False;addpending=None;exitpending=None;addexitpending=False;actions=[];age=0;firstprof=None;firstfresh=None;negfresh=0;dropped=None;out['entry_gross']=float(D(q)*px)
 origin=(str(rr.source_kind),str(rr.source_path),str(rr.segment_id));factor=float(rr.adjustment_factor)
 def marknet(price,date):
  _,ss,pa=getmeta(sid,date);return cashflow+D(core+add)*price-fee(core+add,price,ss,'sell',pa)
 for k in range(t+1,len(cal)):
  d=cal[k];z=p.loc[d];day=str(d.date());age+=1
  if not np.isfinite(z.raw_open) or z.raw_open<=0:return dict(out,status='MISSING_OPEN_PATH_UNKNOWN',unknown_day=d,adds=int(added))
  if (str(z.source_kind),str(z.source_path),str(z.segment_id))!=origin:return dict(out,status='SOURCE_CHANGE_PATH_UNKNOWN',unknown_day=d,adds=int(added))
  if not np.isclose(z.adjustment_factor,factor,rtol=1e-11):return dict(out,status='CORPORATE_ACTION_OR_FACTOR_PATH_UNKNOWN',unknown_day=d,adds=int(added))
  if d not in f.index or not z.observed_bar or not z.price_eligible or not z.volume_eligible or z.source_invalid or not np.isfinite(z.raw_close):return dict(out,status='MISSING_OR_INVALID_CLOSE_PATH_UNKNOWN',unknown_day=d,adds=int(added))
  _,sfee,par=getmeta(sid,d);op=D(str(z.raw_open));sellpx=op*(1-SLIP)
  if exitpending and k>t+1:
   sq=core+add;sf=fee(sq,sellpx,sfee,'sell',par);cashflow+=D(sq)*sellpx-sf;totalfees+=sf;actions.append(dict(day=day,side='sell_all',q=sq,price=str(sellpx),fee=str(sf),reason=exitpending));return dict(out,status='COMPLETE_CONDITIONAL_STOCK_ROUND',exit_day=d,exit_price=float(sellpx),exit_reason=exitpending,net_pnl=float(cashflow),net_return_on_buy_cash=float(cashflow/spent),total_buy_cash=float(spent),all_fees=float(totalfees),adds=int(added),first_profitable_close=firstprof,first_CP_fresh=firstfresh,negative_CP_blocked=negfresh,industry_first_decline=dropped,actions=json.dumps(actions,ensure_ascii=False))
  if addexitpending and add:
   sf=fee(add,sellpx,sfee,'sell',par);cashflow+=D(add)*sellpx-sf;totalfees+=sf;actions.append(dict(day=day,side='sell_add',q=add,price=str(sellpx),fee=str(sf),reason='CP1_add_protection'));add=0;addexitpending=False
  if addpending:
   apfloor=addpending;addpending=None
   if marknet(sellpx,d)>0 and op>apfloor:
    buy=op*(1+SLIP);remaining=max(D(0),SLOT-D(core+add)*op);budget=min(INIT,remaining);cf=f.loc[cal[k-1],'i_floor'];cfraw=D(str(cf))/fac if np.isfinite(cf) else fl;existingrisk=max(D(0),D(core)*(buy-cfraw*(1-SLIP)));remainingrisk=max(D(0),NAV*D('.00125')-existingrisk);vol=p.iloc[:k].raw_volume;vol=vol[vol.gt(0)];acap=int(vol.iloc[-20:].mean()*.01);aq,af,ar,_,_=size(sid,d,buy,apfloor,budget,remainingrisk,acap)
    if aq:
     add=aq;addfloor=apfloor;added=True;cashflow-=D(aq)*buy+af;spent+=D(aq)*buy+af;totalfees+=af;actions.append(dict(day=day,side='buy_add',q=aq,price=str(buy),fee=str(af),prior_round_net_rechecked=True))
  fr=f.loc[d];cl=D(str(z.raw_close));net=marknet(cl*(1-SLIP),d)
  if net>0 and firstprof is None:firstprof=day
  qual=sectorstate[(r.arm,r.sector)].get(d,-1)
  if qual!=1 and dropped is None:dropped=day
  if not bool(fr.i_target):exitpending='I_structure_exit';continue
  if add and cl<=addfloor:addexitpending=True
  if add and not addexitpending:
   if np.isfinite(fr.i_floor):addfloor=max(addfloor,D(str(fr.i_floor))/fac)
   if bool(cps.loc[d,'receipt']) and np.isfinite(cps.loc[d,'candidate']):addfloor=max(addfloor,D(str(cps.loc[d,'candidate']))/fac)
  fresh=bool(cps.loc[d,'receipt'])
  if fresh and firstfresh is None:firstfresh=day
  if fresh and net<=0:negfresh+=1
  if fresh and not added and net>0 and qual==1 and not exitpending and np.isfinite(cps.loc[d,'candidate']) and np.isfinite(fr.i_floor):addpending=max(D(str(fr.i_floor)),D(str(cps.loc[d,'candidate'])))/fac
 return dict(out,status='OPEN_CENSORED_AT_2026_06_30',adds=int(added),first_profitable_close=firstprof,negative_CP_blocked=negfresh,industry_first_decline=dropped)
result=[]
for j,r in enumerate(sel.itertuples()):
 try:result.append(simulate(r))
 except Exception as ex:raise RuntimeError(f'{r.event_id} {r.sid}: {ex}') from ex
 if (j+1)%500==0:print('SIMULATED',j+1,round(time.monotonic()-started,1),flush=True)
z=pd.DataFrame(result);z.to_csv(O/'ALL_SHADOW_ROUNDS.csv',index=False)
summary=[]
for (win,arm,typ),g in z.groupby(['window','arm','event_type']):
 done=g[g.status.eq('COMPLETE_CONDITIONAL_STOCK_ROUND')];wins=done[done.net_pnl.gt(0)];loss=done[done.net_pnl.le(0)];summary.append(dict(window=win,arm=arm,event_type=typ,selected=len(g),conditional_entry=int(g.entry_status.eq('CONDITIONAL_OPEN_PROXY').sum()),completed_conditional=len(done),positive=len(wins),conditional_positive_fraction=len(wins)/len(done) if len(done) else None,mean_net_return=done.net_return_on_buy_cash.mean(),average_win_loss_cny=wins.net_pnl.mean()/(-loss.net_pnl.mean()) if len(wins) and len(loss) else None,any_add=int(done['adds'].gt(0).sum()),not_complete=len(g)-len(done),status_counts=g.status.value_counts().to_dict(),original_resource_screen=g.get('original_resource_screen',pd.Series(dtype=str)).value_counts().to_dict()))
save('SUMMARY.json',dict(rows=summary,seconds=time.monotonic()-started,full_account_runs=0,all_selected_covered=True,independent_overlapping_rounds=True,warning='Conditional independent stock rounds only; missing paths explicitly retained; not full strategy win rate or account return; no historical orderability proof; ACT/new-account capital unknown.'))
save('SOURCE_HASHES.json',hashes);save('OUTPUT_HASHES.json',{str(p):sha(p) for p in O.iterdir() if p.is_file() and p.name!='OUTPUT_HASHES.json'})
print('COMPLETE',round(time.monotonic()-started,1));print(pd.DataFrame(summary).drop(columns=['status_counts','original_resource_screen']).to_string(index=False))
