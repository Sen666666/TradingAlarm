def match(risk):
    used=set();pairs=[];status=[]
    for day,g in risk.groupby('date',sort=True):
        previous=set(used);edges=[];degree=collections.Counter();records=g.to_dict('records')
        for sector,gg in g[g.feature_ready].groupby('sector',sort=True):
            rows=gg.sort_values(['h1','symbol']).to_dict('records')
            for i,a in enumerate(rows):
                for b in rows[i+1:]:
                    hd=b['h1']-a['h1']
                    if hd>1:break
                    ad=abs(a['age']-b['age']);rg=abs(a['runup']-b['runup'])/max(a['scale'],b['scale'])
                    if ad>5 or rg>1:continue
                    known='|'.join(sorted([a['known_id'],b['known_id']]));pid=digest(known);degree[a['known_id']]+=1;degree[b['known_id']]+=1;edges.append((hd,ad,rg,pid,a,b,known))
        chosen=set()
        for hd,ad,rg,pid,a,b,known in sorted(edges,key=lambda x:x[:4]):
            if a['e0_epoch'] in used or b['e0_epoch'] in used:continue
            used.update([a['e0_epoch'],b['e0_epoch']]);chosen.update([a['known_id'],b['known_id']])
            hi=min([a,b],key=lambda z:(-z['h1'],z['symbol']));pr=min([a,b],key=lambda z:(-z['pvr'],z['symbol']))
            tie=a['pvr']==b['pvr'];kind='pvr_tie_no_contrast' if tie else 'same_choice' if pr['symbol']==hi['symbol'] else 'conflict'
            other=b if a['symbol']==hi['symbol'] else a
            p=dict(pair_id=pid,date=str(pd.Timestamp(day).date()),sector=a['sector'],pair_kind=kind,known_id_fields=known,h1_gap=hd,age_gap=ad,runup_gap_scale=rg,h1_exact_tie=a['h1']==b['h1'])
            # H1 and other roles are independent of PVR; matching order never uses score values.
            for role,z in [('h1',hi),('other',other)]:
                for k in ['symbol','e0_epoch','i_epoch','anchor','age','runup','scale','h1','pvr','pvr_raw','grade','known_id']:p[role+'_'+k]=z[k]
            p['pvr_choice_symbol']=hi['symbol'] if tie else pr['symbol'];pairs.append(p)
        for a in records:
            why='feature_missing' if not a['feature_ready'] else 'event_used_earlier_date' if a['e0_epoch'] in previous else 'matched_today' if a['known_id'] in chosen else 'comparable_peer_consumed' if degree[a['known_id']] else 'no_comparable_peer'
            status.append(dict(date=day,symbol=a['symbol'],e0_epoch=a['e0_epoch'],known_id=a['known_id'],reason=why,comparable_edges=degree[a['known_id']]))
    return pd.DataFrame(pairs),pd.DataFrame(status)
