import adapter as m
from pathlib import Path
from decimal import Decimal as D
import time,sys,signal,shutil,traceback,json,gzip
w=m.w;O=m.O;Z=D(0)
legacy=w.load('abc_frozen_identity',O.parent/'entry-loss-budget-cost2-funnel-20261031/run_cost2.py')
def save(p,x):w.K.save(p,x)
def gz(p):
 with gzip.open(p,'rt') as f:return [json.loads(x) for x in f]
def verify_policy(root,ref,ids):
 dd=gz(root/'accounts-v2/daily.jsonl.gz');de=gz(root/'accounts-v2/decisions.jsonl.gz');refs={};checks=[]
 for aid in ids:
  a=w.read(root/'accounts-v2'/f'{aid}.json');p=aid.split('__')[1].split('_')[0];st=aid.rsplit('_',1)[-1];orig=aid.split('__')[0]+'__S0_'+st;b=w.read(ref/f'{orig}.json');logs=a['audit_log'];risk=[x for x in logs if x['kind']=='risk_checkpoint'];act=[x for x in logs if x['kind']=='act_checkpoint'];assert len(risk)==len(act)==681
  on=True;peak=D(1000000);episode=0
  for r,c in zip(risk,act):
   assert r['at']==c['at'];N=D(c['nav']);peak=max(peak,N) if on else peak;ddrop=1-N/peak;event=None
   if on:
    if ddrop>=D('.2'):on=False;event='pause'
   elif (c['flat'] if p=='B' else c['no_orders']) and c['market']:on=True;peak=N;episode+=1;event='resume'
   assert r['on']==c['on']==on and D(r['peak'])==D(c['peak'])==peak and r['episode']==c['episode']==episode and r['event']==c['event']==event and D(r['episode_drawdown'])==ddrop,(aid,r['at'],'policy reconstruction')
   if event=='resume':assert c['no_orders'] and c['market'] and(p!='B' or c['flat'])
  pause=next((x['at'] for x in risk if x['event']=='pause'),None);bpause=next((x['at'] for x in b['audit_log'] if x['kind']=='risk_checkpoint' and x['event']=='pause'),None);assert pause==bpause,(aid,'first pause differs before intervention')
  stop=pause or '9999';assert [f for f in a['fills'] if f['at']<=stop]==[f for f in b['fills'] if f['at']<=stop]
  assert [r for r in logs if not r['kind'].startswith('act_') and legacy.ts(r)<stop]==[r for r in b['audit_log'] if legacy.ts(r)<stop],(aid,'pre-intervention audit')
  for stream,data in [('daily',dd),('decisions',de)]:
   if stream not in refs:refs[stream]=gz(ref/f'{stream}.jsonl.gz')
   aa=[dict(r,account='same') for r in data if r['account']==aid and r['at']<stop];bb=[dict(r,account='same') for r in refs[stream] if r['account']==orig and r['at']<stop];assert aa==bb,(aid,stream,'pre-pause')
  checks.append(dict(account=aid,policy=p,rows=len(risk),first_pause=pause,pre_first_pause_exact=True,transitions=sum(x['event'] is not None for x in risk),nonempty_resumes=sum(x['event']=='resume' and x['has_holdings'] for x in act),max_one_transition_per_cutoff=True))
 return dict(passed=True,checks=checks)
def main():
 sec,stage=sys.argv[1:3];assert sec in ['TECH','DRUG'] and stage in ['off','on','prefix'];p=O/'COMPUTE_TIME.json';prior=w.read(p) if p.exists() else dict(seconds=0,stages=[]);used=sum(x['seconds'] for x in prior['stages'] if x['sector']==sec);left=min(480-prior['seconds'],240-used);assert left>0
 t=time.monotonic();root=O/sec/stage;root.mkdir(parents=True,exist_ok=False);shutil.copyfile(w.RR/'pvr-act-comparison-20261027/execution-rules-v2.json',root/'execution-rules-v2.json');status='started';signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('ACT ABC sector240 total480 budget')));signal.setitimer(signal.ITIMER_REAL,left)
 try:
  assert w.read(O/'SYNTHETIC.json')['passed'];freeze=w.read(O/'FREEZE.json');assert all(w.sha(q)==h for q,h in freeze['sha256'].items());cut='2025-06-30' if stage=='prefix' else None;end=cut or '2026-10-27';enabled=stage!='off';ref=w.RR/('pvr-local-finite-capital-20261029/baseline/accounts-v2' if sec=='TECH' else 'innovative-drug-local-recovery-20261028/S0/accounts-v2')
  if stage=='on':assert w.read(O/sec/'off/IDENTITY.json')['passed']
  R,E,core,prep,mode=m.setup(sec,root,enabled,cut);print(dict(sector=sec,stage=stage,setup_seconds=time.monotonic()-t,budget=left),flush=True);runner=R.run(root/'accounts-v2',modes=[mode],stresses=['base','cost2','delay1'],start='2023-12-29',end=end,cutoff=cut,technical=stage!='on');ids=list(runner.accounts)
  if stage=='off':save(root/'IDENTITY.json',legacy.identity(root,ref,ids,end,True))
  if stage=='prefix':save(root/'IDENTITY.json',legacy.identity(root,O/sec/'on/accounts-v2',ids,end,False))
  if stage=='on':
   save(root/'POLICY_GATE.json',verify_policy(root,ref,ids));AN=w.load('abc_original_independent_analyzer',w.RR/'tech-finite-compound-20261026/code/analyze_v2.py');AN.CORE=core;AN.PREP=prep;AN.HERE=root;AN.main('full')
  assert all(w.sha(q)==h for q,h in freeze['sha256'].items());status='complete'
 except BaseException as e:status='failed';save(root/'ERROR.json',dict(error=repr(e),traceback=traceback.format_exc()));raise
 finally:
  signal.setitimer(signal.ITIMER_REAL,0);elapsed=time.monotonic()-t;r=w.read(p) if p.exists() else dict(seconds=0,stages=[]);r['seconds']+=elapsed;r['stages'].append(dict(sector=sec,stage=stage,status=status,seconds=elapsed));save(p,r);save(root/'TIMING.json',dict(status=status,seconds=elapsed,sector_seconds=used+elapsed,total_seconds=r['seconds']));print(dict(sector=sec,stage=stage,status=status,seconds=elapsed,sector_seconds=used+elapsed,total=r['seconds']),flush=True)
if __name__=='__main__':main()
