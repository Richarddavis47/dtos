"""Lossless, deterministic JSON deltas; no FOIS scoring semantics live here."""
from copy import deepcopy


class InvalidDeltaError(ValueError):
    """Retained delta instructions are not compatible with canonical JSON."""


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


def _validate_path(value, path, action):
    parent = value
    for index, key in enumerate(path):
        last = index == len(path) - 1
        if type(parent) is dict:
            if type(key) is not str or (key not in parent and not (last and action == 'set')):
                raise InvalidDeltaError('Invalid FOIS delta object path')
        elif type(parent) is list:
            # bool is an int subclass; it is never a canonical array index.
            if type(key) is not int or not 0 <= key < len(parent):
                raise InvalidDeltaError('Invalid FOIS delta list path')
        else:
            raise InvalidDeltaError('Invalid FOIS delta path container')
        if not last:
            parent = parent[key]


def apply(before, operations, *, _owned=False):
    if type(operations) is not list:
        raise InvalidDeltaError('Invalid FOIS delta operations')
    # General callers keep independent trees. The decoder's private tree can
    # reuse untouched evidence, but stage shallow ancestor copies before writes.
    # A later invalid instruction cannot mutate the base or operation values.
    result = before if _owned else deepcopy(before)
    staged = {}

    def writable(value):
        if not _owned or staged.get(id(value)) is value:
            return value
        result = value.copy()
        # Hold copies through the call: deleted copies must not allow id reuse.
        staged[id(result)] = result
        return result

    for operation in operations:
        if type(operation) is not list or len(operation) < 2:
            raise InvalidDeltaError('Invalid FOIS delta operation')
        action, path = operation[:2]
        if (action not in ('set', 'del') or type(path) is not list or
                len(operation) != (3 if action == 'set' else 2)):
            raise InvalidDeltaError('Invalid FOIS delta operation')
        if not path:
            if action != 'set':
                raise InvalidDeltaError('Cannot delete FOIS delta root')
            result = operation[2] if _owned else deepcopy(operation[2])
            continue
        _validate_path(result, path, action)
        result = writable(result)
        parent = result
        for key in path[:-1]:
            child = writable(parent[key])
            parent[key] = child
            parent = child
        if action == 'del':
            del parent[path[-1]]
        else:
            parent[path[-1]] = operation[2] if _owned else deepcopy(operation[2])
    return result
