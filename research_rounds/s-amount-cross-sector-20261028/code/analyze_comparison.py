"""Descriptive paired attribution after all four independent account audits.

No account execution or parameter selection. Output directory is exclusive.
"""
from sa_common import *
from collections import Counter
import math

OUT = O / 'analysis-comparison'
SECTORS = ('TECH', 'DRUG')
VERSIONS = ('OLD', 'AMT')
SCENARIOS = ('base', 'cost2', 'delay1')


def native(x):
 if isinstance(x,dict):return {str(k):native(v) for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [native(v) for v in x]
 if isinstance(x,(np.integer,np.bool_)):return x.item()
 if isinstance(x,(float,np.floating)):return float(x) if math.isfinite(x) else None
 if isinstance(x,pd.Timestamp):return str(x)
 return x


def boolcol(frame, name):
 v=frame[name]
 if pd.api.types.is_bool_dtype(v):return v
 if set(v.dropna())<={'True','False'}:return v.eq('True')
 raise ValueError((name,'must be Boolean'))


def read_run(sector,version):
 p=O/sector/version
 a=read(p/'analysis/accounting.json')
 assert a['passed'] and float(a['max_nav_difference'])==0,(sector,version)
 s=pd.read_csv(p/'analysis/summary.csv')
 assert set(s.scenario)==set(SCENARIOS) and len(s)==3
 c=pd.read_csv(p/'analysis/campaigns.csv')
 for name in ['closed','tail_closed']:c[name]=boolcol(c,name)
 return dict(path=p,summary=s,campaigns=c,stocks=pd.read_csv(p/'analysis/stocks.csv'),
             curves=pd.read_csv(p/'analysis/curves.csv'),daily=rows(p/'accounts-v2/daily.jsonl.gz'),
             decisions=rows(p/'accounts-v2/decisions.jsonl.gz'),
             accounts={sc:read(p/'accounts-v2'/f'S__S0_{sc}.json') for sc in SCENARIOS})


def aid(sc):return f'S__S0_{sc}'
def selected(frame,sc):return frame[frame.account.eq(aid(sc))]
def daily_map(run,sc):return {r['at'][:10]:r for r in run['daily'] if r['account']==aid(sc)}
def decision_map(run,sc):return {r['at'][:10]:r for r in run['decisions'] if r['account']==aid(sc)}
def risk_map(run,sc):return {r['at'][:10]:r for r in run['accounts'][sc]['audit_log'] if r['kind']=='risk_checkpoint'}


def buys(obj):
 out={}
 for r in obj['fills']:
  if r['side']!='buy':continue
  key=(r['security_id'],r['at'])
  if key not in out:out[key]=dict(symbol=key[0],at=key[1],shares=0,gross=0.,fees=0.)
  out[key]['shares']+=int(r['shares']);out[key]['gross']+=float(r['gross_cny']);out[key]['fees']+=float(r['fees_cny'])
 return out


def main():
 assert read(O/'admission.json')['passed']
 data={(sector,version):read_run(sector,version) for sector in SECTORS for version in VERSIONS}
 OUT.mkdir(exist_ok=False)
 summary=[];costs=[];paired=[];stockdiff=[];buychanges=[];stockentries=[];windows=[];coverage=[];checks=[];paths=[];risks=[];capacity=[]
 facts_cache={};strict_cache={}
 def fact_at(sector,version,sid,day):
  k=(sector,sid)
  if k not in facts_cache:facts_cache[k]=pd.read_parquet(PREPS[sector]/'facts'/f'{sid}.parquet')
  f=facts_cache[k]
  k2=(sector,version,sid)
  if k2 not in strict_cache:
   d=OLD_TABLES[sector] if version=='OLD' else O/'signals'/sector
   strict_cache[k2]=pd.read_parquet(d/f'{sid}.parquet')
  z=strict_cache[k2];t=pd.Timestamp(day)
  return dict(original_i_buy=bool(f.loc[t,'i_buy']) if t in f.index else None,
              strict_target=bool(z.loc[t,'strict_target']) if t in z.index else None,
              original_i_floor=float(f.loc[t,'i_floor']) if t in f.index else None,
              strict_floor=float(z.loc[t,'strict_floor']) if t in z.index else None)
 for sector in SECTORS:
  baseline=selected(data[sector,'OLD']['campaigns'],'base')
  tails=baseline[baseline.tail_closed].copy()
  fixed_symbols=set(tails.symbol)
  roster=pool(sector).set_index('symbol')
  fixed_days={}
  baseline_days=sorted(daily_map(data[sector,'OLD'],'base'))
  for wid,(_,r) in enumerate(tails.iterrows()):
   start,end=str(r.entry_at)[:10],str(r.exit_at)[:10]
   # Fixed holding window includes entry close and excludes final exit open.
   days=[d for d in baseline_days if start<=d<end]
   fixed_days[wid]=(r,days)
  for version in VERSIONS:
   run=data[sector,version]
   for sc in SCENARIOS:
    s=selected(run['summary'],sc).iloc[0]
    c=selected(run['campaigns'],sc)
    summary.append(dict(sector=sector,version=version,**s.to_dict()))
    closed=c[c.closed];tail=closed[closed.tail_closed];ordinary=closed[~closed.tail_closed];opened=c[~c.closed]
    neg_closed=-closed.loc[closed.net_pnl<0,'net_pnl'].sum()
    net_decomp=tail.net_pnl.sum()+ordinary.net_pnl.sum()+opened.net_pnl.sum()
    assert abs(net_decomp-s.net_profit)<1e-5,(sector,version,sc,'net decomposition')
    fees=(c.buy_fees+c.sell_fees).sum()
    assert abs(fees-s.fees)<1e-5,(sector,version,sc,'fees')
    costs.append(dict(sector=sector,version=version,scenario=sc,closed_cycles=len(closed),
                     negative_closed_cycles=int(closed.net_pnl.lt(0).sum()),tail_cycles=len(tail),
                     tail_net_pnl=tail.net_pnl.sum(),ordinary_closed_net_pnl=ordinary.net_pnl.sum(),
                     all_negative_closed_loss=neg_closed,open_net_pnl=opened.net_pnl.sum(),
                     open_marked_losses=-opened.loc[opened.net_pnl<0,'net_pnl'].sum(),
                     all_negative_closed_and_open_marked_loss=-c.loc[c.net_pnl<0,'net_pnl'].sum(),
                     all_fees=fees,net_profit=s.net_profit,
                     tail_over_all_closed_loss=tail.net_pnl.sum()/neg_closed if neg_closed>0 else None))
    dm=daily_map(run,sc);dec=decision_map(run,sc);rm=risk_map(run,sc)
    active_count=Counter()
    for day,r in dec.items():
     if day not in rm or not rm[day]['on']:active_count['paused_or_unknown_days']+=1;continue
     active_count['active_days']+=1
     occupied={p['security_id'] for p in r['occupancy']};sectors=Counter(p['sector_id'] for p in r['occupancy'])
     for sid in set(r['eligible'])-occupied-set(r['accepted']):
      sec=roster.loc[sid,'sector_id']
      why='post_decision_total_cap' if len(occupied)>=6 else 'post_decision_sector_cap' if sectors[sec]>=2 else 'post_decision_industry_cap' if sec not in sectors and len(sectors)>=3 else 'other_unaccepted'
      active_count[why]+=1
    capacity.append(dict(sector=sector,version=version,scenario=sc,**active_count))
    transitions=[r for r in run['accounts'][sc]['audit_log'] if r['kind']=='risk_checkpoint' and r.get('event')]
    risks.append(dict(sector=sector,version=version,scenario=sc,transitions=transitions))
    covered=set();possible=set()
    for wid,(w,days) in fixed_days.items():
     sid=w.symbol;held=[d for d in days if int(dm.get(d,{}).get('positions',{}).get(sid,0))>0]
     possible.update((sid,d) for d in days);covered.update((sid,d) for d in held)
     windows.append(dict(sector=sector,version=version,scenario=sc,window_id=wid,symbol=sid,name=w['name'],
                         old_base_entry=str(w.entry_at),old_base_exit=str(w.exit_at),old_base_cycle_net=w.net_pnl,
                         market_days=len(days),held_days=len(held),first_held_day=min(held) if held else None,last_held_day=max(held) if held else None))
    coverage.append(dict(sector=sector,version=version,scenario=sc,fixed_old_base_tail_windows=len(tails),
                         fixed_old_base_tail_stocks=len(fixed_symbols),unique_possible_stock_days=len(possible),
                         unique_held_stock_days=len(covered),held_stock_days_fraction=len(covered)/len(possible) if possible else None,
                         fixed_tail_stock_full_period_net=c.loc[c.symbol.isin(fixed_symbols),'net_pnl'].sum()))
  for sc in SCENARIOS:
   old,new=data[sector,'OLD'],data[sector,'AMT']
   a=selected(old['summary'],sc).iloc[0];b=selected(new['summary'],sc).iloc[0]
   metrics=['net_return','max_drawdown','net_profit','mean_exposure','fees','closed','tail_profit','ordinary_profit','open_profit','all_closed_losses','tail_over_all_losses','buy_fills']
   paired.append(dict(sector=sector,scenario=sc,**{f'old_{k}':a[k] for k in metrics},**{f'new_{k}':b[k] for k in metrics},**{f'delta_{k}':b[k]-a[k] for k in metrics}))
   aa=selected(old['stocks'],sc).set_index('symbol');bb=selected(new['stocks'],sc).set_index('symbol')
   ss=[]
   for sid in sorted(set(aa.index)|set(bb.index)):
    av=float(aa.loc[sid,'net_profit']) if sid in aa.index else 0.;bv=float(bb.loc[sid,'net_profit']) if sid in bb.index else 0.
    name=roster.loc[sid,'name']
    row=dict(sector=sector,scenario=sc,symbol=sid,name=name,old_net=av,new_net=bv,delta_net=bv-av,old_fixed_tail_stock=sid in fixed_symbols,
             old_cycles=int(aa.loc[sid,'campaigns']) if sid in aa.index else 0,new_cycles=int(bb.loc[sid,'campaigns']) if sid in bb.index else 0)
    ss.append(row);stockdiff.append(row)
   err=sum(r['delta_net'] for r in ss)-(b.net_profit-a.net_profit)
   assert abs(err)<1e-5,(sector,sc,'stock delta',err)
   checks.append(dict(sector=sector,scenario=sc,stock_delta_sum=sum(r['delta_net'] for r in ss),account_net_delta=b.net_profit-a.net_profit,difference=err))
   ab,bbuy=buys(old['accounts'][sc]),buys(new['accounts'][sc]);oldsy={s for s,t in ab};newsy={s for s,t in bbuy}
   for sid,at in sorted(set(ab)|set(bbuy)):
    av,bv=ab.get((sid,at)),bbuy.get((sid,at))
    kind='same_stock_same_fill_time' if av and bv else 'new_version_only_date_same_stock' if bv and sid in oldsy else 'new_stock_participation' if bv else 'old_version_only_date_same_stock' if sid in newsy else 'old_only_stock_participation'
    buychanges.append(dict(sector=sector,scenario=sc,symbol=sid,name=roster.loc[sid,'name'],at=at,classification=kind,
                           old_shares=av['shares'] if av else 0,new_shares=bv['shares'] if bv else 0,
                           old_gross=av['gross'] if av else 0,new_gross=bv['gross'] if bv else 0))
   for sid in sorted(oldsy|newsy):
    ad=sorted(at for s,at in ab if s==sid);bd=sorted(at for s,at in bbuy if s==sid)
    relation='same_first_fill' if ad and bd and ad[0]==bd[0] else 'new_first_fill_earlier' if ad and bd and bd[0]<ad[0] else 'new_first_fill_later' if ad and bd else 'only_new' if bd else 'only_old'
    stockentries.append(dict(sector=sector,scenario=sc,symbol=sid,name=roster.loc[sid,'name'],old_first=ad[0] if ad else None,new_first=bd[0] if bd else None,
                             old_buy_times=len(ad),new_buy_times=len(bd),relation=relation))
   adm,bdm=daily_map(old,sc),daily_map(new,sc)
   first_financial=next((d for d in sorted(adm) if any(adm[d][k]!=bdm[d][k] for k in ['nav','positions','available'])),None)
   adec,bdec=decision_map(old,sc),decision_map(new,sc)
   first_accept=next((d for d in sorted(adec) if any(adec[d][k]!=bdec[d][k] for k in ['accepted','exits'])),None)
   selected_stocks=[r['symbol'] for r in sorted(ss,key=lambda r:r['delta_net'])[:3]]+[r['symbol'] for r in sorted(ss,key=lambda r:r['delta_net'],reverse=True)[:3]]
   examples=[]
   for sid in dict.fromkeys(selected_stocks):
    item=dict(symbol=sid,name=roster.loc[sid,'name'],versions={})
    decision_days=set()
    for version,run in [('OLD',old),('AMT',new)]:
     logs=run['accounts'][sc]['audit_log'];filled_ids={r['order_id'] for r in logs if r['kind']=='fill' and r['receipt']['side']=='buy' and r['receipt']['security_id']==sid}
     entries=[r for r in logs if r['kind']=='entry_contract' and r['sid']==sid and r['order_id'] in filled_ids]
     decision_days.update(r['decision_at'][:10] for r in entries)
     item['versions'][version]={'campaigns':selected(run['campaigns'],sc).loc[lambda z:z.symbol.eq(sid)].to_dict('records'),'actual_fill_entry_contracts':entries}
    for version,run in [('OLD',old),('AMT',new)]:
     dm2=decision_map(run,sc);rm=risk_map(run,sc);snapshots=[]
     for day in sorted(decision_days):
      d=dm2.get(day)
      if d is None:continue
      same_sector=roster.loc[sid,'sector_id'];occ=d['occupancy']
      snapshots.append(dict(day=day,**fact_at(sector,version,sid,day),risk_on=rm.get(day,{}).get('on'),
                            eligible=sid in d['eligible'],accepted=sid in d['accepted'],
                            occupied=sid in {x['security_id'] for x in occ},post_decision_slots=len(occ),
                            post_decision_same_sector_slots=sum(x['sector_id']==same_sector for x in occ),
                            post_decision_industries=len({x['sector_id'] for x in occ}),occupancy=occ))
     item['versions'][version]['decision_contexts']=snapshots
    examples.append(item)
   paths.append(dict(sector=sector,scenario=sc,first_financial_divergence=first_financial,first_admission_divergence=first_accept,
                     first_admission_snapshots={'OLD':adec.get(first_accept),'AMT':bdec.get(first_accept)},representative_stock_differences=examples))
 tables={'summary':summary,'cost-decomposition':costs,'paired-summary':paired,'stock-differences':stockdiff,'buy-changes':buychanges,
         'first-stock-entries':stockentries,'fixed-winner-windows':windows,'fixed-winner-coverage':coverage,'capacity':capacity}
 for name,rr in tables.items():pd.DataFrame(rr).to_csv(OUT/f'{name}.csv',index=False)
 save(OUT/'paired-attribution-checks.json',native(dict(passed=True,comparisons=checks)))
 save(OUT/'path-contexts.json',native(paths));save(OUT/'risk-transitions.json',native(risks))
 save(OUT/'definitions.json',dict(period='2024-01-02 through 2026-10-27',
      fixed_winner_definition='OLD base closed campaigns with net_return >= 30%; descriptive reference only, never signal input',
      fixed_window_holdings='end-of-day positive quantity in OLD base [entry date, final exit date); deduplicated symbol/date',
      fees='already included in net PnL; shown separately, never subtracted again',
      negative_closed_loss='all negative closed campaigns; not the same as net ordinary loss',
      negative_open_mark='separate marked negative open campaigns, not realized stop-loss cost',
      buy_matching='same stock and execution timestamp only; different dates of same stock are not assumed causal replacements',
      capacity='decision-output occupancy snapshot after admissions, descriptive not a unique causal rejection proof',
      first_stock_fill='whole-period first actual buy, not matched trend episodes',
      dollar_deltas='whole-account path difference, not isolated effect of a single replaced fill',
      no_parameter_selection=True))
 graphs(data)
 print(pd.DataFrame(paired)[['sector','scenario','old_net_return','new_net_return','old_max_drawdown','new_max_drawdown']].to_string(index=False))


def graphs(data):
 import matplotlib;matplotlib.use('Agg')
 import matplotlib.pyplot as plt
 plt.rcParams['font.sans-serif']=['Arial Unicode MS'];plt.rcParams['axes.unicode_minus']=False
 for sector in SECTORS:
  fig,axes=plt.subplots(2,3,figsize=(16,8),sharex='col')
  for j,sc in enumerate(SCENARIOS):
   for version,label,color in [('OLD','原 S','#6b6b6b'),('AMT','S-AMT1','#2178b5')]:
    c=selected(data[sector,version]['curves'],sc);t=pd.to_datetime(c.date)
    axes[0,j].plot(t,c.nav/1e6,label=label,color=color,lw=1.2)
    axes[1,j].plot(t,-c.drawdown*100,label=label,color=color,lw=1.2)
   axes[0,j].set_title({'base':'基础','cost2':'双成本','delay1':'额外执行延迟'}[sc]);axes[0,j].legend()
   axes[0,j].set_ylabel('净值 / 初始100万元');axes[1,j].set_ylabel('回撤 %')
   for a in axes[:,j]:a.grid(alpha=.18);a.tick_params(axis='x',rotation=25)
  fig.suptitle(('科技407股' if sector=='TECH' else '创新药48股（本池恢复）')+'：只替换 S，2024—2026-10-27')
  fig.tight_layout();fig.savefig(OUT/f'{sector.lower()}-equity-drawdown.png',dpi=125);plt.close(fig)


if __name__=='__main__':main()
