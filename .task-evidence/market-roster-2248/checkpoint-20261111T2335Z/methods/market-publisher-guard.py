def verify_market_roster(path, plan, prefix='browser/market-needs/'):
    """Read exact-source real route/browser artifacts, never owner live claims."""
    verify_zip(path)
    expected={(shape,width,height) for shape in ('oneqb-kdef','superflex') for width,height in ((320,432),(375,667),(390,844),(1280,900))}
    def record(archive,name):
        row=json.loads(archive.read(prefix+name+'.json'))
        require(row.get('commit')==plan['candidate'] and row.get('tree')==plan['tree'], 'Market handoff source mismatch')
        require('not owner live' in row.get('scope',''), 'Market fixture scope missing')
        return row['observations']
    with zipfile.ZipFile(path) as archive:
        rows=record(archive,'roundtrip')
        require(len(rows)==8 and {(r['shape'],*r['viewport']) for r in rows}==expected, 'Market round-trip coverage incomplete')
        for row in rows:
            require(all(row.get(k) is True for k in ('roundtrip','exact_asset','draft_preserved','protections_preserved','comparison_preserved','retained_result','no_extra_posts','no_solver_on_navigation')) and row.get('errors')==[], 'Market state or no-work control failed')
            shape,width,height=row['shape'],*row['viewport']
            captured=record(archive,shape+'-'+str(width))
            require(len(captured)==1 and captured[0].get('exact_target')=='player:2-RB-0' and captured[0].get('neutral_movement')==150 and captured[0].get('keyboard_disclosure') is True and captured[0].get('touch_emulation') is (width<1000) and captured[0].get('overflow') is False, 'Market target or accessibility proof missing')
            market=record(archive,'market-'+shape+'-'+str(width))
            require(len(market)==1 and market[0].get('no_search') is True, 'Market disclosure proof missing')
            for stem in (shape+'-'+str(width),'market-'+shape+'-'+str(width)):
                image=archive.read(prefix+stem+'.png')
                require(image.startswith(b'\x89PNG\r\n\x1a\n') and len(image)>=24 and int.from_bytes(image[16:20],'big')==width, 'Market phone capture missing or wrong width')
        stale=record(archive,'stale-and-league')
        require(len(stale)==1 and all(stale[0].get(k) is True for k in ('stale_link_withheld','new_target_not_applied','existing_draft_preserved','league_switch_cleared_scope','no_posts')) and stale[0].get('errors')==[], 'Stale Market handoff protection missing')
    return dict(candidate=plan['candidate'],tree=plan['tree'],cases=8,scope='Disposable authenticated prepared evidence and Chromium phone/touch emulation; owner live and physical Safari unverified')


def verify_market_roster_tests(path, plan):
    with zipfile.ZipFile(path) as archive:
        rows=[json.loads(line) for line in archive.read('tests.jsonl').splitlines()]
    starts=[r['test'] for r in rows if r.get('event')=='start' and 'test_market_roster_relevance' in r.get('test','')]
    stops=[r['test'] for r in rows if r.get('event')=='stop' and 'test_market_roster_relevance' in r.get('test','')]
    require(len(starts)==len(set(starts))==plan['market_roster_tests']==18 and Counter(starts)==Counter(stops), 'Market roster regression population incomplete')
    return starts


