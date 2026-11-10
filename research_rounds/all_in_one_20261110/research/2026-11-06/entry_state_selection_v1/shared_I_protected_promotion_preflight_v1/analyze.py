"""One frozen original-I protected-promotion preflight. No account, promotion or ADD."""
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict
import json,hashlib,sys,ast
import numpy as np,pandas as pd
O=Path(__file__).resolve().parent;R=O.parent;B=R/'m3_ab_shared_probe_v1/indexed_execution_v1/cohort_2024_924'
U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
M=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds');S={};Z=D(0)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def source(p,h=None):
 p=Path(p);S[str(p)]=sha(p)
 if h:assert S[str(p)]==h
 return p
def read(p):return json.loads(source(p).read_text())
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str))
for p,h in read(O/'FREEZE.json')['files'].items():assert sha(p)==h
fixed=read(O/'FIXED_HOLDING_IDENTITIES.json');days=read(O/'PROTOCOL.json')['dates']
sm={x['symbol']:x for x in read(U/'STOCK_MANIFEST.json')}
j=read(B/'EXACT_TRADE_JOURNAL.json');au=read(B/'AUDIT.json');arc=read(B/'ARCHIVES.json');claims=read(B/'CLAIM_LEDGER.json')
assert not [x for x in claims if x['day'][:10]<=max(days)],'Claims need same-round accrued/paid clock'
ledger={x['day'][:10]:x for x in read(B/'DAY_LEDGER.json')}
P=R/'momentum_persistence_breadth_v1/canonical_mu3_comparison_v2'
panel=pd.read_parquet(source(P/'COMMON_K_COMPARISON.parquet'));cal=pd.DatetimeIndex(sorted(panel.day.unique()))
sectors=panel.set_index(['sector','day']).M3_candidate;ids=sorted({x['sid'] for x in fixed})
K=pd.read_parquet(source(P/'KNOWN3.parquet'),columns=ids);MR=pd.read_parquet(source(P/'RIGHT3.parquet'),columns=ids)
sys.path[:0]=[str(M/'pv-strength-b5-20261025/code'),str(M/'b5-g1-20261025/code'),str(M/'pv-participation-response-20261020/code'),str(M/'rs-h1-execution-20261025/code')]
from policy import e0_policy
from policies_g1 import project
from data_utils import eligible_prices
from market_rules import version_on,market_identity_on,RuleUnavailable
from sector_account import QuantityRule,FeeComponent,FeeSchedule
for p in [M/'pv-strength-b5-20261025/code/policy.py',M/'b5-g1-20261025/code/policies_g1.py',M/'pv-participation-response-20261020/code/data_utils.py',M/'rs-h1-execution-20261025/code/market_rules.py',M/'rs-h1-execution-20261025/code/sector_account.py']:source(p)
old=source(R/'shared_probe_order_credit_identity_v1/analyze.py').read_text()
node=next(n for n in ast.parse(old).body if isinstance(n,ast.FunctionDef) and n.name=='native')
exec(compile(ast.Module(body=[node],type_ignores=[]),'NATIVE_I_DEFINITION_ONLY','exec'),globals())
old=source(R/'m3_stock_birth_during_sector_v1/relative_priority_v1/simulate.py').read_text();wanted={'finite','true','false','flags','lineage','getmeta','fee'}
nodes=[n for n in ast.parse(old).body if isinstance(n,ast.FunctionDef) and n.name in wanted]
env=dict(D=D,np=np,pd=pd,RuleUnavailable=RuleUnavailable,QuantityRule=QuantityRule,FeeComponent=FeeComponent,FeeSchedule=FeeSchedule,version_on=version_on,market_identity_on=market_identity_on,rules=read(M/'rs-h1-execution-20261025/inputs-v2/market-rules.json'),proxies=read(M/'rs-h1-execution-20261025/inputs-v2/economic-protocol.json')['approved_proxy_ids'],meta={})
exec(compile(ast.Module(body=nodes,type_ignores=[]),'ORIGINAL_METADATA_AND_FEES_ONLY','exec'),env)
cache={};native_rows=0;structural=[]
def load(sid,full=True):
 global native_rows
 if sid in cache and (not full or 'n' in cache[sid]):return cache[sid]
 m=sm[sid];sp=next(p for p in m['source_sha256'] if p.endswith('/signal.parquet'))
 raw=pd.read_parquet(source(sp,m['source_sha256'][sp])).loc[:max(days)]
 if not full:cache[sid]=dict(raw=raw);return cache[sid]
 f=pd.read_parquet(source(m['refs']['facts'],m['output_sha256'][m['refs']['facts']])).loc[:max(days)]
 cp=pd.read_parquet(source(m['refs']['CP1'],m['output_sha256'][m['refs']['CP1']])).loc[:max(days)]
 ep=next(p for p in m['source_sha256'] if p.endswith('/events.parquet'));stp=next(p for p in m['source_sha256'] if p.endswith('/states.parquet'));xp=next(p for p in m['source_sha256'] if '/ix-a-share-entry-' in p)
 ev=pd.read_parquet(source(ep,m['source_sha256'][ep])).loc[:max(days)];st=pd.read_parquet(source(stp,m['source_sha256'][stp])).loc[:max(days)];xx=pd.read_parquet(source(xp,m['source_sha256'][xp])).loc[:max(days)]
 n,base=native(raw,ev,st,xx);native_rows+=len(n)
 for a,c in [('target','i_target'),('floor','i_floor'),('buy_event','i_buy')]:np.testing.assert_allclose(n[a].to_numpy(float),f[c].to_numpy(float),rtol=0,atol=0,equal_nan=True)
 roots=pd.Series(pd.NaT,index=n.index,dtype='datetime64[ns]');root=pd.NaT
 for t,r in n.iterrows():
  if r.entered==1:root=t
  if r.target!=1:root=pd.NaT
  roots.at[t]=root
 raises=[]
 for k in range(1,len(n)):
  t=n.index[k];p=n.index[k-1]
  if n.at[t,'target']!=1 or n.at[p,'target']!=1 or roots.at[t]!=roots.at[p]:continue
  if not n.at[t,'floor']>n.at[p,'floor']:continue
  e=ev.loc[t];known=bool(e.event==1 and pd.notna(e.confirmed_pivot_date) and np.isfinite(e.confirmed_pivot_price) and pd.Timestamp(e.confirmed_pivot_date)<=t and base.at[t,'floor']==e.confirmed_pivot_price and n.at[t,'floor']==base.at[t,'floor'])
  identity=dict(sid=sid,source_sha256=m['source_sha256'][ep],source_kind=raw.at[t,'source_kind'],source_path=raw.at[t,'source_path'],segment=str(raw.at[t,'segment_id']),I_entered=str(roots.at[t]),confirmation_close=str(t),pivot_observed=str(e.confirmed_pivot_date),pivot_price=str(e.confirmed_pivot_price))
  receipt=hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest() if known else None
  raises.append(dict(day=t,previous_day=p,old_I_floor=n.at[p,'floor'],new_I_floor=n.at[t,'floor'],known=known,derived_audit_identity=receipt,**identity))
 cache[sid]=dict(raw=raw,f=f,cp=cp,n=n,base=base,ev=ev,root=roots,raises=raises);return cache[sid]
def parts(day,include_day_buys=False):
 q=defaultdict(lambda:dict(core=0,add=0));cash=defaultdict(lambda:Z)
 for a in j:
  ad=pd.Timestamp(a['day']);side=a['side'];rid=a['round_id'];qty=int(a['q'])
  if ad>day or (ad==day and side.startswith('buy') and not include_day_buys):continue
  value=D(qty)*D(a['exact_price']);fee=D(a['exact_whole_order_fee'])
  if side.startswith('buy'):q[rid]['core' if side=='buy_core' else 'add']+=qty;cash[rid]-=value+fee
  elif side=='sell_add':q[rid]['add']-=qty;cash[rid]+=value-fee
  else:assert qty==sum(q[rid].values());q[rid]=dict(core=0,add=0);cash[rid]+=value-fee
 return q,cash
def net(sid,day,q,cash,price):
 _,fs,par=env['getmeta'](sid,day);px=price*D('.9995');fee=env['fee'](q,px,fs,'sell',par)
 return cash+D(q)*px-fee,fee
out=[]
for z in fixed:
 sid=z['sid'];rid=z['round_id'];day=pd.Timestamp(z['open_day']);t=cal[cal<day][-1];d=load(sid);raw=d['raw'];f=d['f'];cp=d['cp'];n=d['n']
 b=next(a for a in j if a['round_id']==rid and a['side']=='buy_core');fill=pd.Timestamp(b['day']);fillprior=cal[cal<fill][-1]
 q,cash=parts(day);pq,pcash=parts(t,True);qty=sum(q[rid].values());assert qty==z['q'] and q[rid]['add']==0 and sum(pq[rid].values())==qty
 assert not [a for a in j if a['round_id']==rid and pd.Timestamp(a['day'])<=day and not (pd.Timestamp(a['day'])==day and a['side'].startswith('buy')) and a['side']!='buy_core']
 hist=cal[(cal>=fill)&(cal<=day)];p=raw.reindex(hist);fac=D(str(raw.at[t,'adjustment_factor']))
 lineage=p[['source_kind','source_path','segment_id']].astype('string');sourceknown=bool(lineage.notna().all().all() and lineage.eq(lineage.iloc[0]).all().all() and all(env['flags'](r) for r in p.to_dict('records')))
 factorok=bool(np.isclose(p.adjustment_factor.to_numpy(float),float(fac),rtol=1e-11,atol=0).all())
 original_root=d['root'].at[fillprior];sameI=bool(pd.notna(original_root) and d['root'].reindex(hist[hist<=t]).eq(original_root).all())
 iq=bool(f.at[t,'e0_ready']==1 and f.at[t,'g_ready']==True and f.at[t,'i_target']==1 and np.isfinite(f.at[t,'i_floor']) and f.at[t,'i_floor']>0)
 floor=D(str(f.at[t,'i_floor']))/fac;op=D(str(raw.at[day,'raw_open']));cl=D(str(raw.at[t,'raw_close']))
 lineclose,fscl=net(sid,t,qty,pcash[rid],floor);lineopen,fsop=net(sid,day,qty,cash[rid],floor)
 closep,_=net(sid,t,qty,pcash[rid],cl);openp,_=net(sid,day,qty,cash[rid],op)
 raises=[a for a in d['raises'] if fill<=a['day']<=t and pd.Timestamp(a['I_entered'])==original_root]
 for a in raises:structural.append(dict(round_id=rid,fixed_open=day,**a))
 latest=raises[-1] if raises else None
 newknown=bool(latest is not None and latest['known'] and latest['new_I_floor']==n.at[t,'floor'] and sourceknown and factorok and sameI)
 m3=bool(sectors.loc[(z['sector'],t)]==1 and K.at[t,sid]==True and MR.at[t,sid]==True)
 netprotected=bool(lineclose>=0 and lineopen>=0)
 cert=bool(ledger[z['open_day']]['OPEN']['certified'] and ledger[str(t.date())]['CLOSE']['certified'])
 eligible=bool(z['scope']=='ORIGINAL_PROBE_PRIMARY' and newknown and iq and m3 and netprotected and closep>0 and openp>0 and op>floor and cert)
 cost=-cash[rid];A=D(qty)*op;F=D(qty)*floor;R0=max(Z,A-F);P0=max(Z,min(A,cost)-F);G=max(Z,A-max(F,cost));assert abs(R0-P0-G)<D('1e-20')
 row=dict(z,signal_CLOSE=t,actual_first_fill=fill,original_I_entered=original_root,raw_OPEN=op,raw_CLOSE=cl,raw_I_floor=floor,
 floor_at_first_fill_signal=D(str(f.at[fillprior,'i_floor']))/D(str(raw.at[fillprior,'adjustment_factor'])),I_qualified=iq,sector_M3=sectors.loc[(z['sector'],t)],stock_M3_known=bool(K.at[t,sid]),stock_M3=bool(MR.at[t,sid]),source_known=sourceknown,factor_unchanged=factorok,same_I=sameI,
 genuine_postfill_I_raise_count=len(raises),new_structure_known=newknown,latest_I_raise_confirmed=latest['day'] if latest else None,latest_pivot_observed=latest['pivot_observed'] if latest else None,
 structure_confirmed_at_immediately_prior_CLOSE=bool(latest is not None and latest['day']==t),new_structure_identity=latest['derived_audit_identity'] if latest else None,
 round_trade_cash=cash[rid],round_recognized_receivable=Z,round_paid_dividend=Z,whole_round_NET80_at_CLOSE=closep,whole_round_NET80_at_OPEN=openp,
 whole_round_NET80_at_I_line_CLOSE_fee=lineclose,whole_round_NET80_at_I_line_OPEN_fee=lineopen,I_line_dated_sell_fee=fsop,
 protected_cost_condition=netprotected,positive_CLOSE_OPEN=bool(closep>0 and openp>0),OPEN_above_I=bool(op>floor),prior_CLOSE_fresh_CP=bool(cp.at[t,'receipt']),
 actual_scope_is_probe=z['scope']=='ORIGINAL_PROBE_PRIMARY',promotion_candidate=eligible,nominal_risk=R0,remaining_principal=P0,profit_giveback=G,
 potential_probe_release=R0 if eligible else Z,potential_all_account_risk_release=Z)
 out.append(row)
rows=pd.DataFrame(out);rows.to_csv(O/'FIXED_PROBE_AND_CP_CONTROLS.csv',index=False)
pd.DataFrame(structural).to_csv(O/'POSTFILL_I_STRUCTURE_IDENTITIES.csv',index=False)
primary=rows[rows.actual_scope_is_probe]
summary=[];navqa=[]
for ds in days:
 day=pd.Timestamp(ds);q,cash=parts(day);gross=Z
 for rid,v in q.items():
  qty=sum(v.values())
  if qty:gross+=D(qty)*D(str(load(arc[rid]['sid'],False)['raw'].at[day,'raw_open']))
 batch=next(a for a in au if a['type']=='ALL_RESERVATIONS_COMPLETE' and a['day'][:10]==ds)
 pre=D(batch['cash_before_fills'])+D(ledger[ds]['OPEN']['receivable'])+gross
 bc=Z;bm=Z
 for a in j:
  if a['day'][:10]==ds and a['side'].startswith('buy'):
   bc+=D(a['q'])*D(a['exact_price'])+D(a['exact_whole_order_fee']);bm+=D(a['q'])*D(str(load(arc[a['round_id']]['sid'],False)['raw'].at[day,'raw_open']))
 residual=pre-bc+bm-D(ledger[ds]['OPEN']['NAV']);assert residual==0
 z=primary[primary.open_day==ds]
 summary.append(dict(open_day=ds,probe_names=len(z),new_I_structure=int(z.new_structure_known.sum()),I_line_cost_protected=int(z.protected_cost_condition.sum()),positive_CLOSE_OPEN=int(z.positive_CLOSE_OPEN.sum()),eligible=int(z.promotion_candidate.sum()),nominal_risk=sum(z.nominal_risk,Z),remaining_principal=sum(z.remaining_principal,Z),profit_giveback=sum(z.profit_giveback,Z),potential_probe_release=sum(z.potential_probe_release,Z),all_account_risk_release=Z))
 navqa.append(dict(open_day=ds,original_prebuy_NAV=pre,residual=residual))
pd.DataFrame(summary).to_csv(O/'FIXED_DAY_SUMMARY.csv',index=False);save('FIXED_DAY_SUMMARY.json',summary);save('NAV_QA.json',navqa)
save('SUMMARY.json',dict(primary_observations=len(primary),primary_stocks=primary.sid.nunique(),controls=len(rows)-len(primary),native_rows=native_rows,
 primary_genuine_new_I_structure=int(primary.new_structure_known.sum()),primary_protected_I_line=int(primary.protected_cost_condition.sum()),
 primary_positive_CLOSE_OPEN=int(primary.positive_CLOSE_OPEN.sum()),eligible=int(primary.promotion_candidate.sum()),factor_or_source_unknown=int((~primary.source_known|~primary.factor_unchanged).sum()),
 changed_source_files=0,new_accounts=0,new_promotions=0,new_ADD=0,stop=not bool(primary.promotion_candidate.any())))
assert all(sha(p)==h for p,h in S.items());save('SOURCE_SHA256.json',S)
print((O/'SUMMARY.json').read_text());print(pd.DataFrame(summary).to_string(index=False))
print(rows[['open_day','name','scope','raw_I_floor','new_structure_known','whole_round_NET80_at_OPEN','whole_round_NET80_at_I_line_OPEN_fee','prior_CLOSE_fresh_CP']].to_string(index=False))
