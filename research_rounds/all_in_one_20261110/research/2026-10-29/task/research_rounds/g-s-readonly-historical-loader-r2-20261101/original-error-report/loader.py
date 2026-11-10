"""Read-only cursor interface. No Account/Runner/Policy construction or intents.

Caches are saved original numeric observations, never recalculated indicators.
The output is an input packet, NOT order eligibility/admission or a financial run.
"""
from pathlib import Path
from datetime import date, datetime
from decimal import Decimal
import ast, hashlib, json, math, sys, copy
from bisect import bisect_right
import numpy as np
import pandas as pd

O=Path(__file__).resolve().parent
W=O.parent
RR=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds')
B=Path('/Users/bytedance/Documents/Codex/2026-11-01/task/market-permission-price-only-20261101')
RULE_SRC=RR/'rs-h1-execution-20261025/code'
sys.path.insert(0,str(RULE_SRC))
# Pure dated-rule/admission modules: definitions only, no financial objects.
from market_rules import version_on, market_identity_on, RuleUnavailable
import sector_stock_admission as A
NATIVE_RANK=W/'pvr-slot1-native-readiness-20261101/native_rank.py'
if hashlib.sha256(NATIVE_RANK.read_bytes()).hexdigest()!='5ec91c2323b2d3b8fa5c99df504139e2ac7af9b5b84359222c3d6353d0cd697c':raise ValueError('frozen PVR_SLOT1 source changed')
ns={'math':math}
tree=ast.parse(NATIVE_RANK.read_text())
f=next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='priority_plan')
exec(compile(ast.Module(body=[f],type_ignores=[]),str(NATIVE_RANK),'exec'),ns)
priority_plan=ns['priority_plan']
SCHEMA='GS-READONLY-CURSOR-1'

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def clean(x):
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple,np.ndarray)):return [clean(v) for v in x]
 if isinstance(x,np.generic):return clean(x.item())
 if isinstance(x,(pd.Timestamp,datetime,date,Decimal,Path)):return str(x)
 if isinstance(x,float) and not math.isfinite(x):return None
 return x

def canonical(x):return json.dumps(clean(x),sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)
def digest(x):return hashlib.sha256(canonical(x).encode()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def write(p,x):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 t=p.with_name(p.name+'.tmp');t.write_text(canonical(x)+'\n');t.replace(p)
def finite(x):return x is not None and bool(pd.notna(x)) and math.isfinite(float(x))
def known(day):return day+'T15:10:00+08:00'
def bool_or_none(x):return bool(x) if x is not None and pd.notna(x) else None

def conjunction(checks):
 unknown=[k+':unknown' for k,v in checks.items() if v is None]
 failed=[k+':false' for k,v in checks.items() if v is False]
 return dict(value=None if unknown else not failed,checks=checks,reasons=unknown+failed)

def canonical_receipt(r,sid,day,structure):
 if r['canonical_series']!=sid or r['confirmed_day']!=day:raise ValueError('receipt identity/day mismatch')
 if r['trace_unknown']:raise ValueError('unresolved canonical trace')
 if not r['formation_start_exclusive']<r['formation_end_inclusive']==day:raise ValueError('invalid receipt clock')
 return dict(event_id=r['receipt_id'],sid=sid,start=known(r['formation_start_exclusive']),
    end=known(day),confirmed=known(day),confirmed_cursor=date.fromisoformat(day).toordinal(),
    source='original_canonical_CP1_trace',scale='21',scale_id=r['scale_id'],
    source_segment=r['source_segment'],original_E0_episode_id=r['original_E0_episode_id'],
    structure=structure,canonical_original=r)

def new_order_quantity(rule,q):
 # Fresh order always uses buy_min, including an already-held STAR stock.
 if q<rule['buy_minimum']:return 0
 step=rule['buy_step'];return rule['buy_minimum']+int((q-rule['buy_minimum'])//step)*step

class UnsupportedInput(ValueError):pass

class HistoricalInputs:
 def __init__(self,manifest):
  self.path=Path(manifest);self.m=read(self.path);assert self.m['schema']==SCHEMA
  self.root=self.path.parent;self._verified=set();self.frames={};self.objects={};self.row_index={}
  self.key=self.m['window'];self.days=self.m['days'];self.ids=self.m['fixed_ids']
  assert len(self.ids)==len(set(self.ids))==1709
  self.meta=self.obj('metadata');self.selection=self.obj('selection');self.rules=self.obj('rules');self.protocol=self.obj('protocol')
  self.lines={x['security_id']:x for x in self.selection['lines'] if x['security_id'] in self.ids}
  assert set(self.lines)==set(self.ids)
  self.seeds=self.obj('bootstrap');assert len(self.seeds)==91
  for s in self.seeds.values():
   assert s['confirmed_cursor']==date.fromisoformat(s['asof']).toordinal()
   assert s['asof']==self.m['warm_through']
   assert s['original_F1_scope']==s['f1_checkpoint']['state']['scope']
   assert s['policy_scope']==s['market_context']['scope']
   assert all(p['confirmed']<=s['confirmed_cursor'] for p in s['market_context']['proof_history'])
 def ref(self,key):
  r=self.m['files'][key];p=Path(r['path']);p=p if p.is_absolute() else self.root/p
  if key not in self._verified:
   if sha(p)!=r['sha256']:raise ValueError('input hash changed '+key)
   self._verified.add(key)
  return p
 def obj(self,key):
  if key not in self.objects:self.objects[key]=read(self.ref(key))
  return self.objects[key]
 def table(self,key):
  if key not in self.frames:self.frames[key]=pd.read_parquet(self.ref(key))
  return self.frames[key]
 def rows(self,key,sid,day,exact=False):
  if key not in self.row_index:
   groups={}
   for ident,z in self.table(key).groupby('sid',sort=False):
    z=z.sort_values('day');ds=z.day.tolist()
    if len(set(ds))!=len(ds):raise ValueError('duplicate original identity/day '+key)
    groups[ident]=(ds,[clean(r) for r in z.drop(columns=['sid','day']).to_dict('records')])
   self.row_index[key]=groups
  ds,rs=self.row_index[key].get(sid,([],[]));i=bisect_right(ds,day)-1
  if i<0 or exact and ds[i]!=day:return None
  return dict(rs[i],observed_day=ds[i])
 def bootstrap(self):return copy.deepcopy(self.seeds)
 def initial_financial_state_spec(self):
  # Descriptive initialization contract only. This function creates no account.
  return dict(initial_cash_cny='1000000',positions=0,orders=0,intents=0,
    filled_trials=0,K=[],consumed_receipts=0,loss_history=[],locks=[],receivables=[],
    state_created=False,first_open_has_prestart_intents=False,
    ACT_clock='original date.toordinal / research close, never synthetic counter')
 def availability(self,sid,day):
  try:
   rec=self.meta[sid]['runtime_record']
   if rec.get('unavailable_from') and day>=rec['unavailable_from']:raise RuleUnavailable('source unavailable')
   if any(a['end']<day<b['start'] for a,b in zip(rec.get('segments',[]),rec.get('segments',[])[1:])):raise RuleUnavailable('source discontinuity')
   venue=market_identity_on(self.rules,sid,day,self.protocol['approved_proxy_ids'])
   av=version_on(self.rules['availability_versions'].get(sid,[]),day,self.protocol['approved_proxy_ids'])
   qr=version_on(self.rules['quantity_versions'].get(sid,[]),day,self.protocol['approved_proxy_ids'])
   fees=version_on(self.rules['fee_versions'].get(venue['venue'],[]),day,self.protocol['approved_proxy_ids'])
   return dict(buy_allowed=av['buy_allowed'],sell_allowed=av['sell_allowed'],quantity=qr['rule'],
      venue=venue,availability=av,fee_schedule=fees['schedule'])
  except RuleUnavailable as e:return dict(buy_allowed=None,sell_allowed=None,reason=str(e),quantity=None)
 def stock(self,sid,day,phase):
  if sid not in self.ids or day not in self.days:raise ValueError('outside frozen prefix identity/day')
  if phase not in ('OPEN','CLOSE'):raise ValueError('unknown phase')
  # At OPEN only previous CLOSE facts/CP1 are visible. Current factor is an
  # ex-date coordinate conversion only, never a permission/line update.
  bound=day if phase=='CLOSE' else (self.m['warm_through'] if day==self.days[0] else self.days[self.days.index(day)-1])
  f=self.rows('facts',sid,bound);c=self.rows('cp',sid,bound,exact=True)
  factor=self.rows('facts',sid,day);h=self.rows('h1',sid,bound,exact=True)
  pv=self.rows('pvr',sid,bound,exact=True);raw=self.rows('raw',sid,day,exact=True)
  av=self.availability(sid,day);line=self.lines[sid];ix=self.meta[sid]['structures']
  structure=next((r['identity'] for r in reversed(ix) if r['start']<=bound and (r['end'] is None or bound<=r['end'])),None)
  ready=bool_or_none(f.get('e0_ready')) if f else None
  selected=line['current_stock'] if line['market']=='A' else (None if line['current_stock'] is None or line['southbound_selected'] is None else line['current_stock'] and line['southbound_selected'])
  allowed=None if selected is None or av['buy_allowed'] is None else bool(selected and av['buy_allowed'])
  checks=dict(common_ready_stock=ready,buy_allowed=allowed,
    cap_above_10bn=None if line['company_cap_cny'] is None else line['company_cap_cny']>1e10,
    stock_up=bool_or_none(f.get('i_target')) if f and ready else None,
    issuer_known=True if line['issuer_id'] else None,sector_known=True if line['sector_id'] in self.m['sectors'] else None,
    stock_rs_ready_fresh=True if h and finite(h['score']) else None)
  core=dict(checks);core['buy_allowed']=None if allowed is None else bool(allowed and f and f['observed_day']==bound and f['i_buy'])
  if 'receipt_index' not in self.__dict__:self.receipt_index={(r['canonical_series'],r['confirmed_day']):r for r in self.obj('receipts')}
  r=self.receipt_index.get((sid,bound))
  receipt=canonical_receipt(r,sid,bound,structure) if r else None
  if receipt:
   if not c or not c['receipt'] or c['candidate']!=r['original_candidate']:raise ValueError('canonical/numeric CP1 differs')
  current_factor=factor['factor'] if factor else None
  # No adjusted price is permitted to become raw execution price.
  floors=dict(coordinate='causal_adjusted_signal',known_at=known(f['observed_day']) if f else None,
    core=f.get('i_floor') if f else None,mobile=max(f['i_floor'],c['candidate']) if f and c and finite(f['i_floor']) and finite(c['candidate']) else None,
    raw_conversion_factor_at_event=current_factor,
    core_raw=f['i_floor']/current_factor if f and finite(f['i_floor']) and finite(current_factor) else None)
  legacy=self.rows('legacy_industry',line['sector_id'],bound)
  legacy_H1=self.rows('h1',line['sector_id'],bound,True)
  legacy_checks=dict(common_ready_industry=bool_or_none(legacy['e0_ready']) if legacy else None,sector_observed_today=True if legacy and legacy['observed_day']==bound else None,sector_rs_ready_fresh=True if legacy_H1 and finite(legacy_H1['score']) else None,sector_up=bool_or_none(legacy['e0_target']) if legacy and legacy['e0_ready'] else None)
  return dict(sid=sid,sector=line['sector_id'],cursor=date.fromisoformat(day).toordinal(),phase=phase,
    known_signal_cutoff=bound,facts=f,cp=c,canonical_receipt=receipt,structure=structure,original_I_structural_key=[bool(f['i_target']),int(f['segment_id'])] if f else None,
    retained_stock_Q=conjunction(checks),retained_core_event_Q=conjunction(core),
    legacy_industry_Q_attribution=legacy_checks,industry_Q_replacement=self.m['eligibility_mapping'],H1=h['score'] if h else None,
    PVR=pv['score'] if pv else None,PVR_explicit=pv is not None,availability=av,floors=floors,
    raw_execution_bar_proxy=raw if phase=='OPEN' else None,
    proxy_limit='Daily OHLC/volume legality uses final daily data; not certified real opening executable' if phase=='OPEN' else None)
 def priority(self,day,ids=None):
  # Domain must come from caller's real role/target/account filtering later.
  # Here ALL input identities are a fixture domain, never generated intents.
  if day not in self.days:raise ValueError('outside frozen priority date')
  ids=self.ids if ids is None else list(ids)
  if len(ids)!=len(set(ids)):raise ValueError('unique-stock domain required')
  vals={s:self.rows('h1',s,day,True) for s in self.ids}
  full=sorted(self.ids,key=lambda s:(-round(vals[s]['score'],12) if vals[s] and finite(vals[s]['score']) else 1,s))
  ranks={s:n for n,s in enumerate(full)}
  domain=[dict(sid=s,rank=ranks[s],role=r) for s in ids for r in ('core','mobile')]
  def score(s,d):
   r=self.rows('pvr',s,d,True);return r['score'] if r else None
  keys,log=priority_plan(domain,score,day)
  return [dict(r,original_full_key=[r['original_H1_rank'],0,r['sid']],
      new_full_key=[r['priority_rank'],0,r['sid']],role_keys={'core':[r['priority_rank'],False],'mobile':[r['priority_rank'],True]},roles_are_fixture_domain_not_actual_intents=True,domain='read-only caller supplied unique-stock domain; not account intents') for r in log]
 def market_observations(self,day):
  f=self.table('f1_observations');out=clean(f[f.day==day].to_dict('records'))
  for r in out:
   seed=self.seeds[r['node_id']];source=dict(seed['f1_checkpoint']['state']['source'])
   if r['policy_scope']!='G' and finite(r.get('price_source_segment_id')):
    source['revision']='original-source-segment-'+str(int(r['price_source_segment_id']))
   r.update(source=source,known_at=known(day),confirmed_cursor=date.fromisoformat(day).toordinal(),
    original_scope_sequence=seed['scope_observation_sequence']+len(f[(f.node_id==r['node_id'])&(f.day<=day)]),
    observation_only_no_step=True)
  return out
 def actions(self,day):
  return [r for r in self.obj('actions') if r['effective_date']==day]
 def payments_due(self,at):
  at=datetime.fromisoformat(at) if isinstance(at,str) else at
  if at.tzinfo is None:raise ValueError('aware payment cursor required')
  # These are declared source terms only. A future account must filter its
  # own unpaid entitlements once; source existence does not create a claim.
  return [a for a in self.obj('actions') if a.get('paid_at') and datetime.fromisoformat(a['paid_at'])<=at]
 def event(self,day,phase):
  if day not in self.days:raise ValueError('outside authorized input prefix')
  if phase=='ACTION':return dict(at=day+'T00:00:00+08:00',cursor=date.fromisoformat(day).toordinal(),kind='ACTION_INPUT',actions=self.actions(day),no_account_effect=True)
  if phase=='PAYMENT':return dict(at=day+'T09:30:00+08:00',kind='PAYMENT_INPUT',payments=self.payments_due(day+'T09:30:00+08:00'),unknown_payments=[a['source_id'] for a in self.actions(day) if a['paid_at'] is None],no_invented_payment_date=True)
  if phase not in ('OPEN','CLOSE'):raise UnsupportedInput('unsupported event schema')
  return dict(at=day+('T09:30:00+08:00' if phase=='OPEN' else 'T15:10:00+08:00'),
    cursor=date.fromisoformat(day).toordinal(),kind=phase+'_INPUT',stocks=[self.stock(s,day,phase) for s in self.ids],
    market_observations=self.market_observations(day) if phase=='CLOSE' else [],
    no_account_effect=True,no_intents_created=True)
 def check_action_support(self,event,layer_quantities=None):
  if event['classification']!='ordinary_cash_and_pro_rata_bonus':raise UnsupportedInput('unsupported corporate action classification')
  ratio=Decimal(event['split_ratio'])
  if ratio<=0:raise UnsupportedInput('invalid ratio')
  if layer_quantities is None:return dict(ready='conditional',reason='requires actual inventory/layer attribution; no account instantiated')
  if any(Decimal(q)*ratio!=int(Decimal(q)*ratio) for q in layer_quantities):raise UnsupportedInput('fractional per-layer action attribution unavailable; reject before mutation')
  return dict(ready=True)
