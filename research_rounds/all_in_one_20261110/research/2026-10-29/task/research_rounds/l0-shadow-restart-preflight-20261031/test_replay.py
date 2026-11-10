from pathlib import Path
import sys,time,json,gzip,shutil,traceback,signal
import shadow as S
O=S.O;M=S.M;case=M.read(O/'CASE_FREEZE.json')
def original_identity(r,end):
 root=O.parent/'lr1-cp1-add-preflight-20261031/TECH/full/results'
 with gzip.open(root/'daily.jsonl.gz','rt') as f:old=[json.loads(x) for x in f if x.strip()]
 old=[x for x in old if x['account']=='L0_delay1' and x['at'][:10]<=end]
 assert M.N.encoded(r.daily)==old,'Original batch daily changed'
 with gzip.open(root/'L0_delay1.json.gz','rt') as f:old=json.load(f)
 for field in ['trades','decisions','audit']:
  def at(x):return x.get('at',x.get('receipt',{}).get('at',x.get('receivable',{}).get('ex_at','')))
  target=[x for x in old[field] if at(x)[:10]<=end]
  new=M.N.encoded(getattr(r.accounts['L0_delay1'],'audit_log' if field=='audit' else field));assert new==target,('Original batch',field)
 return dict(daily=len(r.daily),trades=len(r.accounts['L0_delay1'].trades),orders_and_audit=len(r.accounts['L0_delay1'].audit_log))
def factory(label):
 root=O/label;root.mkdir(exist_ok=True);shutil.copyfile(M.RR/'pvr-act-comparison-20261027/execution-rules-v2.json',root/'execution-rules-v2.json')
 r=M.Pilot('TECH',root,stresses=['delay1'],policies=['L0']);r.record_risk=True;return r
def main(stage):
 start=time.monotonic();status='failed';signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('bounded engineering replay 120s stage')));signal.alarm(120)
 try:
  if stage=='batch':
   expected={}
   class Ref(M.Pilot):
    def planning(self,at):
     super().planning(at);day=str(at.date())
     if day==case['checkpoint_before']:S.Daily(self,at).dump(O/'before.chk')
     if day in case['dates']:
      expected[day]=S.fingerprint(self)
      if day==case['dates'][0]:
       with gzip.open(O/'FIRST_EXPECTED_STATE.json.gz','wt',compresslevel=1) as f:json.dump(S.canonical(S.state(self)),f,ensure_ascii=False,allow_nan=False)
   root=O/'reference';root.mkdir(exist_ok=True);shutil.copyfile(M.RR/'pvr-act-comparison-20261027/execution-rules-v2.json',root/'execution-rules-v2.json')
   r=Ref('TECH',root,stresses=['delay1'],policies=['L0']);r.record_risk=True
   r.run(case['dates'][-1]);check=original_identity(r,case['dates'][-1]);S.save(O/'EXPECTED.json',expected);S.save(O/'BATCH_GATE.json',dict(passed=True,original_frozen_batch_identity=check,final_fingerprint=S.fingerprint(r)))
  else:
   r=factory(stage);d=S.Daily(r).load(O/('before.chk' if stage=='increment' else 'mid.chk'));expected=M.read(O/'EXPECTED.json');observations=[]
   dates=[x for x in case['dates'] if M.N.iso(x+'T15:10:00+08:00')>d.cursor]
   if stage=='increment':dates=[x for x in dates if x<=case['restart_close']]
   for day in dates:
    before=S.fingerprint(r);assert d.step(day,'frozen:'+day,False)=='wait_incomplete';assert S.fingerprint(r)==before
    assert d.step('2099-01-01','future')=='wait_missing_or_out_of_order';assert S.fingerprint(r)==before
    assert d.step(day,'frozen:'+day)=='committed'
    if S.fingerprint(r)!=expected[day]:
     original_identity(r,day)
     with gzip.open(O/'FIRST_EXPECTED_STATE.json.gz','rt') as f:want=json.load(f)
     def diff(a,b,path=''):
      if type(a)!=type(b):return [path,'types',str(type(a)),str(type(b))]
      if isinstance(a,list):
       if len(a)!=len(b):return [path,'lengths',len(a),len(b)]
       for n,(aa,bb) in enumerate(zip(a,b)):
        if aa!=bb:return diff(aa,bb,path+'/'+str(n))
      elif a!=b:return [path,'values',str(a)[:300],str(b)[:300]]
     S.save(O/'STATE_DIFF.json',diff(want,S.canonical(S.state(r))));raise AssertionError(('State mismatch',day))
    committed=S.fingerprint(r);assert d.step(day,'frozen:'+day)=='duplicate_noop';assert S.fingerprint(r)==committed
    try:d.step(day,'revised:'+day)
    except ValueError:pass
    else:raise AssertionError('Revision was silently accepted')
    assert S.fingerprint(r)==committed
    a=r.accounts['L0_delay1'];a.check();observations.append(dict(day=day,fingerprint=committed,positions=len(a.positions),buy_orders=len(a.buys),exit_orders=len(a.exits),pending_intents=len(a.pending),dividend_receivables=len(a.dividends),delay_credit=len(a.daily_delay_credit)))
   S.save(O/(stage+'_DAILY.json'),observations)
   if stage=='increment':d.dump(O/'mid.chk')
   else:
    check=original_identity(r,case['dates'][-1]);audit=r.accounts['L0_delay1'].audit_log
    window=[x for x in M.N.encoded(audit) if case['dates'][0]<=x.get('at',x.get('receivable',{}).get('ex_at',''))[:10]<=case['dates'][-1]]
    counts=dict(__import__('collections').Counter(x['kind'] for x in window));assert counts.get('split',0)>0 and counts.get('buy_day_expiry',0)>0
    S.save(O/'ENGINEERING_GATE.json',dict(passed=True,fragment=case,real_process_restart=True,market_days=len(case['dates']),original_frozen_batch_identity=check,financial_and_operational_mutable_state_equal=True,alias_preserved=True,duplicate_noop=True,revision_rejected=True,missing_and_out_of_order_no_advance=True,actual_event_counts=counts,immutable_provider_and_derived_query_caches_excluded=True,output_only_risk_monitors_saved_but_excluded_from_exact_fingerprint='unordered Decimal sum changes last digits; first observed difference 2e-23 CNY; not consumed by controller',real_time_execution_or_live_feed_verified=False))
  status='complete'
 except BaseException as e:
  S.save(O/(stage+'_ERROR.json'),dict(error=repr(e),traceback=traceback.format_exc()));raise
 finally:
  signal.alarm(0);S.save(O/(stage+'_TIMING.json'),dict(status=status,seconds=time.monotonic()-start));print(stage,status,round(time.monotonic()-start,3),flush=True)
if __name__=='__main__':main(sys.argv[1])
