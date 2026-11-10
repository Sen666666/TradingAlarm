from pathlib import Path
import json,pandas as pd,hashlib
O=Path(__file__).parent
m=pd.read_csv(O/'MANUAL_CYCLES.csv')
lines=['原29行业中12个医药金融消费行业补审','90候选→73人工主周期；40旧记录全部对账。17重点中：5完全遗漏新增、2旧非重点延伸上调、10原重点保留或合并。不是17个新发现。','所有广度仅为2026静态1709大市值存续池NON-PIT，成员K、P、F与路径缺失分别列出。']
for r in m.itertuples():
 old=r.old_manual_ids if pd.notna(r.old_manual_ids) else '无'
 lines += [f'\n{r.record_id} {r.name} {r.start}→{r.end} {r.priority}，与旧表关系：{r.new_priority_class}；旧记录{old}。',f'行业{r.industry_return_pct:+.2f}%，途中回撤{r.mdd_pct:.2f}%；成员{r.positive_members}/{r.known_members}/{r.research_pool_members}/{r.current_all_members}，中位{r.member_median_pct:+.2f}%，前三正收益占{r.top3_positive_share_pct:.2f}%。',r.note]
(O/'READOUT.txt').write_text('\n'.join(lines)+'\n')
files=[p for p in O.iterdir() if p.is_file() and p.suffix in ['.csv','.json','.py','.txt'] and p.name!='OUTPUT_SEAL.json']
(O/'OUTPUT_SEAL.json').write_text(json.dumps({p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in files},ensure_ascii=False,indent=2)+'\n')
print('ready')
