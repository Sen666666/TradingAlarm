"""Independent legacy cash/share auditor adapted only to pad and unlimited slots."""
from pathlib import Path
from decimal import Decimal as D
import sys,json,gzip,collections,inspect,hashlib
import pandas as pd
import numpy as np
HERE=Path(__file__).resolve().parents[1];ROOT=HERE.parents[1]
OLD=ROOT/'research_rounds/rs-h1-execution-20261025';IX=ROOT/'research_rounds/ix-a-share-entry-20261025'
sys.path.extend([str(OLD/'code'),str(IX/'code')])
import analyze_accounts as audit
from analyze_ix import IndependentPrices
from market_runner import encoded
PAD=D('1000000000000');CAP=D('1000000');ZERO=D(0)
def read(p):return json.loads(Path(p).read_text())
def write(p,x):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x') as f:json.dump(encoded(x),f,ensure_ascii=False,indent=2,allow_nan=False)
def rows(p,aid=None):
 with gzip.open(p,'rt') as f:
  for line in f:
   x=json.loads(line)
   if aid is None or x['account']==aid:yield x
source=inspect.getsource(audit.audit_account).replace('D(1_000_000)','PAD').replace("if not aid.startswith('B0'):","if False:")
space=dict(audit.audit_account.__globals__,PAD=PAD);exec(compile(source,'unlimited_independent_auditor','exec'),space);audit_unlimited=space['audit_account']

def main(mode):
 short=mode.startswith('short');src=HERE/('technical/'+mode if short else 'accounts-v1');out=HERE/('technical/'+mode+'-analysis' if short else 'analysis-v1');out.mkdir(exist_ok=False)
 meta=read(OLD/'inputs-v2/metadata.json');prices=IndependentPrices();calendar=[audit.t(x) for x in read(OLD/'inputs-v2/market-rules.json')['calendars']['A']]
 aids=read(src/'summary.json')['accounts'];results=[];receipts=[];years=[];stock=[];sector=[];allcurves=[];allcampaigns=[];buy_checks=0;decisions_count=0
 for aid in aids:
  ds=list(rows(src/'daily.jsonl.gz',aid));log=list(rows(src/'audit.jsonl.gz',aid));obj=dict(audit_log=log)
  cc,rc=audit_unlimited(aid,obj,ds,prices,meta,calendar);receipts.append(rc)
  reservations={x['order_id']:x for x in log if x['kind']=='reserve'};spent=collections.defaultdict(lambda:ZERO)
  for x in log:
   if x['kind']=='reserve':assert D(x['gross_budget_cny'])==CAP
   if x['kind']=='fill' and x['receipt']['side']=='buy':
    spent[x['order_id']]+=D(x['receipt']['gross_cny']);assert spent[x['order_id']]<=CAP
    buy_checks+=1
  for c in cc:assert c['buy_gross']<=CAP,(aid,c['symbol'],'episode cap violated')
  assert all(not str(reason).startswith('capacity') for r in rows(src/'decisions.jsonl.gz',aid) for _,reason in r['rejected'])
  for r in rows(src/'decisions.jsonl.gz',aid):
   assert set(r['accepted'])<=set(r['eligible']);assert set(r['selected'])==set(r['accepted'])|{s for s,_ in r['rejected']};decisions_count+=1
  final=read(src/f'{aid}-final.json');K=D(final['peak_funding']);assert K>0
  df=pd.DataFrame(ds);pnl=df.pnl.astype(float).to_numpy();mv=df.inventory.astype(float).to_numpy();equity=float(K)+pnl;peak=np.maximum.accumulate(np.r_[float(K),equity])[1:];dd=1-equity/peak
  assert equity.min()>0
  # End-of-day fully funded ledger is feasible without the pad, including reservations.
  assert min(D(d['available'])-PAD+K for d in ds)>=0
  closed=[c for c in cc if c['closed']];tails=[c for c in closed if c['tail_closed']];ordinary=[c for c in closed if not c['tail_closed']]
  tail=sum((c['net_pnl'] for c in tails),ZERO);normal=sum((c['net_pnl'] for c in ordinary),ZERO);openp=sum((c['net_pnl'] for c in cc if not c['closed']),ZERO);loss=-sum((c['net_pnl'] for c in closed if c['net_pnl']<0),ZERO)
  assert abs(tail+normal+openp-D(ds[-1]['pnl']))<D('1e-8')
  j=int(np.argmax(mv));h=int(df.holding_count.astype(int).to_numpy().argmax())
  r=dict(account=aid,policy=aid.split('__')[0],scenario=aid.rsplit('_',1)[-1],net_profit=float(pnl[-1]),peak_market_value=float(mv[j]),peak_market_value_date=ds[j]['at'][:10],peak_funding=float(K),peak_funding_at=final['peak_funding_at'],profit_over_peak_funding=pnl[-1]/float(K),profit_over_peak_market_value=pnl[-1]/mv[j],max_drawdown=float(dd.max()),max_drawdown_amount=float((peak-equity).max()),max_holdings=int(df.holding_count.iloc[h]),max_holdings_date=ds[h]['at'][:10],ending_market_value=float(mv[-1]),ending_holdings=int(df.holding_count.iloc[-1]),fees=float(df.fees_cny.iloc[-1]),closed=len(closed),open=len(cc)-len(closed),win_rate=sum(c['net_pnl']>0 for c in closed)/len(closed) if closed else None,tail_count=len(tails),tail_profit=float(tail),ordinary_profit=float(normal),open_profit=float(openp),all_closed_losses=float(loss),tail_to_all_losses=float(tail/loss) if loss else None,unique_stocks=len({c['symbol'] for c in cc}))
  results.append(r)
  for i,d in enumerate(ds):allcurves.append(dict(account=aid,policy=r['policy'],scenario=r['scenario'],date=d['at'][:10],pnl=float(pnl[i]),market_value=float(mv[i]),funding_to_date=float(d['peak_funding']),equity_with_peak_funding=float(equity[i]),drawdown=float(dd[i]),holdings=int(d['holding_count']),fees=float(d['fees_cny'])))
  prev=0
  for y,g in df.groupby(df['at'].str[:4],sort=True):
   pp=g.pnl.astype(float);years.append(dict(account=aid,policy=r['policy'],scenario=r['scenario'],year=y,net_profit=float(pp.iloc[-1]-prev),profit_over_full_period_peak_funding=float((pp.iloc[-1]-prev)/float(K)),peak_market_value=float(g.inventory.astype(float).max()),max_holdings=int(g.holding_count.max())));prev=pp.iloc[-1]
  grouped=collections.defaultdict(list)
  for c in cc:
   c.update(account=aid,policy=r['policy'],scenario=r['scenario']);grouped[c['symbol']].append(c)
  for sid,cs in grouped.items():
   stock.append(dict(account=aid,policy=r['policy'],scenario=r['scenario'],symbol=sid,name=meta[sid]['name'],industry=meta[sid]['industry'],sector_id=meta[sid]['sector_id'],net_profit=float(sum((c['net_pnl'] for c in cs),ZERO)),tail_profit=float(sum((c['net_pnl'] for c in cs if c['tail_closed']),ZERO)),closed=sum(c['closed'] for c in cs),episodes=len(cs),held_days=sum(sid in d['positions'] for d in ds),buy_gross=float(sum((c['buy_gross'] for c in cs),ZERO))))
  allcampaigns.extend(cc)
  print(json.dumps(dict(audited=aid,days=len(ds),episodes=len(cc),net_profit=r['net_profit'],peak_funding=r['peak_funding'],return_on_funding=r['profit_over_peak_funding'])),flush=True)
 sf=pd.DataFrame(stock)
 if not sf.empty:
  for (aid,industry),g in sf.groupby(['account','industry']):sector.append(dict(account=aid,industry=industry,net_profit=float(g.net_profit.sum()),tail_profit=float(g.tail_profit.sum()),stocks=len(g)))
 for name,rs in [('summary',results),('annual',years),('stocks',stock),('industries',sector),('curves',allcurves),('campaigns',allcampaigns)]:
  pd.DataFrame(encoded(rs)).to_csv(out/f'{name}.csv',index=False)
 write(out/'accounting.json',dict(passed=True,accounts=len(aids),daily_rows=sum(x['checks']['daily_independent_nav_and_shares'] for x in receipts),actual_buy_checks=buy_checks,decision_checks=decisions_count,max_nav_difference=max(D(x['max_absolute_nav_difference_cny']) for x in receipts),receipts=receipts,adaptations=['initial_pad_only','remove_slot_assertion_only'],all_episodes_under_cap=True))
 if short:write(HERE/'technical/short-validation.json',dict(passed=True,mode=mode,accounts=len(aids),same_frozen_ledger_independent_audit=True))
 else:report(out,results,allcurves,stock,sector)

def report(out,rs,curves,stocks,sectors):
 def money(v):return f'{v/1e4:,.2f}万'
 def pct(v):return f'{v:+.2%}'
 def table(h,rr):return '| '+' | '.join(h)+' |\n| '+' | '.join(['---']*len(h))+' |\n'+''.join('| '+' | '.join(map(str,r))+' |\n' for r in rr)
 text='# 无限总资金、每股100万元上限：资金检验\n\n全部数值为2015—2026-10-22既有1709合格A股开发资料（另2市值未知保留），不含新增行情。所有合格股票可参与，无总资金/行业/持股名额上限；原行业准入、E0/I/IX信号和执行合同保留。每次空仓新开最多100万元成交本金，费用另计，上涨不压回100万元。现有三策略无新增分批加减仓。\n\n'
 text+='净利润包含期末持仓和权益估值，不强平。K是从完整路径倒推的最低固定资金需求，包含预约资金、费用及结算占用，盈利可循环；它不是事前已知资金。收益率为净利润/K。峰值股票市值另列，净利润/峰值市值是规模归一化口径。\n\n'
 text+=table(['政策/情景','净利润','最高持仓市值','峰值资金K','净利润/K','利润/最高市值','按K重建最大日回撤','最高股数'],[[r['policy']+'/'+r['scenario'],money(r['net_profit']),money(r['peak_market_value']),money(r['peak_funding']),pct(r['profit_over_peak_funding']),pct(r['profit_over_peak_market_value']),f"{r['max_drawdown']:.2%}",r['max_holdings']] for r in rs])
 text+='\n所有失败完整计费；30%只是已闭合净收益尾部分类，不是止盈。\n\n'
 text+=table(['基础政策','尾部利润','其他闭合净损益','未闭合净损益','全部闭合亏损金额','尾部/全部亏损','胜率'],[[r['policy'],money(r['tail_profit']),money(r['ordinary_profit']),money(r['open_profit']),money(r['all_closed_losses']),f"{r['tail_to_all_losses']:.2f}",f"{r['win_rate']:.2%}"] for r in rs if r['scenario']=='base'])
 text+='\n[每日资金/市值/收益](analysis-v1/curves.csv)、[完整逐笔周期](analysis-v1/campaigns.csv)、[逐股贡献](analysis-v1/stocks.csv)、[行业贡献](analysis-v1/industries.csv)、[年度损益](analysis-v1/annual.csv)、[独立核账](analysis-v1/accounting.json)。\n\n无息记账现金垫不进入收益或回撤分母；没有融资利息或虚构收益。数据当前存续/分类/市值偏差及日线高低、流动性、权息/派息等原代理继续保留，不称真实逐笔可执行、全历史时点全池或样本外。\n'
 (HERE/'RESULTS.md').write_text(text)
 import matplotlib;matplotlib.use('Agg');import matplotlib.pyplot as plt
 plt.rcParams['font.family']=['Arial Unicode MS','DejaVu Sans']
 cf=pd.DataFrame(curves);fig,axes=plt.subplots(3,1,figsize=(13,10),sharex=True)
 for policy in ['E0','I','IX']:
  g=cf[(cf.policy==policy)&(cf.scenario=='base')];dt=pd.to_datetime(g.date)
  axes[0].plot(dt,g.pnl/1e8,label=policy)
  axes[1].plot(dt,g.market_value/1e8,label=policy)
  axes[2].plot(dt,g.holdings,label=policy)
 axes[0].set_ylabel('累计净损益（亿元）');axes[1].set_ylabel('持仓市值（亿元）');axes[2].set_ylabel('持股数')
 for ax in axes:ax.grid(alpha=.2);ax.legend()
 fig.suptitle('无限总资金 / 单股每轮买入本金上限100万元 — 基础情景');fig.tight_layout();fig.savefig(HERE/'curves.png',dpi=160);plt.close(fig)

if __name__=='__main__':main(sys.argv[1])
