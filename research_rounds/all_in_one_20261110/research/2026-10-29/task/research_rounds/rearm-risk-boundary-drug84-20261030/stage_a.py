from shared import *
T=time.monotonic();assert not (O/'CASE_RESULTS.csv').exists()
prior=read(W/'cross-sector-exit-design-20261030/SOURCE_IDENTITY.json');assert all(sha(p)==h for p,h in prior['source_sha256'].items())
cycles,audit,daily=original();ids={c['symbol'] for c in cycles.values()};m=market(ids);cal=sorted(daily);barid={d:i for i,d in enumerate(cal)};sys.path.insert(0,str(V));from risk_boundary_v2 import RiskBoundary,NegativeReceipt
assert sha(V/'risk_boundary_v2.py')==read(TECH/'FREEZE.json')['sha256'][str(V/'risk_boundary_v2.py')]
arith=loadmod('drug84_original_arithmetic',R/'pv-strength-b5-20261025/code/arithmetic.py');proof=read(PH/'event-validation.json');pr={x['symbol']:x for x in proof['records'] if x['sector']=='DRUG'}
sourcefiles=[O/'PROTOCOL.txt',O/'shared.py',Path(__file__),V/'risk_boundary_v2.py',V/'SPECIFICATION.txt',TECH/'stage_a.py',TECH/'stage_b.py',W/'down-event-transfer-local-20261030/study.py',DRUG/'S0/accounts-v2/ACT__S0_base.json',DRUG/'S0/accounts-v2/daily.jsonl.gz',DRUG/'S0/analysis/campaigns.csv',PRE/'manifest.json',PH/'event-validation.json'];identity={str(p):sha(p) for p in sourcefiles};facts={};events={};signals={};valid={}
for s in sorted(ids):
 fp=PRE/'facts'/f'{s}.parquet';sp=PRE/'signals'/f'{s}.parquet';ep=PH/'events/DRUG'/f'{s}.parquet'
 for p,h in [(fp,pr[s]['inputs'][str(fp)]),(sp,pr[s]['inputs'][str(sp)]),(ep,pr[s]['output_sha256'])]:assert sha(p)==h;identity[str(p)]=h
 f=pd.read_parquet(fp);sg=pd.read_parquet(sp,columns=['volume','observed_bar','source_invalid','synthetic_event_bar']);ev=pd.read_parquet(ep);assert f.index.equals(ev.index) and f.close.equals(ev.close) and f.segment_id.equals(ev.segment_id);facts[s]=f;events[s]=ev;signals[s]=sg;valid[s]={}
 for seg,g in f.groupby('segment_id',sort=False):
  z=g[['close']].join(sg[['volume']]);valid[s][int(seg)]=z[z.gt(0).all(axis=1)&np.isfinite(z).all(axis=1)]
 for ref in [m.bundle.series[s].record['raw'],m.bundle.series[s].record['adjustment']['actions']]:assert sha(ref['path'])==ref['sha256'];identity[ref['path']]=ref['sha256']
save(O/'FREEZE.json',dict(at=datetime.now(timezone.utc).isoformat(),before_drug_v2_behavior_and_returns=True,mother_ids=list(cycles),core_unchanged=True,source_sha256=identity))
checks=Counter();sigma_rows=[];node=next(n for n in ast.parse((TECH/'stage_a.py').read_text()).body if isinstance(n,ast.FunctionDef) and n.name=='sigma_at');exec(compile(ast.Module(body=[node],type_ignores=[]),str(TECH/'stage_a.py'),'exec'),globals())
buys={x['receipt']['security_id']+'|'+x['receipt']['at'][:10]:x for x in audit if x['kind']=='fill' and x['receipt']['side']=='buy'};ent=[x['receivable'] for x in audit if x['kind']=='dividend_accrual'];eps=[];handoffs=[];rr=[];cases=[];mother=[];paths=[];ca=[];blocked=[]
for cid,camp in sorted(cycles.items(),key=lambda x:(x[1]['entry_at'],x[1]['symbol'])):
 s=camp['symbol'];f=facts[s];ev=events[s];sg=signals[s];buy=buys[cid];q0=buy['receipt']['shares'];entry=stamp(camp['entry_at']);closed=camp['closed']=='True';endday=camp['exit_at'][:10] if closed else '2026-10-27';end=H.at(endday,dt(15,10));contracts=[x for x in audit if x['kind']=='entry_contract' and x['order_id']==buy['order_id']];assert len(contracts)==1;floor=float(contracts[0]['floor_signal']);request=[x for x in audit if x['kind']=='exit_request' and x['sid']==s and camp['entry_at']<=x['at']<=str(end)];assert len(request)==int(closed);req=request[0]['at'] if request else '';seg=int(f.loc[pd.Timestamp(entry.date()),'segment_id']);source=f'{s}|source={seg}';unit=f'DRUG_frozen_economic|{s}|source={seg}'
 right=[x for x in ent if x['security_id']==s and entry<=stamp(x['ex_at'])<=end];assert sum((D(x['net_local']) for x in right),Z)==D(camp['dividends']);basis=D(camp['buy_gross'])+D(camp['buy_fees'])
 c=RiskBoundary(cycle_id=cid,symbol=s,source_id=source,unit_id=unit,shares=q0,e0_floor=floor);added='';firstwarn='';firstq=None;arms=[];rearms=[];hd=[];fullunknown=[];behaviorunknown=[];stopped=False;stopq=None;rows0=len(rr)
 days=[d for d in cal if entry.date().isoformat()<=d<=endday and (not closed or d<camp['exit_at'][:10])]
 for day in days:
  ds=daily[day];q=int(ds['positions'].get(s,0));assert q==q0 and q>0;checks['actual_quantity_identity']+=1;d=pd.Timestamp(day);tm=H.at(day,dt(15,10));mk=m.latest_mark(s,tm);rights=sum((D(x['net_local']) for x in right if stamp(x['ex_at'])<=tm),Z);nav=D(q)*mk.raw_price+rights
  native=d in f.index;eventknown=d in ev.index;observed=bool(d in sg.index and sg.loc[d,'observed_bar'] and not sg.loc[d,'source_invalid'] and not sg.loc[d,'synthetic_event_bar']);source_unknown=not(native and eventknown and observed)
  if source_unknown:fullunknown.append(day)
  paths.append(dict(cycle_id=cid,day=day,shares=q,raw_mark=mk.raw_price,mark_known_at=mk.known_at,accrued_dividend=rights,nav_mark_pnl=nav-basis,basis=basis,source_unknown=source_unknown))
  if stopped:continue
  c.sync_execution(shares=q,buy_pending=s in ds['pending_buys'],exit_order_pending=s in ds['pending_sells']);old=f.loc[:day].iloc[-1];original_exit=bool(day==req[:10] or not bool(next(x['on'] for x in audit if x['kind']=='risk_checkpoint' and x['at'][:10]==day)) or not bool(old.i_target));receipt=None;sigma=None;event=int(ev.loc[d,'event']) if eventknown else None
  if original_exit:assert day==req[:10],(cid,day,req,'original priority identity')
  if event==-1:
   eid=f'{s}|source={seg}|confirmed={day}|native_event=-1';receipt=NegativeReceipt(eid,s,source,barid[day]);sigma,sstatus=sigma_at(s,seg,day,eid)
   if not original_exit and s not in ds['pending_buys'] and not firstwarn:firstwarn=day;firstq=q
  if eventknown and event!=0:assert pd.isna(ev.loc[d,'pivot_date']) or str(ev.loc[d,'pivot_date'])[:10]<=day;checks['event_confirmation_not_backdated']+=1
  rc=factor=None;nf=None;unit_here=unit
  if native:
   z=f.loc[d];unit_here=f'DRUG_frozen_economic|{s}|source={int(z.segment_id)}';rc=float(z.raw_close);factor=float(z.factor);nf=float(z.i_floor) if pd.notna(z.i_floor) else None
   assert math.isclose(rc*factor,float(z.close),rel_tol=EPS,abs_tol=0);checks['price_factor_unit_exact']+=1
   if observed:assert math.isclose(float(m.raw[s].loc[d,'close']),rc,rel_tol=EPS,abs_tol=0);checks['execution_raw_close_exact']+=1
  if not observed:rc=factor=None
  ep0=c.episodes;phase=c.phase;out=c.on_close(bar=barid[day],raw_close=rc,factor=factor,unit_id=unit_here,negative=receipt,sigma=sigma,updated_floor=nf,floor_known=native and nf is not None,event_feed_known=eventknown,original_exit=original_exit);out.update(date=day,symbol=s,native_event=event,event_id=receipt.event_id if receipt else None);rr.append(out)
  if out['current_unknown']:behaviorunknown.append(day)
  if c.episodes>ep0:
   arms.append(day)
   if c.episodes>1:rearms.append(day)
   eps.append(dict(cycle_id=cid,episode=c.episodes,arm_date=day,event_id=receipt.event_id,P=c.anchor,sigma=c.frozen_sigma,B=c.boundary,original_floor=c.e0_floor,is_rearm=c.episodes>1))
  if phase=='PROTECTED' and c.phase=='OBSERVING':hd.append(day);handoffs.append(dict(cycle_id=cid,date=day,episode=c.episodes,floor=c.e0_floor,B=c.boundary))
  if c.exit_locked:
   if c.exit_reason=='risk_boundary':added=day;stopq=q;assert c.phase=='EXIT_PENDING';stopped=True
   else:assert original_exit;c.sync_execution(shares=0,buy_pending=False,exit_order_pending=False);assert c.phase=='CLOSED';stopped=True
 if added and not firstwarn:blocked.append(dict(cycle_id=cid,reason='no_original_compliant_warning_for_shared_fee_anchor'))
 cases.append(dict(cycle_id=cid,symbol=s,name=camp['name'],closed=closed,entry=camp['entry_at'],original_request=req,original_exit=camp['exit_at'],endpoint=str(end),first_warning=firstwarn,warning_quantity=firstq,added_request=added,protection_episodes=c.episodes,rearm_count=max(c.episodes-1,0),arm_dates=json.dumps(arms),rearm_dates=json.dumps(rearms),handoff_dates=json.dumps(hd),shares_at_added=stopq,final_phase=c.phase,unknown_dates=json.dumps(fullunknown),unknown_count=len(fullunknown),behavior_unknown_dates=json.dumps(behaviorunknown),behavior_rows=len(rr)-rows0))
 mother.append(dict(cycle_id=cid,old=s,new='',name=camp['name'],date=firstwarn,old_quantity=firstq,unknown_event_days=json.dumps(fullunknown),unknown_before_first=json.dumps([d for d in fullunknown if firstwarn and d<firstwarn]),original_entry=camp['entry_at'],original_exit=camp['exit_at'],endpoint=str(end),closed=closed,dividends=camp['dividends']))
 # Company-action coordinate audit, original actual entitlement only.
 for a in m.actions.get(s,[]):
  ad=H.at(a['effective_date'],dt(0,0))
  if not(entry<=ad<=end):continue
  priorf=f[f.index<pd.Timestamp(a['effective_date'])];afterf=f[f.index>=pd.Timestamp(a['effective_date'])];pre=priorf.iloc[-1];post=afterf.iloc[0];cash=D(a.get('signal_cash_per_old_share',a['cash_per_old_share']));ratio=D(a.get('signal_split_ratio',a['split_ratio']));expected=float(D(str(pre.raw_close))/((D(str(pre.raw_close))-cash)/ratio));found=float(post.factor/pre.factor);ok=math.isclose(expected,found,rel_tol=EPS,abs_tol=0);assert ok
  rights=[x for x in right if x['ex_at'][:10]==a['effective_date']];assert D(a['cash_per_old_share'])==0 or len(rights)==1
  ca.append(dict(cycle_id=cid,date=a['effective_date'],factor_match=ok,entitlement_records=len(rights),same_price_units=True,pay_date_unknown=a.get('paid_at') is None,within_behavior=not added or a['effective_date']<=added))
 print(json.dumps(dict(cycle=cid,new_request=added,episodes=c.episodes,unknown=fullunknown),ensure_ascii=False),flush=True)
export(O/'FROZEN_CASES.csv',mother);export(O/'CASE_RESULTS.csv',cases);export(O/'ACTUAL_CLOSE_PATHS.csv',paths);export(O/'PROTECTION_EPISODES.csv',eps);export(O/'HANDOFFS.csv',handoffs);export(O/'SIGMA_PREFIX_CHECKS.csv',sigma_rows);export(O/'CORPORATE_ACTION_CHECKS.csv',ca);save(O/'ROW_AUDIT.json',rr)
assert all(x['protection_after']>=x['protection_before'] for x in rr);assert all(sha(p)==h for p,h in identity.items())
samples=[]
for test in [lambda c:bool(c['first_warning']),lambda c:any(x['cycle_id']==c['cycle_id'] for x in ca),lambda c:not c['closed'],lambda c:bool(c['unknown_count'])]:
 candidate=next((c['cycle_id'] for c in cases if test(c)),None)
 if candidate and candidate not in samples:samples.append(candidate)
save(O/'STAGE_A_GATE.json',dict(passed=not blocked,cases=84,closed=80,open=4,added_requests=sum(bool(c['added_request']) for c in cases),warning_cycles=sum(bool(c['first_warning']) for c in cases),rearm_cases=sum(c['rearm_count']>0 for c in cases),rearm_episodes=sum(c['rearm_count'] for c in cases),unknown_cycles=[c['cycle_id'] for c in cases if c['unknown_count']],unknown_original_window_rows=sum(c['unknown_count'] for c in cases),behavior_unknown_rows=sum(bool(x['current_unknown']) for x in rr),behavior_rows=len(rr),checks=dict(checks),company_actions=len(ca),blocked=blocked,sample_ids=samples,source_hashes_unchanged=True,core_changed=False,new_economic_paths=0,seconds=time.monotonic()-T));print(json.dumps(read(O/'STAGE_A_GATE.json'),ensure_ascii=False),flush=True)
