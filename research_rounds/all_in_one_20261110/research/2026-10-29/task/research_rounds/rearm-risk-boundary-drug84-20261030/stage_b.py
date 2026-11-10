from shared import *
T=time.monotonic();stage=sys.argv[1];assert stage in ['sample','full'];dest=O/stage;dest.mkdir(exist_ok=False)
freeze=read(O/'FREEZE.json');assert all(sha(p)==h for p,h in freeze['source_sha256'].items());gate=read(O/'STAGE_A_GATE.json');assert gate['passed'] and not gate['blocked'];cycles,audit,daily=original();beh={x['cycle_id']:x for x in csv.DictReader((O/'CASE_RESULTS.csv').open())};mother=list(csv.DictReader((O/'FROZEN_CASES.csv').open()));paths=list(csv.DictReader((O/'ACTUAL_CLOSE_PATHS.csv').open()));path_by={k:[x for x in paths if x['cycle_id']==k] for k in cycles};calendar=sorted(daily);actualfills=[x for x in audit if x['kind']=='fill'];ent=[x['receivable'] for x in audit if x['kind']=='dividend_accrual'];events=mother if stage=='full' else [e for e in mother if e['cycle_id'] in gate['sample_ids']];ids={e['old'] for e in events};m=market(ids)
for e in mother:
 if e['old_quantity']:q=D(e['old_quantity']);assert q==q.to_integral_value();e['old_quantity']=int(q)
source=[Path(__file__),O/'PROTOCOL.txt',O/'shared.py',O/'STAGE_A_GATE.json',O/'CASE_RESULTS.csv',O/'FROZEN_CASES.csv',O/'ACTUAL_CLOSE_PATHS.csv',W/'down-event-transfer-local-20261030/study.py']
if stage=='sample':save(O/'ECONOMIC_FREEZE.json',dict(at=datetime.now(timezone.utc).isoformat(),before_drug_economics=True,sha256={str(p):sha(p) for p in source},mother_ids=[e['cycle_id'] for e in mother],sample_ids=gate['sample_ids']))
ef=read(O/'ECONOMIC_FREEZE.json');assert all(sha(p)==h for p,h in ef['sha256'].items())
checks=Counter();maxres=Z;results=[];curves=[];logs=[];originalchecks=[];execution=[]
names=['near','seed','consume','marks_at','snapshot'];prev=W/'down-event-transfer-local-20261030/study.py';nodes=[n for n in ast.parse(prev.read_text()).body if isinstance(n,ast.FunctionDef) and n.name in names];assert len(nodes)==5;exec(compile(ast.Module(body=nodes,type_ignores=[]),str(prev),'exec'),globals())
def endpoints(e):
 t=H.at(e['date'],dt(15,10));first=m.sessions['A'][bisect.bisect_right(m.sessions['A'],t)];end=stamp(e['endpoint']);return t,first,end,end,'original_exit_or_fixed_cutoff'
def risk(values):
 peak=values[0];dd=Z
 for v in values:peak=max(peak,v);dd=max(dd,ONE-v/peak)
 return min(values)/values[0]-ONE,dd
loadsec=time.monotonic()-T
for n,e in enumerate(events):
 cid=e['cycle_id'];c=cycles[cid];be=beh[cid];basis=D(c['buy_gross'])+D(c['buy_fees']);end=stamp(e['endpoint']);newday=be['added_request'];conditional=bool(int(be['unknown_count']));closed=c['closed']=='True';olddiv=[x for x in ent if x['security_id']==e['old'] and stamp(c['entry_at'])<=stamp(x['ex_at'])<=end];assert sum((D(x['net_local']) for x in olddiv),Z)==D(c['dividends']);initialq=next(x['receipt']['shares'] for x in actualfills if x['receipt']['security_id']==e['old'] and x['receipt']['side']=='buy' and x['receipt']['at']==c['entry_at'])
 if not e['date']:
  vs=[basis]+[basis+D(x['nav_mark_pnl']) for x in path_by[cid]]+([basis+D(c['net_pnl'])] if closed else []);mn,dd=risk(vs)
  for cost in [1,2]:
   for arm in ['A','B']:results.append(dict(cycle_id=cid,symbol=e['old'],name=c['name'],cost=cost,arm=arm,closed=closed,endpoint=e['endpoint'],original_exit=c['exit_at'],original_net=c['net_pnl'],basis=basis,original_return=c['net_return'],first_warning='',new_request='',rearm_count=be['rearm_count'],conditional_missing=conditional,unknown_dates=be['unknown_dates'],final_equity=basis+D(c['net_pnl']),full_cycle_net=D(c['net_pnl']),full_cycle_return=D(c['net_pnl'])/basis,full_fees=D(c['buy_fees'])+D(c['sell_fees']),dividend=D(c['dividends']),first_sell=c['exit_at'],last_sell=c['exit_at'],sold_quantity=initialq if closed else 0,sell_fill_count=1 if closed else 0,final_shares=int(c['final_shares']),terminal_inventory=D(c['market_value']),terminal_claim=D(c['dividends']),terminal_sale_receivable=Z,min_full_cycle_return=mn,max_full_cycle_DD=dd,holding_close_observations=len(path_by[cid]),cash_close_after_trigger=0,execution_unknown='',reused_fact=True,original_pretrigger_pnl=D(c['net_pnl']),trigger_equity='',fees_after_trigger=Z))
  originalchecks.append(dict(cycle_id=cid,normal_original=c['net_pnl'],reproduced=c['net_pnl'],residual=Z,reused_without_warning=True));continue
 t,first,*_=endpoints(e);states=[]
 for cost in [1,2]:
  for arm in ['A','B']:
   st=seed(e,cost,'A');st['arm']=arm;st['windows']=[];states.append(st);snapshot(st,e,t,'trigger_close')
 for day in calendar[calendar.index(str(first.date())):bisect.bisect_right(calendar,str(end.date()))] if first<=end else []:
  op=H.at(day,dt(9,30));cl=H.at(day,dt(15,10))
  for st in states:
   a=st['a']
   for act in m.actions.get(e['old'],[]):
    if act['effective_date']==day:H.action(a,m,e['old'],act)
   H.pay(a,m,op)
   for sid in tuple(a.exits):
    q=a.quantity(sid);w=m.window(sid,op,'sell',st['cost']);fill=a.fill_exit(sid,w) if w else None;st['windows'].append(dict(at=op,quantity_before=q,quantity_after=a.quantity(sid),window_known=w is not None,sell_allowed=w.sell_allowed if w else None,filled=fill is not None,exit_pending=sid in a.exits))
   H.pay(a,m,op);snapshot(st,e,op,'open');H.pay(a,m,cl)
   if a.quantity(e['old']) and e['old'] not in a.exits:
    orig=day==be['original_request'][:10];new=st['arm']=='B' and bool(newday) and day==newday
    if orig or new:
     quote=m.quote(e['old'],cl)
     if quote is None:st['unknowns'].append(day+':exit_quote_unknown')
     else:a.request_exit(quote,H.A.Clock(cl,m.sessions['A'][bisect.bisect_right(m.sessions['A'],cl)],cl.date()));st['requests'].append(dict(sid=e['old'],at=cl,reason='original_I_or_ACT' if orig else 'frozen_v2_boundary'))
   snapshot(st,e,cl,'close')
 for st in states:
  sr=st['snapshots'][-1];assert sr['at']==end;prefix=[basis]+[basis+D(x['nav_mark_pnl']) for x in path_by[cid] if x['day']<=e['date']];near(prefix[-1],st['I0']);mn,dd=risk(prefix+[x['nav'] for x in st['snapshots'][1:]]);sells=[x for x in st['fills'] if x['side']=='sell'];close=[x for x in st['snapshots'] if x['phase']=='close'];net=sr['nav']-basis
  r=dict(cycle_id=cid,symbol=e['old'],name=c['name'],cost=st['cost'],arm=st['arm'],closed=closed,endpoint=e['endpoint'],original_exit=c['exit_at'],original_net=c['net_pnl'],basis=basis,original_return=c['net_return'],first_warning=e['date'],new_request=newday,rearm_count=be['rearm_count'],conditional_missing=conditional,unknown_dates=be['unknown_dates'],final_equity=sr['nav'],full_cycle_net=net,full_cycle_return=net/basis,full_fees=D(c['buy_fees'])+sr['fees'],dividend=sr['dividend'],first_sell=sells[0]['at'] if sells else '',last_sell=sells[-1]['at'] if sells else '',sold_quantity=sum(x['shares'] for x in sells),sell_fill_count=len(sells),final_shares=st['a'].quantity(e['old']),terminal_inventory=sr['inventory'],terminal_claim=sr['claim'],terminal_sale_receivable=sr['sale_receivable'],min_full_cycle_return=mn,max_full_cycle_DD=dd,holding_close_observations=sum(x['day']<=e['date'] for x in path_by[cid])+sum(x['inventory']>0 for x in close),cash_close_after_trigger=sum(x['inventory']==0 for x in close),execution_unknown='|'.join(st['unknowns']),reused_fact=False,original_pretrigger_pnl=st['prior_pnl'],trigger_equity=st['I0'],fees_after_trigger=sr['fees'])
  if st['arm']=='A' and st['cost']==1:
   assert net==D(c['net_pnl']),(cid,net,c['net_pnl']);assert sr['dividend']==D(c['dividends']);assert r['final_shares']==int(c['final_shares']);assert r['full_fees']==D(c['buy_fees'])+D(c['sell_fees'])
   if closed:assert len(sells)==1 and str(sells[0]['at'])==c['exit_at'] and sells[0]['gross']==D(c['sell_gross']) and sells[0]['fees']==D(c['sell_fees'])
   originalchecks.append(dict(cycle_id=cid,normal_original=c['net_pnl'],reproduced=net,residual=Z,reused_without_warning=False));checks['A_normal_exact']+=1
  if st['arm']=='B' and newday:
   ns=[x for x in st['requests'] if x['reason']=='frozen_v2_boundary'];assert len(ns)==1
   tr=next(x for x in st['snapshots'] if x['at']==H.at(newday,dt(15,10)));assert json.loads(tr['shares'])=={e['old']:int(float(be['shares_at_added']))};execution.append(dict(cycle_id=cid,cost=st['cost'],request=newday,request_shares=tr['shares'],request_net_liquidation=tr['nav']-tr['estimated_liquidation_fee']-tr['estimated_liquidation_slippage'],final_equity=sr['nav'],request_est_to_final=sr['nav']-tr['nav']+tr['estimated_liquidation_fee']+tr['estimated_liquidation_slippage'],first_sell=r['first_sell'],last_sell=r['last_sell'],fill_count=len(sells),remaining_shares=r['final_shares'],fees=sr['fees'],slippage=st['slippage']))
  results.append(r);curves.extend(st['snapshots']);maxres=max(maxres,st['maxres']);logs.append(dict(cycle_id=cid,cost=st['cost'],arm=st['arm'],requests=st['requests'],fills=st['fills'],windows=st['windows'],audit=st['a'].audit_log))
 print(json.dumps(dict(stage=stage,processed=n+1,total=len(events),seconds=time.monotonic()-T),ensure_ascii=False),flush=True)
 if time.monotonic()-T+float(ef.get('sample_seconds',0))+gate['seconds']>300:raise TimeoutError('300sec cumulative computation budget')
assert len(results)==4*len(events);export(dest/'unit-ledgers.csv',results);export(dest/'A-original-checks.csv',originalchecks);export(dest/'exit-execution.csv',execution);pd.DataFrame(H.encoded(curves)).to_parquet(dest/'local-equity.parquet',index=False)
with gzip.open(dest/'audit.json.gz','wt') as f:json.dump(H.encoded(logs),f,ensure_ascii=False,allow_nan=False)
if stage=='full':
 sm=pd.read_csv(O/'sample/unit-ledgers.csv',dtype=str).fillna('').set_index(['cycle_id','cost','arm']);fu=pd.read_csv(dest/'unit-ledgers.csv',dtype=str).fillna('').set_index(['cycle_id','cost','arm']);pd.testing.assert_frame_equal(sm,fu.loc[sm.index],check_exact=True)
 assert sum((x['full_cycle_net'] for x in results if x['arm']=='A' and x['cost']==1),Z)==D('-110036.5127407436895')
assert all(sha(p)==h for p,h in freeze['source_sha256'].items());assert all(sha(p)==h for p,h in ef['sha256'].items())
elapsed=time.monotonic()-T;save(dest/'VERIFICATION.json',dict(passed=True,stage=stage,cycles=len(events),ledgers=len(results),normal_original_checks=len(originalchecks),sample_full_exact=stage=='full',max_NAV_residual=maxres,checks=dict(checks),load_seconds=loadsec,seconds=elapsed,new_portfolio_paths=0,new_buys=0,core_parameter_changes=0))
if stage=='sample':ef['sample_seconds']=elapsed;save(O/'ECONOMIC_FREEZE.json',ef)
print(json.dumps(dict(stage=stage,complete=True,seconds=elapsed),ensure_ascii=False),flush=True)
