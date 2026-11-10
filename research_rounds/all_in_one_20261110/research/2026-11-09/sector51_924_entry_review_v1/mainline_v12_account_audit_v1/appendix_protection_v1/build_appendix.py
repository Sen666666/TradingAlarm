"""Saved v1 protection/MFE appendix only. No Data, strategy imports, history or quotes."""
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict
import sys,json,hashlib,csv
sys.dont_write_bytecode=True
O=Path(__file__).resolve().parent
sys.path.insert(0,str(O.parent))
import accounting_core as au
R=O.parent.parent
Z=D(0)
DAYS=['2024-10-08','2024-10-10']
FOCUS={'600779.SH':'水井坊','300085.SZ':'银之杰','000158.SZ':'常山北明'}
SIG='2024-09-23'
def save(n,v):
    p=O/(n+'.json');p.write_text(json.dumps(v,ensure_ascii=False,indent=2,default=str)+'\n')
    if isinstance(v,list) and v:
        with (O/(n+'.csv')).open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(dict.fromkeys(k for x in v for k in x)));w.writeheader()
            w.writerows({k:json.dumps(y,ensure_ascii=False,default=str) if isinstance(y,(list,dict)) else y for k,y in x.items()} for x in v)
def n(x):return f'{D(x):,.2f}'
def main():
    rules=au.read(au.RULES);proxies=au.read(au.PROTOCOL)['approved_proxy_ids'];rows=[];lots=[];daily=[];sources={}
    sources[str(au.RULES)]=au.sha(au.RULES);sources[str(au.PROTOCOL)]=au.sha(au.PROTOCOL)
    for label,path in [('M12',R/'mainline_candidate_v12_winner_funding_competition/once_20250120'),('M7',au.BASE)]:
        manifest=au.read(path/'OUTPUT_HASHES.json');ss=au.read(path/'SOURCE_HASHES.json')
        for f in ['ORDERS','HOLDINGS','EQUITY_EVENTS','DAY_LEDGER','CAPITAL_LOTS']:
            p=path/(f+'.json');assert au.sha(p)==manifest[p.name];sources[str(p)]=manifest[p.name]
        assert ss[str(au.RULES)]==sources[str(au.RULES)] and ss[str(au.PROTOCOL)]==sources[str(au.PROTOCOL)]
        orders=au.read(path/'ORDERS.json');holds=au.read(path/'HOLDINGS.json');eq=au.read(path/'EQUITY_EVENTS.json');capital=au.read(path/'CAPITAL_LOTS.json');cal=[x['day'] for x in au.read(path/'DAY_LEDGER.json') if x['day']<=DAYS[-1]]
        for sid,name in FOCUS.items():
            seeds=[x for x in orders if x['side']=='BUY_SEED' and x['sid']==sid and x['signal_day']==SIG];assert len(seeds)==1;seed=seeds[0];rid=seed['round_id'];rs=[]
            for day in cal:
                if day<seed['day']:continue
                hh=[x for x in holds if x['round_id']==rid and x['day']==day]
                oo=[x for x in orders if x['round_id']==rid and x['day']<=day]
                cf=au.sm(oo,'cash_delta');div=sum((D(x['receivable_delta']) for x in eq if x.get('round_id')==rid and x['day']<=day and D(x.get('receivable_delta',0))>0),Z)
                q=sum(x['qty'] for x in hh);mark=au.sm(hh,'market_value')
                if q:
                    raw=D(hh[0]['raw_mark']);assert all(D(x['raw_mark'])==raw for x in hh)
                    sell=raw*D('.9995');fee=au.fee_calc(rules,proxies,sid,day,q,sell,'sell');net=cf+div+q*sell-fee
                    cc=[x for x in capital if x['round_id']==rid and x['day']==day]
                    assert len(cc)==len(hh)
                    for x in cc:au.near(net,x['round_net'],('close_net_saved',label,sid,day))
                else:raw=None;sell=None;fee=Z;net=cf+div
                row=dict(account=label,name=name,sid=sid,opportunity_key=sid+'|'+SIG,round_id=rid,day=day,qty=q,trade_cashflow=cf,net80_entitlement=div,raw_close=raw,marked_net_PnL=cf+div+mark,hypothetical_close_exit_fee=fee,close_net_liquidation_PnL=net)
                rs.append(row);daily.append(row)
                if day not in DAYS:continue
                peak=max(rs,key=lambda x:x['close_net_liquidation_PnL'])
                row=dict(row,close_MFE=peak['close_net_liquidation_PnL'],close_MFE_day=peak['day'],giveback_from_close_MFE=peak['close_net_liquidation_PnL']-net,close_MFE_is_intraday=False,actual_liquidation_occurred=False)
                groups=defaultdict(int)
                for h in hh:groups[D(h['protection_signal'])/D(h['factor'])]+=h['qty']
                staged=cf+div
                for floor,qty in groups.items():
                    sell=floor*D('.9995');staged+=qty*sell-au.fee_calc(rules,proxies,sid,day,qty,sell,'sell')
                row['hypothetical_each_lot_own_floor_whole_round_PnL']=staged
                row['own_floor_fee_convention']='One hypothetical sell per distinct raw floor, same-date schedule; no future trades or dividends.'
                row['T1_locked_current_qty']=sum(h['qty'] for h in hh if h['bought']==day)
                rows.append(row)
                for h in hh:
                    factor=D(h['factor']);floor=D(h['protection_signal'])/factor;p=floor*D('.9995')
                    feeall=au.fee_calc(rules,proxies,sid,day,q,p,'sell')
                    lots.append(dict(account=label,name=name,sid=sid,round_id=rid,day=day,lot_id=h['lot_id'],kind=h['kind'],bought=h['bought'],qty=h['qty'],T1_same_day_locked=h['bought']==day,cp_id=h['cp_id'],locked_exit=h['locked_exit'],protection_type='I floor' if h['kind']=='SEED' else 'effective CP layer floor including I and later ratchets',adjusted_protection_signal=h['protection_signal'],factor=h['factor'],raw_protection_price=floor,hypothetical_sell_price_after_5bp=p,raw_close=h['raw_mark'],distance_from_close_pct=100*(floor/D(h['raw_mark'])-1),hypothetical_all_remaining_qty_at_this_raw_price=q,hypothetical_whole_round_PnL_if_all_remaining_at_this_price=cf+div+q*p-feeall,hypothetical_full_round_exit_fee=feeall,current_marked_PnL=cf+div+mark,current_close_net_liquidation_PnL=net,not_execution_guarantee=True))
    save('FOCUSED_CLOSE_MFE',rows);save('FOCUSED_LOT_PROTECTION',lots);save('FOCUSED_DAILY_NET_PATH',daily)
    tail=R/'mainline_tail_capture_baseline_v1'
    for name in ['CLOSED_POSITIVE_RANKING.json','BASELINE_DEFINITIONS.json','analyze.py']:
        sources[str(tail/name)]=au.sha(tail/name)
    ranked=au.read(tail/'CLOSED_POSITIVE_RANKING.json');startup=[x for x in ranked if x['cohort']=='SEPT_STARTUP_SEED_OPEN_0923_0930'];top=[x for x in startup if x['in_top10pct_positive']]
    assert len(startup)==188 and len(top)==19
    wins=au.read(O.parent/'STARTUP_19_STRONG_WINNER_PATHS.json');missing=[x for x in wins if not x['candidate_captured']]
    definition=dict(group='SEPT_STARTUP_SEED_OPEN_0923_0930',window='Original M7 first actual SEED OPEN from 2024-09-23 through 2024-09-30 inclusive, all sectors',population_count=222,positive_closed_as_of_original_full_end='2025-01-20',positive_closed_count=188,selection='Sort original M7 final actual realized net PnL of profitable CLOSED rounds descending; ceil(188*10%) = 19',fixed_count=19,source=str(tail/'CLOSED_POSITIVE_RANKING.json'),sha256=au.sha(tail/'CLOSED_POSITIVE_RANKING.json'),evaluation_label_only=True,entry_information=False,out_of_sample=False,note='Fixed before this M12 comparison but selected retrospectively from observed original M7 full window. No future baseline PnL is counted as certified candidate performance.')
    missrows=[dict(name=x['name'],sid=x['sid'],original_signal=x['baseline_original_signal'],original_seed_OPEN=x['baseline_seed_OPEN'],M7_exit_by_common_cutoff=x['baseline_exit_day'],M7_common_window_PnL_through_20241010=x['baseline_common_pnl'],M7_original_full_window_PnL_through_20250120=x['baseline_sealed_final_pnl'],candidate_captured=False,common_pnl_equals_full_because_closed_before_cutoff=x['baseline_open_at_common_end'] is False and D(x['baseline_common_pnl'])==D(x['baseline_sealed_final_pnl'])) for x in missing]
    assert all(x['common_pnl_equals_full_because_closed_before_cutoff'] for x in missrows)
    save('FIXED_19_LABEL_DEFINITION',definition);save('MISSED_FIXED_19_COMMON_VS_FULL',missrows)
    text=['# v1 独立补充：净清算 MFE 与保护线','', '仅使用原M12 v1与原M7已保存输出，截止2024-10-10；不修改主报告/封条，不含新v2。','',
    '## 口径','实际路径是已经发生的成交、费用和权益。净清算PnL仍是假设当日收盘全部剩余数量按收盘价减5bp滑点并扣当日卖费后的整轮结果，不是已经卖出实现的盈利。这里逐日复算并与保存的CAPITAL_LOTS.round_net逐日校验。',
    '收盘MFE是从该轮真实SEED日到该截至日，各日收盘整轮净清算PnL的最高值。它不是日内MFE，不使用high/low，也不提前使用10/10之后的信息。',
    '保护价为保存的复权保护线除当日factor所得原始价格。SEED使用I线，ADD使用当前有效CP层线（可能已经由I或后续CP抬升），不是仅凭购买时cp_id回找旧CP价。保护触发后仍按原OPEN/锁定退出逻辑执行，不是保证成交于该价的止损单。',
    '每lot表同时给出“全部剩余股数都按这一条保护价卖出”的整轮假设PnL，避免把单lot现金误当整轮保护收益。另列“每层各在自己的当前保护价卖出”的合计情景，按相同保护价合并一次卖单计费；不模拟未来路径、更新、停牌、跌停、跳空、T+1或no_fill。两类情景均不是实际回测新交易。',
    '',
    '## 截至当日收盘',
    '|账户|股票|截至日|净清算PnL|此前最高收盘净PnL|峰值日|已回吐|各lot各按自身保护价退出的整轮假设PnL|',
    '|---|---|---|---:|---:|---|---:|---:|']
    for x in rows:text.append(f"|{x['account']}|{x['name']}|{x['day']}|{n(x['close_net_liquidation_PnL'])}|{n(x['close_MFE'])}|{x['close_MFE_day']}|{n(x['giveback_from_close_MFE'])}|{n(x['hypothetical_each_lot_own_floor_whole_round_PnL'])}|")
    text+=['','## 关键解释',
    '水井坊10/10只余300股SEED，原始I线30.730000；现有整轮收盘净清算盈利3,814.64元，但假设剩余股数恰在线上卖出后整轮仅+50.64元，且这不是可保证的最低收益。',
    '银之杰10/9才形成新的收盘峰值52,505.43元，因此10/10自身峰值回吐17,523.08元；原M7同口径回吐11,313.68元，候选多6,209.40元。主报告固定10/8锚点的两日变化与这个峰值回吐是两个不同指标。',
    '银之杰10/10的1200股ADD均已标CP_CLOSE_PROTECTION，当前有效CP原始线41.023422高于当日收盘37.76，其中200股当日新买受T+1限制。按该线卖出的静态情景不是当日尚可成交的保护利润下限；10/11首先被经济预检阻断，不能声称这些锁定层后来已经退出。600股SEED的原始I线仍为7.880000。',
    '常山10/10整轮净清算为新高5,918.60元，尚无收盘峰值回吐；但各层按自身当前线退出的静态整轮情景为-3,960.81元，显示这套现存线不等价于保本或保浮盈规则。',
    '',
    '## M12逐lot保护线','全量M12与原M7对照见FOCUSED_LOT_PROTECTION.json/csv。下表的整轮PnL是把该日所有剩余股数都按该行保护价卖出的独立情景，各行不能相加。',
    '|日|股票|lot末号|类型|剩余股数|原始保护价|全部剩余股数按该价清算的整轮PnL|当日T+1|已锁定退出|','|---|---|---|---|---:|---:|---:|---|---|']
    for x in lots:
        if x['account']=='M12':text.append(f"|{x['day']}|{x['name']}|{x['lot_id'].split('|')[-1]}|{x['kind']}|{x['qty']}|{D(x['raw_protection_price']):.6f}|{n(x['hypothetical_whole_round_PnL_if_all_remaining_at_this_price'])}|{x['T1_same_day_locked']}|{x['locked_exit'] or '无'}|")
    text+=['','## 固定19组是后验评估标签','原M7启动222轮中，截至原完整2025-01-20已闭合且严格盈利的188轮，按最终实际已实现净PnL降序取ceil(188×10%)=19。来源：mainline_tail_capture_baseline_v1/CLOSED_POSITIVE_RANKING.json，SHA256 '+definition['sha256']+'。',
    '这些身份在本次M12实验前固定，但原排序用了原M7全窗口结果，所以是后验评估标签，不是入场可知信息，也不构成样本外验证。建议称“原固定19组”，不要把“强赢家”写成决策时已知属性。',
    '|错失原固定组|原SEED日|原退出日|截至10/10同窗PnL|原截至1/20全窗PnL|','|---|---|---|---:|---:|']
    for x in missrows:text.append(f"|{x['name']}|{x['original_seed_OPEN']}|{x['M7_exit_by_common_cutoff']}|{n(x['M7_common_window_PnL_through_20241010'])}|{n(x['M7_original_full_window_PnL_through_20250120'])}|")
    text+=['两列相等仅因为今世缘10/9、古井贡酒10/10已在原账户闭合。不能从这种相等推及其他未平轮或未到达窗口。','']
    (O/'READOUT.md').write_text('\n'.join(text))
    save('APPENDIX_QA',dict(verdict='PASS_SAVED_NET_MFE_AND_FLOOR_ARITHMETIC',summary_rows=len(rows),lot_rows=len(lots),daily_net_reconciliations=len([x for x in daily if x['qty']]),scope='Original v1 certified through Oct10 only; hypothetical liquidation and close-only MFE, no price/execution guarantee',history_executed=False,strategy_imported=False,network_used=False,source_hashes=sources))
    save('SEAL',dict(scope='Standalone v1 appendix; parent sealed 81-file collection is unchanged',files={p.name:au.sha(p) for p in O.iterdir() if p.is_file() and p.name!='SEAL.json'}))
    for name,h in au.read(O/'SEAL.json')['files'].items():assert au.sha(O/name)==h
    print(json.dumps(dict(rows=rows,report_sha256=au.sha(O/'READOUT.md'),seal_sha256=au.sha(O/'SEAL.json')),ensure_ascii=False,default=str))
if __name__=='__main__':main()
