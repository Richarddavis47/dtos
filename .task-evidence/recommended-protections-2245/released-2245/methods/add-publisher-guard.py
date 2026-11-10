from pathlib import Path
p=Path('/workspace/dtos-publisher-2245/tools/release/publish.py')
s=p.read_text()
code='''def verify_recommended_protections(path, plan, prefix="browser/protections/"):
    """Exact native exclusions and independent draft controls on the pinned source."""
    verify_zip(path)
    with zipfile.ZipFile(path) as archive:
        def report(name):
            row = json.loads(archive.read(prefix + name + '.json'))
            require(row.get('commit') == plan['candidate'] and row.get('tree') == plan['tree']
                    and row.get('working_tree_clean') is True, 'Recommended protection source mismatch')
            require(row.get('source') == 'Disposable prepared Sleeper fixture; actual authenticated routes, canonical search and admission'
                    and row.get('physical_safari_tested') is False, 'Recommended protection scope invalid')
            return row['observations']
        expected = {'2029-R1-1', 'a'}
        for width, height in ((320,432), (375,667), (390,844), (1280,900)):
            row = report('phone-' + str(width))
            require(row.get('width') == width and row.get('height') == height
                    and set(row.get('exact_ids', [])) == expected
                    and row.get('no_search_from_controls') is True, 'Recommended phone control missing')
            require(archive.read(prefix + 'phone-' + str(width) + '.png').startswith(b'\\x89PNG\\r\\n\\x1a\\n'),
                    'Recommended phone screenshot missing')
        row = report('exact-native-search')
        pools = row.get('candidate_pools', [])
        offers = row.get('offers', [])
        require(set(row.get('payload', {}).get('protected_assets', [])) == expected
                and set(row.get('constraints', {}).get('protected_assets', [])) == expected,
                'Native protection request/result mismatch')
        require(pools and any('2029-R1-3' in pool for pool in pools)
                and all(expected.isdisjoint(pool) for pool in pools), 'Exact pick construction isolation missing')
        require(offers and all(expected.isdisjoint(offer['proposal']['assets_sent']) for offer in offers)
                and row.get('saved_preferences_unchanged') is True, 'Protected asset escaped to native results')
        row = report('clear-and-prior-results')
        require(row.get('old_results_not_relabeled') is True and row.get('clearing_did_not_search') is True
                and row.get('second_constraints', {}).get('protected_assets') == []
                and '2029-R1-1' in row.get('first_constraints', {}).get('protected_assets', []),
                'Cleared protections or old search identity missing')
        row = report('draft-and-scope')
        require(row.get('real_evaluations') == 2 and all(row.get(k) is True for k in
                ('recommended_controls_not_applied_to_evaluate', 'original_draft_retained', 'comparison_proposals_retained',
                 'reload_retained', 'league_switch_cleared')), 'Recommended draft/scope isolation missing')
        row = report('completed-zero-result')
        require(row.get('completed') is True and row.get('no_protection_causality_claim') is True
                and not row.get('body', {}).get('results') and not row.get('body', {}).get('exploratory_results')
                and row.get('payload', {}).get('protected_assets'), 'Native completed zero search missing')
    return dict(passed=True, head=plan['candidate'], tree=plan['tree'],
                scope='Exact temporary exclusions through actual fixture search/admission and phone UI; not owner live acceptance')


'''
s=s.replace('def verify_offer_comparison(',code+'def verify_offer_comparison(')
s=s.replace('            verify_offer_comparison(path, plan)','            verify_offer_comparison(path, plan)\n            verify_recommended_protections(path, plan)')
s=s.replace('    offer_comparison = verify_offer_comparison(recovery, plan, prefix="offer-comparison/")','    offer_comparison = verify_offer_comparison(recovery, plan, prefix="offer-comparison/")\n    recommended_protections = verify_recommended_protections(recovery, plan, prefix="protections/")')
s=s.replace("assets / 'Recorded-Trade-Comparison-Handoff.zip'", "assets / 'Recommended-Search-Protections-Handoff.zip'")
s=s.replace('offer_comparison=offer_comparison, completed_trade_observations=', 'offer_comparison=offer_comparison, recommended_protections=recommended_protections, completed_trade_observations=')
s=s.replace("limitations='Two compact recorded offers inside the Trade workspace.", "limitations='Temporary exact Recommended Trades protections do not change Evaluate or saved preferences. Three native assessed fixture offers respect exclusions; own and acquired same-round picks stay distinct. Old searches retain original settings; no-result restrictions imply no causality. No search from control edits. Two compact recorded offers inside the Trade workspace.")
p.write_text(s)
