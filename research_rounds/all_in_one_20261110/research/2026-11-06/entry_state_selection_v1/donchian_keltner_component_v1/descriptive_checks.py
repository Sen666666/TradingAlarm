import sys,json
from pathlib import Path
import pandas as pd
base=Path("/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1/donchian_keltner_component_v1")
sys.path.insert(0,str(base));import replay_keltner_cap as m
metas={x["symbol"]:x for x in json.loads(m.runner.MANIFEST.read_text())}
picks={"000029.SZ":["2022-12-01","2022-12-02","2022-12-05","2022-12-07"],"002385.SZ":["2022-03-04","2022-03-07","2022-03-08"],"002583.SZ":["2024-09-19","2024-09-20","2024-09-23","2024-09-24"],"300085.SZ":["2024-09-19","2024-09-20","2024-09-24","2024-10-09","2024-10-10"],"603061.SH":["2026-01-05","2026-01-15","2026-02-11"],"300623.SZ":["2026-01-09","2026-01-15","2026-02-02"]}
rows=[]
for sid,days in picks.items():
    d,b=m.runner.read_symbol(metas[sid]);p=d["price"];f=m.engine.features(p);z=m.indicators(p,f);n=d["facts"];cp=d["CP1"]
    for day in days:
        t=p.index.get_loc(pd.Timestamp(day));fac=float(p.close.iloc[t]/p.raw_close.iloc[t]);r=z.iloc[t];prev=z.iloc[t-1]
        rows.append(dict(sid=sid,day=day,C=float(p.raw_close.iloc[t]),U20=r.U20/fac,KC_upper_prior=(prev.EMA20+2*prev.ATR10)/fac,KC_lower_prior=r.KC_lower_prior/fac,ATR10_prior=r.ATR10_prior/fac,I=n.loc[day,"i_target"],I_buy=n.loc[day,"i_buy"],CP=cp.loc[day,"receipt"],candidate=cp.loc[day,"candidate"]/fac))
print(pd.DataFrame(rows).to_string(index=False))
existing=[]
for sid,days in m.CASES.items():
    path=m.SHARED/"smoke_v1"/sid.replace(".","_")/"CP_ANCHOR_PAIRS.json"
    if path.exists():
        old=json.loads(path.read_text())
        new=json.loads((base/"ORIGINAL_CP_PAIRS.json").read_text())
        for day in days:
            a=next(x for x in old if x["anchor_day"]==day);b=next(x for x in new if x["sid"]==sid and x["anchor_day"]==day)
            assert a["CP"]==b["CP"];existing.append((sid,day))
print("SAVED_ORIGINAL_CP_EXACT",existing)

pd.DataFrame(rows).to_csv(base/"DESCRIPTIVE_KEY_DAYS.csv",index=False)
(base/"SAVED_CP_CHECK.json").write_text(json.dumps(dict(saved_original_CP_exact=existing,new_economic_runs=0),ensure_ascii=False,indent=2)+"\n")
