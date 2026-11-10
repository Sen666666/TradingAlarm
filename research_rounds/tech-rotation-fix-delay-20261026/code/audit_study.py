from study_common import *
from decimal import Decimal as D
from collections import defaultdict
import collections,inspect
previous=import_path('original_tech_analysis',BASE/'code/analyze_v2.py');old=previous.old;fund=previous.fund;IndependentPrices=previous.IndependentPrices
# Keep the independent raw-money replay. Extend just its price assertion for the
# predeclared paired-buy 25bps proxy, independently identified by order purpose.
src=inspect.getsource(old.audit_account)
needle="   slip=D('.001') if aid.endswith('cost2') else D('.0005')"
assert needle in src
src=src.replace(needle,"   pairs={z['order_id'] for z in obj['audit_log'] if z['kind']=='rotation_buy_reserved'}\n   slip=D('.0025') if aid.startswith('SD25__') and side=='buy' and row['order_id'] in pairs else D('.001') if aid.endswith('cost2') else D('.0005')")
scope=dict(old.__dict__);exec(src,scope);old.audit_account=scope['audit_account']

def check_contract(aid,obj,ds,facts,records):
 intents={};pairs={};rots={};checks=collections.Counter();rules=read(BASE/'execution-rules-v2.json');cal=sorted(pd.Timestamp(x) for x in rules['calendars']['A']);pending={};sd=aid.startswith(('SD__','SD25__'));latch=aid.startswith('IL2__')
 for r in obj['audit_log']:
  k=r['kind']
  if k=='entry_contract':
   intents[r['order_id']]=r;N=D(r['nav']);assert D(r['budget'])<=D('.15')*N+D('.01');checks['frozen_budget']+=1
  elif k=='same_day_rotation_contract':pending[r['rotation_id']]=r
  elif k=='rotation_started':
   z=r['rotation'];assert D(z['candidate_amount'])>=D('1.5')*D(z['victim_amount']);day=pd.Timestamp(z['signal_at'][:10]);assert bool(facts[z['candidate']].loc[day,'i_buy']);rots[z['id']]=z;checks['original_event_and_amount_ratio']+=1
   for s,field in [(z['candidate'],'candidate_amount'),(z['victim'],'victim_amount')]:
    raw=pd.read_parquet(records[s]['raw']['path']).set_index('trade_date');assert D(str(raw.loc[day,'amount']))==D(z[field])
  elif k=='rotation_buy_reserved':pairs[r['order_id']]=r['rotation'];assert r['rotation']['id'] in rots
  elif k=='fill' and r['receipt']['side']=='buy':
   f=r['receipt'];oid=r['order_id'];z=intents[oid];sid=f['security_id'];T=pd.Timestamp(z['decision_at']);S=pd.Timestamp(f['at']);assert T.date()<S.date();ff=facts[sid];day=pd.Timestamp(T.date())
   if oid in pairs:
    p=pairs[oid];assert sid==p['candidate'];assert pd.Timestamp(p['sold_at'])<S;assert S.date().isoformat()<=p['buy_deadline']
    if sd:
     q=pending[p['id']];assert z['floor_signal']==q['support'];assert z['nav']==q['nav'];assert T==pd.Timestamp(q['signal_at']);assert S.second==1;checks['same_day_causal_pair']+=1
   else:
    assert bool(ff.loc[day,'i_buy']),(aid,sid,day,'no source event')
   ix=ff.index.searchsorted(pd.Timestamp(S.date()),side='right')-1;factor=D(str(ff.iloc[ix].factor));assert D(r['raw_open'])>D(z['floor_signal'])/factor
   if latch:
    dates=[x.date() for x in cal if x.date()>T.date()];assert S.date()<=dates[1];checks['bounded_two_session_intent']+=1
   checks['actual_buy']+=1
 return dict(passed=True,checks=dict(checks))

src=inspect.getsource(previous.main)
src=src.replace("HERE/('technical/short-v2' if stage=='short' else 'accounts-v2')","HERE/('technical/short-v2' if stage=='short' else 'accounts')")
src=src.replace("read(HERE/'execution-rules-v2.json')","read(BASE/'execution-rules-v2.json')")
exec(src,globals())
if __name__=='__main__':main(sys.argv[1])
