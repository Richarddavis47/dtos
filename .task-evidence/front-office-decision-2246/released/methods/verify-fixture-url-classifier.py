"""Meaningful PURE metadata controls; no app imports or HTTP/auth requests."""
import argparse
import hashlib
import json
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import fixture_url as classifier


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    canonical = classifier.canonical_fixture_url_for_controls()
    parts = urlsplit(canonical)
    pairs = parse_qsl(parts.query)
    def url(scheme=parts.scheme, host=parts.netloc, path=parts.path, query=parts.query, fragment=''):
        return urlunsplit((scheme, host, path, query, fragment))
    cases = [('exact_public_fixture', canonical, True)]
    cases.extend((name, value, False) for name, value in (
        ('changed_token', url(query=urlencode([pairs[0], ('token', pairs[1][1] + 'changed')]))),
        ('changed_league', url(query=urlencode([('league_id', pairs[0][1] + 'changed'), pairs[1]]))),
        ('changed_path', url(path=parts.path + '/other')),
        ('external_host', url(host='metadata-negative.invalid')),
        ('subdomain_host', url(host='testserver.metadata-negative.invalid')),
        ('port', url(host='testserver:80')),
        ('userinfo', url(host='synthetic@testserver')),
        ('https_scheme', url(scheme='https')),
        ('ftp_scheme', url(scheme='ftp')),
        ('extra_query', url(query=parts.query + '&extra=metadata-only')),
        ('signature_query', url(query=parts.query + '&sig=metadata-only')),
        ('amz_signature', url(query=parts.query + '&X-Amz-Signature=metadata-only')),
        ('duplicate_query', url(query=parts.query + '&token=metadata-only')),
        ('reordered_query', url(query=urlencode(list(reversed(pairs))))),
        ('percent_encoded_value', url(query='league_id=' + pairs[0][1] + '&token=%' + format(ord(pairs[1][1][0]), '02X') + pairs[1][1][1:])),
        ('fragment', url(fragment='metadata-only')),
    ))
    results = []
    for name, value, expected in cases:
        allowed = classifier.is_exact_disposable_fixture_url(value)
        blocked = classifier.has_disallowed_sensitive_url(value.encode())
        passed = allowed is expected and blocked is (not expected)
        results.append({'name': name, 'expected_fixture_allowed': expected, 'fixture_allowed': allowed,
                        'sensitive_url_blocked': blocked, 'passed': passed})
        if not passed:
            raise RuntimeError('Pure metadata classifier control failed: ' + name)
    quoted = ('HTTP Request: GET ' + canonical + ' "HTTP/1.1 401 Unauthorized"').encode()
    additional_unknown = urlunsplit(('https', 'metadata-negative.invalid', '/path',
                                    urlencode([('token', 'synthetic-metadata-negative')]), '')).encode()
    mixed = quoted + b' ' + additional_unknown
    extras = [
        ('quoted_original_log_form', not classifier.has_disallowed_sensitive_url(quoted)),
        ('exact_fixture_does_not_exempt_other_url', classifier.has_disallowed_sensitive_url(mixed)),
        ('ordinary_public_source_url_allowed', not classifier.has_disallowed_sensitive_url(b'https://github.com/example/repo/commit/metadata-only')),
    ]
    for name, passed in extras:
        results.append({'name': name, 'passed': passed})
        if not passed:
            raise RuntimeError('Pure metadata scanner control failed: ' + name)
    test_raw = classifier.read_source(classifier.COMMITS[0], classifier.TEST_FILE)
    prefix_raw = classifier.read_source(classifier.COMMITS[0], classifier.PREFIX_FILE)
    try:
        classifier._spec_from_sources(test_raw + b'\n', prefix_raw)
    except RuntimeError:
        results.append({'name': 'changed_pinned_source_rejected', 'passed': True})
    else:
        raise RuntimeError('Changed pinned source was not rejected')
    try:
        classifier._spec_from_sources(test_raw, prefix_raw + b'\n')
    except RuntimeError:
        results.append({'name': 'changed_pinned_prefix_source_rejected', 'passed': True})
    else:
        raise RuntimeError('Changed pinned prefix source was not rejected')
    output = Path(args.output)
    if output.exists() or output.is_symlink():
        raise RuntimeError('Preserve the existing metadata-control output')
    report = {'schema': 'dtos-disposable-fixture-url-metadata-controls-v1', 'all_controls_passed': True,
              'controls': results, 'provenance': classifier.fixture_provenance(),
              'classifier_sha256': hashlib.sha256(Path(classifier.__file__).read_bytes()).hexdigest(),
              'controls_method_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'authority': 'Pure URL/source-metadata controls only. No request authorization, app import, HTTP call, production credential read, Docker, original-log rewrite, full test or release-gate execution.',
              'fixture_values_emitted': False}
    with output.open('x') as stream:
        stream.write(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'all_controls_passed': True, 'controls': len(results), 'fixture_values_emitted': False,
                      'http_requests': 0, 'app_imports': 0, 'report': str(output)}))


if __name__ == '__main__':
    main()
