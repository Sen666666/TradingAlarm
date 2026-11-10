from pathlib import Path
from decimal import Decimal as D
import json,hashlib
O=Path(__file__).resolve().parent
E=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1/m3_stock_birth_during_sector_v1')
rows=[]
for s,dt in [('002797.SZ','2024-09-13'),('600621.SH','2024-10-11'),('601901.SH','2024-10-11'),('002673.SZ','2024-10-24')]:
 p=E/'cash_dividend_source_feasibility_v1/raw'/(s+'.json');j=json.loads(p.read_text());r=[r for r in j['raw']['records'] if str(r.get('F020D',''))[:10]==dt];assert len(r)==1;r=r[0]
 cash=D(str(r['F012N']))/10
 rows.append(dict(sid=s,ex_date=dt,record_date=r['F018D'][:10],pay_date=r['F023D'][:10],announcement_date=r['F006D'][:10],d_source=str(cash),d_cash=str(cash),economic_event_id_candidate=f'{s}|PURE_CASH|{dt}',evidence_hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest()},scope='EXISTING_COMPANY_FACT_REVIEWED_NET80_NOT_PIT'))
(O/'EXTRA_REVIEWED_EQUITY_EVENTS.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
print(rows)
