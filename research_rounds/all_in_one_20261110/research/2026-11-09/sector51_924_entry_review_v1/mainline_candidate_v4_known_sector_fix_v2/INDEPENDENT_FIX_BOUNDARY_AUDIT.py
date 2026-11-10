import sys, pathlib, itertools, ast, contextlib,io,json
p=pathlib.Path('mainline_candidate_v4_known_sector_fix_v2').resolve();sys.path.insert(0,str(p));import synthetic_m4 as t
e=t.e;old=e.module('independent_old_m4',p.parent/'mainline_candidate_v4_event_representatives/engine.py')
with contextlib.redirect_stdout(io.StringIO()):result=t.run()
print('AUTHOR',result['total'])
n=0
for state,M,kind,confirmed,W,restriction in itertools.product([-1,0,1],[-1,0,1],['SEED','ADD'],[False,True],[False,True],['none','T1','locked']):
 refs=[]
 for mod in [old,e]:
  x=mod.Engine(t.Stub());a=t.add(x,'old',800,kind,confirmed);x.d.M['old']=M;x.d.W['old']=W;x.d.sectors['OLD'].at[t.dt,'state']=state
  if restriction=='T1':a['lots'][0]['bought']=str(t.nxt.date())
  if restriction=='locked':a['exit']='I_INVALID'
  ref=x.classify_reference(t.dt);refs.append(ref)
  if mod is e:
   row=ref['rows'][0]
   if state==-1:assert row['mobile_qty']==0 and row['frozen_qty']==800 and 'SECTOR_M3_UNKNOWN' in row['unknown'] and ref['fixed']['OLD']==t.D(8000) and ref['stress']==0
 if state!=-1:
  refs[1]['rows'][0].pop('sector_state');assert refs[0]==refs[1],(state,M,kind,confirmed,W,restriction)
 n+=1
print('CLASSIFICATION_MATRIX',n)
for kind in ['SEED','ADD']:
 x=t.setup();a=t.add(x,'old',10000,kind,True);x.d.M['old']=0;x.d.W['old']=True;x.d.sectors['OLD'].at[t.dt,'state']=-1;x.cash=t.D(1);r=t.seed('a');x.plan_transfers(t.dt,[r]);assert not x.transfer_plan;assert x.reference['fixed']['OLD']==t.D(100000);before=len(x.orders);x.alloc_open(t.nxt,[r]);assert not [o for o in x.orders[before:] if o['sid']=='old' and o['side'].startswith('SELL')]
print('ACTUAL_CLOSE_OPEN_UNKNOWN_NO_DONOR',2)
a=ast.parse((p/'engine.py').read_text());b=ast.parse((p.parent/'mainline_candidate_v4_event_representatives/engine.py').read_text());assert len(a.body)==len(b.body)
changed=[]
for aa,bb in zip(a.body,b.body):
 if isinstance(aa,ast.ClassDef) and aa.name=='Engine':
  assert len(aa.body)==len(bb.body)
  for x,y in zip(aa.body,bb.body):
   if ast.dump(x)!=ast.dump(y):changed.append(x.name)
 else:assert ast.dump(aa)==ast.dump(bb)
assert changed==['current_trial_seed','classify_reference'];print('ONLY_CHANGED_METHODS',changed)
assert (p/'GENERATED_ALLOCATOR.py').read_bytes()==(p.parent/'mainline_candidate_v4_event_representatives/GENERATED_ALLOCATOR.py').read_bytes()
print('ENGINE',e.sha(p/'engine.py'));print('CONTRACT',e.sha(p/'CONTRACT.md'))
