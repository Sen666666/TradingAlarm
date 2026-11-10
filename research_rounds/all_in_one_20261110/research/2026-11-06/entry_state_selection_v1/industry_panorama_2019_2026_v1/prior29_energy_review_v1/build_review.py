import pathlib,json,hashlib,collections,pandas as pd,numpy as np
O=pathlib.Path(__file__).parent;P=O.parent
U=pathlib.Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031');B=pathlib.Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024');END=pd.Timestamp('2026-10-22')
a=pd.read_csv(O/'AUXILIARY_67_INPUT.csv').set_index('record_id');old=pd.read_csv(O/'OLD_MANUAL_28_INPUT.csv');src=json.loads((O/'SOURCE_HASHES.json').read_text());rows=[]
KEY='重点肥尾候选';NORMAL='普通或次级波段';LIMIT='证据不足'
def add(ids,priority,note,boundary,start=None,end=None):
 ids=ids.split();x=a.loc[ids[0]];y=a.loc[ids[-1]]
 assert len(set(a.loc[ids].sector))==1
 rows.append(dict(record_id=f'E{len(rows)+1:03d}',sector=x.sector,name=x['name'],start=start or x.start,end=end or y.end,priority=priority,note=note,boundary_reason=boundary,auxiliary_ids=';'.join(ids),origin='prior29_energy_full_path_manual_review',nested_in=''))
add('A0024',NORMAL,'2019春季同步修复，涨幅与中位数不构成长周期主线。','保留M007原边界；随后375日回落35.28%，与2020资源趋势断开。')
add('A0025',KEY,'2020—2021资源主升，已知21/21上涨，中位163.71%，去前三仍154.42%。','保留M008；2021峰后64日回撤29.97%，后轮重新立底，不为提高累计收益向后拼接。')
add('A0026 A0027',KEY,'2021末—2022中资源第二主段；4月急跌是内部中断，两个机械段只计一次。','保留M009跨年边界；4月12日历日下跌20.94%，二次底高于起点且很快越过4月峰，整体重算不相加。')
add('A0028',NORMAL,'2023—2024缓慢修复，中位51.20%但行业29.36%，不因成员涨幅自动升级。','2022峰后历经约一年调整才见2023底；2024夏秋再跌25.17%，与后轮分开。')
add('A0029',KEY,'2024秋—2026中独立资源趋势，22/22上涨，中位43.11%、去前三43.23%；广度限当前存续大市值池。','2024年9月在前轮峰下25.17%重建底部，20个月向上；2026年6月峰后再跌24.23%，不接入其后修复。')
add('A0030',NORMAL,'2026夏季回补前跌28.63%，8月峰仍低于6月峰，不列新主线。','与前峰后24.23%调整分开；截至10月22日未触发20%再跌确认，结束日仅截至可见最高点。')
add('A0049',NORMAL,'2019春季钢铁修复，中位31.25%。','保留M010；至2020年2月回撤31.96%，下一趋势另起。')
add('A0050',KEY,'2020—2021钢铁资源主升，18/18上涨，中位128.95%。','将M011起点由2020-03-23前推至同源更低2020-02-04；两底间波动未破坏连续基底，终点仍9月9日，不按年切断。')
add('A0051',NORMAL,'2022末—2023初低位反弹21.12%，已知中位21.86%。','2021峰后417日跌40.60%后才筑底；反弹未收复前高，随后长期回落，独立普通段。')
add('A0052',NORMAL,'2024春钢铁短反弹，行业22.24%、中位13.83%。','随后168日回落23.62%且9月底低于2月底，不把这段接成后轮主升。')
add('A0053',KEY,'2024秋—2026初独立主升108.04%，20/20上涨，中位84.47%，去前三82.43%。','2024-09-18是真正新低基底，跨2025延伸至2026-02-27；其后截至截点跌33.63%，不延至截点或称仍在上行。')
add('A0378',NORMAL,'2018底部延伸到2019春的普涨修复，中位45.70%。','从2018实际底起，不用元旦截断；其后221日回撤23.87%，与晚2019启动主线分开。')
add('A0379',KEY,'旧人工完全遗漏的2019末—2021工业金属大主线；31/31上涨，中位137.64%、去前三143.35%。','2019-11-15底高于2018底，疫情期间未破起点；2021-09-13独立峰，之后22.98%调整及两年箱体，不继续拼2022反弹。')
add('A0380',NORMAL,'2021末—2022初箱体反弹20.64%，中位17.95%，不列肥尾。','前峰后22.98%回撤的新基底；终点低于前峰，随后54日再跌31.42%。')
add('A0381',NORMAL,'2022春夏明显修复47.83%，29/33上涨但中位24.04%，行业与成员分化。','新底低于2021末底，终点仅略高于3月；不接入前反弹制造长趋势。')
add('A0382',NORMAL,'2022末—2023初20.14%反弹，中位20.80%。','前轮回撤20.41%后再起，2023峰低于2022峰，之后近一年回落30.50%。')
add('A0383 A0384',KEY,'2024—2026工业金属长期主线，2024春局部峰与秋季二次底只列内部阶段；属于旧M088延伸，不是完全遗漏新增。','2024夏秋回撤25.07%历116日，但二次底仍高于2月基底，2025持续阶梯上升；合为一条跨年主线并保留完整回撤，不重复计春季重点。')
add('A0385',NORMAL,'2026春高位修复24.20%，终点低于1月峰，中位21.99%。','1月峰后53日跌28.30%，明确分离；不把低于前高的修复拼成长周期延长。')
add('A0386',NORMAL,'2026夏秋反弹22.64%，中位19.73%，连续更低高点。','5月峰后再跌25.03%；截至截点该局部峰尚未20%再跌确认，不能视作已确认经济终点。')
add('A0387',NORMAL,'2018底—2019春贵金属同步修复45.46%，中位33.46%。','保留跨年起点；后续78日回撤21.38%，宽幅震荡下将6月反弹另列普通阶段。')
add('A0388',NORMAL,'2019初夏短反弹36.28%，中位32.02%，之后进入长期回落。','一个月快速上行并略创新高，后140日跌32.13%，不强并入2019末波动。')
add('A0389',NORMAL,'2019末—2020初短反弹31.72%，中位31.81%。','前轮长期回落后的局部修复；2020年2月重新跌24.91%，终点仍低于2019高点。')
add('A0390',NORMAL,'2020年2月短促反弹25.08%，不因过20%阈值称肥尾。','20日历日上行后24日历日跌21.81%，3月再探低，与后波段分开。')
add('A0391',NORMAL,'2020春夏修复47.95%，12/13上涨、中位59.27%，仍按独立次级趋势保留。','3月新底起至8月局部峰；183日跌40.05%，不延伸到2021。')
add('A0392',NORMAL,'2021独立反弹51.24%，13/13上涨但中位34.60%、前三占51.02%，未恢复2020峰。','2021-02-05深跌低点到9月局部峰；之后227日跌29.78%，与2022底分离。')
add('A0393',NORMAL,'2022春—2023春贵金属首轮，旧M086仅覆盖后半段；仍列普通/次级，不包装成新增重点。','M086起点2022-09-28前推至4月28日更低基底；其间最大回撤14%，整段连续，2023峰后297日跌33.10%形成下一底。')
add('A0394 A0395',KEY,'保留2024—2026贵金属大周期；M087春段和M102秋底后主升嵌套同一重点，只计一次。','从2024-02-05全周期基底至2026-01-29最高点；夏秋内部回撤27.27%历153日、二次底仍高于起点。主升子段M102+358.82%保留为阶段信息，不再当新增。')
add('A0396',NORMAL,'2026年2月短修复21.43%，回升未达1月峰。','主峰后15日跌26.88%后反弹；随后至7月再跌45.68%，不能当长周期延长。')
add('A0397',NORMAL,'2026夏季深跌后反弹52.31%，13/13端点上涨，中位54.05%，仍未回前高。','1月主峰至7月底跌51.77%，明确新修复阶段；8月局部峰之后又跌27.26%，不能称2024牛市未结束。')
add('A0520',NORMAL,'2019春能源金属修复，6只已知样本全涨但成员池9、全行业14，不夸大广度。','晚2018回落延至2019-01-31才见底；后108日跌30.61%，下一段重新起点。')
add('A0521',NORMAL,'2019夏—2020初新能源资源早段，中位77%但仅6已知、前三占80.97%、完整路径仅3，广度证据弱。','M056起点由2019-08-06前移至7月25日更低底，结束不变；随后跌36.03%，不与2020主线相拼。')
add('A0522 A0523 A0524',KEY,'保留M057资源新能源大主线；指数505.47%，已知6/6上涨但池9/全14、前三占70.68%，只作为小样本受限重点候选。','原2020-04-29—2021-09-10完整周期不改；内部两次21.31%和35.13%回撤均明确披露，三机械子段不重复计重点；后续28.57%跌落另起修复。')
add('A0525',NORMAL,'2021年11月13日历日反弹26.19%，仅7只已知，不列新主线。','2021主峰后跌28.57%后的短反弹，峰仍低9.87%；之后71日再跌27.50%。')
add('A0526',NORMAL,'2022年2月20日历日反弹24.35%，中位23.70%。','高点继续下降，后57日跌40.40%；不与4月起点合成连续上行。')
add('A0527',NORMAL,'保留M058深跌后独立强修复，78.26%、中位94.16%，但仅8/9池、8/14全行业，仍属前轮熊市修复。','2022-04-26新底到7月5日高点，行业仍低于2021主峰；之后两年跌71.52%，绝不接2024后大周期。')
add('A0528',NORMAL,'2024春能源金属普通反弹37.88%，中位29.90%。','下行过程中的修复，其后136日跌29.67%并创新底，不能并入下轮。')
add('A0529 A0530',KEY,'2024秋—2026春新能源资源新周期，旧人工无任何正时间重叠；仅8只已知存续样本，必须披露集中和缺1只。','以2024-08-23长期新低为基底；2024末—2025春为内部调整再积累，整体MDD25.77%且未破起点。2026-05-06峰后跌超50%，其后修复另列。')
add('A0531',NORMAL,'2026夏季31.35%反弹、已知中位25.81%，不代表恢复前牛市。','前峰后75日跌46.06%，反弹峰仍比5月低29.15%；此后又跌31.45%。')
add('A0624',LIMIT,'2018秋—2020初指数路径131.61%明确，但仅12/28池有端点、10有完整路径，不能把少数存续早上市股代表全部光伏广度。','M071和M072是同一长底部恢复中的两段；中间最大回撤17.81%，改为完整一轮，不把两段重复计数。因unknown16只不升格重点。')
add('A0625',KEY,'保留M073跨年光伏第一主升159.80%；16/17上涨、中位212.33%，但缺11/28池成员，限定于已知样本。','2020-03-31低点至2021-01-07峰；之后96日跌22.83%且持续盘整，保留原独立分段，不为累计涨幅强并下一段。')
add('A0626',KEY,'保留M074独立第二主升133.62%，22/22上涨、中位111.25%。','2021-04-13重新构筑底部到11月22日峰；后155日跌45.56%，明确不能连到2022修复。')
add('A0627',KEY,'保留M075的2022独立主升123.56%，25/25上涨、中位97.96%。','深跌后4月26日起点到8月18日独立峰；峰后至2024底跌66.69%，不能因其后反弹再延长周期。')
add('A0628',NORMAL,'2022秋短修复23.38%，22/25上涨、中位14.80%。','8月高点后53日跌25.50%，反弹高点低于前高；之后再跌23.33%，单列普通修复。')
add('A0629',NORMAL,'2022末—2023初24.18%修复，中位20.21%。','前轮之后独立新底，峰继续降低；后369日跌53.70%，不视作跨年上行主线。')
add('A0630',NORMAL,'2024春光伏反弹33.93%，中位30.33%，长期下跌中的修复。','后165日跌38.62%并创新低；与秋季反弹必须断开。')
add('A0631',NORMAL,'M094等级待讨论现定普通/次级强修复：71.65%、27/27上涨、中位61.89%，但随后147日跌36.15%。','保留原边界与全部上涨证据；长时间明显退潮形成2025年4月新底，不与后轮相拼制造更大涨幅。')
add('A0632',KEY,'旧人工完全遗漏2025春—2026初光伏独立趋势90.93%，28/28上涨、中位70.66%、去前三80.26%。','2025-04-07深回撤后再起，2026-02-09独立峰；截至截点峰后跌39.91%，应完整展示结束和回撤。')
add('A0633',LIMIT,'2018秋—2020末风电行业路径287.62%明确，但仅6/12池成员有端点、2有完整路径、前三占64.30%，不足以确认整轮全行业肥尾广度。','M076与M077部分覆盖同一连续恢复；完整周期最大回撤18.36%。峰应为同源2020-12-25而非旧2021-01-04较低点；合并改峰复算，旧重点不扩大为已证实全行业重点。')
add('A0634',KEY,'保留M078风电独立主升124.99%；8/8上涨、中位136.28%，但全行业32、前三占71.52%，小样本受限。','前峰后139日跌22.46%才重新成底；2021-11-22后155日跌52.76%，不与2022修复相并。')
add('A0635',KEY,'保留M079春夏风电段90.26%，9/9上涨、中位68.39%，仍限当前池12/全行业32。','2022-04-26深跌后独立起点，7月20日峰仍低于2021峰；后156日跌34.48%，不继续拼接小反弹。')
add('A0636',NORMAL,'2022末—2023初21.78%反弹，中位16.46%。','下行过程中更低局部峰；随后361日跌52.75%，完全断开2024修复。')
add('A0637',NORMAL,'2024春风电反弹41.83%，中位24.07%，10/12池有端点。','后174日跌26.11%，长期横盘后9月再起，与春段分别列。')
add('A0638 A0639',KEY,'旧人工完全遗漏2024秋—2026春风电新主线，两个机械候选只计一轮；池仅12/全行业32，不能声称全行业广度。','2025年3—4月17日历日跌20.07%，短暂急跌未破2024底且随后持续创新高，合并为连续主线。2026-03-13峰后40.31%下行保留。')
add('A0640',NORMAL,'2018底—2019春电池同步修复70.48%，23/24上涨；未知21/45池，早期广度受限。','M080起点前推至2018-10-18真实底，不用元旦截断；随后50日跌23.64%，下一段独立。')
add('A0641',NORMAL,'2019夏—2020初电池早段60.40%，23/24上涨、中位108.90%，但端点只覆盖24/45池。','M081起点2019-08-09前推到6月6日真实底；之后48日跌27.33%重建2020底，不跨过此跌直接合并。')
add('A0642',KEY,'2020—2021电池主线301.88%，M082/M083仅为内部两段，合为一个重点；已知28/28上涨、中位344.46%，未知17/45必须披露。','完整路径最大回撤19.62%，2021春未破2020底，连续抬升到11月29日；次年148日跌49.33%后才形成下一独立周期。')
add('A0643',KEY,'保留M084独立2022主升73.01%，38/38上涨、中位50.50%、去前三55.17%。','2022-04-26深回撤后新起点，8月23日峰低于2021峰；峰后至2024底跌65.97%，不能连到2024恢复。')
add('A0644',NORMAL,'2024春电池反弹40.61%，43/44上涨、中位34.54%。','之后136日跌31.83%且创新低，故不是新大周期真正基底。')
add('A0645 A0646',KEY,'2024秋—2026春电池新主线；旧M095仅早期一段，现为原待讨论记录延长并上调，不算完全遗漏新增。','2024-08-23多年低点至2026-05-06独立峰；2025春35日26.49%内部回撤未破起点，后续持续大幅创新高；合并重算并完整披露峰后36.97%。')
# All 67 auxiliary rows are accounted once. Decisions above were written after full daily charts, monthly closes, and bridges.
assigned=[i for r in rows for i in r['auxiliary_ids'].split(';')];assert len(assigned)==67 and set(assigned)==set(a.index) and len(set(assigned))==67
sha=lambda p:hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def readj(p):src[str(p)]=sha(p);return json.loads(p.read_text())
def signal(m):
 p,h=next((p,h) for p,h in m['source_sha256'].items() if p.endswith('/signal.parquet') and '/a-share-selection-e0-' in p);assert sha(p)==h;src[p]=h
 d=pd.read_parquet(p,columns=['close','observed_bar','price_eligible','source_invalid','synthetic_event_bar','symbol']);assert d.index.is_unique and d.index.is_monotonic_increasing
 assert set(d.symbol.dropna())=={m.get('series',m.get('symbol'))}
 good=d.observed_bar.astype(bool)&d.price_eligible.astype(bool)&~d.source_invalid.astype(bool)&~d.synthetic_event_bar.astype(bool)&d.close.gt(0)&np.isfinite(d.close)
 return d.close[good].loc[:END].astype(float)
im=readj(U/'INDUSTRY_MANIFEST.json');wanted={r['sector'] for r in rows};prices={m['series']:signal(m) for m in im if m['series'] in wanted}
meta=readj(B/'inputs-v2/metadata.json');mapping=readj(B/'audit/industry-repair-v2/mapping.json');full={};groups={};lookup={x['symbol']:x for x in mapping};stocks={}
for x in mapping:
 if x['index'] in wanted:full.setdefault(x['index'],[]).append(x['symbol'])
for m in readj(U/'STOCK_MANIFEST.json'):
 sid=m['symbol'];s=meta[sid]['sector_id']
 if s not in wanted:continue
 assert lookup[sid]['index']==s;groups.setdefault(s,[]).append(sid);stocks[sid]=signal(m)
mem=[];ledger=[];phase=[]
for r in rows:
 sec=r['sector'];start=pd.Timestamp(r['start']);end=pd.Timestamp(r['end']);p=prices[sec];q=p.loc[start:end];assert start in p.index and end in p.index
 dd=q/q.cummax()-1;tr=dd.idxmin();pk=q.loc[:tr].idxmax();tail=p.loc[end:];post63=tail.iloc[:64]
 # Correct peaks of continuous canonical windows must be actual highest close.
 assert q.iloc[-1]>=q.max()-1e-8,(r['record_id'],'end not peak',str(q.idxmax()))
 r.update(industry_return_pct=float((q.iloc[-1]/q.iloc[0]-1)*100),mdd_pct=float(dd.min()*100),mdd_peak=str(pk.date()),mdd_trough=str(tr.date()),sessions_after_start=len(q)-1,calendar_days=(end-start).days,peak_following_low=str(tail.idxmin().date()),peak_to_observed_low_pct=float((tail.min()/q.iloc[-1]-1)*100),at_cutoff_vs_peak_pct=float((tail.iloc[-1]/q.iloc[-1]-1)*100),observation_end=str(END.date()),post_low_day=str(post63.idxmin().date()),post_drop_pct=float((post63.min()/q.iloc[-1]-1)*100),post_scope=f'峰后{len(post63)-1}个已有交易日（最多63）',post_newhigh=bool(post63.max()>q.iloc[-1]))
 vals=[];unknown=[];fully=0
 for sid in groups[sec]:
  s=stocks[sid];known=start in s.index and end in s.index;v=float((s[end]/s[start]-1)*100) if known else None;fp=known and not len(q.index.difference(s.index));fully+=int(fp)
  mem.append(dict(record_id=r['record_id'],sector=sec,symbol=sid,start=r['start'],end=r['end'],known=known,full_path=fp,return_pct=v))
  if known:vals.append(v)
  else:unknown.append(sid)
 x=np.array(vals);pos=np.sort(np.maximum(x,0));K=len(x);N=len(groups[sec]);F=len(full[sec]);n=int(sum(x>0))
 r.update(current_all_members=F,research_pool_members=N,known_members=K,unknown_members=N-K,outside_pool=F-N,full_path_members=fully,unknown_symbols=','.join(unknown),positive_members=n,above30_members=int(sum(x>=30)),above50_members=int(sum(x>=50)),member_p25_pct=float(np.quantile(x,.25)),member_median_pct=float(np.median(x)),member_p75_pct=float(np.quantile(x,.75)),member_mean_pct=float(x.mean()),top3_positive_share_pct=float(pos[-3:].sum()/pos.sum()*100) if pos.sum()>0 else None,mean_without_top3_pct=float(np.sort(x)[:-3].mean()) if K>3 else None,n=n,K=K,P=N,F=F,full_path=fully,unknown=N-K)
 overlaps=old[(old.sector==sec)&(old.start<r['end'])&(old.end>r['start'])];keys=overlaps[overlaps.priority==KEY]
 r['old_manual_overlap_ids']=';'.join(overlaps.record_id);r['old_key_overlap_ids']=';'.join(keys.record_id);r['old_manual_positive_time_overlap_ids']=r['old_manual_overlap_ids'];r['old_key_positive_time_overlap_ids']=r['old_key_overlap_ids']
 r['old_exact_match_ids']=';'.join(overlaps[(overlaps.start==r['start'])&(overlaps.end==r['end'])].record_id)
 if r['priority']!=KEY:r['key_novelty_category']='非重点'
 elif not len(overlaps):r['key_novelty_category']='完全遗漏新增'
 elif len(keys)>1:r['key_novelty_category']='合并旧重点'
 elif len(keys)==1:
  z=keys.iloc[0];r['key_novelty_category']='保留旧重点' if (z.start,z.end)==(r['start'],r['end']) else '延伸或重定旧重点'
 else:r['key_novelty_category']='原普通或待讨论上调'
 r['recalculation']='同源行业和全部185只所属成员文件重新计算；未拼接涨幅'
 r['basis_limitation']=f'2026静态大市值存续池NON-PIT；n/K/P/F={n}/{K}/{N}/{F}，完整路径{fully}，unknown={N-K}；行业指数不是成员广度；历史成分与退市样本未重建。'
 if K<10:r['basis_limitation']+=' 已知样本不足10只，重点如有仅为小样本候选。'
 if N-K>=N*.3:r['basis_limitation']+=' 端点unknown至少30%，早期全行业广度不可推断。'
 if r['top3_positive_share_pct']>=60:r['basis_limitation']+=' 前三占正收益总和至少60%，集中度高。'
 if fully<K:r['basis_limitation']+=' 端点已知不等于完整路径。'
 for aid in r['auxiliary_ids'].split(';'):
  z=a.loc[aid];rel='精确等边界保留' if (z.start,z.end)==(r['start'],r['end']) else '嵌套入同一人工主周期'
  ledger.append(dict(auxiliary_id=aid,record_id=aid,sector=sec,name=r['name'],auxiliary_start=z.start,auxiliary_end=z.end,canonical_id=r['record_id'],canonical_start=r['start'],canonical_end=r['end'],priority=r['priority'],disposition=rel,reason=r['boundary_reason'],old_manual_overlap_ids=r['old_manual_overlap_ids'],old_key_overlap_ids=r['old_key_overlap_ids'],key_novelty_category=r['key_novelty_category']))
  phase.append(dict(canonical_id=r['record_id'],phase_id=aid,phase_start=z.start,phase_end=z.end,industry_return_pct=z.industry_return_pct,mdd_pct=z.mdd_pct,n=z.positive_members,K=z.known_members,P=z.research_pool_members,F=z.current_all_members,member_median_pct=z.member_median_pct,role='机械定位子段，不额外计重点'))
recon=[]
for _,z in old.iterrows():
 hits=[r for r in rows if r['sector']==z.sector and r['start']<z.end and r['end']>z.start];assert len(hits)==1,(z.record_id,[r['record_id'] for r in hits]);r=hits[0]
 same=(z.start,z.end)==(r['start'],r['end']);contains=r['start']<=z.start and r['end']>=z.end
 action='保留原边界' if same else ('嵌套入延长或合并周期' if contains else '合并并校正真实峰边界')
 if r['priority']!=z.priority:action+='；等级改判'
 recon.append(dict(old_record_id=z.record_id,sector=z.sector,name=z['name'],old_start=z.start,old_end=z.end,old_priority=z.priority,canonical_id=r['record_id'],canonical_start=r['start'],canonical_end=r['end'],canonical_priority=r['priority'],action=action,reason=r['boundary_reason']+' '+r['note'],canonical_key_novelty_category=r['key_novelty_category'],old_return_pct=z.industry_return_pct,canonical_return_pct=r['industry_return_pct']))
# Independent aggregate checks and same-boundary checks against existing exact statistics.
mf=pd.DataFrame(mem);exact_checks=0
for r in rows:
 z=mf[mf.record_id==r['record_id']];v=z[z.known].return_pct
 assert len(z)==r['P'] and len(v)==r['K'] and int((v>0).sum())==r['n'] and z.full_path.sum()==r['full_path']
 assert abs(v.median()-r['member_median_pct'])<1e-8
 exact=a[(a.sector==r['sector'])&(a.start==r['start'])&(a.end==r['end'])]
 if len(exact):
  o=exact.iloc[0]
  for c in ['industry_return_pct','mdd_pct','member_median_pct','member_mean_pct','top3_positive_share_pct','mean_without_top3_pct']:assert abs(r[c]-o[c])<1e-7,(r['record_id'],c)
  for c in ['positive_members','known_members','full_path_members','unknown_members']:assert r[c]==o[c]
  exact_checks+=1
for sec in wanted:
 z=sorted([r for r in rows if r['sector']==sec],key=lambda r:r['start'])
 assert all(x['end']<y['start'] for x,y in zip(z,z[1:]))
 for i,r in enumerate(z):
  p=prices[sec];lim=z[i+1]['start'] if i+1<len(z) else str(END.date());q=p.loc[r['end']:lim];r['post_until_next_cycle_or_cutoff_low']=str(q.idxmin().date());r['post_until_next_cycle_or_cutoff_pct']=float((q.min()/p[r['end']]-1)*100);r['post_until_next_cycle_or_cutoff_end']=lim
# Review input and raw source immutability verification.
assert all(sha(p)==h for p,h in src.items());d=pd.DataFrame(rows);ledger=pd.DataFrame(ledger);recon=pd.DataFrame(recon)
d.to_csv(O/'MANUAL_CYCLES.csv',index=False);ledger.to_csv(O/'AUXILIARY_REVIEW_LEDGER.csv',index=False);recon.to_csv(O/'OLD_MANUAL_RECONCILIATION.csv',index=False);mf.to_csv(O/'MANUAL_MEMBER_RETURNS.csv',index=False);pd.DataFrame(phase).to_csv(O/'NESTED_AUXILIARY_PHASES.csv',index=False)
key=d[d.priority==KEY];nov=key.key_novelty_category.value_counts().to_dict();d.groupby(['name','priority']).size().unstack(fill_value=0).to_csv(O/'SECTOR_REVIEW_SUMMARY.csv');(O/'SOURCE_HASHES.json').write_text(json.dumps(src,ensure_ascii=False,indent=2)+'\n')
qa=dict(industries=len(wanted),auxiliary_reviewed=len(ledger),old_manual_reconciled=len(recon),canonical_cycles=len(d),priority_counts=d.priority.value_counts().to_dict(),key_novelty_counts=nov,auxiliary_unique_assignment=True,old_manual_unique_assignment=True,canonical_same_sector_nonoverlap=True,all_endpoints_actual_window_high=True,all_industry_and_member_stats_recomputed=True,exact_auxiliary_boundaries_rechecked=exact_checks,source_stock_files=len(stocks),source_files_verified=len(src),member_rows=len(mf),sources_unchanged=True,percent_units='percentage points; MDD negative',member_universe='2026 static surviving approximately >=10bn CNY NON-PIT, not historical membership',price_basis='close from canonical signal.parquet, includes existing theoretical_ex_price adjustments; not claimed official PIT or dividend-total-return',review_scope='All 67 fixed-20% auxiliary candidates and all 28 old manual rows in these 8 prior-covered sectors; daily 2018-2026 and monthly paths reviewed; not exhaustive of sub-20% fluctuations',cutoff='2026-10-22',no_accounts_or_backtests=True)
(O/'QA.json').write_text(json.dumps(qa,ensure_ascii=False,indent=2)+'\n')
print(d[['record_id','name','start','end','priority','industry_return_pct','mdd_pct','n','K','P','F','full_path','unknown','member_median_pct','top3_positive_share_pct','old_manual_overlap_ids','key_novelty_category']].round(2).to_string(index=False));print(json.dumps(qa,ensure_ascii=False,indent=2))
