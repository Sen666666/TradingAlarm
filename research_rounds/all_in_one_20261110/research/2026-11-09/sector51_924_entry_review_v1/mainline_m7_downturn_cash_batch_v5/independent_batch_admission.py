"""Independent manifest batch audit; no historical strategy execution."""
import pathlib,json,copy,types,contextlib,io
P=pathlib.Path(__file__).resolve().parent if '__file__' in globals() else pathlib.Path('mainline_m7_downturn_cash_batch_v5').resolve()
src='\n'.join(l for l in (P/'synthetic_batch.py').read_text().splitlines() if not l.lstrip().startswith('e.save('));ns={'__file__':str(P/'synthetic_batch.py'),'__name__':'independent_repeat'}
with contextlib.redirect_stdout(io.StringIO()):exec(compile(src,'author_repeat','exec'),ns)
e=ns['e'];D=e.D;checks=[]
def ok(n,v=True):
 assert v,n
 checks.append(n)
ok('author_30_repeated',ns['out']['total']==30)
manifest=e.read(e.MANIFEST_PATH);facts,allowed=e.manifest_records(manifest,lambda p,h:ok('manifest_adapter_hash',e.sha(pathlib.Path(p))==h))
expected={'301087.SZ':('0.60','0.5836523'),'603588.SH':('0.33','0.327'),'688029.SH':('0.50','0.4980'),'688563.SH':('0.18',None)}
ok('exact_four_only',set(v['sid'] for v in facts)==set(expected) and len(facts)==4)
for ev in facts:
 s=ev['sid'];cash,ref=expected[s];ok('separate_three_dividend_fields_'+s,ev['d_source']==cash and ev['d_cash']==cash and ev['d_ref']==ref)
 text=''.join(pathlib.Path(ev['notice']['pdf_path']+'.txt').read_text().split())
 ok('official_cash_text_'+s,('6.00' in text or '6元' in text) if s=='301087.SZ' else cash in text)
 if ref:ok('official_reference_text_'+s,ref in text and D(ref)!=D(cash))
 ok('exact_dates_'+s,ev['record_date']=='2024-10-10' and ev['ex_date']==ev['pay_date']=='2024-10-11')
 for p,h in ev['evidence_hashes'].items():ok('fact_hash_'+s+'_'+pathlib.Path(p).name,e.sha(pathlib.Path(p))==h)
 ed=e.pd.Timestamp(ev['ex_date']);z=e.pd.read_parquet(ev['signal_path']);a=z.loc[ev['record_date']];b=z.loc[ed];fo=D(str(a.adjustment_factor));fn=D(str(b.adjustment_factor));pc=D(str(a.raw_close))
 ok('source_coordinate_bridge_'+s,abs(fo*pc/(pc-D(ev['d_source']))/fn-1)<D('1e-11'))
 data=types.SimpleNamespace(end=ed,raw={s:z},actions={s:e.read(ev['local_action_path'])},events={},admission=[],sid_sector={s:'test'})
 e.admit_cash(data,ev,lambda *args:None,allowed)
 ok('admitted_d_ref_preserved_'+s,data.events[(s,ed)]['d_ref']==ref)
 # Actual inherited entitlement uses gross cash, not differential reference decrement.
 x=e.Engine(data);rid=s+'|test';a=dict(id=rid,sid=s,lots=[dict(q=100)],dividend=D(0));x.active[s]=a;x.archive[rid]=a
 x.register_pay(e.pd.Timestamp(ev['record_date']));x.active.clear();old=x.cash;x.accrue(ed);x.register_pay(ed)
 ok('entitlement_gross_cash_not_reference_'+s,x.cash-old==D(100)*D(cash)*D('.8') and x.receivable==0)
# Manifest cannot admit extra/missing/duplicate records.
for label in ['duplicate_key','missing_key','wrong_schema','wrong_window']:
 m=copy.deepcopy(manifest)
 if label=='duplicate_key':m['events'].append(copy.deepcopy(m['events'][0]))
 if label=='missing_key':m['events'].pop()
 if label=='wrong_schema':m['schema']='OTHER'
 if label=='wrong_window':m['latest_ex_date']='2024-11-01'
 try:e.manifest_records(m,lambda *args:None)
 except AssertionError:ok('manifest_reject_'+label)
 else:raise AssertionError(label)
saved=[];oldsave=e.save;e.save=lambda p,v:saved.append(v)
paths=[e.v4.v3.BASE/'once_20241008',e.v4.BASE/'once_20241031',e.BASE/'once_20241031']
for date,path in zip(['2024-10-08','2024-10-09','2024-10-10'],paths):e.check_prefix(path,date)
for q in saved:ok('prefix_economic_families_'+q['through'],all(n in q['families'] for n in ['ORDERS','DAY_LEDGER','EQUITY_EVENTS','REFERENCE_AT_END','TICKET_STATE','PENDING_AT_END']))
ok('prior_prefix_exclusions',set(saved[0]['exclusions'])==e.EXCLUDED_INVENTORY and all(set(q['exclusions'])==e.EXCLUDED_INVENTORY|e.FUTURE_BLOCKER_DIAGNOSTICS for q in saved[1:]));e.save=oldsave
oldexport=e.v4.v3.m7.Engine.export;oldcheck=e.check_prefix;calls=[];e.v4.v3.m7.Engine.export=lambda *a:None;e.check_prefix=lambda p,d:calls.append(d);x=e.Engine.__new__(e.Engine)
for name in ['once_20241031','checkpoint_20241008','checkpoint_20241009','checkpoint_20241010','checkpoint_20241011']:x.export(P/name)
ok('exact_three_checkpoint_routes',calls==['2024-10-08','2024-10-09','2024-10-10']);e.v4.v3.m7.Engine.export=oldexport;e.check_prefix=oldcheck
ok('all_economic_methods_unchanged',all(e.self_check()['method_identity'].values()))
ok('only_new_checkpoint_loop',e.source.replace(e.new_dates,e.old_dates)==e.old_source)
out=dict(result='PASS',total=len(checks),checks=checks,author_tests_repeated=30,engine_sha256=e.sha(P/'engine.py'),contract_sha256=e.sha(P/'CONTRACT.md'),manifest_sha256=e.sha(e.MANIFEST_PATH),history_run=False,scope='Exact four-event manifest; d_source factor bridge, d_cash gross entitlement and official d_ref preserved separately. No alpha changes.')
print(json.dumps(out))
