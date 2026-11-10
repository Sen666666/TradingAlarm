"""Reuse frozen source-only third-session chunks. No account construction/import."""
from pathlib import Path
import json,sys,pickle
from decimal import Decimal as D
HERE=Path(__file__).resolve().parent;W=HERE.parent;ORIG=W/'g-s-C-two-day-finance-20261102'
sys.path.insert(0,str(ORIG));import provider_fix1 as F
P=F.P;E=F.E
sys.path.insert(0,str(W/'g-s-historical-native-nextsession-20261101'));import gs_next_session as X
def read(p):return json.loads(Path(p).read_text())
def main():
 F.guard();P.H.guards();output=[]
 for k,spec in X.SPECS.items():
  manifest=X.O/'inputs'/k/'MANIFEST.json';inputs=X.ExtendedInputs(manifest);day=spec['next_day'];old=read(P.H.INPUT/k/'MANIFEST.json')
  assert inputs.m['files']==old['files']
  files={n:dict(path=str(inputs.ref(n)),sha256=P.sha(inputs.ref(n))) for n in old['files']}
  assert all(files[n]['sha256']==rec['sha256'] for n,rec in old['files'].items())
  extra={n:dict(path=str(inputs.extra(n)),sha256=P.sha(inputs.extra(n)),rows=rec.get('rows')) for n,rec in inputs.m['extensions'].items()}
  pts=[inputs.stock(s,day,'CLOSE') for s in inputs.ids]
  priority=inputs.priority(day,inputs.ids)
  assert len(priority)==1709
  actions=inputs.actions(day);arms=[]
  for mode in ('C10','C_BATCH20'):
   root=ORIG/'runs'/f'{k}-{mode}'
   if k=='2022' and mode=='C10':root=ORIG/'runs/2022-C10-recovered'
   cp=root/(spec['old_end']+'-CLOSE.pkl');assert P.sha(cp)==read(cp.with_suffix('.provenance.json'))['checkpoint_sha256']
   with cp.open('rb') as f:r=pickle.load(f)
   acct=r.account;oldreg=acct.canonical_registry;newreg=P.H.registry(inputs)
   assert all(newreg.get(rid)==payload for rid,payload in oldreg.items())
   related=[]
   for ev in actions:
    sid=ev['sid'];layers=[z for z in acct.layers if z['sid']==sid and z['qty']]
    buys=acct.buys.get(sid);unsubmitted=[cid for cid,c in r.authority.certificates.items() if c['Q'].get(sid,0)>0 and E.iso(c['deadline'])>=E.iso(day+'T00:00:00+08:00') and not any(o['cid']==cid and o['sid']==sid for o in r.authority.orders.values())]
    related.append(dict(sid=sid,ratio=ev['split_ratio'],cash_per_old_share=ev['cash_per_old_share'],held_layers=[dict(id=z['id'],qty=z['qty']) for z in layers],active_buy=bool(buys),unsubmitted_positive_C=unsubmitted,
      fractional_held=any((D(z['qty'])*D(ev['split_ratio']))%1 for z in layers)))
   arms.append(dict(mode=mode,checkpoint=str(cp),checkpoint_sha256=P.sha(cp),cursor=str(r.last_completed_event),pending_intents=len(acct.pending),active_buys=len(acct.buys),sell_obligations=len(acct.exits),all_old_receipt_payloads_preserved=True,actions_related=related,
    current_unsupported_action_exposure=any(e['fractional_held'] or (D(e['ratio'])!=1 and e['unsubmitted_positive_C']) for e in related)))
  h1_unknown=[sec for sec in inputs.m['sectors'] if not (row:=inputs.rows('h1',sec,day,True)) or not X.LD.finite(row['score'])]
  output.append(dict(window=k,next_day=day,manifest=str(manifest),manifest_sha256=P.sha(manifest),loader_class='gs_next_session.ExtendedInputs (read only reuse)',loader_source_sha256=P.sha(Path(X.__file__)),base_all_files_exact_old_prefix=True,files=files,extension_files=extra,
   first_two_days_not_rebuilt=True,third_day_source_chunks_reused=True,models_recomputed=0,finance_scope_inherited_from_old_A=False,
   coverage=dict(fixed_identities=len(inputs.ids),sectors=len(inputs.m['sectors']),facts_rows=extra['facts']['rows'],raw_rows=extra['raw']['rows'],CP1_rows=extra['cp']['rows'],canonical_receipts=extra['receipts']['rows'],PVR_rows=extra['pvr']['rows'],H1_rows=extra['h1']['rows'],F1_observations=extra['f1_observations']['rows'],H1_industry_unknown=h1_unknown,actions=len(actions),payments=extra['payments']['rows'],stock_only_source_qualified=sum(v['retained_stock_Q']['value'] is True and (v['retained_core_event_Q']['value'] is True or v['canonical_receipt']) for v in pts)),arms=arms,
   binding_work_required=['explicit C horizon approval and source/input identity transition; old certificates keep real old binding',
    'C-compatible canonical-generation guard retaining old receipt identities, not casting to old A GenerationAccount',
    'preserve account/budget/goals/locks/buy/sell obligations and old cursor; allow exactly next day in a new runner, do not edit frozen EXPECTED',
    'old A install_inputs/NextSessionRunner must NOT be used to change C account/runner class'],financial_account_events=0))
 E.IO.write_json(HERE/'NEXT_INPUT_READINESS.json',dict(scope='preparation only; no financial horizon import or next-day event',windows=output,models_recomputed=0,accounts_created=0,account_events=0,unmodified_inputs=True),encoder=E.encode)
 print(json.dumps([dict(window=v['window'],next_day=v['next_day'],coverage=v['coverage'],action_exposure=[a['current_unsupported_action_exposure'] for a in v['arms']]) for v in output],ensure_ascii=False,indent=2))
if __name__=='__main__':main()
