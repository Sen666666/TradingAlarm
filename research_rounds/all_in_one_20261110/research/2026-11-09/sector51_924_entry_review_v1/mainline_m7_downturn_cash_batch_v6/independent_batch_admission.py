import pathlib,importlib.util,sys,json,types
P=pathlib.Path(__file__).resolve().parent if '__file__' in globals() else pathlib.Path('mainline_m7_downturn_cash_batch_v6').resolve();sp=importlib.util.spec_from_file_location('v6_facts_audit',P/'engine.py');e=importlib.util.module_from_spec(sp);sys.modules[sp.name]=e;sp.loader.exec_module(e)
checks=[];D=e.D
def ok(n,v=True):
 assert v,n
 checks.append(n)
m=e.read(e.MANIFEST_PATH);facts,allowed=e.manifest_records(m,lambda p,h:ok('adapter_hash_'+pathlib.Path(p).name,e.sha(pathlib.Path(p))==h))
ok('26_unique_events',len(facts)==26 and len({(r['sid'],r['ex_date']) for r in facts})==26)
prior=e.read(e.v5.MANIFEST_PATH);ok('all_prior_adapters_preserved',all(a in m['adapters'] for a in prior['adapters']))
ok('approved_loader_identity',e.admit_cash is e.v5.admit_cash and e.manifest_records is e.v5.manifest_records)
for ev in facts:
 s=ev['sid'];ed=e.pd.Timestamp(ev['ex_date'])
 def checked(p,h):ok('source_hash_'+s+'_'+pathlib.Path(p).name,e.sha(pathlib.Path(p))==h)
 data=types.SimpleNamespace(end=ed,raw={s:e.pd.read_parquet(ev['signal_path'])},actions={s:e.read(ev['local_action_path'])},events={},admission=[],sid_sector={s:'fact_audit'})
 e.admit_cash(data,ev,checked,allowed)
 ok('actual_source_admission_'+s,(s,ed) in data.events and data.events[(s,ed)].get('d_ref')==ev.get('d_ref') and data.events[(s,ed)]['d_cash']==ev['d_cash'])
 if ev.get('d_ref') is not None:
  text=''.join(pathlib.Path(ev['notice']['pdf_path']+'.txt').read_text().split())
  ok('official_d_ref_text_'+s,str(ev['d_ref']) in text)
 if s=='688516.SH':
  text=''.join(pathlib.Path(ev['notice']['pdf_path']+'.txt').read_text().split())
  ok('688516_official_terms','0.86000' in text and '差异化分红送转：否' in text and '2024/10/14' in text and text.count('2024/10/15')>=2 and ev['d_cash']=='0.86' and ev['d_ref'] is None)
  holdings=e.read(e.BASE/'once_20241031/HOLDINGS.json');q=sum(r['qty'] for r in holdings if r['sid']==s and r['day']=='2024-10-14');ok('actual_record_qty_200',q==200)
  x=e.Engine(data);rid='688516|test';a=dict(id=rid,sid=s,lots=[dict(q=q)],dividend=D(0));x.active[s]=a;x.archive[rid]=a;x.register_pay(e.pd.Timestamp(ev['record_date']));x.active.clear();before=x.cash;x.accrue(ed);ok('held_entitlement_137_60',x.receivable==D('137.60') and a['dividend']==D('137.60'));x.register_pay(ed);ok('cash_137_60_paid_once',x.cash==before+D('137.60') and x.receivable==0);x.register_pay(ed);ok('no_double_payment',x.cash==before+D('137.60'))
ok('unchanged_economic_methods',all(e.self_check()['method_identity'].values()))
ok('checkpoint_only_loop_change',e.source.replace(e.new_dates,e.old_dates)==e.old_source)

import contextlib,io
src='\n'.join(l for l in (P/'synthetic_batch.py').read_text().splitlines() if not l.lstrip().startswith('e.save('));ns={'__file__':str(P/'synthetic_batch.py'),'__name__':'repeat'}
with contextlib.redirect_stdout(io.StringIO()):exec(compile(src,'author_repeat','exec'),ns)
ok('author56_repeated',ns['out']['total']==56)
saved=[];oldsave=e.save;e.save=lambda p,v:saved.append(v)
paths=[e.v5.v4.v3.BASE/'once_20241008',e.v5.v4.BASE/'once_20241031',e.v5.BASE/'once_20241031',e.BASE/'once_20241031']
for date,path in zip(['2024-10-08','2024-10-09','2024-10-10','2024-10-14'],paths):e.check_prefix(path,date)
for q in saved:ok('prefix_economic_families_'+q['through'],all(n in q['families'] for n in ['ORDERS','DAY_LEDGER','EQUITY_EVENTS','REFERENCE_AT_END','TICKET_STATE','PENDING_AT_END']))
ok('prefix_exclusions_only',set(saved[0]['exclusions'])==e.EXCLUDED_INVENTORY and all(set(q['exclusions'])==e.EXCLUDED_INVENTORY|e.FUTURE_BLOCKER_DIAGNOSTICS for q in saved[1:]));e.save=oldsave
orig=e.v5.v4.v3.m7.Engine.export;oc=e.check_prefix;calls=[];e.v5.v4.v3.m7.Engine.export=lambda *a:None;e.check_prefix=lambda p,d:calls.append(d);x=e.Engine.__new__(e.Engine)
for name in ['once_20241031','checkpoint_20241008','checkpoint_20241009','checkpoint_20241010','checkpoint_20241014','checkpoint_20241015']:x.export(P/name)
ok('four_checkpoint_only_routes',calls==['2024-10-08','2024-10-09','2024-10-10','2024-10-14']);e.v5.v4.v3.m7.Engine.export=orig;e.check_prefix=oc
out=dict(result='PASS',total=len(checks),checks=checks,author_tests_repeated=56,engine_sha256=e.sha(P/'engine.py'),contract_sha256=e.sha(P/'CONTRACT.md'),manifest_sha256=e.sha(e.MANIFEST_PATH),history_run=False,scope='26 exact cash events; unchanged approved loader/trading, four prefix gates. 688516 actual record200 gross0.86 NET80 entitlement137.60, distinct d_source/d_cash/d_ref.')
print(json.dumps(out))
