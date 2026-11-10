"""Post-run requested stock cases. Saved ledgers only, never a consumer."""
import argparse,json
from pathlib import Path
import pandas as pd
from runtime import O,R,SOURCE,sha,read
from run_economic import save,clean
NAMES={'300229.SZ':'拓尔思','300607.SZ':'拓斯达','300024.SZ':'机器人','002241.SZ':'歌尔股份'}

def build(window):
    folder=O/('report_'+window)
    report=read(folder/'COMPARISON_REPORT.json')
    for n,h in read(folder/'OUTPUT_SHA256.json').items():assert sha(folder/n)==h
    stock={(r['sid'],r['arm']):r for r in report['stock_rows']}
    lanes={(r['sid'],r['arm'],r['lane']):r for r in report['lane_rows']}
    diffs={r['sid']:r for r in report['differences']}
    old=pd.read_csv(SOURCE/('economic_'+window)/'joint/ROUNDS.csv',float_precision='round_trip').to_dict('records')
    new=pd.read_csv(O/('dmi_'+window)/'joint/ROUNDS.csv',float_precision='round_trip').to_dict('records')
    rounds=pd.read_csv(folder/'ALL_ROUNDS.csv',float_precision='round_trip').to_dict('records')
    entered={(r['arm'],r['round_id']) for r in rounds if r['entered'] is True}
    participants=pd.read_csv(folder/'ALL_STOCK_PARTICIPATION.csv').set_index(['sid','arm']).to_dict('index')
    changes=read(folder/'REQUEST_DISPLACEMENT.json')
    roster=pd.read_csv(R/'pvr_persistence_breadth_v1/FIXED_MEMBERSHIP.csv').set_index('sid').name.to_dict()
    def row(r):
        return {k:r.get(k) for k in ['round_id','event_id','owner_lane','signal_day','entry_day','exit_day','status_day','status','entry_q','added_q','net_pnl','last_known_mark_day','last_mark_net','cash_after_payouts','receivable_after_payouts','dividend_net80_total']}
    def case(sid):
        paths={arm:[row(r) for r in native if r['sid']==sid and (arm,r['round_id']) in entered] for arm,native in [('baseline',old),('joint',new)]}
        new_ids={r['event_id'] for r in paths['joint']};lost=[]
        for r in paths['baseline']:
            if r['event_id'] in new_ids:continue
            later=sorted([n for n in paths['joint'] if str(n['entry_day'])>str(r['entry_day'])],key=lambda n:str(n['entry_day']))
            lost.append(dict(old_entered_event=r['event_id'],old_lane=r['owner_lane'],old_entry_day=r['entry_day'],old_closed_net=r['net_pnl'],subsequent_new_participation=later[0] if later else None,meaning='Observed later actual conditional entry, not proof that the original opportunity was recovered'))
        return dict(sid=sid,name=roster.get(sid,NAMES.get(sid)),difference=diffs[sid],old_stock=stock[sid,'baseline'],new_stock=stock[sid,'joint'],old_participation=participants[sid,'baseline'],new_participation=participants[sid,'joint'],lane_values={arm:{lane:dict(net=lanes[sid,arm,lane]['known_total_pnl'],status=lanes[sid,arm,lane]['status'],financial_covered=lanes[sid,arm,lane]['financial_covered']) for lane in ['AB','PRICE']} for arm in ['baseline','joint']},actual_entered_paths=paths,old_entered_events_not_retained=lost,request_changes=[c for c in changes if c['sid']==sid],unknown_total_not_replaced_by_closed_subset=True)
    common=[r for r in report['differences'] if r['common_covered']]
    improving=sorted([r for r in common if r['joint_minus_baseline']>0],key=lambda r:(-r['joint_minus_baseline'],r['sid']))[:5]
    worsening=sorted([r for r in common if r['joint_minus_baseline']<0],key=lambda r:(r['joint_minus_baseline'],r['sid']))[:5]
    out=dict(window=window,cohort='COMMON_COMPARABLE_STOCKS_FOR_TOP5; NAMED_CASES_KEEP_UNKNOWN',improved_top5=[case(r['sid']) for r in improving],worsened_top5=[case(r['sid']) for r in worsening],named_cases=[case(s) for s in NAMES],source_sha256={str(p):sha(p) for p in [folder/'COMPARISON_REPORT.json',folder/'ALL_ROUNDS.csv',folder/'ALL_STOCK_PARTICIPATION.csv',folder/'REQUEST_DISPLACEMENT.json']},script_sha256=sha(__file__),new_economic_runs=0,static_outcome_labels_used=False)
    save(folder/'REQUESTED_STOCK_CASES.json',out)
    lines=[f'# {window} 动态逐股后验病例','', '金额均为条件逐股代理净额，不是共享现金账户收益。UNKNOWN总额不以闭合子集补零。','']
    for title,key in [('共同可比改善前5','improved_top5'),('共同可比恶化前5','worsened_top5'),('指定股票实际动态结果','named_cases')]:
        lines+=['## '+title,'']
        for c in out[key]:
            b,j=c['old_stock'],c['new_stock'];d=c['difference'];bp,jp=c['old_participation'],c['new_participation']
            fmt=lambda x:'UNKNOWN' if x is None else f'{x:,.2f}'
            lines.append(f"- {c['name']} {c['sid']}：净额 {fmt(b['known_total_pnl'])} → {fmt(j['known_total_pnl'])}，差 {fmt(d['joint_minus_baseline'])}；实际进入轮数 {bp['entered_rounds']} → {jp['entered_rounds']}；AB差 {fmt(d['lane_contributions']['AB'])}，PRICE差 {fmt(d['lane_contributions']['PRICE'])}；共同可比={d['common_covered']}。")
            for arm,label in [('baseline','旧PVR'),('joint','新DMI')]:
                values=[f"{r['owner_lane']} {str(r['entry_day'])[:10]}→{str(r['exit_day'])[:10] if pd.notna(r['exit_day']) else r['status']}" for r in c['actual_entered_paths'][arm]]
                lines.append('  - '+label+'真实进入：'+('；'.join(values) if values else '未进入'))
            lost=c['old_entered_events_not_retained']
            if lost:lines.append('  - 旧进入事件未保留 '+str(len(lost))+' 个，其中可观察到之后新轮再次参与 '+str(sum(r['subsequent_new_participation'] is not None for r in lost))+' 个；这不等于原机会已挽回。')
        lines.append('')
    (folder/'REQUESTED_STOCK_CASES.md').write_text('\n'.join(lines),encoding='utf-8')
    save(folder/'CASE_OUTPUT_SHA256.json',{n:sha(folder/n) for n in ['REQUESTED_STOCK_CASES.json','REQUESTED_STOCK_CASES.md']})
    print('SAVED_CASES_READY',window,flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--window',choices=['2022','2024'],required=True);build(p.parse_args().window)
