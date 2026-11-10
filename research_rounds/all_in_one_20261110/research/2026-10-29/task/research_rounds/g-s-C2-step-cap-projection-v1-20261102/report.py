"""Read only archived C10/new C2 results; no target solver or return labels."""
from step_cap import *
import importlib.util,csv
import pandas as pd

spec=importlib.util.spec_from_file_location('c2_archived_c10_metrics_only',CROOT/'report.py')
M=importlib.util.module_from_spec(spec);spec.loader.exec_module(M)

def delta(a,b):return D(a)-D(b)
def nameset(ids,comp):return [dict(sid=s,name=comp[s]['name']) for s in ids]
def decomp(x,large,small):
    ds={d['sid']:d for d in x['B_demands']};both=lost=gain=D(0)
    for sid,d in ds.items():
        a=large['Q'][sid];b=small['Q'][sid];p=D(d['mark'])
        if a and b:both+=D(b-a)*p
        elif a:lost-=D(a)*p
        elif b:gain+=D(b)*p
    return dict(same_funded_stock_size_change=both,C10_only_removed_mark=lost,C2_only_added_mark=gain,total_mark_buy_change=both+lost+gain,
        this_is_not_PnL_or_independent_causal_effect=True)

def riskdensity(x,r):
    ds={d['sid']:d for d in x['B_demands']};buy=sum((D(ds[s]['mark'])*q for s,q in r['Q'].items()),D(0))
    risk=sum((D(q)*max(D(0),D(ds[s]['mark'])-D(ds[s]['floor'])) for s,q in r['Q'].items()),D(0))
    sell=sum((D(z['capital']) for z in r['donors']['rows']),D(0));rel=sum((D(z['risk_release']) for z in r['donors']['rows']),D(0))
    buyfee=sum((J.buy_cost(ds[s],q)-D(q)*D(ds[s]['mark'])*(D(1)+C.B.SLIP) for s,q in r['Q'].items() if q),D(0))
    sellfee=sum((D(z['fees']) for z in r['donors']['orders']),D(0))
    return dict(new_risk_at_mark=risk,new_mark_capital=buy,new_risk_per_mark_capital=risk/buy if buy else None,
        projected_buy_fees=buyfee,projected_sell_fees=sellfee,projected_total_fees=buyfee+sellfee,
        projected_old_risk_release=rel,sold_mark_capital=sell,old_risk_per_sold_mark=rel/sell if sell else None)

def main():
    names=pd.read_parquet(M.FACT/'LOCAL2026-RANKS_AND_OPPORTUNITIES.parquet',columns=['sector','industry']).drop_duplicates().set_index('sector')['industry'].to_dict()
    summary={};tables=[]
    for k,day in [('2025_26','2025-07-03'),('2022','2022-01-06')]:
        x=read(O/'inputs'/(k+'.json'));large=read(CROOT/'results'/k/'C.json');small=read(O/'results'/k/'C2.json');verify(x,small)
        C.verify_result(x,large);comp={q['sid']:q for q in x['evidence']['full_union']};ds={d['sid']:d for d in x['B_demands']}
        caps={d['sid']:d for d in small['C2_upper_bounds']};trace={r['sid']:r for r in small['trace']}
        actual=read(O.parent/'g-s-historical-native-nextsession-20261101/run'/k/'close'/(day+'-CLOSE.json'));exits=actual['account']['exits']
        rows=[]
        for sid,d in ds.items():
            c=caps[sid];t=trace[sid]
            rows.append(dict(sid=sid,name=comp[sid]['name'],sector=d['sector'],industry=names[d['sector']],
                eligibility_same=True,original_C_priority=large['C_rank_binding']['stock_priority'][sid]['C_key'],
                use=d['use'],role=d['role'],pool=d['pool'],receipt_id=d['receipt_id'],deadline=d['deadline'],
                old_mobile=comp[sid]['existing_mobile'],old_all_capital=sum(D(z['capital']) for z in x['snapshot']['rows'] if z['sid']==sid),
                mark=d['mark'],actual_new_floor=d['floor'],minimum=c['minimum'],step=c['step'],
                C10_independent_max=c['original_C10_max_q'],C2_independent_max=c['C2_max_q'],
                extra_target_minlot_reject=c['target_minlot_lost'],C10_new_q=large['Q'][sid],C2_new_q=small['Q'][sid],
                C10_sold_q=large['D'].get(sid,0),C2_sold_q=small['D'].get(sid,0),
                C10_actual_target_minlot_fail=c['original_C10_max_q']<c['minimum'],C2_actual_target_minlot_fail=c['C2_max_q']<c['minimum'],
                C2_trace_reason=t.get('reason'),C2_joint_bounds_failures=t.get('blockers_or_necessary_bounds',{}),
                source_actual_pending_sell=exits.get(sid),submit_allowed=False))
        rows.sort(key=lambda r:r['original_C_priority']);save(O/'report'/(k+'-FULL_FRESH_SIZE_COMPARISON.json'),rows)
        M.csvsave(O/'report'/(k+'-FULL_FRESH_SIZE_COMPARISON.csv'),[{n:(json.dumps(v,ensure_ascii=False,default=str) if isinstance(v,(dict,list)) else v) for n,v in r.items()} for r in rows])
        ml=[r for r in rows if r['extra_target_minlot_reject']];gain=[s for s,q in small['Q'].items() if q and not large['Q'][s]];lost=[s for s,q in large['Q'].items() if q and not small['Q'][s]]
        m10=M.metrics(x,large,names);m2=M.metrics(x,small,names)
        for mode,mm in [('C10',m10),('C2',m2)]:M.csvsave(O/'report'/(k+'-'+mode+'-INDUSTRY_WEIGHTS.csv'),mm['sectors'])
        comparison=[]
        for sid in sorted(set(large['mobile_targets'])|set(small['mobile_targets'])):
            comparison.append(dict(sid=sid,name=comp[sid]['name'],industry=names[comp[sid]['sector']],
                C10_mobile_target=large['mobile_targets'].get(sid,0),C2_mobile_target=small['mobile_targets'].get(sid,0),
                C10_new=large['Q'].get(sid,0),C2_new=small['Q'].get(sid,0),C10_sell=large['D'].get(sid,0),C2_sell=small['D'].get(sid,0),real_pending_sell=sid in exits))
        M.csvsave(O/'report'/(k+'-ALL_MOBILE_TARGETS.csv'),comparison)
        donor_details=[]
        for part in small['donors']['rows']:
            z=next(z for z in x['snapshot']['lots'] if z['id']==part['layer'])
            donor_details.append(dict(part,name=comp[z['sid']]['name'],sector=z['sector'],industry=names[z['sector']],
                qty_before=z['qty'],mark=z['mark'],actual_floor=z['floor'],role=z['role'],pool=z['pool'],purpose=z['purpose'],
                native_sellable=z['sellable_qty'],C10_sold_stock=large['D'].get(z['sid'],0),same_C_priority=small['C_rank_binding']['stock_priority'][z['sid']]['C_key']))
        save(O/'report'/(k+'-C2_DONOR_LAYERS.json'),donor_details)
        summary[k]=dict(C10=m10,C2=m2,fresh_mother=len(rows),original_qualification_and_rank_identical=True,
            extra_target_minlot_rejects=[dict(sid=r['sid'],name=r['name'],C10_new_q=r['C10_new_q']) for r in ml],
            C10_funded_lost_to_new_minlot=sum(bool(r['C10_new_q']) for r in ml),C10_only=nameset(lost,comp),C2_only=nameset(gain,comp),
            buy_mark_decomposition=decomp(x,large,small),risk_density_C10=riskdensity(x,large),risk_density_C2=riskdensity(x,small),
            actual_pending_sell_conflicts=[dict(sid=s,name=comp[s]['name'],C2_new=q,real_old_exit=exits[s]) for s,q in small['Q'].items() if q and s in exits],
            internal_buy_sell_conflict=[s for s,q in small['Q'].items() if q and small['D'].get(s)],
            C2_run_seconds=read(O/'results'/k/'RUN.json')['seconds'],C10_recomputed=False,financial_events=0)
        lines=[k,'模式 | 获资请求/同一fresh母域 | 净筹资 | 买入含费 | 条件曝险 | 原价买+卖换手/决策NAV | 最大行业 | risk/条件权益']
        for mode,m in [('C10',m10),('C2',m2)]:
            top=m['sectors'][0];lines.append(f"{mode} | {m['new_positive_requests']}/{len(rows)} | {m['net_sell']:,.2f} | {m['buy_cash_including_fee']:,.2f} | {m['projected_exposure']*100:.2f}% | {m['turnover_mark_over_decision_NAV']*100:.2f}% | {top['industry']} {top['projected_NAV_weight']*100:.2f}% | {m['account_risk_fraction']*100:.2f}%")
        lines+=['新增目标整手拒绝：'+(','.join(r['name']+'(C10获资'+str(r['C10_new_q'])+')' for r in ml) or '无'),
            '投影买+卖费用（原费率/每单最低费/同股聚合）：C10 '+str(summary[k]['risk_density_C10']['projected_total_fees'])+'，C2 '+str(summary[k]['risk_density_C2']['projected_total_fees'])+'；滑点另计，均非已发生费用。',
            'C2逐阶段最小余量：'+'; '.join(n+' '+str(v['residual'])+' ['+v['stage']+']' for n,v in m2['minimum_constraint_residuals'].items()),
            'C2保留旧原生待卖冲突：'+(','.join(z['name']+' 新'+str(z['C2_new']) for z in summary[k]['actual_pending_sell_conflicts']) or '未见同股新增')+'；全部纯目标不可提交。']
        tables+=lines+['']
    save(O/'report/SUMMARY.json',summary)
    lines=['C2 vs C10：同资格/同次序/同联合约束，唯一单次增量上界差分。',
        '12/12受影响合成通过；原C10读取归档未重算，两新C2静态投影，无金融事件、无实际买卖、无收益比较。净筹资/新买/行业权重均是指定卖出和结算完成后的条件目标，非现实已发生。',
        '上界：C2=min(原C10 max_q, legal_floor(.02*冻结决策NAV/(保存mark*(1+5bp))))。毛金额目标、费用另占资源；股10%仍含全部承诺；已有股新单STAR最低200，不向上例外。',
        '资格、slot、行业H1→业内原PVR次序、canonical身份/deadline、旧库存/实际floor、供资方向/费用/整账约束均完全相同，不加行业当天推进门。']+tables
    for k,s in summary.items():
        a,b=s['C10'],s['C2'];z=s['buy_mark_decomposition']
        lines.append(f"{k}：新买款变化{(b['buy_cash_including_fee']/a['buy_cash_including_fee']-1)*100:.2f}%，净筹资变化{(b['net_sell']/a['net_sell']-1)*100:.2f}%。原价新买资本分解：同获资股票尺寸变化{z['same_funded_stock_size_change']:,.2f}；C10独有移除{z['C10_only_removed_mark']:,.2f}；C2独有增加{z['C2_only_added_mark']:,.2f}；合计{z['total_mark_buy_change']:,.2f}。这不是损益或独立因果效应。")
    lines+=['', '取舍归因',
        'Jul3获资6→24、Jan6获资9→25，因此更低换手不是少了参与股票数。Jul3春风动力/柏楚电子因2%不足最低新单被挡，但C10本来也未给它们资金；Jan6没有额外目标整手拒绝。不能把这两点筹资下降主要解释为剔除已获资高价股。',
        'Jul3总新买款仅降约1.69%，筹资降低约9.62%，而条件曝险上升；这是缩小前排大目标后，更多后排候选与不同保护距离/旧仓保留的资源组合结果，不是固定一组订单同比例缩小。东睦股份实际新增量可由100变900，说明单次上界变小不保证每股实际量都减少。',
        'Jan6新买款降低约36.72%、筹资降低约37.83%，条件总曝险仍约90%，主要是保留更多原库存、减小原中药集中扩张，并给更多后排小额请求。它体现减少本批新买资本和集中速度的代价，不能以低换手宣布算法改进。',
        '小单不等于整账名义风险更低：Jan6 risk/条件权益反由5.21%升至5.91%，C2现金/资本仍是最紧约束，但账户风险余量明显缩小；Jul3仍约5.98%。这是保留旧仓与新候选组合改变的真实资源差异，不能把2%称为统一降风险方案。',
        '持续强势若只有一次fresh，C2不能把一股主动补至10%；固定NAV/价格且所有资源可容纳的理想8股首轮最多约16%，接近80%要约40张合法fresh分布到8股。5张凭据不是5天；被动上涨不是主动追加。昂贵最低单位仍可能永久不能首次参与，除非后来价格/NAV与原条件允许，不能靠待单续命或整手例外救它。',
        'C2不消除原供资排序会误卖旧赢家的问题，也不保证全局最小换手；保留真实旧卖责任，源账户未撤单。逐股净目标和全部原先获资股缩量、被供资旧层/行业变化均保留，不使用未来收益判断谁应被留。',
        '', '2026与已知边界',
        '本轮不计算2026容量或金额。已收到独审旧nullable分析器勘误：Apr30名单14、May7名单62，同日推进55、严格半导体C首32；旧8/61/54/31均不用于本C2结果。Jan6/Jul3冻结金融输入不受该脚本影响，金融loader未调用它。详见2026_ERRATA_BOUNDARY.txt；不重写旧归档。',
        'A只CLOSE参考不重算，本次仅C10/C2同94/29 fresh母域比较；没有新年份/日期/尺寸/压力/资金或行业门。',
        '', '结论',
        '支持：单次上界是当前高迁移强度的实质来源之一，且它会改变后排机会和行业集中；低换手并不必以较少股票名额实现。否定：2%必然更好、换手下降就是省损失、高价股筛除解释了全部差异。未知：较慢主动扩张损失的真实肥尾与减少迁移/假突破风险是否值得；需后续另行授权经济验证。']
    (O/'REPORT.txt').write_text('\n'.join(lines)+'\n');print('C2_REPORT_READY',flush=True)

if __name__=='__main__':main()
