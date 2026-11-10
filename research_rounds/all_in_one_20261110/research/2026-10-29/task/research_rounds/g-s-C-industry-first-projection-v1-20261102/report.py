"""Summarize existing static outputs only. No new target solves or future labels."""
from c_selector import *
from collections import defaultdict
import csv
import pandas as pd
FACT=Path('/Users/bytedance/Documents/Codex/2026-11-01/task/market-permission-price-only-20261101/industry-evidence-ranking-readonly-v1')
D=Decimal

def total(xs):return sum((D(x) for x in xs),D(0))
def csvsave(p,rows):
    p.parent.mkdir(parents=True,exist_ok=True)
    if not rows:return
    with p.open('w') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def metrics(x,r,names):
    s=x['snapshot'];ds={d['sid']:d for d in x['B_demands']};sectors=defaultdict(lambda:dict(before_capital=D(0),projected_capital=D(0),projected_risk=D(0),new_buy_cash=D(0),sold_mark=D(0)))
    for z in s['rows']:
        a=sectors[z['sector']];a['before_capital']+=D(z['capital']);a['projected_capital']+=D(z['capital']);a['projected_risk']+=D(z['risk'])
    by={z['id']:z for z in s['rows']}
    for p in r['donors']['rows']:
        sec=by[p['layer']]['sector'];a=sectors[sec];a['projected_capital']-=D(p['capital']);a['projected_risk']-=D(p['risk_release']);a['sold_mark']+=D(p['capital'])
    for sid,q in r['Q'].items():
        if not q:continue
        d=ds[sid];a=sectors[d['sector']];a['projected_capital']+=D(q)*D(d['mark']);a['projected_risk']+=D(q)*max(D(0),D(d['mark'])-D(d['floor']));a['new_buy_cash']+=J.buy_cost(d,q)
    nav=D(r['validation']['terminal']['nav']);nd=D(s['decision_nav']);rows=[]
    for sec,a in sectors.items():
        rows.append(dict(sector=sec,industry=names.get(sec,sec),**a,projected_NAV_weight=a['projected_capital']/nav,decision_NAV_weight=a['projected_capital']/nd))
    rows.sort(key=lambda a:a['projected_capital'],reverse=True)
    minima={}
    for check in r['validation']['checks']:
        kind=check['constraint']
        if kind not in minima or D(check['residual'])<D(minima[kind]['residual']):minima[kind]=check
    buy=total(J.buy_cost(ds[sid],q) for sid,q in r['Q'].items() if q);net=total(o['net'] for o in r['donors']['orders'])
    rawsell=total(p['capital'] for p in r['donors']['rows']);buyraw=total(D(ds[sid]['mark'])*q for sid,q in r['Q'].items() if q)
    return dict(new_positive_requests=sum(bool(q) for q in r['Q'].values()),donor_stocks=len(r['D']),
        net_sell=net,buy_cash_including_fee=buy,sold_mark_capital=rawsell,new_mark_capital=buyraw,
        cash_change=net-buy,turnover_mark_over_decision_NAV=(rawsell+buyraw)/nd,
        projected_terminal=r['validation']['terminal'],projected_exposure=D(r['validation']['terminal']['capital'])/nav,
        account_risk_fraction=D(r['validation']['terminal']['risk'])/nav,
        minimum_constraint_residuals=minima,sectors=rows,
        projected_risk_sector_sum_minus_terminal=total(z['projected_risk'] for z in rows)-D(r['validation']['terminal']['risk']),
        actual_cash_released=r['validation']['actual_cash_released'],actual_risk_released=r['validation']['actual_risk_released'])

def main():
    names=pd.read_parquet(FACT/'LOCAL2026-RANKS_AND_OPPORTUNITIES.parquet',columns=['sector','industry']).drop_duplicates().set_index('sector')['industry'].to_dict()
    summary={};sentences=[]
    for k,day in [('2025_26','2025-07-03'),('2022','2022-01-06')]:
        x=read(HERE/'inputs'/(k+'.json'));c=read(HERE/'results'/k/'C.json');verify_result(x,c)
        assert read(HERE/'results'/k/'RESTORED.json')['exact']
        b=read(BASE/'results'/k/'B.json');a=read(BASE/'results'/k/'A_JF2.json');comp={s['sid']:s for s in x['evidence']['full_union']}
        original=read(BASE.parent/'g-s-historical-native-nextsession-20261101/run'/k/'close'/(day+'-CLOSE.json'))
        exits=original['account']['exits'];mb=metrics(x,b,names);mc=metrics(x,c,names);allrows=[]
        traces={z['sid']:z for z in c['trace']};order={sid:i+1 for i,sid in enumerate(sorted(c['Q'],key=lambda sid:c['C_rank_binding']['stock_priority'][sid]['C_key']))}
        for d in x['B_demands']:
            sid=d['sid'];r=comp[sid];sec=d['sector'];t=traces[sid]
            allrows.append(dict(sid=sid,name=r['name'],sector=sec,industry=names.get(sec,sec),
                industry_H1=x['industry_evidence']['industry_H1'][sec],industry_C_order=c['C_rank_binding']['stock_priority'][sid]['C_key'][0]+1,
                original_B_stock_order=r['competition_rank'],C_request_order=order[sid],PVR=r['PVR'],PVR_ready=r['PVR_ready'],
                old_mobile=bool(r['existing_mobile']),use=d['use'],pool=d['pool'],role=d['role'],
                original_independent_max=d['max_q'],minimum=d['quantity']['buy_minimum'],buy_step=d['quantity']['buy_step'],
                B_new_qty=b['Q'][sid],C_new_qty=c['Q'][sid],B_sold_qty=b['D'].get(sid,0),C_sold_qty=c['D'].get(sid,0),
                canonical_receipt_id=d['receipt_id'],real_original_pending_exit=bool(sid in exits),
                C_raw_trace_reason=t.get('reason'),C_raw_joint_bounds_or_failures=json.dumps(t.get('blockers_or_necessary_bounds',{}),ensure_ascii=False),
                rejection_counts_are_exclusive=False,submit_allowed=False))
        allrows.sort(key=lambda z:z['C_request_order']);save(HERE/'report'/(k+'-FULL_FRESH_B_C.json'),allrows);csvsave(HERE/'report'/(k+'-FULL_FRESH_B_C.csv'),allrows)
        targets=[]
        for sid in sorted(set(b['mobile_targets'])|set(c['mobile_targets'])):
            r=comp[sid];targets.append(dict(sid=sid,name=r['name'],sector=r['sector'],industry=names.get(r['sector'],r['sector']),
                original_B_order=r['competition_rank'],B_target=b['mobile_targets'].get(sid,0),C_target=c['mobile_targets'].get(sid,0),
                B_new=b['Q'].get(sid,0),C_new=c['Q'].get(sid,0),B_sell=b['D'].get(sid,0),C_sell=c['D'].get(sid,0),
                real_pending_exit=sid in exits))
        csvsave(HERE/'report'/(k+'-ALL_MOBILE_TARGETS.csv'),targets);save(HERE/'report'/(k+'-ALL_MOBILE_TARGETS.json'),targets)
        donors=[]
        for row in c['donors']['rows']:
            z=next(z for z in x['snapshot']['lots'] if z['id']==row['layer']);donors.append(dict(row,name=comp[z['sid']]['name'],sector=z['sector'],industry=names[z['sector']],
                mark=z['mark'],actual_floor=z['floor'],role=z['role'],pool=z['pool'],purpose=z['purpose'],
                original_B_key=z['rank_key'],C_key=c['C_rank_binding']['stock_priority'][z['sid']]['C_key'],
                qty_before=z['qty'],legal_sellable=z['sellable_qty'],line_fraction=(D(z['mark'])-D(z['floor']))/D(z['mark']),
                sold_for_price_failure=False,actual_pending_exit=z['sid'] in exits))
        save(HERE/'report'/(k+'-C_DONOR_LAYERS.json'),donors)
        gain=[s for s in c['Q'] if c['Q'][s] and not b['Q'][s]];lost=[s for s in b['Q'] if b['Q'][s] and not c['Q'][s]]
        conflicts=[dict(sid=sid,name=comp[sid]['name'],C_new=q,real_pending_exit=exits[sid]) for sid,q in c['Q'].items() if q and sid in exits]
        summary[k]=dict(B=mb,C=mc,fresh_mother_size=len(x['B_demands']),same_full_fresh_mother=True,
            gained_requests=[dict(sid=s,name=comp[s]['name'],q=c['Q'][s]) for s in gain],lost_requests=[dict(sid=s,name=comp[s]['name'],q=b['Q'][s]) for s in lost],
            C_same_stock_net_conflicts=[s for s,q in c['Q'].items() if q and c['D'].get(s)],C_actual_legacy_exit_conflicts=conflicts,
            original_actual_exit_orders_unchanged=len(exits),A_CLOSE_REFERENCE_ONLY=dict(raw_items=len(x['A_demands']),Q=a['Q'],D_rows=a['donors']['rows'],not_whole_account_comparison=True),
            C_run_seconds=read(HERE/'results'/k/'RUN.json')['seconds'],crossprocess_exact=True,financial_events=0)
        sentences.append(k+' B新请求'+str(mb['new_positive_requests'])+'→C'+str(mc['new_positive_requests'])+'；C首行业'+mc['sectors'][0]['industry']+' '+str(round(mc['sectors'][0]['projected_NAV_weight']*100,2))+'%。')
    save(HERE/'report/SUMMARY.json',summary)
    for k,s in summary.items():
        for p in ('B','C'):csvsave(HERE/'report'/(k+'-'+p+'-INDUSTRY_WEIGHTS.csv'),s[p]['sectors'])
    lines=['C_INDUSTRY_FIRST：只读目标投影结果；非订单、非成交、非历史收益。','17/17合成通过；失败fixture身份原稿保留。两真实C投影跨进程复算精确，未重跑A/B，0金融事件。']+sentences
    for k,s in summary.items():
        lines+=['',k,'政策 | 净卖款 | 新买含费 | 条件现金变化 | 条件曝险 | 名义risk/条件权益 | 最大行业']
        for policy in ('B','C'):
            m=s[policy];top=m['sectors'][0];lines.append(f"{policy} | {m['net_sell']:,.2f} | {m['buy_cash_including_fee']:,.2f} | {m['cash_change']:,.2f} | {m['projected_exposure']*100:.2f}% | {m['account_risk_fraction']*100:.2f}% | {top['industry']} {top['projected_NAV_weight']*100:.2f}% (冻结决策NAV {top['decision_NAV_weight']*100:.2f}%)")
        lines+=['原价卖+买换手/冻结决策NAV：B '+str(round(s['B']['turnover_mark_over_decision_NAV']*100,2))+'%，C '+str(round(s['C']['turnover_mark_over_decision_NAV']*100,2))+'%；不是实际成交换手。',
            'C逐阶段最小余量：'+ '; '.join(t+' '+str(v['residual'])+' ['+v['stage']+']' for t,v in s['C']['minimum_constraint_residuals'].items()),
            'C新增相对B：'+','.join(z['name']+' '+str(z['q']) for z in s['gained_requests']),
            'C失去B新请求：'+','.join(z['name']+' '+str(z['q']) for z in s['lost_requests']),
            '实际旧卖冲突：'+(','.join(z['name']+' 新目标'+str(z['C_new']) for z in s['C_actual_legacy_exit_conflicts']) or '未见新增买目标与原待卖同股')+'；全部仍只读不可提交。']
    lines+=['','解释与反例',
        'Jan6的C集中在中药；这证明行业目标能够改变资本方向，不证明中药后来有收益。Jul3实际前排行业得到资金，但并未形成单主题80%。行业机会数、真实保护风险和旧仓占用仍限制集中。',
        'Jul3 C把北方铜业4200股列为供资者；B保留它。它在原个股联合域靠前且原I/线/A仍合法，C仅因行业优先发生替换；不是价格支持失败。这是C可能误卖旧赢家的明示新政策代价。全部其他减持/增量见完整目标表，不能只看受益行业。',
        '两点C净卖款仍高，不是最小换手解；仍沿B弱者前缀供资、前排量最大优先。Jan6风险未用满时现金/资本已接近边界；Jul3仍接近6%风险边界。各阶段全部残差保留在C.json，不能把聚合失败计数称独立机会或独占拒因。',
        'C净目标没有同股正买正卖；但真实原A未完成退出没有取消，Jan6创维数字待卖100与C新100冲突。analysis-only共同视图不是实际账户，实际9/16退出仍保留。',
        'A仅原CLOSE S筹资层，单列参考，不与B/C完整fresh域做整户优越或收益对比。',
        '', '2026市场列表边界',
        'Apr30市场扩张列表8股：化学品4、元件2、电池2。C前4为化学品；严格半导体未成熟，不在扩张列表，但原canonical_CP1_Q为19，不能叫无信号。',
        'May7市场扩张列表61股：化学品9、元件14、通信设备6、电池1、半导体21、消费电子10。C前9全为化学品，严格半导体首个到第31名；原B第6已有安路科技。行业优先不自动把严格半导体推80%。',
        '能源金属May7行业H1第一但扩张列表0；跳过源于没有当日机会，不是预测下跌。其他电子也没有当日列表机会。所有90行业（含无机会/无许可）及61股完整排序均保留。',
        '两日均没有本G/S账户状态；源表只有minimum fee/minimum quantity，没有完整费用合同与日期化数量规则。按授权停在排名名额：未执行空账户fixture、未补费用/步长、未计算金额或可同时成交仓位。若以后授权容量fixture，两政策必须同为1m现金、零持仓、零旧单，且不得冒称历史连续状态。',
        '', '验收结论',
        '支持：在完全相同资源约束下，行业先序确能显著改变目标方向，且不需保证均分。否定：行业优先必然严格半导体80%、排序靠前就是更好机会、坐标不可再减就是全局最小换手。未知：卖旧强股集中新行业是否值得，行业H1迟滞损失及真实执行后的净收益；本轮不以长回测回答。',
        '未修改原B/JF2、指标、F1、价格或任何风险数值。原策略仍可运行；本包只读、submit_allowed=False，实际释放现金/风险均0。']
    (HERE/'REPORT.txt').write_text('\n'.join(lines)+'\n')
    print('\n'.join(lines[:10]),flush=True)

if __name__=='__main__':main()
