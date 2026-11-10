"""Read-only post-confirmation effect and background accounting."""
from pathlib import Path
import json,csv,gzip,collections,datetime,hashlib,time
from decimal import Decimal as D
import pandas as pd
O=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/cp1-incremental-mechanism-20261029');E1=O.parent/'s-entry-mechanism-audit-20261029';R=O/'results';Z=D(0)
def d(x):return D(str(x))
def conv(x):
    if isinstance(x,D):return str(x)
    if isinstance(x,dict):return {k:conv(v) for k,v in x.items()}
    if isinstance(x,list):return [conv(v) for v in x]
    return x
def save(p,x):
    with p.open('x') as f:json.dump(conv(x),f,ensure_ascii=False,indent=2,allow_nan=False)
def output(p,rows):
    with p.open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(conv(rows))
def good(x):return x is not None and not pd.isna(x)
def stats(pairs,w):
    answer={};tails={k for k,c,n in pairs if any(good(u['net_return']) and float(u['net_return'])>=.3 for u in [c,n])}
    for label,pos in [('confirmed',1),('control',2)]:
        total=positive=loss=tail=ordinary=fees=real=unreal=claim=own=Z;wins=[];losers=[];total_fill_weight=Z;win_weight=Z
        counts=collections.Counter()
        for row in pairs:
            k,u=row[0],row[pos];weight=w[k];p=d(u['net_pnl']);total+=weight*p;positive+=weight*max(p,Z);loss+=weight*max(-p,Z);fees+=weight*(d(u['buy_fees'])+d(u['sell_fees']))
            if k in tails:tail+=weight*p
            else:ordinary+=weight*p
            if good(u['net_return']) and float(u['net_return'])>=.3:own+=weight*p;counts['settled_tail' if u['financial_closed'] else 'terminal_valued_or_claim_tail']+=1
            real+=weight*(d(u['realized_trading_pnl'])+d(u['paid_dividend_income']));unreal+=weight*d(u['unrealized_inventory_pnl']);claim+=weight*d(u['accrued_unpaid_dividend_income'])
            counts['traded' if good(u['first_fill']) else 'not_filled']+=1;counts['terminal_inventory']+=int(int(u['shares'])>0);counts['unpaid_dividend_units']+=int(d(u['dividend_receivable'])>0)
            if good(u['first_fill']):
                total_fill_weight+=weight
                if p>0:wins.append((float(u['net_return']),float(weight)));win_weight+=weight
                elif p<0:losers.append((-float(u['net_return']),float(weight)))
        mw=sum(x*y for x,y in wins)/sum(y for x,y in wins) if wins else None;ml=sum(x*y for x,y in losers)/sum(y for x,y in losers) if losers else None
        answer[label]=dict(net_pnl=total,positive=positive,negative_loss=loss,pair_tail_pnl=tail,pair_ordinary_pnl=ordinary,own_tail_pnl=own,actual_fees=fees,realized_and_paid=real,unrealized_inventory=unreal,unpaid_dividend_income=claim,profit_factor=float(positive/loss) if loss else None,payoff_ratio=mw/ml if mw and ml else None,mean_win_return=mw,mean_loss_return_abs=ml,win_rate_descriptive=float(win_weight/total_fill_weight) if total_fill_weight else None,counts=dict(counts))
    c=answer['confirmed'];n=answer['control'];answer.update(delta=c['net_pnl']-n['net_pnl'],saved_losses=n['negative_loss']-c['negative_loss'],foregone_positive=n['positive']-c['positive'],delta_tail=c['pair_tail_pnl']-n['pair_tail_pnl'],delta_ordinary=c['pair_ordinary_pnl']-n['pair_ordinary_pnl'])
    assert abs(answer['delta']-(answer['saved_losses']-answer['foregone_positive']))<D('.01')
    assert abs(answer['delta']-answer['delta_tail']-answer['delta_ordinary'])<D('.01')
    return answer

def main():
    t=time.monotonic();f=pd.read_parquet(R/'units.parquet');ps=pd.read_parquet(O/'pairs.parquet');coverage=json.loads((O/'MATCH_COVERAGE.json').read_text());look={(u['pair_id'],u['cost'],u['leg']):u for u in f.to_dict('records')};counts=ps.case_symbol.value_counts().to_dict();summary={};rows=[];ranks=[]
    for cost in [1,2]:
        pairs=[(p.pair_id,look[p.pair_id,cost,'case'],look[p.pair_id,cost,'control']) for p in ps.itertuples()]
        main=stats(pairs,{k:D(1) for k,c,n in pairs});rob=stats(pairs,{k:D(1)/(D(407)*D(counts[c['symbol']])) for k,c,n in pairs});summary[str(cost)]=dict(main=main,case_stock_equal_robustness=rob,mean_delta_per_1m_unit=main['delta']/D(len(pairs)))
        for k,c,n in pairs:rows.append(dict(cost=cost,pair_id=k,case_symbol=c['symbol'],control_symbol=n['symbol'],decision_day=c['decision_day'],case_fill=str(c['first_fill']) if good(c['first_fill']) else '',control_fill=str(n['first_fill']) if good(n['first_fill']) else '',case_pnl=d(c['net_pnl']),control_pnl=d(n['net_pnl']),delta=d(c['net_pnl'])-d(n['net_pnl']),case_return=c['net_return'] if good(c['net_return']) else '',control_return=n['net_return'] if good(n['net_return']) else '',case_holds=int(c['shares']),control_holds=int(n['shares']),case_unpaid=c['dividend_receivable'],control_unpaid=n['dividend_receivable'],case_financial_closed=c['financial_closed'],control_financial_closed=n['financial_closed']))
        for ordering,key in [('confirmed_contribution',lambda x:x['case_pnl']),('control_contribution',lambda x:x['control_pnl'])]:
            cc=nn=Z
            for j,x in enumerate(sorted([x for x in rows if x['cost']==cost],key=key,reverse=True),1):
                cc+=x['case_pnl'];nn+=x['control_pnl'];ranks.append(dict(cost=cost,ordering=ordering,rank=j,pair_id=x['pair_id'],case_symbol=x['case_symbol'],control_symbol=x['control_symbol'],cumulative_case=cc,cumulative_control=nn,cumulative_delta=cc-nn))
    output(R/'paired-effects.csv',rows);output(R/'continuous-contributions.csv',ranks)
    # Full original I-background ledger: separate from and never added to post-confirmation alpha.
    es=pd.read_parquet(E1/'opportunities.parquet');cases=pd.read_parquet(O/'all-confirmations.parquet');confirmed=set()
    for c in cases.itertuples():
        hit=es[es.symbol.eq(c.symbol)&es.start.le(c.date)&(es.end_signal.isna()|es.end_signal.gt(c.date))];assert len(hit)==1;confirmed.add(hit.iloc[0].event_id)
    old=pd.read_parquet(E1/'results/units.parquet');old=old[(old.variant=='I')&(old.cost==1)];back=collections.defaultdict(lambda:dict(events=0,traded=0,net_pnl=Z,negative_loss=Z,actual_fees=Z))
    for u in old.to_dict('records'):
        tag=('ever_qualified_CP1' if u['event_id'] in confirmed else 'no_qualified_CP1')+'|'+('negative' if d(u['net_pnl'])<0 else 'nonnegative')
        z=back[tag];z['events']+=1;z['traded']+=int(good(u['first_fill']));z['net_pnl']+=d(u['net_pnl']);z['negative_loss']+=max(Z,-d(u['net_pnl']));z['actual_fees']+=d(u['buy_fees'])+d(u['sell_fees'])
    background=[dict(group=k,**v) for k,v in back.items()];assert sum(x['events'] for x in background)==5349
    output(R/'first-participation-background.csv',background)
    # Export existing audit streams and actual fee components, no rerun.
    fills=[];flows=[];holds=[]
    with gzip.open(R/'audit.jsonl.gz','rt') as stream:
        for line in stream:
            a=json.loads(line);last_sell=None
            for x in a['audit']:
                flows.append(dict(pair_id=a['pair_id'],leg=a['leg'],cost=a['cost'],kind=x['kind'],details_json=json.dumps(x,ensure_ascii=False)))
                if x['kind']=='fill':
                    z=x['receipt'];fills.append(dict(pair_id=a['pair_id'],leg=a['leg'],cost=a['cost'],symbol=a['symbol'],at=z['at'],side=z['side'],shares=z['shares'],gross=z['gross_cny'],fees=z['fees_cny'],fee_components=json.dumps(x['fee_components'],ensure_ascii=False)))
                    if z['side']=='sell':last_sell=z['at']
            u=look[a['pair_id'],a['cost'],a['leg']]
            if good(u['first_fill']):
                end=datetime.datetime.fromisoformat(last_sell) if not int(u['shares']) and last_sell else datetime.datetime.fromisoformat('2026-10-27T15:10:00+08:00')
                days=(end-datetime.datetime.fromisoformat(str(u['first_fill']))).total_seconds()/86400
                holds.append(dict(pair_id=a['pair_id'],leg=a['leg'],cost=a['cost'],holding_calendar_days=days,actual_initial_spend=d(u['buy_gross'])+d(u['buy_fees']),terminal_holds=int(u['shares'])>0))
    output(R/'fills.csv',fills);output(R/'cashflows.csv',flows);output(R/'holding-and-capital.csv',holds)
    # Sample/full identity and frozen input checks.
    sample=pd.read_parquet(O/'sample/units.parquet');keys=['pair_id','leg','cost'];full=f.set_index(keys).loc[sample.set_index(keys).index].reset_index();pd.testing.assert_frame_equal(sample.sort_values(keys).reset_index(drop=True),full[sample.columns].sort_values(keys).reset_index(drop=True),check_exact=True,check_dtype=False)
    frozen=json.loads((O/'economic-freeze.json').read_text());bad=[p for p,h in frozen['sha256'].items() if hashlib.sha256(Path(p).read_bytes()).hexdigest()!=h];assert not bad,bad
    b=summary['1']['main'];c=summary['2']['main'];rob=summary['1']['case_stock_equal_robustness']
    if b['delta']*c['delta']<0 or b['delta']*rob['delta']<0:verdict='不确定：成本或计权口径反向'
    elif b['delta']>0 and b['delta_tail']>0:verdict='匹配支持区间内存在正向尾部取舍，须结合覆盖与残余失衡审阅，不是因果或整池验证'
    elif b['delta']>0:verdict='匹配区间净改善但未支持尾部增益，不能以少亏替代新增资金抓肥尾目标'
    else:verdict='匹配支持区间未显示正的后确认增量；不能据此否定整个CP1/PVR复合确认或N1晋升'
    result=dict(verdict=verdict,primary_question=read_protocol_question(),coverage=coverage,scenarios=summary,background_only_not_added=background,matched_pairs=len(ps),unmatched_not_zero=coverage['unmatched'],causal_claim=False,global_claim=False,early_support_limit=True,sample_full_exact=True,source_freeze_unchanged=True,all_terminal_assets_included=True,report_seconds=time.monotonic()-t)
    save(R/'summary.json',result)
    lines=['实验二：暖度与PVR>50同期集合中的首次CP1凭据增量','',verdict,'','覆盖2916确认中715配对，2201未匹配不记零。704对年龄0-20，11对21-62，无63+。年龄和波动仍不完全平衡，不能全池或因果外推。']
    for cost in ['1','2']:
        z=summary[cost];v=z['main'];lines += ['',f'费用合同{cost}：后确认净差{v["delta"]}元；每100万影子配对平均差{z["mean_delta_per_1m_unit"]}元。',f'省亏损{v["saved_losses"]}；丢正收益{v["foregone_positive"]}；尾部对差{v["delta_tail"]}；普通对差{v["delta_ordinary"]}。',f'确认组盈亏比{v["confirmed"]["payoff_ratio"]}，对照{v["control"]["payoff_ratio"]}；胜率仅描述。',f'股票等权净差{z["case_stock_equal_robustness"]["delta"]}。']
    lines += ['','每单元独立100万，无共享资金。两边均在同一配对决策之后申请新资金，统一原I/E0退出，未带入确认前利润。','未平仓和未付权益进入主账；financial_closed=False可能仅含待结算权益，并不等于仍持股。','背景first-participation-background.csv包含实验一全部5349 I事件和失败成本，只作路径背景，不与新增资金净差相加，也不是2%试仓回测。','本轮资格保留市场/行业趋势、来源/准备、当前快照市值和身份、RS准备/新鲜度；取消ACT/现金/名额竞争。','不代表完整小仓+追加策略的整户净增益，不代表N1成本晋升，不改变产品或交易账户。','本轮到此结项，不调CP1/PVR阈值、不扩匹配、不自动续实验三。']
    (O/'REPORT.txt').write_text('\n'.join(lines)+'\n');print(json.dumps(conv(dict(verdict=verdict,summary=summary,report_seconds=result['report_seconds'])),ensure_ascii=False))
def read_protocol_question():return json.loads((O/'PROTOCOL.json').read_text())['primary_question']
if __name__=='__main__':main()
