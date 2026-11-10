"""Read completed R1/B_diag journals; never instantiate an account runner."""
import collections,gzip,inspect,json,time
from decimal import Decimal as D
from pathlib import Path
import pandas as pd
import adapter_r1 as R
L=R.L;J=R.J;OUT=R.O/'analysis';OLD=R.BASE.O/'run';NEW=R.O/'run';Z=D(0)
def gz(p):
 with gzip.open(p,'rt') as f:return json.load(f)
def rows(p):
 with gzip.open(p,'rt') as f:
  for l in f:yield json.loads(l)
def label_accounts(path):return gz((OLD if Path(path).name=='A.json.gz' else NEW)/'pair/B.json.gz')
def label_rows(path):
 for alias,origin in [('A',OLD),('B',NEW)]:
  for r in rows(origin/'pair'/Path(path).name):
   if r['account']=='B':yield dict(r,account=alias)
def main():
 t=time.monotonic();assert all(L.read(p/'DONE.json')['completed'] for p in (OLD,NEW));assert L.read(NEW/'FREEZE.json')['valid_R1_resume'];assert L.read(R.O/'RESUME_CLASS_GATE.json')['passed'];OUT.mkdir(exist_ok=True)
 m=J.W.load('R1_original_saved_analyzer',J.O/'analyze_saved.py');source=inspect.getsource(m.main)
 needle="out=J.O/('run-'+scope);pair=out/'pair';assert L.read(out/'DONE.json')['completed']"
 assert source.count(needle)==1;source=source.replace(needle,"out=OUT;pair=out/'read_only_alias';assert True")
 env=dict(m.__dict__,gz=label_accounts,rows=label_rows,OUT=OUT);exec(source,env);env['main']('read-only')
 labels={'A':'B_diag','B':'R1_diag'}
 s=L.read(OUT/'SUMMARY.json');s['metrics']={labels[k]:v for k,v in s['metrics'].items()};s['source_aliases']=labels;L.save(OUT/'SUMMARY.json',s)
 meta=L.read(Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/inputs-v2/metadata.json'))
 for n in ['SIX_CASES','INDUSTRY_MONEY_CONTRIBUTION','OPPORTUNITY_FUNDING_FUNNEL']:
  data=L.read(OUT/(n+'.json'))
  for x in data:
   x['account']=labels[x['account']]
   if 'sector' in x:x['industry']=next(v['industry'] for v in meta.values() if v['sector_id']==x['sector'])
  L.save(OUT/(n+'.json'),data)
 a=gz(NEW/'pair/B.json.gz');audit=L.read(NEW/'R1_AUDIT.json');reserved={r['CP1_id']:r for r in audit['actual_reservations']};previews={r['CP1_id']:r for r in audit['opening_eligible_previews']}
 journal=[x for x in a['journal'] if x['kind']=='real_buy_fill'];tagged=[x for x in journal if x.get('CP1_id') in reserved];tagged_ids={x['layer'] for x in tagged};filled_cp={x['CP1_id'] for x in tagged}
 byreceipt=collections.Counter()
 for x in tagged:byreceipt[x['CP1_id']]+=x['shares']
 assert all(r['quantity']==previews[rid]['minimum_quantity'] and r['pool']=='confirmed' for rid,r in reserved.items())
 assert all(n<=reserved[rid]['quantity'] for rid,n in byreceipt.items())
 sm={x['symbol']:x for x in L.read(L.U/'STOCK_MANIFEST.json')};price={sid:pd.read_parquet(sm[sid]['refs']['facts'],columns=['raw_close']).raw_close for sid in {x['sid'] for x in tagged}}
 r1layers=[];partition=collections.defaultdict(lambda:Z);fees=Z;cash=Z;excess=[]
 buys={x['layer']:x for x in a['trades'] if x['side']=='buy'}
 for x in a['layers']:
  if x['id'] not in tagged_ids:continue
  tr=buys[x['id']];j=next(j for j in tagged if j['layer']==x['id']);r=reserved[j['CP1_id']];cost=D(tr['gross_cny'])+D(tr['fees_cny']);mark=D(str(price[x['sid']].asof(pd.Timestamp(J.END))))
  pnl=D(x['cash'])+D(x['dividend'])+D(x['qty'])*mark;tail=pnl/cost>=D('.3');prefix='open' if x['qty'] else 'closed';partition[prefix+('_loss' if pnl<0 else '_tail_profit' if tail else '_ordinary_profit')]+=pnl
  cash+=cost;fees+=D(tr['fees_cny']);over=D(tr['gross_cny'])>D(r['max_gross'])
  if over:excess.append(dict(layer=x['id'],gross=tr['gross_cny'],max_gross=r['max_gross']))
  r1layers.append(dict(layer=x['id'],sid=x['sid'],name=meta[x['sid']]['name'],industry=meta[x['sid']]['industry'],signal_at=x['signal_at'],opened=x['opened'],closed=x['closed'],actual_buy_shares=tr['shares'],initial_qty_field_after_actions=x['initial_qty'],remaining_qty=x['qty'],buy_gross=tr['gross_cny'],buy_cash=cost,net_contribution=pnl,tail_ge30pct=tail,actual_gross_above_frozen4pct=over,original_receipt=j['CP1_id'],frozen_max_gross=r['max_gross']))
 for tr in a['trades']:
  if tr['side']!='sell':continue
  fees+=sum((D(tr['fees_cny'])*D(p['shares'])/D(tr['shares']) for p in tr['parts'] if p['layer'] in tagged_ids),Z)
 counts=dict(preview_eligible_receipts=len(previews),admitted_reserved_receipts=len(reserved),actual_filled_receipts=len(filled_cp),reserved_unfilled_receipts=len(reserved)-len(filled_cp),actual_buy_fill_records=len(tagged),ordinary_buy_fill_records=len(journal)-len(tagged),actual_R1_buy_cash=cash,allocated_R1_buy_and_sell_fees=fees,actual_gross_above_frozen4pct=excess,all_reservations_exact_opening_minimum_and_confirmed=True,filled_receipt_share_totals=dict(byreceipt),partially_filled_receipts=[rid for rid,n in byreceipt.items() if n<reserved[rid]['quantity']],tagged_layer_net_contribution=sum(partition.values(),Z),tagged_layer_partitions=dict(partition),interpretation='R1-only immediate unlock at this endogenous account state; tagged sleeve contribution is descriptive, not total policy causal increment')
 L.save(OUT/'R1_ONLY_COUNTS_AND_CONTRIBUTION.json',counts);L.save(OUT/'R1_ACTUAL_LAYERS.json',r1layers)
 named={}
 for sid in ['300308.SZ','300502.SZ']:
  op=[x for x in rows(NEW/'pair/opportunities.jsonl.gz') if x['sid']==sid]
  f=[x for x in rows(NEW/'pair/funding.jsonl.gz') if x['sid']==sid]
  ts=[x for x in a['trades'] if x['security_id']==sid];own=[x for x in r1layers if x['sid']==sid]
  named[sid]=dict(name=meta[sid]['name'],raw_I_Q_true_stock_days=sum(x['core_Q'] is True for x in op),fresh_CP1=sum(bool(x['CP1_id']) for x in op),fresh_CP1_Q_true=sum(bool(x['CP1_id']) and x['mobile_Q'] is True for x in op),funding_attempt_results=dict(collections.Counter(x['result'] for x in f)),buy_fills=sum(x['side']=='buy' for x in ts),R1_layers=own,actual_transactions=ts)
 L.save(OUT/'NAMED_STOCKS.json',named)
 bridges=list(rows(NEW/'pair/balances.jsonl.gz'));maxima={k:max(abs(D(str(r[k]))) for r in bridges) for k in ['independent_NAV_difference','budget_NAV_difference','spendable_difference','reserved_difference','capital_occupancy_difference','maximum_stock_quantity_difference']}
 native_exits=sum(x['kind']=='exit_request' for x in a['audit']);sells=sum(x['side']=='sell' for x in a['trades'])
 L.save(OUT/'VERIFICATION.json',dict(days=len(bridges),maximum_absolute_gaps=maxima,exit_requests=native_exits,actual_sell_fill_records=sells,terminal_pending_exit_stocks=len(a['exits']),sources={str(p/'pair/B.json.gz'):L.sha(p/'pair/B.json.gz') for p in (OLD,NEW)},new_account_runs=0,seconds=time.monotonic()-t,baseline_not_replayed=True))
 print('R1_ANALYSIS_DONE',json.dumps(J.W.canon(dict(metrics=s['metrics'],R1_counts=counts,named={k:{x:v for x,v in y.items() if x not in ['R1_layers','actual_transactions']} for k,y in named.items()})),ensure_ascii=False),flush=True)
if __name__=='__main__':main()
