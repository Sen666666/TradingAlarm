"""Completed-date saved-output checks only; no model/account imports or calls."""
from pathlib import Path
import hashlib,json,datetime,argparse
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parent;ENTRY=ROOT.parent

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n')

def main(day):
 out=ROOT/day/'signals';assert not(out/'SEAL.json').exists()
 freeze=json.loads((out/'FREEZE.json').read_text());completion=json.loads((out/'COMPLETION.json').read_text())
 raw=out/'ALL_SIGNALS.parquet';rawhash=sha(raw);assert rawhash==completion['all_signals_sha256']
 feature_path=ENTRY/'local_observable_selection_v1/features/LOCAL_FIXED_DATE_FEATURES.parquet'
 assert sha(feature_path)==freeze['features_sha256']
 feature=pd.read_parquet(feature_path);feature=feature.loc[feature.day.eq(day)].set_index('sid')
 f=pd.read_parquet(raw);assert len(f)==f.sid.nunique()==5517 and set(f.sid)==set(feature.index)
 exact=f.signal_status.eq('EXACT_TARGET_STOCK_SIGNAL');missing=f.signal_status.eq('MISSING_TARGET_BAR')
 assert f.day.eq(day).all()and f.prefix_end_day.dropna().le(day).all()
 assert f.loc[exact,'prefix_end_day'].eq(day).all()and f.loc[exact,'target_source_row_present'].eq(True).all()
 actual=f.loc[exact].set_index('sid').sort_index()
 assert np.array_equal(actual.close.to_numpy(float).view(np.uint64),feature.loc[actual.index,'current_close_qfq'].to_numpy(float).view(np.uint64))
 assert set(f.loc[missing,'sid'])==set(feature.loc[feature.target_row_present.eq(False)].index)
 for p,h in freeze['original_algorithm_code_sha256'].items():assert sha(p)==h
 e0=exact&f.e0_ready.eq(1);knownfresh=e0&f.g_ready.eq(True)
 hold_true=e0&f.i_target.eq(1);fresh_true=knownfresh&f.i_target.eq(1)&f.i_buy.eq(True)
 check=dict(day=day,rows=5517,status_counts=f.signal_status.value_counts().to_dict(),
    same_source_exact_close_bitexact_count=int(exact.sum()),missing_ID_set_matches_saved_source=True,
    every_prefix_not_after_day=True,every_exact_prefix_ends_on_day=True,original_code_SHA_unchanged=True,
    controls=json.loads((out/'CONTROL_EQUALITY.json').read_text()),
    raw_ready=int(e0.sum()),raw_i_target_true=int((exact&f.i_target.eq(1)).sum()),raw_i_buy_true=int((exact&f.i_buy.eq(True)).sum()),
    interpreted_hold=dict(true=int(hold_true.sum()),false=int((e0&~f.i_target.eq(1)).sum()),unknown=int((~e0).sum())),
    interpreted_fresh=dict(true=int(fresh_true.sum()),false=int((knownfresh&~fresh_true).sum()),unknown=int((~knownfresh).sum())),
    stock_only_not_full_S0=True,no_accounts=True,no_new_model_calls=True,
    raw_table_and_COMPLETION_unchanged=True,raw_sha256=rawhash)
 timing_text=f"full批次墙钟{completion['full_batch_wall_seconds']/60:.3f}分钟"
 if(out/'RESUME_RECEIPT.json').exists():
  resume=json.loads((out/'RESUME_RECEIPT.json').read_text());old_ids=set()
  for item in resume['old_part_index']:
   assert sha(item['path'])==item['sha256'],'Old durable part changed during resume'
   old_ids.update(item['symbols'])
  records=[json.loads(s)for p in sorted((out/'full').glob('*.jsonl'))for s in p.read_text().splitlines()]
  assert len(records)==len({r['sid']for r in records})
  initial=datetime.datetime.fromisoformat(resume['initial_block_plan_mtime_UTC']).timestamp()
  finish=(out/'COMPLETION.json').stat().st_mtime
  timing=dict(initial_session=resume['initial_session'],resumed_session=resume['resumed_session'],
    first_observed_write_span_seconds=resume['old_part_write_span_seconds'],
    last_old_write_to_resume_transition_seconds=resume['transition_span_last_old_write_to_resume_seconds'],
    initial_exact_termination_time='UNKNOWN; see RESUME_RECEIPT',
    resumed_invocation_wall_seconds=completion['full_batch_wall_seconds'],
    end_to_end_wall_including_interruption_seconds=finish-initial,
    completed_model_CPU_seconds_first_segment=sum(r.get('model_cpu_seconds',0)for r in records if r['sid']in old_ids),
    completed_model_CPU_seconds_resumed_segment=sum(r.get('model_cpu_seconds',0)for r in records if r['sid']not in old_ids),
    completed_model_CPU_seconds_total=sum(r.get('model_cpu_seconds',0)for r in records),
    CPU_seconds_are_core_seconds_not_parallel_elapsed_time=True,
    lost_inflight_model_CPU_and_exact_total_active_wall_not_recoverable=True,
    old_parts_hashes_unchanged=True,old_complete_ids_never_recomputed=True,
    end_to_end_origin='initial full/BLOCK_PLAN mtime to final COMPLETION mtime; includes pause and invocation overhead')
  save(out/'SEGMENT_TIMING.json',timing);check['segment_timing']=timing
  timing_text=(f"续跑调用墙钟{completion['full_batch_wall_seconds']/60:.3f}分钟（不是全日期耗时）；"
      f"首段可观测写入跨度{resume['old_part_write_span_seconds']/60:.3f}分钟，"
      f"含中断的全程墙钟{(finish-initial)/60:.3f}分钟。首段精确终止时刻未知，分段已完成模型CPU秒与过渡时间另存SEGMENT_TIMING.json")
 save(out/'SAVED_OUTPUT_CHECK.json',check)
 text=f'''# {day} 同scope全本地原信号

已完成5517个唯一请求。状态为{check['status_counts']}，{timing_text}。复用当日target42 exact {completion['reuse_count']}股；三只控制的19个原字段全部精确相同。12worker按约24股块运行，每股完成即JSONL flush+fsync，missing不调用模型，error不写False，已完成ID不自动重跑。

正式入口ALL_SIGNALS.parquet和COMPLETION.json未被后处理改写。全{int(exact.sum())}条exact收盘与冻结同源特征逐bit一致；missing证券集合与源观察元数据精确一致；每个前缀不晚于本日期，每条exact前缀正好止于本日期。原算法源码SHA未变。

原E0/I/G/numeric的19字段和来源原样保留。仅作知识状态解释：hold在exact且E0 ready后读I，fresh另要求G ready后读I且i_buy；本日hold为{check['interpreted_hold']}，fresh为{check['interpreted_fresh']}。未成熟/缺行情保UNKNOWN，不能把初始状态0当已知不合格；raw helper只是便利列，正式根合并独立生成三态解释。没有修改raw i_buy或保护线。

本wrapper只把immutable旧worker代码的DAY/HERE参数化；未执行924日期，未修改原stock_signal或原公式。全价源实际SHA仍11e7f9e38798e6e411f33b3250c564bcd5fcfbe34af2bda74e04c02cf8d08d9b。5517是现存canonical本地母体，不是认证历史全证券池；qfq参考/历史available_at、ST停牌和可成交性未认证。缺行不推断上市退市。这里只是stock-only E0/G1_I，不含CP、行业/市场/资金资格、订单、成本或账户收益。
'''
 (out/'READOUT.md').write_text(text)
 assert sha(raw)==rawhash
 files={str(p):sha(p)for p in sorted(out.rglob('*'))if p.is_file()and p.name!='SEAL.json'}
 save(out/'SEAL.json',dict(status='SEALED_COMPLETE_RAW_UNCHANGED',sealed_at_UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),files_sha256=files))
 print(json.dumps(dict(day=day,raw_sha256=rawhash,completion_sha256=sha(out/'COMPLETION.json'),seal_sha256=sha(out/'SEAL.json'),checks=check),ensure_ascii=False),flush=True)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('day',choices=['2022-01-24','2026-01-15']);main(p.parse_args().day)
