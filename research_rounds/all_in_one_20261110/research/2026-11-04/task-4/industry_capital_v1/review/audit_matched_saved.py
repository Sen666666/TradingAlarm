"""Independently rejoin actual old-layer cash/div/qty and all saved fee/value equations.
No Account, path, market mark or source price is recomputed.
"""
from pathlib import Path
from collections import Counter,defaultdict
from decimal import Decimal as D,ROUND_CEILING,ROUND_HALF_UP
from datetime import datetime
import gzip,hashlib,json,time
R=Path(__file__).resolve().parent;I=R.parent;W=I.parent;Z=D(0);ONE=D(1);SLIP=D('.0005')
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def rows(p):
 with gzip.open(p,'rt')as h:
  for x in h:yield json.loads(x)
def dec(x):return D(str(x))
def eff(xs,day):return next(x for x in reversed(xs)if x['from']<=day and(x.get('to')is None or day<x['to']))
t0=time.monotonic();rules=read('/Users/bytedance/Documents/ChatGPT/money/research_rounds/pvr-act-comparison-20261027/execution-rules-v2.json');fc={}
def fee(sid,day,q,p):
 if not q:return Z
 venue=eff(rules['venue_versions'][sid],day)['venue'];s=eff(rules['fee_versions'][venue],day)['schedule'];ans=Z
 for c in s['components']:
  if c.get('side','both')not in ['sell','both']:continue
  basis=c.get('amount_basis','notional');amt=q*p if basis=='notional'else q if basis=='shares'else q*dec(rules['security_metadata'][sid]['par_value'])
  v=max(dec(c.get('minimum_local',0)),amt*dec(c['rate']))
  if c.get('maximum_local')is not None:v=min(v,dec(c['maximum_local']))
  if c.get('rounding_unit')is not None:
   u=dec(c['rounding_unit']);v=(v/u).to_integral_value(rounding=ROUND_CEILING if c.get('rounding_mode')=='ceil'else ROUND_HALF_UP)*u
  ans+=v
 return ans
def liq(sid,d,q,m):
 p=m*(ONE-SLIP);return q*p-fee(sid,d,q,p)if q else Z
snap=read(I/'events/ORIGINAL_EXISTING_LAYER_SNAPSHOTS.json');mark={x['sid']+'|'+x['OPEN']:x for x in read(I/'release_bound/OPEN_MARK_STATUS.json')};base={};pending={};final={}
for w in ['long','strong']:
 root=W/'new_price_trend_v1/funding/runs'/(w+'_OFF')/'pair';base[w]={};pending[w]={}
 for d in rows(root/'daily.jsonl.gz'):
  day=d['at'][:10];base[w][day]={int(x['id']):{k:x[k]for k in ['qty','cash','dividend','closed']}for x in d['layers']};pending[w][day]=set(d['pending_sells'])
 with gzip.open(root/'B.json.gz','rt')as h:b=json.load(h)
 final[w]={int(x['id']):{k:x[k]for k in ['qty','cash','dividend','closed']}for x in b['layers']};del b
def at(w,lid,end):
 if lid in base[w][end]:return base[w][end][lid]
 z=final[w][lid];assert dec(z['qty'])==0 and z['closed'][:10]<=end;return z
basket_count=layer_count=0
def check_basket(b,s,end,unlocked=False):
 global basket_count,layer_count
 ls=s['surviving_existing_layers_at_S0'];locks=set(s['CLOSE_account']['pending_sells'])
 if unlocked:ls=[x for x in ls if x['sid']not in locks and not x['previous_CLOSE_raw_layer'].get('reason')and not x['previous_CLOSE_raw_layer'].get('pending_I_exit_reference')]
 if not ls:assert b['layers']==0;return
 det={int(x['layer']):x for x in b['layers_detail']};assert set(det)=={x['layer']for x in ls};cash=div=Z;qs=defaultdict(lambda:Z);qe=defaultdict(lambda:Z)
 for r in ls:
  lid=int(r['layer']);x=det[lid];start=r['next_CLOSE_raw_layer'];z=at(s['window'],lid,end);q=dec(r['qty_after_original_actions_and_protection_exits']);dc=dec(z['cash'])-dec(start['cash']);dd=dec(z['dividend'])-dec(start['dividend']);assert dec(x['qty_S0'])==q and dec(x['qty_terminal'])==dec(z['qty'])and dec(x['actual_sale_net_wealth_after_anchor'])==dc and dec(x['new_dividend_entitlement_after_anchor'])==dd
  qs[r['sid']]+=q;qe[r['sid']]+=dec(z['qty']);cash+=dc;div+=dd;layer_count+=1
 refs={x['sid']:x for x in b['mark_references']};assert set(refs)==set(qs);g0=l0=tail=Z
 for sid,q in qs.items():
  x=refs[sid];m=dec(x['OPEN_mark']);z=mark[sid+'|'+s['OPEN']];assert m==dec(z['mark'])and x['known_at']==z['known_at']and x['exact_current_raw_OPEN']==z['strict_OPEN_identity'];assert dec(x['initial_qty'])==q and dec(x['terminal_qty'])==qe[sid]
  g0+=q*m;l0+=liq(sid,s['OPEN'],q,m);tail+=liq(sid,end,qe[sid],dec(x['terminal_mark']))
 assert dec(b['G0'])==g0 and dec(b['L0'])==l0 and dec(b['actual_net_sale_wealth_after_anchor'])==cash and dec(b['new_dividend_entitlement_after_anchor'])==div and dec(b['terminal_net_liquidation'])==tail and dec(b['Vh'])==cash+div+tail
 assert dec(b['old_net_return_from_current_gross_mark_pct'])==(cash+div+tail)/g0*100-100 or abs(dec(b['old_net_return_from_current_gross_mark_pct'])-((cash+div+tail)/g0-1)*100)<D('1e-22')
 assert abs(dec(b['old_keep_value_relative_to_sell_now_pct'])-((cash+div+tail)/l0-1)*100)<D('1e-22');basket_count+=1
minimal={x['key']:{'snapshot_key':x['snapshot_key']}for x in rows(I/'events/CORE_SECTOR_REJECT_EVENTS_WITH_PREFIX.jsonl.gz')if x['is_first_sector_reject_in_original_source_I_epoch']}
co=Counter();quads=Counter();groups=defaultdict(list);seen=set();gapc=Counter();partial_examples=[]
for x in rows(I/'MATCHED_HOLDINGS.jsonl.gz'):
 k=x['key'];assert k in minimal and k not in seen;seen.add(k);co[x['matched_status']]+=1;n=x['new'];end=n.get('horizon_CLOSE_day')
 if x['matched_status']=='candidate_unfilled_or_unknown':assert not n['known_net']or not n.get('entry_cash_actual')or dec(n['entry_cash_actual'])<=0 or n.get('unknown_reason');continue
 s=snap[minimal[k]['snapshot_key']]
 if 'old_all'in x:check_basket(x['old_all'],s,end)
 if 'old_prior_CLOSE_unlocked'in x:check_basket(x['old_prior_CLOSE_unlocked'],s,end,True)
 if x['matched_status']!='known_conditional_match':continue
 old=x['old_all'];cn=dec(n['entry_cash_actual']);vn=dec(n['wealth_from_invested_Cn_net_liquidation']);g0=dec(old['G0']);l0=dec(old['L0']);vh=dec(old['Vh']);nr=(vn/cn-1)*100;orr=(vh/g0-1)*100;eq=cn*vh/l0;assert dec(x['new_net_return_pct'])==nr and dec(x['equal_cash_old_terminal'])==eq and dec(x['equal_cash_gap'])==vn-eq
 q='zero_boundary'if nr==0 or orr==0 else('new_profit'if nr>0 else'new_loss')+'_'+('old_profit'if orr>0 else'old_loss');assert q==x['quadrant'];quads[q]+=1
 if x.get('required_release_lower_bound')is not None:
  r=dec(x['required_release_lower_bound']);assert r==dec(x['release_bound']['required_sector_relief_lower_bound_SAFE']);assert dec(x['release_adjusted_conditional_gap'])==(vn-cn)-(r/g0)*(vh-l0);gapc['relief_scaled_scenarios']+=1;gapc['relief_above_entire_old_gross']+=r>g0
 groups[x['window'],x['classification']].append(x)
assert len(seen)==8335
summary=read(I/'MATCHED_SUMMARY.json');assert sum(x['events']for x in summary)==8335 and sum(x['matched']for x in summary)==co['known_conditional_match']
for g in summary:
 known=groups[tuple(g['group'])];assert len(known)==g['matched']and Counter(x['quadrant']for x in known)==Counter(g['quadrants'])
res={'passed':True,'scope':'All8335 saved matched rows and original old-layer cash/dividend/units independently rejoined; dated sell-fee formulas, old G0/L0/Vh and new/old equal-cash and relief-scale scenario arithmetic checked. No new source mark/path/account.','events':8335,'matched_status_counts':dict(co),'known_quadrants':dict(quads),'old_baskets_checked_including_unlocked':basket_count,'old_layer_cash_dividend_quantity_checks':layer_count,'scenario_counts':dict(gapc),'all_original_layer_CF_differences_exact':True,'all_per_stock_hypothetical_fees_independently_recomputed':True,'all_capital_match_equations_exact':True,'saved_current_OPEN_marks_reused_and_matched':True,'terminal_price_source_recalculated':False,'required_relief_scenario_interpretation':'Secondary proportional old-basket scenario at a necessary gross-release lower bound; neither FIFO executable nor a universal economic upper bound. Sign of Vh-L0 changes monotonicity in release amount.','not_financial_admission':True,'reviewer_new_accounts':0,'reviewer_new_marks':0,'source_sha256':{str(p.resolve()):sha(p)for p in [Path(__file__),I/'MATCHED_HOLDINGS.jsonl.gz',I/'MATCHED_SUMMARY.json',I/'MATCHED_SCOPE.json',I/'analyze_matched_holdings.py']},'seconds':time.monotonic()-t0}
(R/'MATCHED_HOLDINGS_SAVED_REVIEW.json').write_text(json.dumps(res,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in res.items()if k!='source_sha256'},indent=2))
