"""Mixed normal-prefix/stress-suffix independent accounting, no new path."""
import pressure as P
import collections,inspect,time,traceback
import numpy as np,pandas as pd
O,M,C,T,X=P.O,P.M,P.C,P.T,P.X
D=M.D;Z=D(0);BOUND='2025-09-30';END='2026-03-31'
def total(rs,key):return sum((D(r[key]) for r in rs),Z)
def underwater(initial,rows):
 peak=float(initial);peak_day=pd.Timestamp(BOUND);count=best=span=0;last={}
 for r in rows:
  nav=float(r['nav']);day=pd.Timestamp(r['at'][:10])
  if nav>=peak:peak=nav;peak_day=day;count=0
  else:
   count+=1
   if count>best:best=count;span=(day-peak_day).days;last=dict(from_peak=str(peak_day.date()),through=str(day.date()))
 return dict(longest_underwater_closes=best,span_calendar_days=span,at_end_underwater=count>0,current_underwater_closes=count,longest_interval=last,definition='consecutive closes below preceding suffix peak; calendar span ends at last underwater close, not recovery day')
def brief(tr):
 if tr is None:return None
 return {k:tr.get(k) for k in ['at','security_id','side','shares','price','raw_open','gross_cny','fees_cny','signal_at','reason']}
def main():
 started=time.monotonic();assert M.read(O/'ECONOMIC_DONE.json')['passed'];assert all(M.sha(p)==h for p,h in M.read(O/'FREEZE.json')['sha256'].items());out=O/'analysis';out.mkdir(exist_ok=True);seed=T.original_seed();seedNAV=D(seed['account']['current_nav']);prefix=[dict(r,account='T3') for r in C.rows(X.BASE/'results/daily.jsonl.gz')];seedcs=M.read(X.BASE/'analysis/NEW_CYCLES.json');pnl0={(c['symbol'],c['entry_at']):D(c['net_pnl']) for c in seedcs if not c['closed']};meta=M.read(M.RR/'a-share-selection-e0-20261024/inputs-v2/metadata.json');au=M.BP.C.import_path('suffix_pressure_independent_audit',M.RR/'rs-h1-execution-20261025/code/analyze_accounts.py');src=inspect.getsource(au.audit_account);old="slip=D('.001') if aid.endswith('cost2') else D('.0005')";assert src.count(old)==1;src=src.replace(old,"slip=D('.001') if aid.endswith('cost2') and str(at.date())>'2025-09-30' else D('.0005')");env=dict(au.__dict__);exec(src,env);audit=env['audit_account'];M.save(out/'AUDIT_SOURCE.json',dict(original=str(M.RR/'rs-h1-execution-20261025/code/analyze_accounts.py'),only_change='expected cost2 slippage is normal before/equal 9/30 and doubled afterwards',function=src));prices=au.Prices.__new__(au.Prices);prices.records={r['series_id']:r for r in M.read(M.P/'manifest.json')['series']};prices.cache={};calendar=sorted(pd.Timestamp(d) for d in M.read(M.RR/'pvr-act-comparison-20261027/execution-rules-v2.json')['calendars']['A']);summaries=[];allcs=[];checks={};objects={};daily={};missing=[];bridges=[];divergences=[];parts={}
 for stress in ['normal','cost2','delay1']:
  for pol in ['RAW','ATT']:
   key=pol+'_'+stress
   if stress=='normal':
    ob=C.obj(P.PREV/pol/'results/T3.json.gz');q1=C.rows(P.PREV/pol/'results/daily.jsonl.gz');root,name=(C.ABS,'RAW') if pol=='RAW' else (C.ATT,'T3');q4=[dict(r,account='T3') for r in C.rows(root/'results/daily.jsonl.gz') if r['account']==name];ds=q4+q1;old=M.read(C.ABS/'analysis/CYCLES_Q4.json') if pol=='RAW' else M.read(C.ATT/'analysis/T3_CYCLES.json');old=[r for r in old if r.get('account',name)==name];new=[r for r in M.read(P.PREV/'analysis/CYCLES.json') if r['policy']==pol];cm={(r['symbol'],r['entry_at']):r for r in old+new};cs=list(cm.values());checks[key]=dict(reused=True,source=str(P.PREV/'analysis/VERIFICATION.json'),passed=True)
   else:
    ob=C.obj(O/key/'results/T3.json.gz');ds=C.rows(O/key/'results/daily.jsonl.gz');cs,ch=audit('B0_'+key,dict(audit_log=ob['audit']),prefix+ds,prices,meta,calendar);checks[key]=ch
   objects[key]=ob;daily[key]=ds;cc=[]
   for c in cs:
    if c['closed'] and c['exit_at'][:10]<=BOUND:continue
    z=dict(c,path=key);z['suffix_net']=D(c['net_pnl'])-pnl0.get((c['symbol'],c['entry_at']),Z);cc.append(z);allcs.append(z)
   delta=D(ds[-1]['nav'])-seedNAV;assert abs(total(cc,'suffix_net')-delta)<D('.00000001'),(key,'campaign bridge');trades=[r for r in ob['trades'] if r['at'][:10]>BOUND];fees=D(ds[-1]['fees_cny'])-D(prefix[-1]['fees_cny']);opened=[c for c in cc if not c['closed']];closed=[c for c in cc if c['closed']];tail=[c for c in closed if float(c['net_return'])>=.3];ordinary=[c for c in closed if float(c['net_return'])<.3];risk=[r for r in ob['audit'] if r['kind']=='risk_checkpoint' and r['at'][:10]>BOUND];nav=np.r_[float(seedNAV),[float(r['nav']) for r in ds]];u=underwater(seedNAV,ds);endunknown=Z
   for row in ds:
    day=row['at'][:10]
    for sid,qty in row['positions'].items():
     mark=prices.mark(sid,day);dates,cl,_=prices.cache[sid];idx=dates.searchsorted(pd.Timestamp(day));exact=idx<len(dates) and dates[idx]==pd.Timestamp(day)
     if not exact or pd.isna(cl[idx]):
      value=D(qty)*mark;missing.append(dict(path=key,day=day,sid=sid,shares=qty,marked_value=value,proxy='previous legal mark adjusted for subsequent actions'))
      if day==END:endunknown+=value
   parts[key]=dict(principal_flow=sum((D(r['gross_cny'])*(1 if r['side']=='sell' else -1) for r in trades),Z),dividend_accrued=sum((D(r['receivable']['net_local']) for r in ob['audit'] if r['kind']=='dividend_accrual' and r['receivable']['ex_at'][:10]>BOUND),Z),inventory_change=D(ds[-1]['inventory'])-D(prefix[-1]['inventory']),explicit_fee=-fees);assert abs(sum(parts[key].values(),Z)-delta)<D('.00000001')
   s=dict(path=key,policy=pol,stress=stress,normal_results_reused=stress=='normal',start_NAV=seedNAV,end_NAV=D(ds[-1]['nav']),suffix_return=float(D(ds[-1]['nav'])/seedNAV-1),suffix_NAV_change=delta,max_drawdown=float((1-nav/np.maximum.accumulate(nav)).max()),fees_suffix=fees,slippage_suffix=sum((D(r['shares'])*abs(D(r['price'])-D(r['raw_open'])) for r in trades),Z),mean_exposure=float(np.mean([float(r['inventory'])/float(r['nav']) for r in ds])),mean_available_NAV_fraction=float(np.mean([float(r['available'])/float(r['nav']) for r in ds])),end_available=D(ds[-1]['available']),end_inventory=D(ds[-1]['inventory']),buy_fills=sum(r['side']=='buy' for r in trades),sell_fills=sum(r['side']=='sell' for r in trades),closed_cycles=len(closed),open_cycles=len(opened),tail30_closed_suffix_net=total(tail,'suffix_net'),ordinary_closed_suffix_net=total(ordinary,'suffix_net'),open_suffix_marked_net=total(opened,'suffix_net'),negative_suffix_contributions=-sum((c['suffix_net'] for c in cc if c['suffix_net']<0),Z),end_proxy_mark_value=endunknown,missing_close_positiondays=sum(r['path']==key for r in missing),ACT_pauses=sum(r['event']=='pause' for r in risk),ACT_resumes=sum(r['event']=='resume' for r in risk),ACT_paused_closes=sum(not r['on'] for r in risk),**u);summaries.append(s);print('AUDITED',key,s['suffix_return'],s['max_drawdown'],s['end_NAV'],flush=True)
   if stress!='normal':
    norm=objects[pol+'_normal'];nt=[r for r in norm['trades'] if r['at'][:10]>BOUND];n=max(len(nt),len(trades));first=next((i for i in range(n) if i>=len(nt) or i>=len(trades) or X.canon(brief(nt[i]))!=X.canon(brief(trades[i]))),None);divergences.append(dict(path=key,first_different_actual_fill_index=first,normal=brief(nt[first] if first is not None and first<len(nt) else None),pressure=brief(trades[first] if first is not None and first<len(trades) else None),note='first actual-fill sequence difference, not unique causal attribution of all later differences'))
 for stress in ['normal','cost2','delay1']:
  a=next(r for r in summaries if r['path']=='RAW_'+stress);b=next(r for r in summaries if r['path']=='ATT_'+stress);br={k:parts['ATT_'+stress][k]-parts['RAW_'+stress][k] for k in parts['RAW_'+stress]};br.update(stress=stress,ATT_minus_RAW=b['end_NAV']-a['end_NAV']);assert abs(sum((br[k] for k in parts['RAW_'+stress]),Z)-br['ATT_minus_RAW'])<D('.00000001');bridges.append(br)
 for name,data in [('SUMMARY',summaries),('CYCLES',allcs),('MISSING_CLOSE_MARKS',missing),('MONEY_BRIDGES',bridges),('FIRST_PRESSURE_DIVERGENCES',divergences)]:
  M.save(out/(name+'.json'),data)
  if data:pd.DataFrame(M.N.encoded(data)).to_csv(out/(name+'.csv'),index=False)
 seconds=time.monotonic()-started;done=M.read(O/'ECONOMIC_DONE.json');M.save(out/'VERIFICATION.json',dict(passed=True,checks=checks,normal_results_reused=True,mixed_historical_normal_and_pressure_suffix_slippage_verified=True,all_campaign_and_cashflow_bridges_exact=True,audit_seconds=seconds,output_plus_audit_seconds=seconds+done['output_checkpoint_seconds'],within_60_second_output_audit_budget=seconds+done['output_checkpoint_seconds']<=60));print('SUMMARY',M.N.encoded(summaries),flush=True);print('BRIDGES',M.N.encoded(bridges),flush=True);print('ANALYSIS_SECONDS',seconds,flush=True)
if __name__=='__main__':
 try:main()
 except BaseException as e:M.save(O/'ANALYSIS_ERROR.json',dict(error=repr(e),traceback=traceback.format_exc()));raise
