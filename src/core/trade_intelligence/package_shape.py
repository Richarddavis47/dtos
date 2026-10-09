"""Shared two-sided, manager-oriented package vocabulary."""
from collections.abc import Iterable
from collections import Counter


def package_shape(received_types: Iterable[str], sent_types: Iterable[str]) -> str:
    received, sent = tuple(received_types), tuple(sent_types)
    types = (*received, *sent)
    if not received or not sent:
        return "incomplete_package"
    def side(values):
        return "_".join(f"{kind}{count}" for kind, count in sorted(Counter(values).items()))
    orientation = f":receive_{side(received)}_send_{side(sent)}"
    if len(received) == len(sent) == 1:
        return "one_for_one" if all(kind == "player" for kind in types) else "one_for_one" + orientation
    if types.count("pick") > types.count("player"):
        return "pick_heavy" + orientation
    if any("player" in values and "pick" in values for values in (received, sent)):
        return "player_plus_pick" + orientation
    if sorted((len(received), len(sent))) == [1, 2]:
        return (("one_for_two:receive_one_send_two" if len(received) == 1
                 else "one_for_two:receive_two_send_one") if all(kind == "player" for kind in types)
                else "one_for_two" + orientation)
    return "multi_asset" + orientation
