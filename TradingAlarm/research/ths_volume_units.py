"""Map known THS share distributions to causal signal-volume units only."""
import pandas as pd
from stock_actions import parse_ths_rights
from volume_units import split_consistent_volume

def ths_split_consistent_volume(volume,rights):
    if volume.empty:return volume.astype(float)
    if not rights.get('records'):raise ValueError('empty rights response is not certified no-events')
    splits=[];dates=set()
    for row in rights['records']:
        date=pd.to_datetime(str(row['1']),format='%Y%m%d')
        if date<=volume.index.min() or date>volume.index.max():continue
        if date in dates:raise ValueError('duplicate same-date rights')
        dates.add(date);e=parse_ths_rights(rights['symbol'],row)
        ratio=1+e['bonus_shares_per_old_share']+e['capitalization_shares_per_old_share']
        if ratio!=1:splits.append({'date':str(date.date()),'ratio':ratio})
    return split_consistent_volume(volume,splits)
