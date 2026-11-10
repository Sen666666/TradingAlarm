"""Independent accounting plus original-event, rank-gap and pair contract audit."""
from study import *
from collections import Counter
import gzip

def rows(p):
 with gzip.open(p,'rt') as f:return [json.loads(x) for x in f]

def check_contract(aid,obj,ds,facts,records):
 checks=Counter();intents={};rotations={};contexts={};pairs={};byday={x['at'][:10]:x for x in ds};scores={}
 meta=read(P.OLD/'inputs-v2/metadata.json') if hasattr(P,'OLD') else C.read(C.OLD/'inputs-v2/metadata.json')
 for x in obj['audit_log']:
  k=x['kind']
  if k=='entry_contract':
   intents[x['order_id']]=x;assert D(x['budget'])<=D('.15')*D(x['nav'])+D('.01');checks['entry_budget']+=1
  elif k=='rotation_started':
   z=x['rotation'];sid=z['candidate'];old=z['victim'];day=z['signal_at'][:10];T=pd.Timestamp(day)
   assert bool(facts[sid].loc[T,'i_buy']) and bool(facts[sid].loc[T,'i_target'])
   for s,field in [(sid,'candidate_score'),(old,'victim_score')]:
    if s not in scores:scores[s]=pd.read_parquet(PREVIOUS/'scores'/f'{s}.parquet')
    v=float(np.round(scores[s].loc[T,'score'],12));assert v==z[field],(s,day,field,v,z[field])
   assert z['candidate_score']>50 and z['candidate_score']-z['victim_score']>=15
   r=byday[day];assert old in r['positions'] and sid not in r['positions'];ids=set(r['positions'])|set(r['pending_buys']);ids.discard(old);ids.add(sid)
   counts=Counter(meta[s]['sector_id'] for s in ids);assert len(ids)<=6 and len(counts)<=3 and max(counts.values())<=2
   rotations[z['id']]=z;checks['original_new_event_and_frozen_score_gap']+=1;checks['capacity_after_one_for_one']+=1
  elif k=='same_day_rotation_contract':
   contexts[x['rotation_id']]=x;z=rotations[x['rotation_id']];sid=z['candidate'];day=pd.Timestamp(z['signal_at'][:10]);assert D(x['support'])==D(str(facts[sid].loc[day,'i_floor']))
  elif k=='rotation_buy_reserved':
   z=x['rotation'];assert z['id'] in rotations;assert pd.Timestamp(z['sold_at'])==pd.Timestamp(x['at']);assert z['sold_at'][:10]<=z['sell_deadline'];pairs[x['order_id']]=z;checks['funded_after_full_sale']+=1
  elif k=='fill' and x['receipt']['side']=='buy':
   f=x['receipt'];oid=x['order_id'];z=intents[oid];sid=f['security_id'];T=pd.Timestamp(z['decision_at']);S=pd.Timestamp(f['at']);assert T.date()<S.date()
   ff=facts[sid];ix=ff.index.searchsorted(pd.Timestamp(S.date()),side='right')-1;factor=D(str(ff.iloc[ix].factor))
   assert D(x['raw_open'])>D(z['floor_signal'])/factor
   if oid in pairs:
    p=pairs[oid];ctx=contexts[p['id']];assert T==pd.Timestamp(ctx['signal_at']);assert z['floor_signal']==ctx['support'];assert z['nav']==ctx['nav']
    assert pd.Timestamp(p['sold_at'])<S and S.second==1 and str(S.date())<=p['buy_deadline']
    assert any(g['security_id']==p['victim'] and g['side']=='sell' and g['at']==p['sold_at'] for g in obj['fills'])
    cap=ctx['share_cap']
    for ev in C.read(records[sid]['adjustment']['actions']['path'])['events']:
     if T.date().isoformat()<ev['effective_date']<=S.date().isoformat():cap=int(D(cap)*D(ev['split_ratio']))
    group=[g for g in obj['audit_log'] if g['kind']=='fill' and g['order_id']==oid and g['receipt']['at']<=f['at']]
    assert sum(g['receipt']['shares'] for g in group)<=cap
    assert sum(D(g['receipt']['gross_cny']) for g in group)<=D(rotations[p['id']]['budget'])
    checks['causal_same_day_pair_or_bounded_wait']+=1
   else:assert bool(ff.loc[pd.Timestamp(T.date()),'i_buy']);checks['ordinary_original_event']+=1
   checks['actual_buy_support_and_no_same_day_decision']+=1
 return {'passed':True,'checks':dict(checks)}

def run_audit(version,stage):
 root=O/version;A.CORE=PREVIOUS/'input';A.PREP=Path(read(PREVIOUS/'input.json')['snapshot']['path']);A.HERE=root;A.check_contract=check_contract
 if stage=='control':
  original=inspect.getsource(A.main);original=original.replace("HERE/('technical/short-v2' if stage=='short' else 'accounts-v2')","HERE/'technical/control'").replace("HERE/('technical/short-analysis' if stage=='short' else 'analysis')","HERE/'technical/control-analysis'")
  scope=dict(A.__dict__);exec(original,scope);fn=scope['main']
 else:fn=A.main
 if version=='ROT25':
  src=inspect.getsource(A.old.audit_account);needle="   slip=D('.001') if aid.endswith('cost2') else D('.0005')";assert src.count(needle)==1
  src=src.replace(needle,"   paired={z['order_id'] for z in obj['audit_log'] if z['kind']=='rotation_buy_reserved'}\n   slip=D('.0025') if side=='buy' and row['order_id'] in paired else D('.001') if aid.endswith('cost2') else D('.0005')")
  scope=dict(A.old.__dict__);exec(src,scope);A.old.audit_account=scope['audit_account']
 fn('short' if stage=='short' else 'full')

def admission():
 assert read(O/'synthetic.json')['passed'];results=[]
 fields=['available','order_reserved','settlement_locked','payable','sale_receivable','dividend_receivable','inventory','nav','fees_cny','positions','pending_buys','pending_sells']
 for version in ['RS','PVR','ROT','ROT25']:
  a=read(O/version/'technical/short-analysis/accounting.json');assert a['passed'];results.append(a)
 for version in ['RS','PVR']:
  ref={(r['account'],r['at']):r for r in rows(PREVIOUS/version/'accounts-v2/daily.jsonl.gz')};ds=rows(O/version/'technical/short-v2/daily.jsonl.gz')
  for r in ds:
   for field in fields:assert r[field]==ref[r['account'],r['at']][field],(version,r['account'],r['at'],field)
  for sc in ['base','cost2','delay1']:
   aid='I__S0_'+sc;a=read(O/version/'technical/short-v2'/f'{aid}.json')['fills'];b=read(PREVIOUS/version/'accounts-v2'/f'{aid}.json')['fills'];assert a==[f for f in b if f['at'][:10]<='2024-06-28']
 save(O/'admission.json',{'passed':True,'short_paths':10,'control_paths':6,'technical_tests':read(O/'synthetic.json')['tests'],'audits':results})

if __name__=='__main__':
 if sys.argv[1]=='admission':admission()
 else:run_audit(sys.argv[1],sys.argv[2])
