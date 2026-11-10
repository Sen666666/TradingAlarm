import pathlib,json,csv,hashlib,datetime,collections,re
O=pathlib.Path(__file__).parent;B=O.parent
def sha(p): return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def dump(p,j): p.write_text(json.dumps(j,ensure_ascii=False,indent=2)+'\n')
def csvout(p,rows):
 with p.open('w',newline='',encoding='utf-8-sig') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
cases=json.loads((O/'CASES_DRAFT.json').read_text())
control=json.loads((O/'BATCH_CONTROL.json').read_text())
requests=[json.loads(l) for l in (O/'REQUEST_LEDGER.jsonl').read_text().splitlines()]
docs={x['number']:x for x in requests if x['kind']=='document_read'}
assert len(docs)==47 and len([r for r in requests if r['kind']=='search'])==23
assert set(docs)==set(range(1,48))
for n,d in docs.items():
 if d.get('path'):
  p=pathlib.Path(d['path']);d['verified_sha256']=sha(p);assert d['verified_sha256']==d['sha256']
  tp=next(iter((O/'texts').glob(f'{n:02d}_*.txt')),None)
  d['text_path']=str(tp) if tp else None;d['text_sha256']=sha(tp) if tp else None
  d['content_status']='HTML_SCRIPT_PLACEHOLDER_NO_ANNOUNCEMENT' if n in (14,20,22) else 'READABLE_DOCUMENT'
  if n==12:d['local_extraction_recovered']='Swift PDFKit extraction without refetch after missing Python module'
 else:d['content_status']='READ_FAILED_NO_MATERIALIZED_DOCUMENT'
dump(O/'SOURCE_MANIFEST.json',list(docs.values()))
pack=json.loads((B/'halt_evidence_batch_v1/EPISODE_PACKAGING_NOTE.json').read_text())['proposed_12_unique_episodes']
frozen={p['sid']:p for p in pack}
daily=list(csv.DictReader((B/'daily_gap_inventory_v1/DAILY_ISSUES_V2.csv').open()))
invalid=list(csv.DictReader((B/'daily_gap_inventory_v1/INVALID_EXISTING_ROW_DETAILS.csv').open()))
sessionrows=[];outrows=[]
for c in cases:
 p=frozen[c['sid']];c['episode']=p
 sd={r['day']:r['issue'] for r in daily if r['sid']==c['sid'] and p['study_start']<=r['day']<=p['study_end']}
 for r in invalid:
  if r['sid']==c['sid'] and p['study_start']<=r['day']<=p['study_end']:sd[r['day']]='EXISTING_SYNTHETIC_NONQUOTE'
 assert len(sd)==p['unusable_quote_sessions'],(c['sid'],len(sd),p)
 c['sessions']=sorted(sd);c['review_candidate_sessions']=[];c['unresolved_session_list']=[]
 for day in sorted(sd):
  rule=c['review_session_rule']
  if rule=='CONTINUOUS_STATUS_ALL_EPISODE': st='CONTINUOUS_STATUS_REVIEW_ONLY'
  elif rule=='EXPLICIT_FIXED_ALL_EPISODE':st='FIXED_INTERVAL_PRIOR_ISSUE_DATE_REVIEW_ONLY'
  elif rule=='FIRST_SESSION_ONLY' and day==p['study_start']:st='NEWS_MATCHED_START_REVIEW_ONLY'
  elif rule.startswith('PRIOR_ISSUE_CONTINUATION_FROM_') and day>=rule.split('_FROM_')[1]:st='LATE_NOTICE_FUTURE_CONTINUATION_REVIEW_ONLY'
  else:st='UNRESOLVED'
  (c['unresolved_session_list'] if st=='UNRESOLVED' else c['review_candidate_sessions']).append(day)
  sessionrows.append({'sid':c['sid'],'session':day,'source_issue':sd[day],'study_evidence_grade':c['grade'],'review_status':st,'strict_fact_clock_pair_candidate':day in c['strict_fact_clock_sessions'],'admitted':False,'economic_order_fill_proven':False,'corporate_action_bridge_admitted':False})
 c['document_refs']={str(n):{k:docs[n].get(k) for k in ['label','url','path','sha256','text_path','text_sha256','content_status']} for n in sorted(set(c.get('official_docs',[])+c.get('secondary_docs',[])+c.get('clock_docs',[])))}
 c['known_at_upper_bound']=c['clock']['value'];c['clock_basis']=c['clock']['basis'];c['actual_publication_date']=c['clock']['value'][:10]
 c['admitted_sessions']=0;c['registry_write_authorized']=False;c['bridge_release_authorized']=False
 outrows.append({'sid':c['sid'],'episode_start':p['study_start'],'episode_end':p['study_end'],'unusable_sessions':p['unusable_quote_sessions'],'grade':c['grade'],'status':c['status'],'official_fact':c.get('official_fact') or '未核到官方原文；仅二手线索','secondary_fact':c.get('secondary_fact',''),'range_semantics':c['range_semantics'],'actual_publication_date':c['actual_publication_date'],'known_at_upper_bound':c['known_at_upper_bound'],'clock_basis':c['clock_basis'],'review_candidate_sessions':';'.join(c['review_candidate_sessions']),'unresolved_sessions':';'.join(c['unresolved_session_list']),'planned_resume':c.get('planned_resume') or '未证','actual_resume_verified':c.get('actual_resume_verified') or '未证','corporate_action_boundary':c['corporate_action_boundary'],'remaining':c['remaining'],'official_urls':';'.join(docs[n]['url'] for n in c['official_docs']),'clock_urls':';'.join(docs[n]['url'] for n in c['clock_docs']),'admitted_sessions':0})
assert len(cases)==12 and sum(len(c['sessions']) for c in cases)==76
dump(O/'EPISODE_EVIDENCE.json',cases);csvout(O/'FINAL_CLASSIFICATION.csv',outrows);csvout(O/'SESSION_SUPPORT_AUDIT.csv',sessionrows)
existing=json.loads((B/'halt_evidence_batch_v1/SZSE_2022_04_SAMPLE_ROWS.json').read_text())
dump(O/'LOCAL_SOURCE_REUSE.json',{'path':str(B/'halt_evidence_batch_v1/SZSE_2022_04_SAMPLE_ROWS.json'),'sha256':sha(B/'halt_evidence_batch_v1/SZSE_2022_04_SAMPLE_ROWS.json'),'related_sids':['000552.SZ','000933.SZ'],'interpretation':'官方月表仅事件生效起点。9999未知终点；没有历史known_at。没有新增外网请求。','rows':existing})
input_checks={k:sha(B/k)==v for k,v in control['inputs'].items()}
protected=json.loads((B/'daily_gap_inventory_v1/PROTECTED_LEDGER_HASHES.json').read_text())
protected_checks={k:sha(k)==v for k,v in protected.items()}
dump(O/'PROTECTED_INPUT_CHECK.json',{'fixed_inputs':input_checks,'prior_protected_ledgers':protected_checks,'all_match':all(input_checks.values()) and all(protected_checks.values())})
now=datetime.datetime.now(datetime.timezone.utc)
created=datetime.datetime.fromisoformat(control['created_at_utc'])
readelapsed=[]
for d in docs.values():
 if 'completed_at_utc' in d:readelapsed.append((datetime.datetime.fromisoformat(d['completed_at_utc'])-datetime.datetime.fromisoformat(d['requested_at_utc'])).total_seconds())
summary={'status':'SEALED_RESEARCH_ONLY_NO_ADMISSION','fixed_episodes':12,'fixed_unusable_sessions':76,'missing_row_sessions':75,'synthetic_nonquote_sessions':1,'search_requests':23,'search_cap':24,'document_read_attempts':47,'document_cap':48,'readable_documents':sum(d['content_status']=='READABLE_DOCUMENT' for d in docs.values()),'materialized_script_placeholders':3,'failed_document_attempts_without_bytes':sum(d['content_status']=='READ_FAILED_NO_MATERIALIZED_DOCUMENT' for d in docs.values()),'python_ca_failures_included':11,'grade_counts':dict(collections.Counter(c['grade'] for c in cases)),'first_session_primary_plus_preopen_clock_candidates':3,'strict_fact_clock_candidate_sessions_before_semantic_admission':sum(r['strict_fact_clock_pair_candidate'] for r in sessionrows),'fixed_interval_prior_issue_date_candidate_sessions':6,'continuous_state_review_sessions':10,'late_notice_future_continuation_review_sessions':9,'news_start_only_review_sessions':1,'total_review_candidate_sessions_not_admitted':sum(r['review_status']!='UNRESOLVED' for r in sessionrows),'remaining_unresolved_sessions':sum(r['review_status']=='UNRESOLVED' for r in sessionrows),'registered_new_sessions':0,'economic_accounts_run':0,'private_or_paid_sources_used':False,'minute_price_data_used':False,'tls_verification_disabled':False,'created_at_utc':control['created_at_utc'],'sealed_at_utc':now.isoformat(),'wall_elapsed_seconds':(now-created).total_seconds(),'measured_fetch_elapsed_seconds_excluding_three_web_tool_failures':sum(readelapsed),'protection_all_match':all(input_checks.values()) and all(protected_checks.values()),'stop_reason':'Fixed 12-object pass completed; parent directed sealing without expanding research. 1 search and 1 document allowance left unused rather than chasing pass rate.','coverage_limit':'26 session labels are evidence review candidates including continuous/conditional state; they are not 26 proved preOPEN permissions or restored accounting sessions. 8 have direct dated-interval/start fact-plus-clock candidates, including 6 P subtype sessions. All 76 remain unregistered.'}
dump(O/'COVERAGE_AND_COST.json',summary)
readout=f"""# 固定12对象停牌证据查证：研究封存，未准入
已实际查证原冻结12对象，76个无价会话（75缺行+000552四月十一日合成无价行），未更换股票或按结果筛选。

## 核心结果
- A 1：柳工，法定全文与新浪同公告2022-03全文、原文直链和先日公开时钟配对；是连续状态语义，复牌边界未闭合。
- B 1：靖远煤电，巨潮原文与第一财经盘前摘要匹配四月十一日起点；摘要不含原文的预计期限，后续九天不自动覆盖。
- P 1：中科三环，二月十一日法定全文真实发行日可保守取当日结束上界，明确二月十六日至二十三日停止交易。这不是A类转载秒级时钟，须统一审定。
- C 4：中泰化学、首钢股份、粤水电、神火股份，已有官方部分事实/后续公告/事件起点，但初始配对或公开时钟仍缺。
- D 5：皓元医药、洪城环境、上海机场、华电能源、海南机场，所需初始官方原文未物化或仅二手/晚于OPEN；不等于资料不存在。

## 会话覆盖如何读
最直接的事实+时钟候选为8会话：三环固定区间6天、柳工初始日1天、靖远初始日1天。仍须审定，非准入。
更宽的26会话仅是待审集合：柳工连续状态10天、三环固定区间6天、靖远起点1天，以及中泰/神火后续公告公开日之后的持续状态9天；剩余50会话仍未闭合。后续公告不向前回灌，预估10天不等于已知实际10天停牌。月表9999不是无限终点。
上海机场界面新闻真实时间由HTML Unix字段解为2022-04-08 13:38:38上海，已晚于当日09:30；不能用来授权当日OPEN。海南机场的新报网全文标09:01，但官方原件未核及转载来源不足，仍D。

## 权益与订单边界
柳工现金选择权、三环配股/除权、靖远合成权益边界单列。停牌事实不释放原权益、身份或factor桥UNKNOWN，不认购、不行权、不改股数/现金。复牌真实bar只说明数据恢复，不证明历史订单成交。任何新增注册为0，经济账户运行0。

## 成本与限制
实际23搜索查询、47文档读取尝试，分别不超过24/48上限；多查询wrapper均逐条计数。47次包括11次Python本地CA失败、3次web工具访问失败、1次HTTP失败及3个HTML脚本占位，29份可读文档。系统curl保留TLS验证；没有-k或安全配置修改。
从建隔离目录到封存约{summary['wall_elapsed_seconds']/60:.1f}分钟，已计时抓取约{summary['measured_fetch_elapsed_seconds_excluding_three_web_tool_failures']:.1f}秒，另含检索、阅读与核对；不是可外推的全库成功成本。不为凑通过率花最后1搜索/1读取。
静态核对{len(input_checks)}个固定输入及{len(protected_checks)}个既有保护账文件哈希，全部一致：{summary['protection_all_match']}。

## 文件
FINAL_CLASSIFICATION.csv：12对象简表，含事实、clock_basis、known_at_upper_bound、实际发行/发布日、支持与未解会话、权益边界及来源。
EPISODE_EVIDENCE.json：完整分离的原文事实/时钟/对齐与限制。
SESSION_SUPPORT_AUDIT.csv：76会话逐日，全部admitted=false。
SOURCE_MANIFEST.json与REQUEST_LEDGER.jsonl：每请求、UTC检索时间、URL、物化路径及SHA256；反爬占位明确非公告。
COVERAGE_AND_COST.json与FINAL_SEAL.json：计数、边界与封存。
"""
(O/'READOUT.md').write_text(readout)
control.update(status='SEALED_RESEARCH_ONLY',external_research_stopped=True,sealed_at_utc=now.isoformat())
dump(O/'BATCH_CONTROL.json',control)
print(json.dumps(summary,ensure_ascii=False,indent=2))
