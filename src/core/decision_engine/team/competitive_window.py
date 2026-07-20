"""Team competitive-window classification."""
from __future__ import annotations

from src.core.decision_engine.models.decision import TeamWindow
from src.core.decision_engine.models.evaluation import Evaluation


def classify_competitive_window(current: Evaluation, future: Evaluation) -> tuple[TeamWindow, str]:
    if current.score >= 75 and future.score >= 55:
        return TeamWindow.CHAMPIONSHIP, f"Current outlook is {current.score}/100 and future outlook is {future.score}/100; both clear the Championship Window thresholds."
    if current.score >= 65:
        return TeamWindow.PLAYOFF, f"Current outlook is {current.score}/100, supporting a playoff-oriented window while future outlook remains independently rated at {future.score}/100."
    if current.score < 50 and future.score >= 65:
        return TeamWindow.ASCENSION, f"Future outlook ({future.score}/100) materially exceeds current outlook ({current.score}/100), indicating an ascending asset base."
    if current.score < 50 and future.score < 55:
        return TeamWindow.REBUILD, f"Current ({current.score}/100) and future ({future.score}/100) outlooks are both below their foundation thresholds; rebuilding flexibility deserves attention."
    return TeamWindow.TRANSITION, f"Current ({current.score}/100) and future ({future.score}/100) signals do not strongly fit the other window thresholds."
