"""Analysis-only corrections; original report/source/output remain immutable."""
from pathlib import Path
from statistics import median
from decimal import Decimal as D
import json,hashlib
O=Path(__file__).resolve().parent;P=O.parent
def main():
 a=json.loads((P/'PROTECTION_ACCEPTED_LINES.json').read_text());c=json.loads((P/'ALL_FRESH_CP1_COHORT.json').read_text());out={}
 for arm,rr in a.items():
  d=[D(r['initial_distance']) for r in rr];unfund=[r for r in c[arm] if r['C_Q'] and not r['C_actual_reserved_orders']]
  out[arm]=dict(CP_exit_responsibilities=len(rr),regular_even_sample_median_initial_distance=median(d),Q_unknown=sum(r['stock_Q'] is None for r in c[arm]),Q_false=sum(r['stock_Q'] is False for r in c[arm]),positive_plan_unreserved=len(unfund),terminal_censored=sum(r['day']=='2025-07-31' for r in unfund),within_window_unreserved=sum(r['day']<'2025-07-31' for r in unfund),unreserved_rows=[dict(sid=r['sid'],day=r['day'],Q=r['C_Q'],terminal_censored=r['day']=='2025-07-31') for r in unfund])
 (O/'CORRECTIONS.json').write_text(json.dumps(out,default=str,sort_keys=True,indent=2)+'\n')
 (O/'ERRATA.txt').write_text('原28项0799246a…包及finish.py/REPORT不改，以下仅统计/措辞勘误，无金融重跑。\n1. 偶数样本须取中间两项均值：两档常规中位数均4.1591%，非原上中位数4.6156%。correct.py复用statistics.median。\n2. 8张Q未知，不能归False；两档Q False均0。\n3. 正计划未预留C10 7=期末3+期内4；C20 6=期末1+期内5，不能全说终点删失，也不把计划当成交。\n4. Jul8全90行业第31、真实C队列第23。\n5. 铁建Jul25 E0_down_reset→Jul28 lower_anchor→Jul29新receipt期间e0_target/i_target仍1，负事件/CP1重置不等于原趋势资格失效后恢复。\n6. 原排序+资源下未获C钱已证；排序主要贡献、risk独占或放宽必赚钱均未证。\n')
 (O/'ARTIFACT_SHA256.json').write_text(json.dumps({p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in O.iterdir() if p.is_file() and p.name!='ARTIFACT_SHA256.json'},sort_keys=True,indent=2)+'\n');print(out)
if __name__=='__main__':main()
