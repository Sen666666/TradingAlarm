"""Read-only full Jan04-Jan28 native history; no account events or future labels."""
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict
import argparse,json,sys
import month_worker as W
C=W.C;O=W.O;Z=D(0);EPS=D('0.00000001')
def dd(points):
 peak=D(1000000);peak_at='INITIAL';worst=Z;result={}
 for at,v in points:
  if v>peak:peak=v;peak_at=at
  loss=1-v/peak
  if loss>worst:worst=loss;result=dict(peak_at=peak_at,trough_at=at,peak=peak,trough=v)
 return dict(max_drawdown_pct=worst*100,**result)
def main():
 p=argparse.ArgumentParser();p.add_argument('--arm',required=True);a=p.parse_args();arm=a.arm
 assert W.read(O/(arm+'-DONE.json'))['passed'];progress=W.read(O/'progress'/(arm+'.json'))
 rec=progress['record'];r=C.ContinuationRunner.restore(rec['checkpoint'],registry_sha=progress['registry_sha256'])
 assert str(r.last_completed_event)=='2022-01-28 15:10:00+08:00'
 account=r.account;at=r.last_completed_event;balance=account.bridge(at);initial=D(1000000)
 assert all(v==1 for v in account.share_ratio.values()),'actual share conversion attribution needs explicit extension'
 closes=[e for e in r.events if e['phase']=='CLOSE'];days=[e['at'].date().isoformat() for e in closes]
 assert days==r.inputs.days and len(days)==19 and len(r.events)==40
 curve=[dict(at=str(e['at']),phase=e['phase'],NAV=e['bridge']['nav'],available=e['bridge']['available'],inventory=e['bridge']['inventory'],fees=e['bridge']['fees_cny']) for e in r.events]
 mean_nav=sum((e['bridge']['nav'] for e in closes),Z)/len(closes)
 sectors={s:dict(sector=s,buy_gross=Z,sell_gross=Z,fees=Z,buy_fills=0,sell_fills=0,bought_stocks=set(),held_stock_days=0,exposure_days=0,end_market_value=Z,mean_close_weight=Z,peak_close_weight=Z,realized_net=Z,unrealized_net=Z) for s in r.inputs.m['sectors']}
 stock_sector=account.market.sectors
 for e in closes:
  t=e['at'];b=e['bridge'];mv=defaultdict(lambda:Z);counts=defaultdict(int)
  for sid,q in b['quantities'].items():
   if not q:continue
   value=D(q)*account.market.native.latest_mark(sid,t).cny_price(t);mv[stock_sector[sid]]+=value;counts[stock_sector[sid]]+=1
  assert abs(sum(mv.values(),Z)-b['inventory'])<EPS,'historical native mark/bridge inventory mismatch'
  for sec,row in sectors.items():
   weight=mv[sec]/b['nav'];row['mean_close_weight']+=weight/len(closes);row['peak_close_weight']=max(row['peak_close_weight'],weight);row['held_stock_days']+=counts[sec];row['exposure_days']+=int(mv[sec]>0)
 fills={f.receipt_id:f for f in account.fills};buygross=Z;sellgross=Z;fees=Z
 for f in account.fills:
  row=sectors[stock_sector[f.security_id]];fees+=f.fees_cny;row['fees']+=f.fees_cny
  if f.side=='buy':buygross+=f.gross_cny;row['buy_gross']+=f.gross_cny;row['buy_fills']+=1;row['bought_stocks'].add(f.security_id)
  else:sellgross+=f.gross_cny;row['sell_gross']+=f.gross_cny;row['sell_fills']+=1
 assert fees==account.fees_cny
 bought={v['layer']:fills[v['receipt']] for v in account.inventory_map.values() if v.get('parent') is None}
 sold_net=defaultdict(lambda:Z);sold_q=defaultdict(int)
 for trade in account.trades:
  if trade['side']=='sell':
   for part in trade['parts']:sold_net[part['layer']]+=part['net_cash'];sold_q[part['layer']]+=part['shares']
 stock_pnl=defaultdict(lambda:dict(realized_net=Z,unrealized_net=Z,end_market_value=Z))
 realized=Z;unrealized=Z;mv_total=Z
 for layer in account.layers:
  lid=layer['id'];f=bought[lid];meta=account.capital_meta[lid];q=layer['qty'];sq=f.shares-q
  assert meta['ratio']==1 and sq==sold_q[lid] and sq>=0
  assert abs(layer['cash']-(-f.gross_cny-f.fees_cny+sold_net[lid]))<EPS
  allocated_buy_fee=f.fees_cny*D(sq)/f.shares;remaining_buy_fee=f.fees_cny-allocated_buy_fee
  rp=sold_net[lid]-D(sq)*meta['unit_cost']-allocated_buy_fee
  mv=D(q)*account.market.native.latest_mark(layer['sid'],at).cny_price(at) if q else Z
  up=mv-D(q)*meta['unit_cost']-remaining_buy_fee
  realized+=rp;unrealized+=up;mv_total+=mv;sec=meta['sector'];assert sec==stock_sector[layer['sid']]
  sectors[sec]['realized_net']+=rp;sectors[sec]['unrealized_net']+=up;sectors[sec]['end_market_value']+=mv
  s=stock_pnl[layer['sid']];s['realized_net']+=rp;s['unrealized_net']+=up;s['end_market_value']+=mv
 dividend=account.dividend_income;net=balance['nav']-initial
 assert abs(mv_total-balance['inventory'])<EPS and abs(realized+unrealized+dividend-net)<EPS
 for sec,row in sectors.items():
  row['bought_stock_count']=len(row['bought_stocks']);row['bought_stocks']=sorted(row['bought_stocks']);row['net_pnl_ex_dividend']=row['realized_net']+row['unrealized_net'];row['turnover_one_way_equivalent']=(row['buy_gross']+row['sell_gross'])/(2*mean_nav)
 summary=dict(arm=arm,period=['2022-01-04','2022-01-28'],initial_cash=initial,final_NAV=balance['nav'],net_pnl=net,return_pct=(balance['nav']/initial-1)*100,close_drawdown=dd([(str(e['at']),e['bridge']['nav']) for e in closes]),event_observation_drawdown=dd([(str(e['at']),e['bridge']['nav']) for e in r.events]),realized_net=realized,unrealized_net=unrealized,recognized_dividend=dividend,PnL_reconciliation_difference=realized+unrealized+dividend-net,fee_allocation='Actual buy fee allocated by actual sold/original fill shares per native layer; remaining fee capitalized in unrealized, actual sell fees in net proceeds. No actual share splits; rights actual ratio1.',fees=fees,buy_gross=buygross,sell_gross=sellgross,buy_fills=sum(f.side=='buy' for f in account.fills),sell_fills=sum(f.side=='sell' for f in account.fills),turnover_one_way_equivalent=(buygross+sellgross)/(2*mean_nav),turnover_two_sided_gross_nav=(buygross+sellgross)/mean_nav,mean_close_NAV=mean_nav,mean_close_invested_weight=sum((e['bridge']['inventory']/e['bridge']['nav'] for e in closes),Z)/len(closes),end_cash=balance['available'],end_inventory=balance['inventory'],end_positions=len(account.positions),end_pending=len(account.pending),end_buys=len(account.buys),end_exits=len(account.exits),industries_bought=sum(v['buy_fills']>0 for v in sectors.values()),industry_denominator=len(sectors),stock_domain=len(r.inputs.ids),close_points=len(closes),event_points=len(r.events),rights_actions=r.action_log,cursor=str(r.last_completed_event),trusted_checkpoint=rec['checkpoint'],checkpoint_sha256=rec['sha256'],registry_sha256=progress['registry_sha256'],all_certificates_recomputed=len(r.authority.certificates),day_proxy='unchanged native daily HLV postcheck; event DD is sampled events, not tick/intraday maximum',R0_overlay=False)
 W.save(O/'analysis'/(arm+'-SUMMARY.json'),summary);W.save(O/'analysis'/(arm+'-NAV.json'),curve);W.save(O/'analysis'/(arm+'-INDUSTRIES.json'),list(sectors.values()));W.save(O/'analysis'/(arm+'-STOCK_PNL.json'),[dict(sid=k,sector=stock_sector[k],**v) for k,v in stock_pnl.items()])
 # Pure recovery validation at the final cutoff, no extra event or account time API.
 rejected=False
 try:r.execution_guard('2022-02-07','OPEN')
 except ValueError:rejected=True
 assert rejected and str(r.last_completed_event)=='2022-01-28 15:10:00+08:00'
 W.save(O/'analysis'/(arm+'-RESTORE.json'),dict(passed=True,all_current_fields_exact=True,certificates_recomputed=len(r.authority.certificates),February_rejected=True,new_financial_events=0,checkpoint_sha256=rec['sha256']))
 print('MONTH_ANALYSIS_AND_RESTORE_PASS',arm,'NAV',balance['nav'],'DD',summary['close_drawdown']['max_drawdown_pct'],flush=True)
if __name__=='__main__':main()
