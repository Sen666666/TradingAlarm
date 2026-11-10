"""Summarize fixed actual paths, not proposed orders or backtest returns."""
from pathlib import Path
import json,gzip,collections
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
O=Path(__file__).resolve().parents[1];ROOT=O.parents[1];BASE=ROOT/'research_rounds/broad-stage-reentry-20261029'
plt.rcParams['font.family']=['Arial Unicode MS','PingFang SC','DejaVu Sans']
def load(p):return json.loads(Path(p).read_text())
def main():
    d=O/'data';x=pd.read_csv(d/'miss-traces.csv');rejected=pd.read_csv(d/'pre-intent-budget-rejections.csv');cases=pd.read_csv(d/'case-summaries.csv')
    summaries=[]
    for sid in ['ALL','688498.SH','688256.SH','688502.SH','688615.SH']:
        z=x if sid=='ALL' else x[x.symbol.eq(sid)];cash=z[z.reason.eq('cash_competition_for_whole_order')];gap=z[z.reason.str.startswith('next_open')]
        summaries.append(dict(symbol=sid,cash_misses=len(cash),
           physically_can_pay_one=int(cash.total_cash_can_pay.sum()),reserve_restricts_initial_pool=int((~cash.deployable_can_pay).sum()),
           earlier_priority_group_uses_pool=int((cash.deployable_can_pay&~cash.group_start_can_pay).sum()),
           same_group_competition=int(cash.group_start_can_pay.sum()),
           static_defer_mobile_can_pay=int(cash.skip_same_day_mobile_cash_arithmetic.sum()),
           frozen_contract_misses=len(gap),gap_median=float(gap.open_gap.median()),gap_at_most_one_percent=int(gap.open_gap.le(.01).sum())))
    w=pd.read_csv(BASE/'analysis/winner-windows.csv');zero=w[w.account.eq('N1')&w.is_price_3x&w.held_days.eq(0)]
    funds=pd.read_csv(BASE/'analysis/funding-causes.csv');obj=load(BASE/'results/N1.json')
    with gzip.open(BASE/'results/daily.jsonl.gz','rt') as f:ds=[r for r in map(json.loads,f) if r['account']=='N1']
    on={r['at'][:10]:r['on'] for r in ds};zeros=[]
    for z in zero.itertuples():
        facts=pd.read_parquet(ROOT/'TradingAlarm/runtime/market/update-20261027-153013-2ffe04/prepared/facts'/f'{z.symbol}.parquet')
        part=facts.loc[z.trough:z.peak];raw=part[part.i_buy.astype(bool)];window_intents=funds[funds.symbol.eq(z.symbol)&funds.signal_at.str[:10].between(z.trough,z.peak)]
        actual=[t for t in obj['trades'] if t['security_id']==z.symbol and t['side']=='buy']
        ready=facts[facts.e0_ready.astype(bool)]
        zeros.append(dict(symbol=z.symbol,name=z.name,window_start=z.trough,window_end=z.peak,
           whole_period_buy_fills=len(actual),whole_period_net_profit=float(z.whole_period_net_profit),first_e0_ready=str(ready.index.min().date()) if len(ready) else None,
           window_i_buy_days=len(raw),window_i_buy_days_act_off=sum(not on[str(t.date())] for t in raw.index),
           window_intents=len(window_intents),window_intent_causes=window_intents.reason.value_counts().to_dict(),
           whole_period_pre_intent_cap_rejections=int(rejected.symbol.eq(z.symbol).sum())))
    pd.DataFrame(zeros).to_csv(d/'all-six-window-absences.csv',index=False)
    # Original allocation order and current PVR: no alternative ordering is executed.
    key='2025-10-21 15:10:00+08:00';ints={(i['sid'],r['at']):i for r in obj['decisions'] for i in r['intents']}
    meta=pd.read_csv(ROOT/'research_rounds/tech-compound-design-20261026/proposed-pool.csv').set_index('symbol').name
    order=[]
    for a in obj['audit']:
        if a['kind']=='lot_allocation' and a['at'][:10]=='2025-10-22' and ints[a['sid'],key]['group']==0:
            i=ints[a['sid'],key];order.append(dict(rank=len(order)+1,symbol=a['sid'],name=meta[a['sid']],pvr=i['score'],minimum_cash=float(a['minimum_cash']),
                ideal_cash=float(a['ideal_cash']),minimum_ratio=float(a['minimum_share_ratio']),selected=a['minimum_selected']))
    pd.DataFrame(order).to_csv(d/'source-20251022-allocation-order.csv',index=False)
    target=next(z for z in order if z['symbol']=='688498.SH');target['pvr_rank']=1+sum(z['pvr']>target['pvr'] for z in order)
    summary=dict(cash_miss_components=summaries,six_fixed_window_absences=zeros,source_example=target,
         warning='Single-order affordability is not simultaneous affordability of all orders. Skipping mobile layers is a static cash boundary, not alternate fills or account returns.')
    with (O/'ANALYSIS_SUMMARY.json').open('x') as f:json.dump(summary,f,ensure_ascii=False,indent=2)
    # Scientific figure: actual cash split, actual queue, existing owners.
    fig,axs=plt.subplots(3,1,figsize=(15,16),gridspec_kw={'height_ratios':[1,4,3]},layout='constrained')
    case=cases[cases.symbol.eq('688498.SH')&cases.signal_at.eq(key)].iloc[0]
    axs[0].barh(['开盘实际现金'],[case.buffer/1e4],label='保留10%净值缓冲',color='#b7bdc6')
    axs[0].barh(['开盘实际现金'],[case.deployable/1e4],left=[case.buffer/1e4],label='可分配现金',color='#5087bf')
    axs[0].set_xlabel('万元');axs[0].set_title('源杰为何没买到｜2025-10-21收盘信号 → 10-22开盘｜旧N1实际路径',loc='left');axs[0].legend()
    y=np.arange(len(order));color=['#c83d48' if z['symbol']=='688498.SH' else '#468b73' for z in order]
    axs[1].barh(y,[z['minimum_cash']/1e4 for z in order],color=color)
    axs[1].set_yticks(y,[f'{z["rank"]}. {z["name"]} | PVR {z["pvr"]:.2f} | '+('获分配' if z['selected'] else '未分配') for z in order]);axs[1].invert_yaxis();axs[1].set_xlabel('合法最小一单含买费 / 万元');axs[1].set_title('第0组实际分配顺序：源杰PVR第1，却按理论金额/最小单成本排第13',loc='left')
    h=pd.read_csv(d/'case-ownership.csv');h=h[h.target.eq('688498.SH')&h.signal_at.eq(key)].head(10);yy=np.arange(len(h));left=np.zeros(len(h))
    for col,label,c in [('core_value','核心','#368568'),('trial_value','未晋升试仓','#a66bb6'),('mobile_value','机动','#d8a044')]:
        v=h[col].to_numpy()/1e4;axs[2].barh(yy,v,left=left,label=label,color=c);left+=v
    axs[2].set_yticks(yy,h.name);axs[2].invert_yaxis();axs[2].set_xlabel('前收盘实际持仓市值 / 万元');axs[2].set_title('当时前10大持仓：是资金占用，不是对源杰的股票/行业名额否决',loc='left');axs[2].legend()
    for ax in axs:ax.grid(axis='x',alpha=.15)
    fig.savefig(O/'cash-and-priority.png',dpi=140);plt.close(fig)
    print(json.dumps(summary,ensure_ascii=False))
if __name__=='__main__':main()
