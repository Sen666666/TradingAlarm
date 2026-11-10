import time
START=time.monotonic()
from local import *
import signal,traceback
STAGE=sys.argv[1];assert STAGE in ['sample','full'];OUT=O/STAGE;OUT.mkdir(exist_ok=False)
BUDGET=read(O/'COMPUTE_BUDGET.json');remaining=180-BUDGET['seconds']-(time.monotonic()-START);assert remaining>0
signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('180-second total compute budget')));signal.setitimer(signal.ITIMER_REAL,remaining)
status='started';results=[];curves=[];audits=[];checks=0
try:
 assert read(O/'STATE_TESTS.json')['passed'] and read(O/'ACTUAL_R_REPRODUCTION.json')['passed'];freeze=read(O/'FREEZE.json');assert all(sha(Path(p))==h for p,h in freeze['sha256'].items())
 allunits=read(O/'UNITS.json');units=[u for u in allunits if STAGE=='full' or u['unit_id'] in freeze['sample_units']]
 if STAGE=='full':assert read(O/'sample/VERIFICATION.json')['passed']
 for sec in ['TECH','DRUG']:
  subset=[u for u in units if u['sector']==sec];ids={u['symbol'] for u in subset};m=market(sec,ids);feed=Feed(sec,ids);print(dict(stage=STAGE,sector=sec,provider_loaded=len(ids),elapsed=time.monotonic()-START),flush=True);contexts={st:loadcase(sec,st) for st in ['base','delay1']}
  for u in subset:
   cc=contexts[u['stress']];s=u['symbol'];seed=stamp(u['seed_at']);end=at(u['end_at'][:10]);stop=stamp(u['stop_signal']);daylist=[d for d in cc['ds'] if seed.date().isoformat()<=d['at'][:10]<=end.date().isoformat()]
   if not u['actionable']:
    eq=D(u['seed_cash'])+sum((D(x['net_local']) for x in u['seed_claims']),Z)
    for arm in ['R','G','N']:results.append(dict(unit_id=u['unit_id'],sector=sec,stress=u['stress'],symbol=s,name=u['name'],arm=arm,actionable=False,status='common_prefix_no_complete_risk_flat',initial_equity=u['initial_equity'],seed_equity=eq,final_equity=eq,net_contribution=eq-D(u['initial_equity']),after_seed_profit=Z,full_fees=u['prefix_fees'],new_fees=Z,buys=0,sells=0,new_risk_requests=0,applications=0,accepted=0,gate_rejected=0,budget_rejected=0,held_closes=0,waiting_closes=0,first_restore=None,inventory_time=Z,unknown_closes=0,terminal_shares=0,terminal_claim=sum((D(x['net_local']) for x in u['seed_claims']),Z),max_drawdown_after_seed=Z,initial_private_cash=u['seed_cash'],cap=u['target_cap_at_seed']))
    continue
   for arm in ['R','G','N']:
    a=RiskSlice(sid=s,unit_id=u['unit_id'],group=u['group'],cap=int(u['target_cap_at_seed']),old_B=u['old_B'],seed_at=seed,cash=D(u['seed_cash']),claims=u['seed_claims'],delay=1 if u['stress']=='delay1' else 0,fractional=m.protocol['fractional_split_policy']);book=Independent(a);bal=book.check(a,m,s,seed);seedEq=bal['nav'];peak=seedEq;maxdd=Z;held=waiting=unknown=0;inventory_time=Z;apps=accepted=greject=breject=0;firstrestore=None;equity=[]
    for d in daylist:
     day=d['at'][:10];op=at(day,9,30);cl=at(day)
     if op>seed:
      for action in m.actions.get(s,[]):
       if action['effective_date']==day:H.action(a,m,s,action)
      H.pay(a,m,op)
      if s in a.exits:
       w=m.window(s,op,'sell',1)
       if w:a.fill_exit(s,w)
      if s in a.buys:
       w=m.window(s,op,'buy',1);fr=feed.row(s,day);factor=float(fr.factor) if fr is not None else None
       if w:
        bf=a.fill_buy(s,w,factor)
        if bf and firstrestore is None:firstrestore=str(bf.at)
      H.pay(a,m,op);book.check(a,m,s,op)
     H.pay(a,m,cl);a.expire_day_buys(cl);ob=feed.obs(s,day,u['group']);fr=feed.row(s,day);full=cl>=stop or (fr is not None and pd.notna(fr.i_target) and not bool(fr.i_target));quote=m.quote(s,cl);clock=A.Clock(cl,m.sessions['A'][bisect.bisect_right(m.sessions['A'],cl)],cl.date());sig=feed.sigma(s,day,ob['segment']) if ob['event']==-1 and a.quantity(s) and ob['source_known'] else None;z=a.close(clock=clock,quote=quote,ob=ob,sigma=sig,full=full)
     native=bool(ob['native'] and bool(feed.f[s].loc[pd.Timestamp(day),'i_buy']));pa=cc['pa'].get(d['at']);el=next((x for x in pa['decisions'][-1]['eligibility'] if x['security_id']==s),None) if pa else None;Q=el['q'] if el is not None else None
     if a.quantity(s) and (not ob['event_known'] or ob['raw_close'] is None or not ob['source_known']):unknown+=1
     if not full and native and Q is True and cc['act'][d['at']]['on'] and quote is not None and a.quantity(s)<a.cap and s not in a.buys and s not in a.exits:
      apps+=1;ok,why=a.submit(arm=arm,clock=clock,quote=quote,floor=ob['floor'],native_I=native,Q=Q,budget=D(d['nav'])*D('.15'));accepted+=int(ok);greject+=int(why=='floor_below_B_or_unknown');breject+=int(why=='insufficient_budget_or_quantity')
      a.extra.append(dict(kind='restore_application',at=cl,floor=ob['floor'],oldB=a.gate_B,ok=ok,why=why,available=a.available))
     bal=book.check(a,m,s,cl);v=bal['nav'];peak=max(peak,v);maxdd=max(maxdd,1-v/peak);held+=int(a.quantity(s)>0);waiting+=int(a.quantity(s)==0);inventory_time+=bal['inventory'];curves.append(dict(unit_id=u['unit_id'],arm=arm,at=cl,nav=v,inventory=bal['inventory'],available=bal['available'],claim=bal['dividend_receivable'],shares=a.quantity(s),gate_B=a.gate_B,ended=a.ended));equity.append(v)
    assert daylist and daylist[-1]['at'][:10]==end.date().isoformat();final=book.check(a,m,s,end);fills=a.fills
    results.append(dict(unit_id=u['unit_id'],sector=sec,stress=u['stress'],symbol=s,name=u['name'],arm=arm,actionable=True,status='conditional_local_path',initial_equity=u['initial_equity'],seed_equity=seedEq,final_equity=final['nav'],net_contribution=final['nav']-D(u['initial_equity']),after_seed_profit=final['nav']-seedEq,full_fees=D(u['prefix_fees'])+a.fees_cny,new_fees=a.fees_cny,buys=sum(f.side=='buy' for f in fills),sells=sum(f.side=='sell' for f in fills),new_risk_requests=sum(x['kind']=='independent_risk_request' for x in a.extra),applications=apps,accepted=accepted,gate_rejected=greject,budget_rejected=breject,held_closes=held,waiting_closes=waiting,first_restore=firstrestore,inventory_time=inventory_time,unknown_closes=unknown,terminal_shares=a.quantity(s),terminal_claim=final['dividend_receivable'],max_drawdown_after_seed=maxdd,initial_private_cash=u['seed_cash'],cap=u['target_cap_at_seed'],max_residual=book.maximum))
    audits.append(dict(unit_id=u['unit_id'],arm=arm,source_seed=u,fills=fills,audit=a.audit_log,extra=a.extra));checks+=1
   if STAGE=='sample' or len(results)%30==0:print(dict(stage=STAGE,unit=u['unit_id'],results=len(results),seconds=time.monotonic()-START),flush=True)
 export(OUT/'unit-results.csv',results);pd.DataFrame(H.encoded(curves)).to_parquet(OUT/'equity.parquet',index=False)
 with gzip.open(OUT/'audit.jsonl.gz','wt',compresslevel=1) as f:
  for r in audits:f.write(json.dumps(H.encoded(r),ensure_ascii=False,allow_nan=False)+'\n')
 if STAGE=='full':
  sample=pd.read_csv(O/'sample/unit-results.csv',dtype=str).fillna('').set_index(['unit_id','arm']);full=pd.read_csv(OUT/'unit-results.csv',dtype=str).fillna('').set_index(['unit_id','arm']);pd.testing.assert_frame_equal(sample,full.loc[sample.index],check_exact=True)
 assert all(sha(Path(p))==h for p,h in freeze['sha256'].items());save(OUT/'VERIFICATION.json',dict(passed=True,units=len(units),results=len(results),self_financing_paths=checks,accounting_max_residual=max([D(r.get('max_residual','0')) for r in results] or [Z]),sample_full_equal=STAGE=='full',seconds=time.monotonic()-START,scope='dedicated risk capital local paths, not original P portfolio'));status='complete'
except BaseException as ex:
 save(OUT/'ERROR.json',dict(error=repr(ex),traceback=traceback.format_exc()));raise
finally:
 signal.setitimer(signal.ITIMER_REAL,0);elapsed=time.monotonic()-START;BUDGET['seconds']+=elapsed;BUDGET['stages'].append(dict(stage=STAGE,status=status,seconds=elapsed));save(O/'COMPUTE_BUDGET.json',BUDGET);print(dict(stage=STAGE,status=status,seconds=elapsed,total=BUDGET['seconds']),flush=True)
