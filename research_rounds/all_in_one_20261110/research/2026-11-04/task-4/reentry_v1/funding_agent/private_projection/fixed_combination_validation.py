def fixed_validation(s0,intents,attempts,plan,at,expected_migrations):
    """Validate fixed quantities/pools, never call full route or choose an argmax."""
    validation_count();b=copy.deepcopy(s0);b.migrations=[];a=AccountView(b);by={bid(i):i for i in intents};pmap={x['key']:x for x in plan};failures=[]
    for attempt in attempts:
        budget_check()
        i=copy.deepcopy(by[attempt['key']]);x=i['_preview'];b.context=bid(i)
        if attempt['eval_migrate']:
            b.phase='evaluation';b.migrate(b.sector_by_sid[i['sid']])
        if bid(i) in pmap:
            o=pmap[bid(i)];r,why=reserve_fixed(a,i,x,o['quantity'],o['pool'],at)
            if why:failures.append(dict(key=bid(i),reason=why));break
    if not failures and migration_signature(b.migrations)!=migration_signature(expected_migrations):failures.append(dict(reason='migration_sequence_differs_from_first_pass'))
    return dict(valid=not failures,failures=failures,state=b,available=a.available)
