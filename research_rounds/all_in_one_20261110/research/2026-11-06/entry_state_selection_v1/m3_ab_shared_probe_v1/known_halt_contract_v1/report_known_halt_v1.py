"""Report-only overlay. Original exact cash/layer attribution remains unchanged."""
import report_layers_v2 as base
from engine_known_halt_v1 import HALT

def reports(b,end):
    r=base.reports(b,end)
    for rows in (r['rounds'],r['layers']):
        for row in rows:
            st=b.states.get(row['sid'],{})
            if st.get('round_id')==row['round_id'] and st.get('state')==HALT:
                row['known_full_day_suspension']=True
                row['stale_source_day']=b.last_valid_close.get(row['round_id'])
                row['current_liquidation_value_known']=False
                if 'status' in row:row['status']='KNOWN_HALT_UNCERTIFIED'
                if 'round_status' in row:row['round_status']='KNOWN_HALT_UNCERTIFIED';row['layer_status']='KNOWN_HALT_UNCERTIFIED'
    r['counts']['known_halt_uncertified']=sum(x['status']=='KNOWN_HALT_UNCERTIFIED' for x in r['rounds'])
    r['counts']['open_censored']=sum(x['status']=='OPEN_CENSORED' for x in r['rounds'])
    return r
