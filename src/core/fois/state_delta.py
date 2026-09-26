"""Lossless, deterministic JSON deltas; no FOIS scoring semantics live here."""
from copy import deepcopy


def changes(before, after, path=()):
    if type(before) is not type(after):
        return [['set', list(path), after]]
    if isinstance(before, dict):
        result = [['del', [*path, key]] for key in sorted(before.keys() - after.keys())]
        for key in sorted(after):
            if key not in before:
                result.append(['set', [*path, key], after[key]])
            else:
                result.extend(changes(before[key], after[key], (*path, key)))
        return result
    if isinstance(before, list) and len(before) == len(after):
        return [op for index, (a, b) in enumerate(zip(before, after))
                for op in changes(a, b, (*path, index))]
    return [] if before == after else [['set', list(path), after]]


def apply(before, operations):
    result = deepcopy(before)
    for operation in operations:
        action, path = operation[:2]
        if action not in ('set', 'del') or not isinstance(path, list):
            raise ValueError('Invalid FOIS delta operation')
        if not path:
            if action != 'set':
                raise ValueError('Cannot delete FOIS delta root')
            result = deepcopy(operation[2])
            continue
        parent = result
        for key in path[:-1]:
            parent = parent[key]
        if action == 'del':
            del parent[path[-1]]
        else:
            parent[path[-1]] = deepcopy(operation[2])
    return result
