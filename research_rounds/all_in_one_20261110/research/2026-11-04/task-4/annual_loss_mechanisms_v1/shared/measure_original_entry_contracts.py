"""Read saved contracts/raw factors. Diagnostic lower bound only, no order sizing."""
from pathlib import Path
from decimal import Decimal as D
from collections import Counter,defaultdict
import gzip,json,hashlib,pandas as pd
O=Path(__file__).resolve().parent;ROOT=O.parents[1];BASE=ROOT/'new_price_trend_v1/funding/runs/long_OFF/pair';Z=D(0);sources={}
def bind(p):
 p=Path(p);sources[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();return p
def read(p):return json.loads(bind(p).read_text())
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
def load(p,lines=False):
 with gzip.open(bind(p),'rt')as f:return list(map(json.loads,f))if lines else json.load(f)
b=load(BASE/'B.json.gz');ds=load(BASE/'daily.jsonl.gz',True);day={r['at'][:10]:r for r in ds};m={r['symbol']:r for r in read('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')};classes=read(O/'ORIGINAL_BUY_CLASSIFICATIONS.json');annual=read(O/'ANNUAL_LAYER_WEALTH_CHANGES.json');al={(r['year'],r['layer']):r for r in annual};buy=[t for t in b['trades']if t['side']=='buy'and t['at'][:4]in ['2022','2023']]
facts={}
for sid in {t['security_id']for t in buy}:
 facts[sid]=pd.read_parquet(bind(m[sid]['refs']['facts']),columns=['factor','raw_close','close','i_floor','e0_floor','e0_target','i_target','i_buy','g_grade','g_fresh_up'])
rows=[]
for t in buy:
 sid=t['security_id'];date=t['at'][:10];signal=t['signal_at'][:10];f=facts[sid];fr=f.loc[date];sr=f.loc[signal];factor=D(str(fr['factor']));p=D(t['price']);h=D(t['floor'])/factor;q=t['shares'];r=D(q)*max(p-h,Z);nav=D(day[signal]['nav']);year=int(date[:4]);a=al.get((year,t['layer']),{});c=classes[str(t['layer'])]
 rows.append({'year':year,'layer':t['layer'],'sid':sid,'name':c['name'],'kind':t['kind'],'classification':c['classification'],'cycle_id':c['cycle_id'],'cycle_after_prior_closed_loss':c['cycle_after_prior_closed_loss'],'signal_at':t['signal_at'],'opened':t['at'],'shares':q,'price':p,'raw_open':D(t['raw_open']),'signal_NAV':nav,'entry_factor':factor,'entry_floor_a':D(t['floor']),'entry_floor_raw':h,'price_above_entry_floor':p>h,'price_distance_risk_excluding_fees_and_sell_slip':r,'price_distance_risk_pct_signal_NAV':100*r/nav,'original_CORE_budget_comparator':D('.0025')*nav,'lower_bound_exceeds_original_CORE_budget':r>D('.0025')*nav,'annual_layer_wealth_change':a.get('annual_wealth_change'),'signal_raw_close':D(str(sr['raw_close'])),'signal_E0_target':bool(sr['e0_target']),'signal_I_target':bool(sr['i_target']),'signal_i_buy':bool(sr['i_buy']),'signal_G1_grade':float(sr['g_grade']),'source':m[sid]['refs']['facts']})
summary={}
for year in [2022,2023]:
 yr=[r for r in rows if r['year']==year];gr=[]
 for kind in ['core','add']:
  rr=[r for r in yr if r['kind']==kind];high=[r for r in rr if r['lower_bound_exceeds_original_CORE_budget']]
  def stats(xs):
   vv=[D(str(x['annual_layer_wealth_change']))for x in xs if x['annual_layer_wealth_change']is not None]
   return {'layers':len(xs),'annual_wealth_change':sum(vv,Z),'negative_layer_sum':sum((v for v in vv if v<0),Z),'positive_layer_sum':sum((v for v in vv if v>0),Z),'max_initial_price_distance_risk_pct_NAV':max((x['price_distance_risk_pct_signal_NAV']for x in xs),default=None)}
  gr.append({'kind':kind,'all':stats(rr),'price_distance_lower_bound_above_original_CORE_budget':stats(high)})
 summary[str(year)]={'groups':gr,'all_entry_floor_present_and_below_fill':all(r['price_above_entry_floor']for r in yr),'fills':len(yr),'fees':sum((D(t['fees_cny'])for t in b['trades']if t['at'][:4]==str(year)),Z),'explicit_buy_proxy_slip_amount':sum((D(t['shares'])*(D(t['price'])-D(t['raw_open']))for t in b['trades']if t['at'][:4]==str(year)and t['side']=='buy'),Z),'explicit_sell_proxy_slip_amount':sum((D(t['shares'])*(D(t['raw_open'])-D(t['price']))for t in b['trades']if t['at'][:4]==str(year)and t['side']=='sell'),Z)}
save('ALL_1557_INITIAL_PROTECTION_CONTRACTS.json',rows);save('INITIAL_CONTRACT_COVERAGE.json',{'scope':'Saved actual fill quantities x initial floor distance. Comparator .25% is existing CORE budget, not fitted/new threshold. This price-distance risk is only a lower bound to native fee/sell-slip contract and not actual execution loss. No proposed quantities or orders generated.','years':summary,'new_accounts':0,'new_backtests':0,'native_modules_imported':False,'future_outcomes_not_used_as_signal':True});save('ENTRY_CONTRACT_SOURCE_SHA256.json',sources)
print(json.dumps(summary,ensure_ascii=False,default=str))
