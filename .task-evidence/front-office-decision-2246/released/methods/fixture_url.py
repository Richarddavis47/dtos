"""Source-pinned disposable in-process test URL classifier; no app/HTTP imports.

This permits evidence bytes only. It changes no request authorization and reads
no production configuration or credentials. Errors never print fixture values.
"""
import ast
from functools import lru_cache
import hashlib
from pathlib import Path
import re
import subprocess
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

REPOSITORY = Path('/workspace/dtos')
COMMITS = ('b602d6acd03cc1c95d85ee734d2d7f28658885cf', '4cf524c488efb36c77defd78bfd7acf84a3f6ddd')
TEST_FILE = 'tests/test_restoration_preflight_http.py'
TEST_SHA256 = '07b81fcfb222d43d27c84957e62ed7bcac757a906b0af195f20917195ec5ec9c'
PREFIX_FILE = 'src/platform/inspection_security.py'
PREFIX_SHA256 = '9385cd34ff31a10dbd162bbb489298535510395b0f27e4e879421fe76b7cfe5a'
TARGET_TEST = 'test_cookie_bearer_and_query_values_cannot_authorize'
SENSITIVE_KEYS = frozenset({'sig', 'signature', 'token', 'access_token', 'x-amz-signature', 'x-amz-credential',
    'x-amz-security-token', 'x-goog-signature', 'x-goog-credential', 'googleaccessid', 'jwt'})
URL = re.compile(rb'[A-Za-z][A-Za-z0-9+.-]*://[^\s<>"\x27]+')
LEGACY = re.compile(rb'https?://[^\s"<>]*[?&](?:sig|signature|token|access_token|X-Amz-Signature|X-Amz-Credential|X-Goog-Signature|X-Goog-Credential)=', re.I)


def require(condition):
    if not condition:
        raise RuntimeError('Pinned public fixture URL source contract changed; no URL/value exception is granted')


def read_source(commit, name):
    return subprocess.check_output(['git', 'show', commit + ':' + name], cwd=REPOSITORY)


def _function(tree, name):
    matches = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == name]
    require(len(matches) == 1)
    return matches[0]


def _constant(tree, name):
    rows = [node for node in tree.body if isinstance(node, ast.Assign) and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name) and node.targets[0].id == name]
    require(len(rows) == 1)
    value = ast.literal_eval(rows[0].value)
    require(isinstance(value, str))
    return value


def _spec_from_sources(test_raw, prefix_raw):
    require(hashlib.sha256(test_raw).hexdigest() == TEST_SHA256 and hashlib.sha256(prefix_raw).hexdigest() == PREFIX_SHA256)
    tree, prefix_tree = ast.parse(test_raw), ast.parse(prefix_raw)
    imports = {(node.module, alias.name, alias.asname) for node in tree.body if isinstance(node, ast.ImportFrom) for alias in node.names}
    require(('fastapi.testclient', 'TestClient', None) in imports and ('fastapi', 'FastAPI', None) in imports
            and ('src.platform.inspection_security', 'PREFIX', None) in imports)
    require(not any(isinstance(node, ast.Name) and node.id == 'TestClient' and isinstance(node.ctx, ast.Store) for node in ast.walk(tree)))
    require(not any(isinstance(node, ast.Attribute) and node.attr == 'base_url' for node in ast.walk(tree)))
    require(not any(isinstance(node, ast.keyword) and node.arg == 'base_url' for node in ast.walk(tree)))
    factory = _function(tree, 'make_client')
    client_calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'TestClient']
    require(len(client_calls) == 1 and client_calls[0] in list(ast.walk(factory))
            and len(client_calls[0].args) == 1 and isinstance(client_calls[0].args[0], ast.Name)
            and client_calls[0].args[0].id == 'app' and not client_calls[0].keywords)
    require(any(isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == 'app' for target in node.targets)
                and isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name) and node.value.func.id == 'FastAPI'
                and not node.value.args and not node.value.keywords for node in factory.body))
    endpoint_rows = [node for node in tree.body if isinstance(node, ast.Assign) and len(node.targets) == 1
                    and isinstance(node.targets[0], ast.Name) and node.targets[0].id == 'ENDPOINT']
    require(len(endpoint_rows) == 1)
    endpoint = endpoint_rows[0].value
    require(isinstance(endpoint, ast.BinOp) and isinstance(endpoint.op, ast.Add)
            and isinstance(endpoint.left, ast.Name) and endpoint.left.id == 'PREFIX'
            and isinstance(endpoint.right, ast.Constant) and endpoint.right.value == '/restoration-preflight')
    path = _constant(prefix_tree, 'PREFIX') + endpoint.right.value
    require(path == '/api/inspect/operations/restoration-preflight')
    granite, token = _constant(tree, 'GRANITE'), _constant(tree, 'TOKEN')
    require(len(granite) == 19 and len(token) == 36 and 'disposable' in token.lower())
    target = _function(tree, TARGET_TEST)
    parameter_dicts = [node for node in ast.walk(target) if isinstance(node, ast.Dict)
                       and [key.value if isinstance(key, ast.Constant) else None for key in node.keys] == ['league_id', 'token']]
    require(len(parameter_dicts) == 1 and all(isinstance(node, ast.Name) for node in parameter_dicts[0].values)
            and [node.id for node in parameter_dicts[0].values] == ['GRANITE', 'TOKEN'])
    require(any(isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == 'assertEqual'
                and len(node.args) == 2 and isinstance(node.args[0], ast.Attribute) and node.args[0].attr == 'status_code'
                and isinstance(node.args[1], ast.Constant) and node.args[1].value == 401 for node in ast.walk(target)))
    getter = _function(tree, 'get')
    require(any(isinstance(node, ast.Return) and isinstance(node.value, ast.Call)
                and isinstance(node.value.func, ast.Attribute) and node.value.func.attr == 'get'
                and isinstance(node.value.func.value, ast.Attribute) and node.value.func.value.attr == 'client'
                and len(node.value.args) == 1 and isinstance(node.value.args[0], ast.Name) and node.value.args[0].id == 'ENDPOINT'
                for node in ast.walk(getter)))
    return granite, token, path


@lru_cache(maxsize=1)
def _fixture_spec():
    sources = [(read_source(commit, TEST_FILE), read_source(commit, PREFIX_FILE)) for commit in COMMITS]
    require(sources[0] == sources[1])
    return _spec_from_sources(*sources[0])


def canonical_fixture_url_for_controls():
    """Pure metadata control input derived from public constants; never log it."""
    granite, token, path = _fixture_spec()
    return urlunsplit(('http', 'testserver', path, urlencode([('league_id', granite), ('token', token)]), ''))


def is_exact_disposable_fixture_url(value):
    """Allow only the exact source-backed canonical URL, never a whole file."""
    if not isinstance(value, str):
        return False
    granite, token, path = _fixture_spec()
    try:
        parts = urlsplit(value)
        pairs = parse_qsl(parts.query, keep_blank_values=True, strict_parsing=True)
    except ValueError:
        return False
    expected_pairs = [('league_id', granite), ('token', token)]
    return (parts.scheme == 'http' and parts.netloc == 'testserver' and parts.path == path and not parts.fragment
            and pairs == expected_pairs and value == urlunsplit(('http', 'testserver', path, urlencode(expected_pairs), '')))


def has_disallowed_sensitive_url(raw, legacy_pattern=LEGACY):
    """Reject every other sensitive URL; retain legacy scanner coverage too."""
    matches = list(URL.finditer(raw))
    for match in matches:
        data = match.group()
        try:
            value = data.decode('utf-8')
            query = value.partition('?')[2].partition('#')[0]
            keys = {key.lower() for key, _ in parse_qsl(query, keep_blank_values=True)}
        except UnicodeDecodeError:
            if legacy_pattern.search(data):
                return True
            continue
        if (keys & SENSITIVE_KEYS or legacy_pattern.search(data)) and not is_exact_disposable_fixture_url(value):
            return True
    # A malformed/quoted legacy match must never evade full-URL extraction.
    for legacy in legacy_pattern.finditer(raw):
        if not any(match.start() <= legacy.start() and legacy.end() <= match.end() for match in matches):
            return True
    return False


def fixture_provenance():
    granite, token, path = _fixture_spec()
    return {'scope': 'Metadata-only exception for one public disposable in-process test URL; no request/authentication change',
            'source_commits': list(COMMITS), 'test_file': TEST_FILE, 'test_file_sha256': TEST_SHA256,
            'prefix_file': PREFIX_FILE, 'prefix_file_sha256': PREFIX_SHA256, 'source_test': TARGET_TEST,
            'inprocess_TestClient_without_base_url_override': True, 'origin': 'http://testserver', 'path': path,
            'query_keys': ['league_id', 'token'], 'fixture_values_emitted': False,
            'public_fixture_token_length': len(token), 'public_fixture_token_sha256': hashlib.sha256(token.encode()).hexdigest(),
            'public_fixture_league_sha256': hashlib.sha256(granite.encode()).hexdigest(),
            'expected_authentication_result': 401}
