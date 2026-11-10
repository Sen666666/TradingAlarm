import json,pathlib,hashlib,pandas as pd,numpy as np
O=pathlib.Path(__file__).parent;U=pathlib.Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
sha=lambda p:hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
mm={r.get('series',r.get('symbol')):r for fn in ['INDUSTRY_MANIFEST.json','STOCK_MANIFEST.json'] for r in json.loads((U/fn).read_text())}
# Retrospective narrative envelopes, not trading signal or frozen predictive test.
specs=[
('AI通信第一轮','URFI881129','2022-10-01','2023-01-31','2023-02-01','2023-07-31','2023-10-31'),
('游戏AI重估','URFI881275','2022-10-01','2023-01-31','2023-02-01','2023-07-31','2024-02-05'),
('传媒AI重估','URFI881164','2022-10-01','2023-01-31','2023-02-01','2023-07-31','2023-10-31'),
('软件AI重估','URFI881272','2022-10-01','2023-01-31','2023-02-01','2023-07-31','2024-02-05'),
('CPO中际第一轮','300308.SZ','2022-10-01','2023-01-31','2023-02-01','2023-07-31','2023-10-31'),
('华为汽车赛力斯','601127.SH','2023-05-01','2023-08-31','2023-09-01','2023-11-30','2024-02-05'),
('华为电子光弘','300735.SZ','2023-05-01','2023-08-31','2023-09-01','2023-11-30','2024-02-05'),
('短剧中文在线','300364.SZ','2023-08-01','2023-10-23','2023-10-24','2023-12-29','2024-02-05'),
('CPO中际第二轮','300308.SZ','2023-10-01','2023-11-30','2023-12-01','2024-07-31','2024-09-23'),
('CPO新易盛跨年轮','300502.SZ','2023-10-01','2023-11-30','2023-12-01','2024-07-31','2024-09-23'),
('贵金属2022至2023首轮','URFI881169','2022-09-01','2022-11-30','2022-12-01','2023-06-30','2024-02-05'),
('贵金属2024再起','URFI881169','2023-10-01','2024-02-05','2024-02-06','2024-05-31','2024-09-23'),
('工业金属2024','URFI881168','2023-10-01','2024-02-05','2024-02-06','2024-05-31','2024-09-23'),
('银行跨年趋势','URFI881155','2023-10-01','2023-12-29','2024-01-02','2024-12-31','2024-12-31'),
('红利中国神华','601088.SH','2023-05-01','2023-08-31','2023-09-01','2024-08-30','2024-12-31'),
('红利长江电力','600900.SH','2023-10-01','2023-12-29','2024-01-02','2024-09-23','2024-12-31'),
('低空万丰首轮','002085.SZ','2024-01-02','2024-02-05','2024-02-06','2024-06-28','2024-09-23'),
('低空宗申再起','001696.SZ','2024-06-01','2024-07-31','2024-08-01','2024-12-31','2024-12-31'),
('924软件及后续','URFI881272','2024-08-01','2024-09-23','2024-09-24','2024-12-31','2024-12-31'),
('924半导体及后续','URFI881121','2024-08-01','2024-09-23','2024-09-24','2024-12-31','2024-12-31'),
('924证券及后续','URFI881157','2024-08-01','2024-09-23','2024-09-24','2024-12-31','2024-12-31'),
('国产AI寒武纪秋季','688256.SH','2024-08-01','2024-09-23','2024-09-24','2024-12-31','2024-12-31'),
('国产芯片中芯秋季','688981.SH','2024-08-01','2024-09-23','2024-09-24','2024-12-31','2024-12-31'),
('华为软件常山','000158.SZ','2024-07-01','2024-08-30','2024-09-01','2024-12-31','2024-12-31'),
('金融软件银之杰','300085.SZ','2024-08-01','2024-09-23','2024-09-24','2024-12-31','2024-12-31'),
('零售秋冬','URFI881158','2024-08-01','2024-09-23','2024-09-24','2024-12-31','2024-12-31'),
('光伏924反弹','URFI881279','2024-08-01','2024-09-23','2024-09-24','2024-12-31','2024-12-31'),
('电池924反弹','URFI881281','2024-08-01','2024-09-23','2024-09-24','2024-12-31','2024-12-31'),
('白酒924反弹','URFI881273','2024-08-01','2024-09-23','2024-09-24','2024-12-31','2024-12-31'),
('生物制品924反弹','URFI881142','2024-08-01','2024-09-23','2024-09-24','2024-12-31','2024-12-31')]
rows=[]
for label,sid,a,b,c,e,f in specs:
 p,h=next((p,h) for p,h in mm[sid]['source_sha256'].items() if p.endswith('/signal.parquet') and '/a-share-selection-e0-' in p);assert sha(p)==h;d=pd.read_parquet(p)
 d=d[d.observed_bar.astype(bool)&d.price_eligible.astype(bool)&~d.source_invalid.astype(bool)&~d.synthetic_event_bar.astype(bool)&d.close.gt(0)]
 low=d.loc[a:b].close.idxmin();peak=d.loc[c:e].close.idxmax();assert low<peak
 tail=d.loc[peak:f];pull=tail.close.idxmin();x=d.loc[low:peak].close
 rows.append(dict(episode=label,sid=sid,low_day=str(low.date()),peak_day=str(peak.date()),sessions_low_to_peak=len(x),low_to_peak_pct=float((d.loc[peak,'close']/d.loc[low,'close']-1)*100),ascent_max_drawdown_pct=float((x/x.cummax()-1).min()*100),after_peak_low_day=str(pull.date()),after_peak_drawdown_pct=float((d.loc[pull,'close']/d.loc[peak,'close']-1)*100),observation_end=f,end_vs_peak_pct=float((d.loc[:f].iloc[-1].close/d.loc[peak,'close']-1)*100),source=p,source_sha256=h,search_low_start=a,search_low_end=b,search_peak_start=c,search_peak_end=e))
pd.DataFrame(rows).to_csv(O/'INDEPENDENT_EPISODES.csv',index=False);(O/'INDEPENDENT_EPISODES.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n');print(pd.DataFrame(rows).drop(columns=['source','source_sha256','search_low_start','search_low_end','search_peak_start','search_peak_end']).round(2).to_string(index=False))
