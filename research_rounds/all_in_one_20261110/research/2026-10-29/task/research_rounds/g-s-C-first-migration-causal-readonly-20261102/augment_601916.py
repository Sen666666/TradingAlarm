"""Saved original-pending/order metadata; no native event or preview."""
from pathlib import Path
from decimal import Decimal as D
import json
HERE=Path(__file__).resolve().parent;W=HERE.parent
def read(p):return json.loads(p.read_text())
def main():
 p=HERE/'601916.json';x=read(p)
 for row in x['rows']:
  mode=row['mode'];old=read(W/'g-s-C-nextsession-native-20261102/runs'/('2025_26-'+mode)/'full/2025-07-03-CLOSE.json');op=read(W/'g-s-C-month-continuation-20261102/runs'/('2025_26-'+mode)/'2025-07-04-OPEN.json');sid='601916.SH'
  row['raw_pending_known_at_same_Jul3_close']=next(i for i in old['pending'] if i['sid']==sid);row['new_native_order_meta']=op['account']['order_meta'][row['new_meta']['order']];row['capital_receiver_trace']=next(t for t in old['results'][-1]['projection']['trace'] if t['sid']=='601698.SH');row['old_vs_receiver_C_priority']={s:old['results'][-1]['projection']['C_rank_binding']['stock_priority'][s] for s in [sid,'601698.SH']};row['known_free_cash_above10']=str(D(old['account']['balance']['available'])-D('.1')*D(old['account']['policy']['nd']))
 p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
if __name__=='__main__':main()
