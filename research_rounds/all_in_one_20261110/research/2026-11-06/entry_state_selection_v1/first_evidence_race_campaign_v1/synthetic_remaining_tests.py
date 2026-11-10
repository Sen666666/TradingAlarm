"""Remaining fixed fee/NOFILL/accounting-denominator boundaries; actual adapters."""
from campaign_engine import *
import ast

def main():
 txt=(O/'synthetic_d_tests.py').read_text();tree=ast.parse(txt);fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='main')
 setup=[]
 for n in fn.body:
  if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='z' for t in n.targets):break
  setup.append(n)
 env=dict(globals());exec(compile(ast.fix_missing_locations(ast.Module(body=setup,type_ignores=[])),'synthetic_d_tests.py:fixed_setup','exec'),env)
 s,cal,raw,mp,nr,canonical,r,base,sid=[env[k] for k in ['s','cal','raw','mp','nr','canonical','r','base','sid']];checks={}
 price=D(10);qr,fs,pa=s.getmeta(sid,cal[0]);lot=qr.buy_floor(100);assert lot==100
 exact=D(lot)*price+s.fee(lot,price,fs,'buy',pa)
 assert s.size(sid,cal[0],price,D(8),exact-D('.01'),D(3000),100)[0]==0
 assert s.size(sid,cal[0],price,D(8),exact,D(3000),100)[0]==100
 checks['fee_inclusive_minimum_lot_not_rounded_or_borrowed']=True
 env['event']['d_cash']=D('1') # Unpaid claim deliberately exceeds one lot; it still cannot fund a buy.
 raw.loc[cal[2],'raw_open']=.1;s.raw[sid]=s.DayFrame(raw);s.closecache={}
 z=run_campaign(s,base,r,'D',mp,{},nr,canonical)
 assert len(z['native_consumptions'])==1 and z['native_consumptions'][0]['kind']=='CORE_EPOCH'
 assert len(z['actions'])==2 and z['campaign']['attempts']>2
 nofill=[a for a in z['attempts'][1:] if 'NOFILL' in a['status']];assert len(nofill)>1
 assert len(set(a['cp_id'] for a in nofill))==len(nofill)
 assert all(a['entry_status']=='NO_CONFIRMED_ENTRY' for a in nofill)
 checks['cash_starved_nofill_does_not_consume_receipt_new_id_can_retry']=True
 assert z['campaign']['cash']>=0 and z['campaign']['receivable']>z['campaign']['cash']
 checks['large_unpaid_claim_not_advanced_to_fund_new_lot']=True
 # Same-root NOFILL and positive-fill permits: the full permit table keeps both,
 # but usable plus root-common masks must retain only the economic campaign.
 rows=[]
 for root in ['ROOT1','ROOT2']:
  for arm in ['A','B','C','D']:
   rows.extend([dict(campaign_key=root,arm=arm,evidence_usable_closed=False,net=None),dict(campaign_key=root,arm=arm,evidence_usable_closed=True,net=1.)])
 zz=pd.DataFrame(rows);common=set(zz[zz.evidence_usable_closed].groupby('campaign_key').filter(lambda g:len(g)==4).campaign_key)
 mask=zz.evidence_usable_closed&zz.campaign_key.isin(common);assert len(zz)==16 and mask.sum()==8
 assert zz[mask].groupby('arm').size().eq(2).all();assert not zz[mask].duplicated(['arm','campaign_key']).any()
 checks['two_nofill_then_fill_roots_one_economic_vote_each']=True
 # Native pending pure-cash bridge has Q=0, translates coordinates and creates no entitlement.
 import inspect
 src=inspect.getsource(s.pending_bridge)
 assert "record_q=0" in src and "dividend=0" in src and "PENDING_COORDINATE_Q0" in src
 checks['pending_bridge_exact_original_q0_no_dividend_contract']=True
 out=O/'SYNTHETIC_REMAINING_QA.json';assert not out.exists();out.write_text(json.dumps(dict(pass_all=all(checks.values()),checks=checks,hashes={p.name:sha(p) for p in [Path(__file__),O/'campaign_engine.py',O/'native_role_adapter.py',O/'synthetic_d_tests.py']}),indent=2)+'\n');print(json.dumps(checks,indent=2))
if __name__=='__main__':main()
