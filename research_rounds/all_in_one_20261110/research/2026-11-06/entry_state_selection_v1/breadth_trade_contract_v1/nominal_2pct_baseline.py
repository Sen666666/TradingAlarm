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
NAV=D('1200000');INIT=NAV*D('.02');SLOT=NAV*D('.04');SLIP=D('.0005');END='2026-06-30'
WINDOWS=[('2022','2022-01-01','2022-12-31',None),('2024_924','2024-09-01','2024-12-31',None),('2026H1_SEMI','2026-01-01',END,'URFI881121')]
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
def fee(q,p,s,side,par):return sum(s.incremental(side,D(q)*p,{}, {},1,shares=q,par_value=par).values(),D(0))
DEST=O/'nominal_2pct_baseline'
def save(n,x):(DEST/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
started=time.monotonic()
seal=read(O/'SELECTION_SEAL.json');assert all(sha(p)==h for p,h in seal['hashes'].items()),'Selection drift'
assert not (DEST/'ALL_SHADOW_ROUNDS.csv').exists()
md=R/'momentum_persistence_breadth_v1/canonical_mu3_comparison_v2';panel=pd.read_parquet(md/'COMMON_K_COMPARISON.parquet').sort_values(['sector','day']);cal=pd.DatetimeIndex(sorted(panel.day.unique()));dates={t:i for i,t in enumerate(cal)}
sm={x['symbol']:x for x in read(U/'STOCK_MANIFEST.json')};rules=read(B/'inputs-v2/market-rules.json');proxies=read(B/'inputs-v2/economic-protocol.json')['approved_proxy_ids'];names=rules['security_metadata'];hashes=seal['source_hashes'].copy();rights={'M3':None,'PVR3':None}
sel=pd.read_csv(O/'SEALED_SELECTED.csv',parse_dates=['day','I_start','last_I_buy']);facts={};cp={};sources={}
for sid in sel.sid.unique():
 m=sm[sid];facts[sid]=pd.read_parquet(m['refs']['facts']).loc[:END];cp[sid]=pd.read_parquet(m['refs']['CP1']).loc[:END];sources[sid]=next(p for p in m['source_sha256'] if p.endswith('/signal.parquet'))
save('EVALUATION_AMENDMENT.json',dict(reason='Correct truncated prior-volume warmup. Preserve sealed choices. Added nominal2pct baseline only after first0p5pct results and parent direction; not preregistered. Existing core fees retained in total-slot risk residual.',evaluation_script_sha256=sha(Path(__file__))))
# Forward evaluation starts only after the complete selection artifact is sealed.
raw={};history={};meta={}
for sid in sel.sid.unique():
 p=sources[sid];history[sid]=pd.read_parquet(p).loc[:END];raw[sid]=history[sid].reindex(cal);hashes[p]=sha(p)
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
 if D(str(sc.get('capital',0) if isinstance(sc,dict) else sc[0]))+cap>fee_nav*D('.02'):f.append('new_probe_sector_2pct_cap')
 if D(str(sc.get('risk',0) if isinstance(sc,dict) else sc[1]))+loss>fee_nav*D('.01'):f.append('sector_risk')
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
 vv=history[sid].loc[:r.day,'raw_volume'];vv=vv[vv.gt(0)]
 if len(vv)<20:return dict(out,status='PRIOR_VOLUME_UNKNOWN')
 capacity=int(vv.iloc[-20:].mean()*.01)
 try:q,bf,risk,fs,par=size(sid,od,px,fl,INIT,NAV*D('.0025'),capacity)
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
    buy=op*(1+SLIP);remaining=max(D(0),SLOT-D(core+add)*op);budget=min(INIT,remaining);cf=f.loc[cal[k-1],'i_floor'];cfraw=D(str(cf))/fac if np.isfinite(cf) else fl;existingrisk=max(D(0),D(core)*(buy-cfraw*(1-SLIP))+bf+fee(core,cfraw*(1-SLIP),sfee,'sell',par));remainingrisk=max(D(0),NAV*D('.0025')-existingrisk);vol=history[sid].loc[history[sid].index<d,'raw_volume'];vol=vol[vol.gt(0)];acap=int(vol.iloc[-20:].mean()*.01);aq,af,ar,_,_=size(sid,d,buy,apfloor,budget,remainingrisk,acap)
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
z=pd.DataFrame(result);z.to_csv(DEST/'ALL_SHADOW_ROUNDS.csv',index=False)
summary=[]
for (win,arm,typ),g in z.groupby(['window','arm','event_type']):
 done=g[g.status.eq('COMPLETE_CONDITIONAL_STOCK_ROUND')];wins=done[done.net_pnl.gt(0)];loss=done[done.net_pnl.le(0)];summary.append(dict(window=win,arm=arm,event_type=typ,selected=len(g),conditional_entry=int(g.entry_status.eq('CONDITIONAL_OPEN_PROXY').sum()),completed_conditional=len(done),positive=len(wins),conditional_positive_fraction=len(wins)/len(done) if len(done) else None,mean_net_return=done.net_return_on_buy_cash.mean(),average_win_loss_cny=wins.net_pnl.mean()/(-loss.net_pnl.mean()) if len(wins) and len(loss) else None,any_add=int(done['adds'].gt(0).sum()),not_complete=len(g)-len(done),status_counts=g.status.value_counts().to_dict(),original_resource_screen=g.get('original_resource_screen',pd.Series(dtype=str)).value_counts().to_dict()))
save('SUMMARY.json',dict(rows=summary,seconds=time.monotonic()-started,full_account_runs=0,all_selected_covered=True,independent_overlapping_rounds=True,warning='Conditional independent stock rounds only; missing paths explicitly retained; not full strategy win rate or account return; no historical orderability proof; ACT/new-account capital unknown.'))
save('SOURCE_HASHES.json',hashes);save('OUTPUT_HASHES.json',{str(p):sha(p) for p in DEST.iterdir() if p.is_file() and p.name!='OUTPUT_HASHES.json'})
print('COMPLETE',round(time.monotonic()-started,1));print(pd.DataFrame(summary).drop(columns=['status_counts','original_resource_screen']).to_string(index=False))
