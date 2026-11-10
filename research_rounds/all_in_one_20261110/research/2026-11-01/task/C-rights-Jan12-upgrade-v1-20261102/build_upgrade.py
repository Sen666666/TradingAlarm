"""Import exactly the two selected Jan12 accounts; zero financial events."""
from pathlib import Path
import copy,json,subprocess,sys,time
import upgrade_runtime as U
O=Path(__file__).resolve().parent
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
def main():
 require=U.require;require(not (O/'COMPLETION.json').exists(),'do not overwrite completed upgrade')
 cases=[];registry=[];live={};begun=time.monotonic()
 for arm in ['2022-C10','2022-C_BATCH20']:
  original=U.load_original(arm);before=U.prefix_hashes(original)
  before_certs=U.E.digest(original.authority.certificates);before_trusted=U.E.digest(original.trusted)
  r,status=U.upgrade_runner(original,arm);require(status=='upgraded_no_event','upgrade status');after=U.prefix_hashes(r);require(after==before,'prefix conservation')
  audits=[]
  for c in r.authority.certificates.values():
   result=r.verify_native(c);require(U.E.digest(result)==c['projection_hash'],'original result exact')
   audits.append(dict(certificate_id=c['certificate_id'],known_at=c['known_at'],projection_hash=U.E.digest(result),old_source_hash=U.E.digest(c['source_binding']),in_month_old=c['certificate_id'] in r.month_old_certificates,
    route='genuine month_runtime.MonthRunner.verify_native -> its unchanged legacy hierarchy',legacy_input_class=type(r.rights_legacy_inputs).__module__+'.'+type(r.rights_legacy_inputs).__qualname__))
  require(before_certs==U.E.digest(r.authority.certificates) and before_trusted==U.E.digest(r.trusted),'certificate or snapshot changed')
  rec=copy.deepcopy(r.rights_upgrade_record);again,dup=U.upgrade_runner(r,arm);require(again is r and dup=='already_upgraded' and r.rights_upgrade_record==rec and U.prefix_hashes(r)==before,'duplicate upgrade altered state')
  out=O/'upgraded'/arm;out.mkdir(parents=True,exist_ok=False);cp=out/'JAN12_UPGRADED.pkl';r.checkpoint(cp)
  registry.append(dict(arm=arm,checkpoint=str(cp),sha256=U.sha(cp),provenance_sha256=U.sha(cp.with_suffix('.provenance.json')),cursor=str(r.last_completed_event),prefix_sha256=before['whole']))
  a=r.account;cases.append(dict(arm=arm,status=status,cursor=str(r.last_completed_event),before=before,after=after,certificates=audits,certificate_bank_sha256=before_certs,trusted_bank_sha256=before_trusted,
   native_buys=len(a.buys),native_exits=len(a.exits),pending_intents=len(a.pending),available=str(a.available),native_share_digest=U.E.digest({s:a.quantity(s) for s in a.positions}),
   New=str(r.budget.batch['new']) if r.budget and r.budget.batch else None,Carry=str(r.budget.batch['carry']) if r.budget and r.budget.batch else None,duplicate_upgrade=dup,historical_events=0))
  live[arm]=r;print('UPGRADED_NO_EVENT',arm,len(audits),'certificates',flush=True)
 save('UPGRADED_CHECKPOINTS.json',registry);save('UPGRADE_RESULTS.json',cases)
 tests=[]
 def denied(name,fn):
  try:fn()
  except (ValueError,KeyError,TypeError):tests.append(dict(check=name,passed=True));return
  raise AssertionError('expected rejection '+name)
 for arm,r in live.items():
  entry=U.arm_entry(arm);prefix_before=U.prefix_hashes(r);cid=next(iter(r.authority.certificates));cert=r.authority.certificates[cid]
  denied(arm+' wrong source path',lambda:U.load_original(arm,source_path=U.HERE/'wrong.pkl'))
  denied(arm+' wrong requested source hash',lambda:U.load_original(arm,source_sha='0'*64))
  oldmode=r.mode;r.mode='WRONG_MODE';denied(arm+' wrong mode',lambda:r.verify_native(cert));r.mode=oldmode
  bad=copy.deepcopy(cert);bad['source_binding']={'wrong':'source'};denied(arm+' changed certificate source',lambda:r.verify_native(bad))
  bad=copy.deepcopy(cert);bad['mode']='WRONG_MODE';denied(arm+' changed certificate mode',lambda:r.verify_native(bad))
  bad=copy.deepcopy(cert);bad['Q']=dict(bad['Q']);sid=next(iter(bad['Q']));bad['Q'][sid]+=1;denied(arm+' changed certificate target',lambda:r.verify_native(bad))
  tid=cert['trusted_id'];v=r.trusted[tid];r.trusted[tid]=copy.deepcopy(v);r.trusted[tid]['snapshot']['decision_nav']='1';denied(arm+' changed trusted snapshot',lambda:r.verify_native(cert));r.trusted[tid]=v
  oldinputs=r.rights_legacy_inputs;r.rights_legacy_inputs=r.inputs;denied(arm+' wrong legacy input class',lambda:r.verify_native(cert));r.rights_legacy_inputs=oldinputs
  denied(arm+' no Jan13 event authority',lambda:r.corporate_actions('2022-01-13'))
  denied(arm+' OPEN denied',lambda:r.step('2022-01-13','OPEN'))
  denied(arm+' native event denied',lambda:r.event(r.last_completed_event))
  require(U.prefix_hashes(r)==prefix_before and r.rights_upgrade_record['arm']==arm,'negative checks changed prefix')
  print('NEGATIVE_GATES_PASS',arm,flush=True)
 save('NEGATIVE_TESTS.json',dict(passed=True,checks=len(tests),tests=tests,historical_events=0))
 cross=[]
 for rec in registry:
  result=subprocess.run([sys.executable,'-B',str(O/'restore_upgrade.py'),rec['checkpoint']],cwd=O,capture_output=True,text=True)
  (O/(rec['arm']+'-RESTORE.stderr.txt')).write_text(result.stderr);require(result.returncode==0,'crossprocess restore failed '+result.stderr)
  data=json.loads(result.stdout);require(data['prefix']['whole']==rec['prefix_sha256'] and data['duplicate_upgrade']=='already_upgraded','crossprocess prefix/duplicate mismatch')
  save(rec['arm']+'-RESTORE.json',data);cross.append(data);print('CROSSPROCESS_EXACT',rec['arm'],flush=True)
 save('COMPLETION.json',dict(passed=True,upgraded_accounts=2,original_certificates_recomputed=sum(len(x['certificates']) for x in cases),certificates_outside_month_old=sum(not c['in_month_old'] for x in cases for c in x['certificates']),
  negative_checks=len(tests),crossprocess_restores=len(cross),historical_events=0,original_writes=0,accounts_reset=0,accounts_2025_opened=0,seconds=time.monotonic()-begun))
 print('UPGRADE_COMPLETE',round(time.monotonic()-begun,2),flush=True)
if __name__=='__main__':main()
