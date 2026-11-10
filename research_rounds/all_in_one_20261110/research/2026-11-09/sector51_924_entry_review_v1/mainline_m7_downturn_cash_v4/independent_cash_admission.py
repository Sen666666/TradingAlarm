"""Independent v4 cash facts/integration audit, no strategy history."""
import pathlib,json,copy,contextlib,io
P=pathlib.Path(__file__).resolve().parent if '__file__' in globals() else pathlib.Path('mainline_m7_downturn_cash_v4').resolve()
source='\n'.join(line for line in (P/'synthetic_cash.py').read_text().splitlines() if not line.startswith('e.save('))
ns={'__file__':str(P/'synthetic_cash.py'),'__name__':'independent_repeat'}
with contextlib.redirect_stdout(io.StringIO()):exec(compile(source,'repeat_author','exec'),ns)
e=ns['e'];D=e.D;checks=[]
def ok(n,v=True):
 assert v,n
 checks.append(n)
ok('author_26_repeated',ns['out']['total']==26)
facts=e.read(e.FACT_PATH);residuals={}
for ev in facts:
 s=ev['sid'];text=pathlib.Path(ev['notice']['pdf_path']+'.txt').read_text();compact=''.join(text.split())
 ok('official_notice_dates_'+s,'2024/10/9' in compact and compact.count('2024/10/10')>=2)
 ok('official_notice_gross_cash_'+s,('每股现金红利0.26元' if s=='600535.SH' else '每股现金红利0.5元') in compact)
 ok('official_no_differential_'+s,'差异化分红送转：否' in compact)
 ok('official_adapter_pay_cash_'+s,ev['pay_date']=='2024-10-10' and ev['d_cash']==ev['d_source'])
 for path,h in ev['evidence_hashes'].items():ok('evidence_hash_'+s+'_'+pathlib.Path(path).name,e.sha(pathlib.Path(path))==h)
 z=e.pd.read_parquet(ev['signal_path']);a=z.loc['2024-10-09'];b=z.loc['2024-10-10']
 residuals[s]=str(D(str(a.adjustment_factor))*D(str(a.raw_close))/(D(str(a.raw_close))-D(ev['d_source']))/D(str(b.adjustment_factor))-1)
 ok('factor_bridge_'+s,abs(D(residuals[s]))<D('1e-11') and e.v3.m7.m3.lineage(a)==e.v3.m7.m3.lineage(b))
 # Unchanged standard accounting: registered holder accrues NET80, one payment, no shares fabricated.
 data,event=ns['fixture'](s);e.admit_cash(data,event,lambda *a:None);x=e.Engine(data);record=ns['record'];dt=ns['dt'];rid=s+'|test'
 a=dict(id=rid,sid=s,lots=[dict(q=100)],dividend=D(0));x.active[s]=a;x.archive[rid]=a
 x.register_pay(record);ok('explicit_record_shares_'+s,x.snapshots[(s,'2024-10-09')]==dict(q=100,round=rid))
 x.active.clear();cash=x.cash;x.accrue(dt);expected=100*D(event['d_cash'])*D('.8')
 ok('registered_entitlement_not_current_holdings_'+s,x.receivable==expected and a['dividend']==expected and x.cash==cash)
 x.register_pay(dt);ok('pay_NET80_once_'+s,x.cash==cash+expected and x.receivable==0)
 x.register_pay(dt);ok('no_double_payment_'+s,x.cash==cash+expected and x.quantity(a)==100)
# Prefix gates require economics and only exclude source inventory/later blocker diagnostics.
saves=[];oldsave=e.save;e.save=lambda path,value:saves.append(value)
e.check_prefix(e.v3.BASE/'once_20241008','2024-10-08');e.check_prefix(e.BASE/'once_20241031','2024-10-09')
ok('prefix_1008_exact_exclusions',set(saves[0]['exclusions'])==e.EXCLUDED_INVENTORY)
ok('prefix_1009_only_future_diagnostics_excluded',set(saves[1]['exclusions'])==e.EXCLUDED_INVENTORY|{'BLOCKERS','ALL_TARGETS_BLOCKER_SCAN','UNCERTIFIED_DAY'})
ok('all_key_economics_checked',all(n in q['families'] for q in saves for n in ['ORDERS','DAY_LEDGER','EQUITY_EVENTS','REFERENCE_AT_END','TICKET_STATE','PENDING_AT_END']))
e.save=oldsave
oldexport=e.v3.m7.Engine.export;oldcheck=e.check_prefix;called=[]
e.v3.m7.Engine.export=lambda *args:None;e.check_prefix=lambda path,date:called.append(date)
x=e.Engine.__new__(e.Engine)
for name in ['once_20241031','checkpoint_20241008','checkpoint_20241009','checkpoint_20241010']:x.export(P/name)
ok('checkpoint_only_two_prefix_routes',called==['2024-10-08','2024-10-09']);e.v3.m7.Engine.export=oldexport;e.check_prefix=oldcheck
ok('only_loop_change_checkpoint',e.source.replace(e.new_dates,e.old_dates)==e.old_source)
ok('all_economic_methods_identity',all(e.self_check()['method_identity'].values()))
out=dict(result='PASS',total=len(checks),checks=checks,author_tests_independently_repeated=26,engine_sha256=e.sha(P/'engine.py'),contract_sha256=e.sha(P/'CONTRACT.md'),fact_sha256=e.sha(e.FACT_PATH),factor_residuals=residuals,history_run=False,scope='Two frozen ordinary cash facts, unchanged NET80 accounting/pending bridge, exact 10/8 and 10/9 prefix gates. No alpha or suspension changes.')
print(json.dumps(out))
