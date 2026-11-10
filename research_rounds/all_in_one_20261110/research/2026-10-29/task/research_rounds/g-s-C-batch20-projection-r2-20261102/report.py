"""Summaries of saved static targets, not execution or hypothetical PnL."""
from c_batch20 import *
import importlib.util,pandas as pd
spec=importlib.util.spec_from_file_location('batch20_archived_C10_metrics',CROOT/'report.py')
M=importlib.util.module_from_spec(spec);spec.loader.exec_module(M)

def main():
    names=pd.read_parquet(M.FACT/'LOCAL2026-RANKS_AND_OPPORTUNITIES.parquet',columns=['sector','industry']).drop_duplicates().set_index('sector')['industry'].to_dict()
    summary={};tables=[]
    for k,day in [('2025_26','2025-07-03'),('2022','2022-01-06')]:
        x=read(O/'inputs'/(k+'.json'));r=read(O/'results'/k/'C20.json');verify(x,r);old=read(CROOT/'results'/k/'C.json');C.verify_result(x,old)
        comp={z['sid']:z for z in x['evidence']['full_union']};ds={d['sid']:d for d in x['B_demands']};trace={z['sid']:z for z in r['trace']}
        m10=M.metrics(x,old,names);m20=M.metrics(x,r,names)
        actual=read(O.parent/'g-s-historical-native-nextsession-20261101/run'/k/'close'/(day+'-CLOSE.json'));exits=actual['account']['exits']
        rows=[]
        for d in x['B_demands']:
            sid=d['sid'];rows.append(dict(sid=sid,name=comp[sid]['name'],sector=d['sector'],industry=names[d['sector']],
                same_eligibility=True,same_stock_upper=d['max_q'],same_C_priority=r['C_rank_binding']['stock_priority'][sid]['C_key'],
                role=d['role'],pool=d['pool'],use=d['use'],canonical_receipt=d['receipt_id'],minimum=d['quantity']['buy_minimum'],
                C10_new=old['Q'][sid],C20_new=r['Q'][sid],C10_sell=old['D'].get(sid,0),C20_sell=r['D'].get(sid,0),
                C20_trace_reason=trace[sid].get('reason'),raw_joint_bounds_or_failures=trace[sid].get('blockers_or_necessary_bounds',{}),
                raw_failures_not_exclusive_opportunity_counts=True,actual_pending_sell=exits.get(sid),submit_allowed=False))
        rows.sort(key=lambda z:z['same_C_priority']);save(O/'report'/(k+'-FULL_FRESH_COMPARISON.json'),rows)
        M.csvsave(O/'report'/(k+'-FULL_FRESH_COMPARISON.csv'),[{n:json.dumps(v,ensure_ascii=False,default=str) if isinstance(v,(list,dict)) else v for n,v in z.items()} for z in rows])
        targets=[]
        for sid in sorted(set(old['mobile_targets'])|set(r['mobile_targets'])):
            targets.append(dict(sid=sid,name=comp[sid]['name'],industry=names[comp[sid]['sector']],
                C10_target=old['mobile_targets'].get(sid,0),C20_target=r['mobile_targets'].get(sid,0),
                C10_new=old['Q'].get(sid,0),C20_new=r['Q'].get(sid,0),C10_sell=old['D'].get(sid,0),C20_sell=r['D'].get(sid,0),
                original_pending_sell=sid in exits))
        M.csvsave(O/'report'/(k+'-ALL_MOBILE_TARGETS.csv'),targets)
        donor=[]
        for part in r['donors']['rows']:
            z=next(v for v in x['snapshot']['lots'] if v['id']==part['layer']);donor.append(dict(part,name=comp[z['sid']]['name'],sector=z['sector'],industry=names[z['sector']],
                qty_before=z['qty'],mark=z['mark'],actual_floor=z['floor'],role=z['role'],pool=z['pool'],purpose=z['purpose'],
                native_sellable=z['sellable_qty'],line_fraction=(D(z['mark'])-D(z['floor']))/D(z['mark']),
                same_C_priority=r['C_rank_binding']['stock_priority'][z['sid']]['C_key']))
        save(O/'report'/(k+'-C20_DONOR_LAYERS.json'),donor)
        for mode,m in [('C10',m10),('C_BATCH20',m20)]:M.csvsave(O/'report'/(k+'-'+mode+'-INDUSTRIES.csv'),m['sectors'])
        after=json.loads(r['budget_after'])['body']['batch']
        selected=[dict(sid=s,name=comp[s]['name'],q=q,C10_q=old['Q'][s],new_mark=D(ds[s]['mark'])*q) for s,q in r['Q'].items() if q]
        lost=[dict(sid=s,name=comp[s]['name'],old_q=q) for s,q in old['Q'].items() if q and not r['Q'][s]]
        conflicts=[dict(sid=s,name=comp[s]['name'],new_q=q,actual_old_exit=exits[s]) for s,q in r['Q'].items() if q and s in exits]
        summary[k]=dict(C10=m10,C_BATCH20=m20,same_fresh_mother=len(rows),same_target_qualification_priority=True,
            selected=selected,C10_funded_now_zero=lost,actual_pending_sell_conflicts=conflicts,
            budget_limit=r['batch20']['limit'],carry_before=r['batch20']['carry'],New_before=r['batch20']['already_new'],
            proposed_New_after=after['new'],budget_remaining=r['batch20']['residual'],
            planned_D_mark_gross=sum((D(z['capital']) for z in r['donors']['rows']),D(0)),
            saved_expected_net_sell=sum((D(z['net']) for z in r['donors']['orders']),D(0)),actual_sell_gross='UNKNOWN_NO_FINANCIAL_EVENTS',
            C10_recomputed=False,R1_economic_identity=read(O/'results'/k/'R1_ECONOMIC_IDENTITY.json'),
            internal_buy_sell_conflicts=[s for s,q in r['Q'].items() if q and r['D'].get(s)],
            seconds=read(O/'results'/k/'RUN.json')['seconds'],financial_events=0)
        lines=[k,'模式 | 正增量请求/同一fresh母域 | 计划毛减持 | 条件净卖款 | 买款含费 | 条件曝险 | 最大行业 | risk/条件权益']
        for mode,m in [('C10',m10),('C_BATCH20',m20)]:
            top=m['sectors'][0];lines.append(f"{mode} | {m['new_positive_requests']}/{len(rows)} | {m['sold_mark_capital']:,.2f} | {m['net_sell']:,.2f} | {m['buy_cash_including_fee']:,.2f} | {m['projected_exposure']*100:.2f}% | {top['industry']} {top['projected_NAV_weight']*100:.2f}% | {m['account_risk_fraction']*100:.2f}%")
        lines+=['C_BATCH20 Carry='+str(r['batch20']['carry'])+'，批前New='+str(r['batch20']['already_new'])+'，拟批New='+after['new']+'，上限='+r['batch20']['limit']+'，余量='+r['batch20']['residual']+'。实际卖出毛额/结算均未知。',
            '原价买+卖换手/决策NAV：C10 '+str(round(m10['turnover_mark_over_decision_NAV']*100,2))+'% → C_BATCH20 '+str(round(m20['turnover_mark_over_decision_NAV']*100,2))+'%。',
            '正增量：'+','.join(z['name']+' '+str(z['q'])+'(原C10 '+str(z['C10_q'])+')' for z in selected),
            '原C10获资而本档为0：'+','.join(z['name'] for z in lost),
            '各原限制最小余量：'+'; '.join(n+' '+str(z['residual'])+' ['+z['stage']+']' for n,z in m20['minimum_constraint_residuals'].items()),
            '真实旧卖同股冲突：'+(','.join(z['name'] for z in conflicts) or '未见新增买入同股')+'；真实原9/16单未撤，本结果不可提交。','']
        tables+=lines
    save(O/'report/SUMMARY.json',summary)
    lines=['C_BATCH20 R2：整批机会性计划毛减持限20%，C10目标/排序/联合约束保持。',
        '20/20合成通过（预算状态镜像组件+原生费率/数量/联合资源算术，未安装原生账户回调）。两真实快照只是纯条件目标，不是订单/实际成交/收益；没有创建金融账户或推进事件。',
        '原C10归档只读。Carry=0只对应已核pre-A请求前分支；真实post-A的9/16单全部同close筹资责任，不等于现实已撤。只读分支不能装回账户。']+tables
    lines+=['解释与不利行为',
        '单股10%上界保持，首排完整新买目标仍可得到大额资本；没有C2式每票2%。批次资本腾挪变慢后，后排合格机会可能完全失资，而非所有股票均匀缩小。原资格/整手上界并未改变，归零是联立资源/新整批预算/先后状态的结果；原始计数不是独立或独占拒因。',
        'Jul3仍把北方铜业4200股列为供资，与C10相同；总腾挪减少不保证保住这只原健康旧股，也没改变弱者先供资会误卖整理赢家的假说。完整供资层/所有新旧目标已列出，不能只报降换手。',
        '计划减持上限约19.96万元不等于新买上限：已有超现金底线的真实资金也能投入，所以本批买款可超过20%。同时旧仓保留更多，条件总曝险可能高于大腾挪的C10；不能将此档自动称降风险。',
        '空仓合成中G与成熟S的原目标分别接近89.1%/79.2%，D=0，不被此20%压慢；仅是费用/数量/资源可行目标，不证明开盘真实可成交。',
        '', '资金到位速度反例',
        '若90%旧仓健康、10%已是现金底线，新主线8合法股同时fresh且旧/新风险均可容纳：C10可争取本批换入约80%，本档首批只能以约20%原价旧资本筹资（费用/风险还会减量）。若主升极速完成且之后不再出现新fresh，本档可能长期只有初批参与；不说4天自动80%，不把被动价格上涨当追加。反之假突破可少迁移但旧90%也可能继续亏，本上限不是DD保证。',
        '', '修复与验证边界',
        'R1保留两项真实预算组件入口反例：未来成交观察后开启更早批次会少算carry；非正价格可形成负carry。R2加入观察时间单调、非正价格/ratio与非整数股数拒绝、相同观察ID不能改payload。无新参数/经济规则。两快照未使用这些观察接口且价格合法，R2八个经济对象（Q/D/targets/donors/validation/batch20/trace/checks）规范化摘要与R1完全一致。',
        'R2首次出口把内存Decimal与归档字符串直接比较导致中断；失败原稿保留，模型未改。规范化比较恢复时先存计算结果再核同，只恢复静态输出，不隐瞒金融重跑。',
        '预算book的部分fill/split/cancel接口只消费显式观察fixture，不生成成交账；原生回调接线、实际live或长历史尚未验收，也没有授权。跨进程状态测试含成交/撤ACK后New不返还及外部commitment核对；不冒称已证明实际native provider。',
        '', '结论',
        '支持：整批节奏上限可保留大额单股目标/空仓部署能力，同时显著限制一次换走健康旧仓。代价：本批后排机会和快速行业资本到位受损，旧错误仓位也可能保留更久，实际收益取舍未知。不改20%、不加新门、不扫描参数，不据降低计划换手晋升。待独审后再决定下一步。']
    (O/'REPORT.txt').write_text('\n'.join(lines)+'\n');print('REPORT_READY',flush=True)

if __name__=='__main__':main()
