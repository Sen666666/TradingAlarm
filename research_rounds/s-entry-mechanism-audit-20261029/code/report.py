"""Read frozen mechanism outputs; no strategy evaluation or signal computation."""
from pathlib import Path
import json,gzip,csv,collections,hashlib,datetime,time
from decimal import Decimal as D, getcontext
import pandas as pd
O=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/s-entry-mechanism-audit-20261029')
R=O/'results'; Z=D(0); B=D('1000000')
def clean(x):
    if isinstance(x,D):return str(x)
    if isinstance(x,dict):return {k:clean(v) for k,v in x.items()}
    if isinstance(x,list):return [clean(v) for v in x]
    return x
def save(p,x):
    with p.open('x') as f:json.dump(clean(x),f,ensure_ascii=False,indent=2,allow_nan=False)
def csvout(p,rows):
    if not rows:return
    with p.open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows([clean(x) for x in rows])
def dd(x):return D(str(x))
def nonempty(x):return x is not None and not pd.isna(x)
def group(i,s):
    if not nonempty(i['first_fill']):return 'neither_filled'
    if not nonempty(s['first_fill']):return 'S_no_entry_completed_epoch' if nonempty(i['end_signal']) else 'S_not_yet_entered_open_epoch'
    return 'same_entry' if i['first_fill']==s['first_fill'] else 'S_delayed_entry'
def metric(pairs,weights):
    out={};tail={k for k,i,s in pairs if nonempty(i['net_return']) and float(i['net_return'])>=.30}
    for arm in ['I','S']:
        pos=loss=total=tailp=ordp=real=unreal=claims=fee=Z;closed=marked=0;wins=[];losers=[]
        for k,i,s in pairs:
            u=i if arm=='I' else s;v=dd(u['net_pnl']);w=weights[k]
            total+=w*v;pos+=w*max(v,Z);loss+=w*max(-v,Z)
            if k in tail:tailp+=w*v
            else:ordp+=w*v
            real+=w*(dd(u['realized_trading_pnl'])+dd(u['paid_dividend_income']))
            unreal+=w*dd(u['unrealized_inventory_pnl']);claims+=w*dd(u['accrued_unpaid_dividend_income'])
            fee+=w*(dd(u['buy_fees'])+dd(u['sell_fees']))
            if nonempty(u['first_fill']):
                if u['financial_closed']:closed+=1
                else:marked+=1
                if v>0:wins.append(float(u['net_return']))
                if v<0:losers.append(-float(u['net_return']))
        out[arm]=dict(total_pnl=total,positive_contribution=pos,negative_loss=loss,fixed_I_tail_pnl=tailp,fixed_I_ordinary_pnl=ordp,realized_and_paid=real,unrealized_inventory=unreal,unpaid_dividend_claims=claims,actual_fees=fee,closed_traded_units=closed,terminal_mark_or_claim_units=marked,profit_factor=float(pos/loss) if loss else None,mean_win_return=sum(wins)/len(wins) if wins else None,mean_loss_return_abs=sum(losers)/len(losers) if losers else None,payoff_ratio=(sum(wins)/len(wins))/(sum(losers)/len(losers)) if wins and losers else None,win_rate_descriptive=len(wins)/(len(wins)+len(losers)) if wins or losers else None)
    out['saved_losses']=out['I']['negative_loss']-out['S']['negative_loss']
    out['foregone_positive']=out['I']['positive_contribution']-out['S']['positive_contribution']
    out['delta']=out['S']['total_pnl']-out['I']['total_pnl']
    out['delta_tail']=out['S']['fixed_I_tail_pnl']-out['I']['fixed_I_tail_pnl']
    out['delta_ordinary']=out['S']['fixed_I_ordinary_pnl']-out['I']['fixed_I_ordinary_pnl']
    d=Z
    for k,i,s in pairs:
        if i['strict_at_entry'] is True:d+=weights[k]*dd(i['net_pnl'])
    out['static_deletion_delta']=d-out['I']['total_pnl'];out['delayed_participation_delta']=out['S']['total_pnl']-d
    for value in [out['saved_losses']-out['foregone_positive'],out['delta_tail']+out['delta_ordinary'],out['static_deletion_delta']+out['delayed_participation_delta']]:
        scale=max(D(1),abs(value),abs(out['delta']))
        bound=D(1).scaleb(scale.adjusted()-getcontext().prec+1)*D(max(1,len(pairs))*32)
        assert abs(value-out['delta'])<=bound,'aggregation Decimal residue'
    return out

def main():
    started=time.monotonic();units=pd.read_parquet(R/'units.parquet').to_dict('records');ev=pd.read_parquet(O/'opportunities.parquet')
    frozen=json.loads((O/'freeze.json').read_text());counts=frozen['stock_event_counts'];look={(u['event_id'],u['cost'],u['variant']):u for u in units}
    summaries={};pairrows=[];rankrows=[];effects=[]
    for cost in [1,2]:
        pairs=[(k,look[k,cost,'I'],look[k,cost,'S']) for k in ev.event_id]
        main=metric(pairs,{k:D(1) for k,_,_ in pairs})
        robust=metric(pairs,{k:D(1)/(D(407)*D(counts[i['symbol']])) for k,i,s in pairs})
        # Closed-only is supplementary, never changes main cohort or its weights.
        cs=[x for x in pairs if x[1]['financial_closed'] and x[2]['financial_closed']]
        supplemental=metric(cs,{k:D(1) for k,_,_ in cs})
        summaries[str(cost)]=dict(main=main,stock_equal_robustness=robust,closed_only_supplement=supplemental,common_events=len(pairs),closed_supplement_events=len(cs),groups=dict(collections.Counter(group(i,s) for _,i,s in pairs)),mean_delta_per_common_initial_cash=float(main['delta']/(B*len(pairs))))
        for basis,m in [('equal_event',main),('stock_equal',robust),('closed_only_supplement',supplemental)]:
            effects.append(dict(cost=cost,basis=basis,**{k:m[k] for k in ['saved_losses','foregone_positive','delta','delta_tail','delta_ordinary','static_deletion_delta','delayed_participation_delta']}))
        for k,i,s in pairs:
            row=dict(cost=cost,event_id=k,symbol=i['symbol'],group=group(i,s),I_signal=str(i['first_signal']) if nonempty(i['first_signal']) else '',S_signal=str(s['first_signal']) if nonempty(s['first_signal']) else '',I_fill=str(i['first_fill']) if nonempty(i['first_fill']) else '',S_fill=str(s['first_fill']) if nonempty(s['first_fill']) else '',I_pnl=dd(i['net_pnl']),S_pnl=dd(s['net_pnl']),delta=dd(s['net_pnl'])-dd(i['net_pnl']),I_return=i['net_return'] if nonempty(i['net_return']) else '',S_return=s['net_return'] if nonempty(s['net_return']) else '',I_closed=i['financial_closed'],S_closed=s['financial_closed'],I_unrealized=i['unrealized_inventory_pnl'],S_unrealized=s['unrealized_inventory_pnl'],I_unpaid_claims=i['accrued_unpaid_dividend_income'],S_unpaid_claims=s['accrued_unpaid_dividend_income'])
            pairrows.append(row)
        base=[x for x in pairrows if x['cost']==cost]
        for ordering,key in [('I_profit',lambda x:float(x['I_pnl'])),('I_return',lambda x:float(x['I_return']) if x['I_return']!='' else -float('inf'))]:
            ci=cs_=Z
            for n,x in enumerate(sorted(base,key=key,reverse=True),1):
                ci+=x['I_pnl'];cs_+=x['S_pnl'];rankrows.append(dict(cost=cost,ordering=ordering,rank=n,event_id=x['event_id'],symbol=x['symbol'],group=x['group'],I_pnl=x['I_pnl'],S_pnl=x['S_pnl'],cumulative_I=ci,cumulative_S=cs_,cumulative_delta=cs_-ci))
    assert len(units)==4*len(ev)
    # Independent available-cash reconstruction from original reservation and settlement logs.
    fills=[];flows=[];cash_checks=[];fee_names=set()
    with gzip.open(R/'audit.jsonl.gz','rt') as f:
        for line in f:
            obj=json.loads(line);available=B;fee_reserved={}
            for x in obj['audit']:
                k=x['kind'];delta=Z;econ=Z
                if k=='reserve':available-=dd(x['gross_budget_cny'])+dd(x['fee_reserved_cny']);fee_reserved[x['order_id']]=dd(x['fee_reserved_cny'])
                elif k=='release_buy':available+=dd(x['gross_released'])+dd(x['fee_released']);fee_reserved.pop(x['order_id'],None)
                elif k=='fill':
                    r=x['receipt'];fee=dd(r['fees_cny']);gross=dd(r['gross_cny'])
                    if r['side']=='buy':
                        extra=max(Z,fee-fee_reserved[x['order_id']]);available-=extra;fee_reserved[x['order_id']]=max(Z,fee_reserved[x['order_id']]-fee);econ=-gross-fee
                    else:econ=gross-fee
                    fr=dict(event_id=obj['event_id'],symbol=obj['symbol'],arm=obj['variant'],cost=obj['cost'],at=r['at'],side=r['side'],shares=r['shares'],raw_open=x['raw_open'],price=x['price'],gross=gross,fees=fee,order_id=x['order_id'])
                    for n,v in x['fee_components'].items():fr[n]=v;fee_names.add(n)
                    fills.append(fr)
                elif k=='settle' and not x['settlement']['debit']:available+=dd(x['settlement']['cny_amount'])
                elif k=='dividend_payment':available+=dd(x['entitlement']['net_local']);econ=dd(x['entitlement']['net_local'])
                flows.append(dict(event_id=obj['event_id'],symbol=obj['symbol'],arm=obj['variant'],cost=obj['cost'],kind=k,economic_flow=econ,details_json=json.dumps(x,ensure_ascii=False)))
            u=look[obj['event_id'],obj['cost'],obj['variant']];residue=abs(available-dd(u['available']));bound=dd(u['precision_bound']);assert residue<=bound,(obj['event_id'],'independent available cash',residue,bound)
            cash_checks.append(residue)
    fields=['event_id','symbol','arm','cost','at','side','shares','raw_open','price','gross','fees','order_id']+sorted(fee_names)
    with (R/'fills.csv').open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows([clean(x) for x in fills])
    csvout(R/'cashflows.csv',flows);csvout(R/'paired-events.csv',pairrows);csvout(R/'effects.csv',effects);csvout(R/'continuous-contributions.csv',rankrows)
    csvout(R/'top-I-events.csv',sorted([x for x in pairrows if x['cost']==1],key=lambda x:-float(x['I_pnl'])))
    base=summaries['1']['main'];stress=summaries['2']['main'];rob=summaries['1']['stock_equal_robustness']
    if base['delta']*stress['delta']<0 or base['delta']*rob['delta']<0:verdict='不确定：成本或共同权重口径反向，不能挑选有利结果'
    elif all(m['delta_tail']<=0 and m['delta_ordinary']<=0 and m['delta']<0 for m in [base,stress]):verdict='否定当前S首次参与改法：普通与尾部均未改善'
    elif all(m['delta_tail']>=0 and m['delta_ordinary']>=0 and m['delta']>0 for m in [base,stress]):verdict='直接支持保留研究候选：普通与尾部共同改善，非产品晋升'
    elif base['delta']>0 and base['delta_tail']>0:verdict='正向尾部取舍：尾部增益覆盖普通代价；需审阅取舍，不称失败或自动晋升'
    elif base['delta']>0:verdict='净改善伴尾部取舍：披露损尾部代价，不自动晋升'
    elif base['delta']==0:verdict='本样本无新增净效果，不以样本数量宣称普遍无效'
    else:verdict='负向总取舍或证据不足：解释普通与尾部方向，不扩大参数搜索'
    result=dict(verdict=verdict,all_events_included=True,event_count=len(ev),shadow_initial_cash_per_event='1000000',not_a_tradeable_shared_portfolio=True,scenarios=summaries,correctness=dict(native_ledger_verification=json.loads((R/'verification.json').read_text()),independent_available_cash_units=len(cash_checks),max_available_cash_residue=max(cash_checks),pairing_and_decompositions=True),seconds_reporting=time.monotonic()-started)
    save(R/'summary.json',result)
    lines=['实验一：现有S相对I的首次参与机制裁决，v2','',verdict,'',f'共同事件{len(ev)}；每事件100万元独立影子初始现金，全部纳入，不是可交易共享资金组合。','主账：全部事件等额；股票等权和闭合子集仅作附表。','末端未平仓及未付权益已纳入；实际费用计入，估计清算费用另列。','']
    for cost in ['1','2']:
        d=summaries[cost];m=d['main'];lines += [f'成本合同{cost}：I净贡献{m["I"]["total_pnl"]}元；S净贡献{m["S"]["total_pnl"]}元。',f'省亏损{m["saved_losses"]}；丢正收益{m["foregone_positive"]}；净差{m["delta"]}。',f'固定I尾部差{m["delta_tail"]}；普通差{m["delta_ordinary"]}。',f'首次静态删除差{m["static_deletion_delta"]}；后续延迟参与差{m["delayed_participation_delta"]}。',f'股票等权净差{d["stock_equal_robustness"]["delta"]}；闭合子集净差{d["closed_only_supplement"]["delta"]}。',f'分组{d["groups"]}','']
    lines += ['I最大贡献事件明细与全部排序见top-I-events.csv；连续贡献分布见continuous-contributions.csv。','一次E0段每臂最多一次实际入场，仅检验首次参与政策，不涵盖ACT强退后段内重试/资金换仓。','已见当前存续科技池、行业/市值快照、日线成交代理；不称样本外。','下一步：本轮结项，不改S阈值；按第二实验检验确认后的新资金是否有条件优势。']
    (O/'REPORT.txt').write_text('\n'.join(lines)+'\n')
    progress={k:result[k] for k in ['verdict','event_count','seconds_reporting']};print(json.dumps(clean(progress),ensure_ascii=False));print(json.dumps(clean(summaries),ensure_ascii=False))

if __name__=='__main__':main()
