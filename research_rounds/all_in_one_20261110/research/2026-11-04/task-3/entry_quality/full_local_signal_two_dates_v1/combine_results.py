"""Read sealed per-date summaries only; never recomputes924 or any model."""
from pathlib import Path
import json,hashlib
import pandas as pd

ROOT=Path(__file__).resolve().parent;ENTRY=ROOT.parent


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def pct(v):return 'NA'if pd.isna(v)else f'{float(v)*100:.2f}%'


def main():
    sources={'2022-01-24':ROOT/'2022-01-24','2024-09-24':ENTRY/'pvr_924_discrimination_v1','2026-01-15':ROOT/'2026-01-15'}
    rows=[];inputs={};counts=[]
    for day,b in sources.items():
        f=b/'GROUP_SUMMARIES.csv';p=b/'PRIOR_RANKS_RECEIPT.json';d=pd.read_csv(f);prior=json.loads(p.read_text())
        index=json.loads((b/'FINAL_OUTPUT_SHA256.json').read_text())if(b/'FINAL_OUTPUT_SHA256.json').exists()else None
        if index:assert sha(f)==index['files']['GROUP_SUMMARIES.csv'],('sealed summary changed',day)
        inputs[day]={'summary_path':str(f),'summary_sha256':sha(f),'prior_sha256':sha(p),'read_only_924_reference':day=='2024-09-24'}
        if 'scopes'in prior:
            signalN=prior['N'];rankN=prior['scopes']['ALL']['rankable_N'];unknown=signalN-rankN
        else:signalN=rankN=prior['N'];unknown=0
        counts.append(dict(day=day,signal_i_buy_N=signalN,rankable_N=rankN,PVR_unknown_N=unknown))
        z=d.loc[d.view.eq('WITHIN_SCOPE_RANKS')&d.scope.eq('ALL')]
        for h in [5,20]:
            for k in [20,100]:
                top=z.loc[z.horizon.eq(h)&z.band.eq('TOP'+str(k))].iloc[0]
                rest=z.loc[z.horizon.eq(h)&z.band.eq('REST'+str(k))].iloc[0]
                rows.append(dict(day=day,horizon=h,top_k=k,signal_i_buy_N=signalN,rankable_N=rankN,PVR_unknown_N=unknown,
                    top_N=int(top.prior_N),top_complete_N=int(top.complete_N),rest_ranked_N=int(rest.prior_N),rest_complete_N=int(rest.complete_N),
                    terminal_mean_top=top.terminal_mean,terminal_mean_rest=rest.terminal_mean,terminal_mean_lift=top.terminal_mean-rest.terminal_mean,
                    terminal_median_top=top.terminal_median,terminal_median_rest=rest.terminal_median,terminal_median_lift=top.terminal_median-rest.terminal_median,
                    MFE_mean_top=top.MFE_mean,MFE_mean_rest=rest.MFE_mean,
                    MAE_signed_mean_top=top.MAE_signed_mean,MAE_signed_mean_rest=rest.MAE_signed_mean,
                    top_positive_rate=top.terminal_positive_rate_complete,rest_positive_rate=rest.terminal_positive_rate_complete,
                    ex_post_top1pct_hits=int(top.EXPOST_TOP1PCT_hits),ex_post_top1pct_global_complete_N=int(top.EXPOST_TOP1PCT_global_N),
                    top_common_endpoint_N=int(top.common_endpoint_N),top_common_endpoint_terminal_mean=top.common_endpoint_terminal_mean,
                    rest_common_endpoint_N=int(rest.common_endpoint_N),rest_common_endpoint_terminal_mean=rest.common_endpoint_terminal_mean))
    out=pd.DataFrame(rows);out.to_csv(ROOT/'CROSS_DATE_TOP_REST.csv',index=False)
    pd.DataFrame(counts).to_csv(ROOT/'CROSS_DATE_DENOMINATORS.csv',index=False)
    table=['|日期|有效观察|比较|i_buy/可排名|前列N/其余N|前列末端均值|其余末端均值|均值差|前列中位数/其余|',
           '|---|---:|---|---:|---:|---:|---:|---:|---:|']
    for _,r in out.iterrows():
        table.append(f'|{r.day}|{r.horizon}|前{r.top_k}|{r.signal_i_buy_N}/{r.rankable_N}|{r.top_N}/{r.rest_ranked_N}|{pct(r.terminal_mean_top)}|{pct(r.terminal_mean_rest)}|{pct(r.terminal_mean_lift)}|{pct(r.terminal_median_top)}/{pct(r.terminal_median_rest)}|')
    text='''# 固定两日期执行结果与924只读对照

完成用户预定2022-01-24和2026-01-15的全本地原E0/G1/I及原PVR诊断。两个日期按相同源码/数据/排名/5与20有效观察定义执行，未因结果改日期、得分、权重、阈值或尾部标签。924仅读取此前封存统计，未重跑模型、路径或账户。

下表各日期分别评价，不合并股日为独立账户/样本，不计算池化显著性。末端/MFE/MAE均为信号日收盘锚定的价格变化；不能买到收盘/开盘或卖在MFE的假设不存在。MAE是相对锚最低收盘，不是峰谷回撤。

'''+ '\n'.join(table)+'''

“其余”仅为其余有原PVR排名的候选；未知PVR成员始终在完整i_buy分母和单独桶中，不造最差排名、不按后续输赢补位。旧名单/池外的全部分组及自然终点延后、源尾/缺行原因见各日期文件；空组为NA，Top100只取现有rankable人数。

本地5517仍有供应商/幸存者、历史截断和代码别名局限；239退市档案未在单位/复权未统一时混入。历史上市/ST/停牌/限价/真实发布时间与执行资格UNKNOWN；qfq版本及时间可用性非PIT。5/20有效个股观察可能跨缺行而延后，不等于相同市场持有期。三个历史日期已经被消费，不称真正样本外，不从其中选择更好参数。

日期文件：[2022完整报告](2022-01-24/READOUT.md)、[2026完整报告](2026-01-15/READOUT.md)。逐股价路、完整5517信号、十分位、前20/100与旧池/池外均保留；独审分别落在日期目录。
'''
    (ROOT/'COMPARISON_READOUT.md').write_text(text)
    (ROOT/'CROSS_DATE_READONLY_RECEIPT.json').write_text(json.dumps(dict(status='DESCRIPTIVE_FIXED_DATE_COMPARISON_NO_POOLED_ACCOUNT_OR_RERUN',inputs=inputs,new_model_or_account_calls=0,no_parameter_change=True),ensure_ascii=False,indent=2)+'\n')
    print(out[['day','horizon','top_k','signal_i_buy_N','rankable_N','terminal_mean_top','terminal_mean_rest','terminal_mean_lift']].to_string(index=False))


if __name__=='__main__':main()
