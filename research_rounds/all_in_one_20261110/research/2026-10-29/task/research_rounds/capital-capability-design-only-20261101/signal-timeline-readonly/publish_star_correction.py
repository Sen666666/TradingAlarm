"""Analysis-report correction only; preserves bad reports and financial sources."""
from pathlib import Path
import json,hashlib
O=Path(__file__).resolve().parent;A=O/'errata-star-new-order-minimum-v1'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def save(p,x):
 q=p.with_name(p.name+'.tmp');q.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n');q.replace(p)
def main():
 old=read(A/'TIMELINES.json');new=read(O/'TIMELINES.json');audit=read(O/'independent-review/AUDIT.json');by={r['name']:r for r in new}
 checked=0
 for expected in audit['capacities']:
  r=by[expected['name']];v='capacity_original_Q_subset' if expected['qonly'] else 'capacity_raw_CP1'
  for threshold,e in expected['minimum_each_new_order'].items():
   a=r[v]['first_reaches'][threshold]
   if e is None:assert a is None
   else:assert (a['signal_close'],a['next_observed_session'],a['context'],a['units'])==(e['signal_close'],e['next'],e['context'],e['units']),(r['name'],v,threshold,a,e)
   checked+=1
 # All eight2023 first-date cells unchanged, regardless of raw/Q view.
 for before,after in zip(old,new):
  assert before['node']==after['node']
  if not before['lo'].startswith('2023'):continue
  for v in ['capacity_raw_CP1','capacity_original_Q_subset']:
   for k,b in before[v]['first_reaches'].items():
    a=after[v]['first_reaches'][k]
    assert (a['next_observed_session'] if a else None)==(b['next_observed_session'] if b else None)
 s=(A/'READOUT.txt').read_text()
 s=s.replace('2026-04-23 / 2026-04-30 / 2026-05-08','2026-04-23 / 2026-05-06 / 2026-05-12')
 wrong='Q名额80%乐观窗5/8，不是此前临时按每次都要200股算出的5/12。688首次200股与已有仓step1已分开。'
 assert wrong in s
 s=s.replace(wrong,'修正后Q名额50%乐观窗5/6、80%窗5/12。此前5/8误将已有持仓视为可另开1股新单；STAR每张新CP1单仍最低200，step1只是在200以上递增。同一原单部分成交余量另论，不能视为新凭据名额。')
 s=s.replace('最多一股可有成熟前2%小试（可令其后STAR追加step1合法）','最多一股可有成熟前2%小试（不改变其后新CP1订单最低量）')
 s=s.replace('原Q还含旧行业门，故不是新F1合同完整股票Q；raw也非全部合法候选。','原Q还含旧行业门，故仅是原口径限制性参考子集，不代表新F1资格全体；raw也非全部合法候选。')
 s+='\n独审实质纠正：半导体5/11累计乐观名额由45修正44，80%窗口仍5/12；化学品50%窗口4/30→5/6、80%窗口5/8→5/12；2023八行业日期不变。\n逐日选择最有利的初始试仓，是可随日期改变选择的点态乐观包络，不是一条固定、可执行的资金计划。原Q子集不代表新F1资格全体。旧稿和原错误ANALYSIS_ERRATA.json均保留，见errata-star-new-order-minimum-v1；错误说明本身也已被本次更正。未改账户、指标或行情。\n'
 (O/'READOUT.txt').write_text(s)
 p=(A/'PROTOCOL.txt').read_text()
 p=p.replace('最低100/688首次200股','最低100/STAR每张新单200股')
 p=p.replace('688追加step=1；本分析按完全无持仓首次单位起点，不开R1。','STAR新单最低200，200以上按1股递增；已有仓位不令下一新单最低1股。同一原单部分成交余量可小于200；这不是新canonical CP1订单，本分析不计为新名额，不开R1。')
 p=p.replace('同时区分该股已有仓后STAR可step1追加的路径','所有随后新CP1仍检查同样的200股最低值')
 p=p.replace('是拟替代股票侧Q的保守子集','仅是原口径限制性参考子集，非新F1资格全体')
 p+='\n本次修正：每张新CP1均为新单，即使已持股仍须STAR最低200；step1不是新单最低1。逐日挑最有利初始试仓只是点态乐观包络，不能把各日期的不同选择串成一条固定执行计划。原冻结范围及旧错误协议/报告见归档，不伪称本次更正事前已知。\n'
 (O/'PROTOCOL.txt').write_text(p)
 checks=read(A/'READONLY_CHECKS.json');checks.pop('stock_STAR_initial200_vs_addstep1',None);checks['STAR_new_order_minimum_200_regardless_of_holdings']=True;checks['partial_same_original_order_remainder']='fill_step applies only to partially filled original order, not fresh CP1/new order';checks['independent_correction_cells_exact']=checked;checks['order_minimum_regression']=read(O/'ORDER_MINIMUM_REGRESSION.json');save(O/'READONLY_CHECKS.json',checks)
 correction=dict(status='analysis correction complete, independent re-review ready',new_STAR_order_minimum=200,new_order_minimum_unchanged_by_existing_position=True,fill_step_meaning='1-share increments at/above200 for new STAR orders; same-order partial remainder separately may be below200',changes={'electronic_chemicals_50_next_window':['2026-04-30','2026-05-06'],'electronic_chemicals_80_next_window':['2026-05-08','2026-05-12'],'semiconductor_80_next_window':['2026-05-12','2026-05-12'],'semiconductor_May11_units':[45,44]},year2023_eight_nodes_dates_unchanged=True,independent_reference_cells_exact=checked,original_errata_preserved_sha256=sha(O/'ANALYSIS_ERRATA.json'),original_errata_archive_sha256=sha(A/'ANALYSIS_ERRATA.json'),original_scope_freeze_unchanged=sha(O/'SCOPE_FREEZE.json')==sha(A/'SCOPE_FREEZE.json'),source_and_account_modified=False,financial_runs=0,new_indicator_runs=0,scope_warning='pointwise optimistic envelope, not one fixed executable plan; original Q subset not complete new F1 eligibility')
 assert correction['original_errata_preserved_sha256']==correction['original_errata_archive_sha256'];assert correction['original_scope_freeze_unchanged']
 prior_scope=read(A/'SCOPE_FREEZE.json');assert sha(A/'PROTOCOL.txt')==prior_scope['clarified_protocol_sha256']
 correction['historical_scope_protocol_binding']=dict(path=str(A/'PROTOCOL.txt'),sha256=sha(A/'PROTOCOL.txt'),old_scope_is_historical_not_rewritten=True)
 correction['current_analysis_binding']=dict(analyzer_sha256=sha(O/'analyze.py'),protocol_sha256=sha(O/'PROTOCOL.txt'),report_sha256=sha(O/'READOUT.txt'))
 save(O/'STAR_NEW_ORDER_CORRECTION.json',correction)
 source=read(O/'SOURCE_SHA256.json')
 for q,h in read(A/'SOURCE_SHA256.json').items():
  if not Path(q).resolve().is_relative_to(O):assert sha(q)==h,('changed external input/source',q);source[q]=h
 for q in [O/'analyze.py',O/'PROTOCOL.txt',O/'test_order_minimum.py',Path(__file__),O/'independent-review/AUDIT.json']:source[str(q)]=sha(q)
 save(O/'SOURCE_SHA256.json',source)
 artifacts={str(q):sha(q) for q in O.iterdir() if q.is_file() and q.name!='ARTIFACT_SHA256.json'};artifacts[str(A/'ARCHIVE_MANIFEST.json')]=sha(A/'ARCHIVE_MANIFEST.json');artifacts[str(O/'independent-review/AUDIT.json')]=sha(O/'independent-review/AUDIT.json');save(O/'ARTIFACT_SHA256.json',artifacts)
 print(json.dumps(dict(regression=correction['independent_reference_cells_exact'],analyzer_sha256=sha(O/'analyze.py'),report_sha256=sha(O/'READOUT.txt'),tests=read(O/'ORDER_MINIMUM_REGRESSION.json')),ensure_ascii=False,indent=2))
if __name__=='__main__':main()
