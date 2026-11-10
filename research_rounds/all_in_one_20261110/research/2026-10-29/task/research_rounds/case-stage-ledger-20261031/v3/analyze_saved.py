"""Read saved journals only. Reconcile contributions; no new trading paths."""
from pathlib import Path
from decimal import Decimal as D
import argparse,collections,gzip,json,math,time
import pandas as pd
import launch_v3 as L
J=L.J;Z=D(0)
def gz(p):
 with gzip.open(p,'rt') as f:return json.load(f)
def rows(p):
 with gzip.open(p,'rt') as f:
  for line in f:yield json.loads(line)
def day(at):return str(at)[:10]
def num(x):return D(str(x))

def main(scope):
 started=time.monotonic();out=J.O/('run-'+scope);pair=out/'pair';assert L.read(out/'DONE.json')['completed']
 sm={x['symbol']:x for x in L.read(L.U/'STOCK_MANIFEST.json')}
 meta=L.read(WROOT/'research_rounds/a-share-selection-e0-20261024/inputs-v2/metadata.json')
 sector={s:meta[s]['sector_id'] for s in sm};prices={}
 accounts={k:gz(pair/(k+'.json.gz')) for k in ('A','B')}
 daily=collections.defaultdict(list)
 for r in rows(pair/'daily.jsonl.gz'):daily[r['account']].append(r)
 for sid in sorted({t['security_id'] for a in accounts.values() for t in a['trades']}):
  f=pd.read_parquet(sm[sid]['refs']['facts'],columns=['raw_close']).loc[:J.END]
  prices[sid]=f.raw_close.dropna()
 def price(sid,at):
  p=prices[sid].asof(pd.Timestamp(day(at)));assert pd.notna(p) and p>0,(sid,at,'unknown mark')
  return D(str(p))
 weights={};industry_values={};maximum_mark_gap=Z;metrics={};contribution={};new_buy=collections.defaultdict(lambda:Z)
 for name,a in accounts.items():
  peak=D(1000000);dd=Z;expos=[];under_start=None;max_water=0;pause=0;per={};byday={}
  for r in daily[name]:
   d=day(r['at']);nav=num(r['nav']);peak=max(peak,nav);dd=max(dd,1-nav/peak);expos.append(num(r['inventory'])/nav)
   pause+=not r['on'];vals=collections.defaultdict(lambda:Z)
   for sid,q in r['positions'].items():vals[sector[sid]]+=D(q)*price(sid,d)
   gap=sum(vals.values(),Z)-num(r['inventory']);maximum_mark_gap=max(maximum_mark_gap,abs(gap))
   assert abs(gap)<D('.00001'),('original mark source mismatch',name,d,str(gap))
   byday[d]=dict(vals);per[d]={s:v/nav for s,v in vals.items()}
   if nav<peak:
    if under_start is None:under_start=pd.Timestamp(d)
    max_water=max(max_water,(pd.Timestamp(d)-under_start).days)
   else:under_start=None
  weights[name]=per;industry_values[name]=byday
  trade_net=collections.defaultdict(lambda:Z);divs=collections.defaultdict(lambda:Z)
  for t in a['trades']:
   g=sector[t['security_id']];flow=(num(t['gross_cny']) if t['side']=='sell' else -num(t['gross_cny']))-num(t['fees_cny']);trade_net[g]+=flow
   if t['side']=='buy':new_buy[(name,g)]+=num(t['gross_cny'])+num(t['fees_cny'])
  for x in a['audit']:
   if x['kind']=='dividend_accrual':
    e=x['receivable'];sid=e['security_id'];divs[sector[sid]]+=num(e['net_local'])
  final=byday[J.END];allsectors=set(trade_net)|set(divs)|set(final)
  contribution[name]={s:trade_net[s]+divs[s]+final.get(s,Z) for s in allsectors}
  gap=sum(contribution[name].values(),Z)-(num(a['ending_NAV'])-D(1000000));assert abs(gap)<D('.00001'),('sector contribution gap',name,gap)
  closed_loss=sum((-num(x['cash'])-num(x['dividend']) for x in a['layers'] if not x['qty'] and num(x['cash'])+num(x['dividend'])<0),Z)
  fees=sum((num(t['fees_cny']) for t in a['trades']),Z)
  metrics[name]=dict(NAV=a['ending_NAV'],net_profit=num(a['ending_NAV'])-D(1000000),return_pct=(num(a['ending_NAV'])/D(1000000)-1)*100,
   DD_pct=dd*100,longest_observed_underwater_calendar_days=max_water,average_exposure_pct=sum(expos)/len(expos)*100,peak_exposure_pct=max(expos)*100,
   cumulative_buy_cash=sum((v for (k,s),v in new_buy.items() if k==name),Z),fees=fees,buy_fills=sum(t['side']=='buy' for t in a['trades']),sell_fills=sum(t['side']=='sell' for t in a['trades']),
   ACT_paused_closes=pause,closed_negative_layer_loss=closed_loss,record_only_gross_negative_realization_plus_all_fees=sum((num(v) for v in a['budget']['losses'].values()),Z),
   terminal_stock_count=len(daily[name][-1]['positions']),terminal_inventory=daily[name][-1]['inventory'],terminal_sale_AR=daily[name][-1]['sale_receivable'],terminal_dividend_AR=daily[name][-1]['dividend_receivable'],
   industry_contribution_NAV_gap=gap,actual_splits=sum(x['kind'] in ('split','split_fraction_floor_proxy') for x in a['audit']))
 cases=[];old=L.read(J.BASE/'SIX_CASE_BEHAVIOR.json');specs={x['review_id']:x for x in old}
 for rid,oldcase in sorted(specs.items()):
  g,quarter=rid.split('|');year=int(quarter[:4]);q=int(quarter[-1]);start=f'{year}-{3*q-2:02d}-01';end=str(pd.Period(quarter,freq='Q').end_time.date());peakday=oldcase['industry_price_peak']
  for name,a in accounts.items():
   period=[r for r in daily[name] if start<=day(r['at'])<=end];ds=[day(r['at']) for r in period]
   series=[(d,weights[name][d].get(g,Z)) for d in ds];peak_date,peak_weight=max(series,key=lambda x:x[1]);before=[d for d in industry_values[name] if d<start]
   initial=industry_values[name][before[-1]].get(g,Z) if before else Z
   final=industry_values[name][ds[-1]].get(g,Z)
   trades=[t for t in a['trades'] if sector[t['security_id']]==g and start<=day(t['at'])<=end]
   buys=[t for t in trades if t['side']=='buy'];active=sum((num(t['gross_cny'])+num(t['fees_cny']) for t in buys),Z)
   flow=sum((((num(t['gross_cny']) if t['side']=='sell' else -num(t['gross_cny']))-num(t['fees_cny'])) for t in trades),Z)
   div=sum((num(x['receivable']['net_local']) for x in a['audit'] if x['kind']=='dividend_accrual' and sector[x['receivable']['security_id']]==g and start<=day(x['receivable']['ex_at'])<=end),Z)
   expansion=[x for x in a['journal'] if x['kind']=='real_buy_fill' and x['role']=='mobile' and x['pool']=='confirmed' and sector[x['sid']]==g and start<=day(x['at'])<=end]
   cases.append(dict(review_id=rid,industry=oldcase['industry'],account=name,first_actual_buy=buys[0] if buys else None,
    first_actual_expansion=expansion[0] if expansion else None,actual_new_buy_cash=active,buy_cash_before_or_at_industry_peak=sum((num(t['gross_cny'])+num(t['fees_cny']) for t in buys if day(t['at'])<=peakday),Z),
    peak_weight_pct=peak_weight*100,peak_weight_day=peak_date,weight_at_preexisting_industry_price_peak_pct=weights[name].get(peakday,{}).get(g,Z)*100,
    preexisting_industry_price_peak=peakday,mean_weight_through_price_peak_pct=sum((w for d,w in series if d<=peakday),Z)/max(1,sum(d<=peakday for d,w in series))*100,
    inherited_industry_value=initial,terminal_industry_value=final,period_contribution=flow+div+final-initial,
    buy_fills=len(buys),sell_fills=len(trades)-len(buys),interpretation='fixed price-selected retrospective case, no privilege in candidate ranking'))
 eligibility=collections.defaultdict(collections.Counter);funding=collections.defaultdict(collections.Counter)
 for r in rows(pair/'opportunities.jsonl.gz'):
  k=(r['account'],r['sector']);eligibility[k]['stock_days']+=1
  eligibility[k]['core_Q_'+str(r['core_Q'])]+=1;eligibility[k]['mobile_Q_'+str(r['mobile_Q'])]+=1
  if r['CP1_id']:eligibility[k]['fresh_stock_CP1']+=1
  if r['roles']:eligibility[k]['legal_role_stock_days']+=1
  if r['core_Q'] is True and not r['held'] and 'core' not in r['roles']:eligibility[k]['core_epoch_lock_inferred_from_exact_branch']+=1
  for x in r['barriers']:eligibility[k]['barrier:'+x]+=1
 for r in rows(pair/'funding.jsonl.gz'):
  funding[(r['account'],sector[r['sid']])][r['result']]+=1
 ftable=[dict(account=k,sector=s,known_stock_opportunity_counts=dict(eligibility[(k,s)]),funding_results=dict(funding[(k,s)])) for k,s in sorted(eligibility)]
 sector_table=[dict(account=k,sector=s,cumulative_new_buy_cash=new_buy[(k,s)],net_contribution=contribution[k].get(s,Z),final_inventory=industry_values[k][J.END].get(s,Z)) for k in ('A','B') for s in sorted(set(contribution[k])|{s for n,s in new_buy if n==k})]
 L.save(out/'SUMMARY.json',dict(metrics=metrics,maximum_direct_price_mark_difference=maximum_mark_gap,analysis_seconds=time.monotonic()-started,
  accounting='sector net trade cashflows + accrued dividends + terminal inventory; all sectors reconcile NAV; original raw-close mark proxy shared',
  no_new_economic_paths=True,opportunity_barriers_can_coexist_not_single_cause_attribution=True,snapshot_and_selected_history_not_OOS=True))
 L.save(out/'SIX_CASES.json',cases);L.save(out/'INDUSTRY_MONEY_CONTRIBUTION.json',sector_table);L.save(out/'OPPORTUNITY_FUNDING_FUNNEL.json',ftable)
 print(json.dumps(L.W.canon(dict(metrics=metrics,strong_case_capital=[x for x in cases if x['review_id'] in ('URFI881267|2025Q3','URFI881124|2025Q4','URFI881101|2026Q1')])),ensure_ascii=False,indent=2))

WROOT=Path('/Users/bytedance/Documents/ChatGPT/money')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--scope',choices=('case','universe'),required=True)
 main(p.parse_args().scope)
