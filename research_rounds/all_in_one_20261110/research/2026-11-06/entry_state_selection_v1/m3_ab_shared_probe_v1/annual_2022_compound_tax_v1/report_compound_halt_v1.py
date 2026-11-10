"""Report-only v2: terminal suspension does not erase closed-layer accounting."""
import report_compound_layers_v1 as base
from engine_known_halt_v1 import HALT

def reports(b,end):
    r=base.reports(b,end)
    for rows in (r['rounds'],r['layers']):
        for row in rows:
            st=b.states.get(row['sid'],{})
            if st.get('round_id')!=row['round_id'] or st.get('state')!=HALT:continue
            row['round_known_full_day_suspension']=True
            if 'status' in row:
                row.update(status='KNOWN_HALT_UNCERTIFIED',known_full_day_suspension=True,
                    stale_source_day=b.last_valid_close.get(row['round_id']),current_liquidation_value_known=False)
            else:
                row['round_status']='KNOWN_HALT_UNCERTIFIED'
                if row['q']>0:
                    row.update(layer_status='KNOWN_HALT_UNCERTIFIED',known_full_day_suspension=True,
                        stale_source_day=b.last_valid_close.get(row['round_id']),current_liquidation_value_known=False)
                else:
                    # q=0 has no remaining inventory to price. Keep the base
                    # layer's exact cash, NET80 and individual claim status.
                    row.update(known_full_day_suspension=False,current_liquidation_value_known=True)
    r['counts']['known_halt_uncertified']=sum(x['status']=='KNOWN_HALT_UNCERTIFIED' for x in r['rounds'])
    r['counts']['open_censored']=sum(x['status']=='OPEN_CENSORED' for x in r['rounds'])
    return r
