from study_common import *
from engine_fix import Runner,Account
from dataclasses import replace
import time
CONFIG={
 'I__S0_base':{},'I__S0_delay1':{},'AMT15__S0_base':{},
 'SD__S0_base':{'sd':True},'SD__S0_cost2':{'sd':True},'SD__S0_delay1':{'sd':True},
 'SD25__S0_base':{'sd':True,'paired_buy_bps':25},
 'IBD__S0_delay1':{'sell_delay':0},'ISD__S0_delay1':{'buy_delay':0},
 'IL2__S0_base':{'latch':True},'IL2__S0_cost2':{'latch':True},'IL2__S0_delay1':{'latch':True}}

def specs():
 originals={s.stress.name:s for s in base_run.original_specs() if s.variant=='S0'}
 return tuple(replace(originals[aid.rsplit('_',1)[-1]],account_id=aid) for aid in CONFIG)

def run(out,end='2026-10-26',cutoff=None,technical=True):
 b,m=base_run.context(cutoff=cutoff);ss=specs();native.first10_specs=lambda:ss;native.SectorAccount=Account;sink=base_engine.Sink(out)
 r=Runner(b,m,start=native.iso('2023-12-29T15:10:00+08:00'),end=native.iso(end+'T15:10:00+08:00'),sink=sink,synthetic=technical);r.facts=base_engine.Facts(b,m,cutoff);r.benchmark=[]
 for aid,a in r.accounts.items():
  a.cfg=CONFIG[aid];a.mode='AMT15' if aid.startswith(('SD','AMT15')) else 'I';a.facts=r.facts;a.market=m;a.protect=True
 t=time.time()
 try:
  summary=r.run_tech();r.write(out,summary,dict(recorded_at=now(),seconds=time.time()-t,new_economic=not technical,configs=CONFIG,source= str(BASE)))
 except BaseException as e:r.write(out,dict(status='failed_partial',error=repr(e)),dict(recorded_at=now()));raise
 finally:sink.close()
 print(dict(done=True,paths=len(ss),seconds=time.time()-t,output=str(out)),flush=True)

if __name__=='__main__':
 mode=sys.argv[1]
 if mode=='short':run(HERE/'technical/short-v2',end='2024-03-29')
 elif mode=='prefix':run(HERE/'technical/prefix',end='2024-12-31',cutoff='2024-12-31')
 elif mode=='economic':
  assert read(HERE/'technical/admission.json')['passed'];assert not (HERE/'accounts').exists()
  paths=list((HERE/'code').glob('*.py'))+[HERE/'PROTOCOL.md',HERE/'GRAPH_REVIEW.md',BASE/'account-freeze-v2.json',BASE/'execution-rules-v2.json',CORE/'manifest.json',PREP/'manifest.json',PREP/'h1.npz']
  write(HERE/'freeze.json',dict(recorded_at=now(),paths=12,new_mechanisms=9,controls=3,after_prior_results=True,sha256={str(p.relative_to(ROOT)):sha(p) for p in paths}));run(HERE/'accounts',technical=False)
 else:raise ValueError(mode)
