"""Only three screened zero-fill batches; reuse frozen V2, never a runner."""
from pathlib import Path
from decimal import Decimal as D
from types import SimpleNamespace as NS
from dataclasses import asdict
import json,hashlib,gzip,copy,sys,gc
import pandas as pd
O=Path(__file__).resolve().parent;W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
A=W/'g-s-C-August-continuation-v1-20261102';V=W/'g-s-pre-sell-quote-prototype-v2-20261102'
sys.path.insert(0,str(V));import quote_package as P
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
def read(p):return json.loads(Path(p).read_text())
source={str(V/'quote_package.py'):sha(V/'quote_package.py')}
manifest=A/'full-August/MANIFEST.json';m=read(manifest);source[str(manifest)]=sha(manifest)
raw_path=manifest.parent/m['continuation_extension']['raw']['path'];fact_path=manifest.parent/m['continuation_extension']['facts']['path']
for p,key in [(raw_path,'raw'),(fact_path,'facts')]:
 assert sha(p)==m['continuation_extension'][key]['sha256'];source[str(p)]=sha(p)
# Exactly four columns read; no H/L/C, volume, day validity or fill-window labels.
raw=pd.read_parquet(raw_path,columns=['sid','day','open']);factors=pd.read_parquet(fact_path,columns=['sid','day','factor'])
archive=read(A/'LOSSLESS_OUTPUT_ARCHIVE.json')['entries']
def saved(p):
 q=p if p.exists() else A/archive[str(p.relative_to(A))]['archive'];source[str(q)]=sha(q)
 if q.suffix=='.gz':
  r=archive[str(p.relative_to(A))];assert sha(q)==r['gzip_sha256'];b=gzip.open(q,'rb').read();assert hashlib.sha256(b).hexdigest()==r['original_sha256']
 else:b=q.read_bytes()
 return json.loads(b)
def build(b):
 day=b['actual_source_days'][0];assert len(b['actual_source_days'])==1
 p=A/'runs'/b['cell']/(day+'-ACTION.json');x=saved(p);a=x['account'];parent=copy.deepcopy(x['active'])
 assert parent['certificate_id']==b['certificate']
 assert not a['buys'],'UNKNOWN: existing native pending buy; not dropped'
 assert a['balance']['order_reserved']=='0','UNKNOWN: existing reserved cash'
 orig=next(r['projection'] for r in x['results'] if r['certificate']['certificate_id']==parent['certificate_id'])
 at=P.instant(day+'T09:30:00+08:00')
 pp=P.N.CPolicy.__new__(P.N.CPolicy);pp.nd=D(a['policy']['nd']);pp.act=a['policy']['act'];pp.incident=a['policy']['incident'];pp.scopes={s:NS(**v) for s,v in a['policy']['scopes'].items()}
 pending={r['sid']:r for r in x['pending']};ids={z['sid'] for z in a['layers'] if z['qty']}|set(b['Q'])|set(b['D'])
 quotes={};specs={}
 for sid in ids:
  r=raw[(raw.sid==sid)&(raw.day==day)];f=factors[(factors.sid==sid)&(factors.day==day)]
  assert len(f)==1 and D(str(f.iloc[0].factor))==D(a['market_factors'][sid]),'UNKNOWN: changed/unknown current factor'
  quotes[sid]=dict(price=None if len(r)!=1 or pd.isna(r.iloc[0].open) else str(r.iloc[0].open),known_at=at.isoformat(),session=day,source='frozen_raw_open|'+source[str(raw_path)],kind='current_open_print')
  specs[sid]=dict(quantity=asdict(P.N.quantity(at,sid.startswith('688'))),fees=asdict(P.N.fees(at,sid.startswith('688'))))
 lots=[];meta=a['capital_meta']
 for z in a['layers']:
  if not z['qty']:continue
  sid=z['sid'];lid=z['id'];mm=meta[str(lid)];f=D(a['facts_floors'][sid] if z['kind']=='core' else z['floor'])/D(a['market_factors'][sid])
  lots.append(dict(id=lid,sid=sid,sector=mm['sector'],pool=mm['pool'],role=mm['role'],qty=z['qty'],floor=str(f),locks=[copy.deepcopy(e) for e in a['policy']['locks'].values() if e['lot']==lid and e['remaining']]))
 rank=orig['C_rank_binding']['stock_priority'];demands=[]
 for sid,q in b['Q'].items():
  i=pending[sid];sec=i['sector'];use='S' if pp.allowed(sec,'S') else 'G'
  floor=max(D(i['I_floor']),D(i['cp_floor']))/D(a['market_factors'][sid])
  assert i['receipt']['event_id']==parent['receipt_bindings'][sid]['event_id']
  auth=[v for v in x['authority']['orders'].values() if v['cid']==parent['certificate_id'] and v['sid']==sid]
  demands.append(dict(sid=sid,sector=sec,use=use,role='mobile',pool='confirmed',priority=rank[sid]['C_key'],receipt=copy.deepcopy(parent['receipt_bindings'][sid]),deadline=parent['deadline'],
   i_valid=i['i_valid'],stock_q=i['stock_q'],permission_valid=pp.allowed(sec if use=='S' else 'G',use),floor=str(floor),industry_target=str(pp.nd*(D('.8') if use=='S' else D('.2'))),quantity=specs[sid]['quantity'],fees=specs[sid]['fees'],
   authority=dict(filled=sum(int(v['filled']) for v in auth),permanent_reduction=sum(int(v['cancelled']) for v in auth),pending=0,order_bound=bool(auth))))
 donors=[];parent_layers={}
 for z in orig['donors']['rows']:
  lid=z['layer'];sid=z['sid'];parent_layers[lid]=z['q'];active=[e for e in a['policy']['locks'].values() if e['lot']==lid and e['remaining'] and e['sid'] in a['exits'] and e.get('native_exit')==a['exits'][sid]['event_id']]
  order=a['exits'][sid];n=sum(e['remaining'] for e in active);pure=all(a['exit_duties'][e['eid']]['reasons']==['actionable_S_funding'] for e in active)
  unsellable=min([P.instant(v['sellable_at']) for v in a['inventory_map'].values() if v['layer']==lid],default=at)>at
  donors.append(dict(layer=lid,sid=sid,role=meta[str(lid)]['role'],original_cap=z['q'],max_remaining=min(z['q'],n),sellable_qty=0 if unsellable else min(z['q'],n),lock_ids=[e['eid'] for e in active],mixed_mandatory=not pure,
   submitted_unacked=order['submitted_remaining'],quantity=specs[sid]['quantity'],fees=specs[sid]['fees'],paid=order['fees_local'],accrued=order['fee_accrued_local']))
 permissions={s:{**{u:pp.allowed(s,u) for u in ['S','G','T']},**{'holding_'+u:pp.allowed(s,u,holding=True) for u in ['S','G','T']}} for s in {d['sector'] for d in demands}|{'G'}}
 # Zero is the same optimistic cash convention as V2's existing adapter.
 # For a proven NO_LEGAL_RECIPIENTS risk bound, additional nonnegative cash
 # encumbrances cannot reverse NO. No positive feasibility claim is promoted.
 state=dict(available=a['balance']['available'],non_inventory_equity=str(D(a['balance']['nav'])-D(a['balance']['inventory'])),decision_nav=a['policy']['nd'],consumed_receipts=a['policy']['consumed'],lots=lots,pending_rows=[],pending_orders={},receiver_responsibilities=[d['sid'] for d in demands if d['sid'] in a['exits']],other_goal_cash_encumbrance='0')
 result=dict(case=b['cell']+'_'+day,parent=parent,trusted_parent_id=parent['certificate_id'],at=at.isoformat(),quote_session=day,decision_nav=a['policy']['nd'],state=state,quotes=quotes,specs=specs,demands=demands,donors=donors,parent_D_layers=parent_layers,
  frozen_donor_order=[d['layer'] for d in sorted(donors,key=lambda d:(rank[d['sid']]['C_key'],-d['layer']),reverse=True)],frozen_priority={d['sid']:d['priority'] for d in demands},permissions=permissions,industry_targets={d['sector']:d['industry_target'] for d in demands},source=dict(snapshot=str(p),source_manifest=str(manifest),source_manifest_sha256=source[str(manifest)],read_only=True))
 return result

results=[]
for b in [r for r in read(O/'BATCHES.json') if r['C_category']=='NONE']:
 case=b['cell']+'_'+b['actual_source_days'][0]
 try:
  if case=='C20_2025-08-25':
   binding=read(V/'INPUT_BINDING.json')['cases']['Aug25_C20'];p=Path(binding['path']);assert sha(p)==binding['bytes_sha256'];source[str(p)]=sha(p);x=read(p);x['parent_D_layers']={int(k):v for k,v in x['parent_D_layers'].items()};assert P.digest(x)==binding['trusted_body_sha256']
  else:x=build(b)
  flow=A/'runs'/b['cell']/(b['actual_source_days'][0]+'-OPEN-FLOW.json');ff=read(flow)['new_fills'];source[str(flow)]=sha(flow)
  # No other actual fill precedes the first funding sell in these three events.
  assert {t['receipt_id'] for t in ff}=={t['receipt_id'] for t in b['source_fills']}
  before=P.digest(x);out=P.proposal(x,expected_sha256=before,max_checks=25000);assert P.digest(x)==before
  save(case+'-QUOTE_RESULT.json',out)
  # A small pure input, not a financial checkpoint.
  save(case+'-QUOTE_INPUT.json',x)
  results.append(dict(case=case,parent=b['certificate'],status=out['state'],Q=out['Q'],D=out['D'],checks=out.get('checks'),bound=out.get('bound'),unknown=out.get('unknown'),source_gross=b['actual_source_gross'],
   causal_scope='OPEN current-print proxy before first actual funding fill; no other actual fill in event; no daily fill-window labels',actual_releases=out['actual_releases']))
 except Exception as e:results.append(dict(case=case,parent=b['certificate'],status='UNKNOWN_NOT_RECHECKED',reason=type(e).__name__+': '+str(e),source_gross=b['actual_source_gross']))
 print(results[-1],flush=True);gc.collect()
assert source[str(V/'quote_package.py')]==sha(V/'quote_package.py')
save('QUOTE_RECHECKS.json',results);save('QUOTE_SOURCE_SHA256.json',source)
