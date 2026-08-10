"""Read-only FOIS General Manager Intelligence APIs and pages."""
from __future__ import annotations

from dataclasses import asdict
from html import escape
from typing import Any, Callable

from fastapi import APIRouter, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from fastapi.responses import HTMLResponse

from app_metadata import BUILD_NUMBER, VERSION, deployment_metadata
from src.core.fois.configuration import DEFAULT_FOIS_CONFIGURATION
from src.core.fois.models import FOIS_MODEL_VERSION
from src.core.fois.registry import DEFAULT_METRIC_REGISTRY
from src.core.fois.service import FOISService, fois_enabled
from src.ui.intelligence_presentation import exact_rank, human_status, technical_details

PageRenderer = Callable[[str, str], HTMLResponse]


def _metadata(score: Any | None = None) -> dict[str, Any]:
    deployment = deployment_metadata()
    return {
        "application_version": VERSION,
        "application_build": BUILD_NUMBER,
        "commit": deployment["commit"],
        "fois_model_version": FOIS_MODEL_VERSION,
        "brain_snapshot_id": getattr(score, "brain_snapshot_id", None),
        "brain_version": getattr(score, "brain_version", None),
        "generation_timestamp": getattr(score, "generated_at", None),
        "confidence": getattr(score, "confidence", 0.0),
        "completeness": getattr(score, "completeness", 0.0),
        "evidence_state": getattr(score, "evidence_state", "unavailable"),
    }


def _summary(score: Any) -> dict[str, Any]:
    return {
        "gm_id": score.gm_id,
        "gm_name": score.gm_name,
        "franchise_id": score.franchise_id,
        "tenure_id": score.tenure_id,
        "executive_score": score.overall_score,
        "grade": score.overall_letter_grade,
        "confidence": score.confidence,
        "completeness": score.completeness,
        "evidence_state": score.evidence_state,
        "current_team_score": score.current_team_score,
        "management_momentum": score.management_momentum,
        "strongest_category": score.strongest_category,
        "weakest_category": score.weakest_category,
    }


def create_fois_router(
    *,
    service: FOISService,
    require_data: Callable[[], dict[str, Any]],
    page: PageRenderer | None = None,
) -> APIRouter:
    router = APIRouter(tags=["fois"])

    def require_enabled() -> None:
        if not fois_enabled():
            raise HTTPException(404, "FOIS is disabled.")

    def league_scores(league_id: str):
        require_enabled()
        return service.repository.league(league_id, FOIS_MODEL_VERSION)

    def gm_score(league_id: str, gm_id: str):
        require_enabled()
        score = service.repository.score_for_gm(league_id, gm_id, FOIS_MODEL_VERSION)
        if score is None:
            raise HTTPException(404, "No FOIS score exists for this GM tenure.")
        return score

    @router.get("/api/fois")
    async def root() -> dict[str, Any]:
        return {**_metadata(), "status": service.status(), "links": {
            "status": "/api/fois/status", "model": "/api/fois/model",
        }}

    @router.get("/api/fois/status")
    async def status() -> dict[str, Any]:
        return {**_metadata(), **service.status()}

    @router.get("/api/fois/model")
    async def model() -> dict[str, Any]:
        require_enabled()
        return {**_metadata(), "configuration": jsonable_encoder(asdict(DEFAULT_FOIS_CONFIGURATION)),
                "metrics": jsonable_encoder([asdict(metric) for metric in DEFAULT_METRIC_REGISTRY])}

    @router.post("/api/fois/leagues/{league_id}/calculate")
    async def calculate(league_id: str) -> dict[str, Any]:
        require_enabled()
        data = require_data()
        actual_id = str((data.get("league") or {}).get("league_id") or league_id)
        if actual_id != league_id:
            raise HTTPException(404, "The requested league is not loaded.")
        scores = await service.generate(data)
        return {**_metadata(scores[0] if scores else None), "league_id": league_id,
                "scores": jsonable_encoder(scores)}

    @router.get("/api/fois/leagues/{league_id}")
    async def league(league_id: str) -> dict[str, Any]:
        scores = league_scores(league_id)
        return {**_metadata(scores[0] if scores else None), "league_id": league_id,
                "gms": [_summary(score) for score in scores]}

    @router.get("/api/fois/leagues/{league_id}/rankings")
    async def rankings(league_id: str) -> dict[str, Any]:
        scores = sorted(league_scores(league_id), key=lambda row: (
            -(row.overall_score if row.overall_score is not None else -1), -row.confidence,
            row.gm_id or "",
        ))
        return {**_metadata(scores[0] if scores else None), "league_id": league_id,
                "rankings": [{"rank": index, **_summary(score)} for index, score in enumerate(scores, 1)]}

    @router.get("/api/fois/leagues/{league_id}/gms")
    async def gms(league_id: str) -> dict[str, Any]:
        return await league(league_id)

    @router.get("/api/fois/leagues/{league_id}/gms/{gm_id}")
    async def gm(league_id: str, gm_id: str) -> dict[str, Any]:
        score = gm_score(league_id, gm_id)
        tenure = service.repository.tenure_for_gm(league_id, gm_id)
        return {**_metadata(score), "profile": jsonable_encoder(score),
                "tenure": jsonable_encoder(tenure),
                "takeover": jsonable_encoder(service.repository.takeover(tenure.tenure_id)) if tenure else None,
                "gm_quality_is_not_team_quality": True}

    @router.get("/api/fois/leagues/{league_id}/gms/{gm_id}/timeline")
    async def timeline(league_id: str, gm_id: str) -> dict[str, Any]:
        score = gm_score(league_id, gm_id)
        return {**_metadata(score), "timeline": jsonable_encoder(service.repository.timeline(league_id, gm_id))}

    async def category(league_id: str, gm_id: str, category_key: str) -> dict[str, Any]:
        score = gm_score(league_id, gm_id)
        row = next((item for item in score.category_scores if item.category_key == category_key), None)
        if row is None:
            raise HTTPException(404, "FOIS category is unavailable.")
        return {**_metadata(score), "category": jsonable_encoder(row)}

    @router.get("/api/fois/leagues/{league_id}/gms/{gm_id}/results")
    async def results(league_id: str, gm_id: str):
        return await category(league_id, gm_id, "results")

    @router.get("/api/fois/leagues/{league_id}/gms/{gm_id}/trading")
    async def trading(league_id: str, gm_id: str):
        return await category(league_id, gm_id, "trading_asset_management")

    @router.get("/api/fois/leagues/{league_id}/gms/{gm_id}/roster-construction")
    async def roster(league_id: str, gm_id: str):
        return await category(league_id, gm_id, "roster_construction")

    @router.get("/api/fois/leagues/{league_id}/gms/{gm_id}/drafting")
    async def drafting(league_id: str, gm_id: str):
        return await category(league_id, gm_id, "drafting_talent_evaluation")

    @router.get("/api/fois/leagues/{league_id}/gms/{gm_id}/evidence")
    async def evidence(league_id: str, gm_id: str):
        score = gm_score(league_id, gm_id)
        return {**_metadata(score), "evidence_references": score.evidence_references,
                "warnings": score.warnings}

    @router.get("/api/fois/leagues/{league_id}/gms/{gm_id}/resume")
    async def resume(league_id: str, gm_id: str):
        score = gm_score(league_id, gm_id)
        results_row = next(row for row in score.category_scores if row.category_key == "results")
        details = results_row.details or {}
        return {**_metadata(score), "gm_id": gm_id, "achievements": {
            "championships": details.get("championships"),
            "playoff_appearances": details.get("playoff_appearances"),
            "competitive_cycles": details.get("competitive_cycles", []),
        }, "superlatives": [], "limitations": [
            "Superlatives are omitted unless canonical evidence is sufficient."
        ]}

    @router.get("/api/fois/leagues/{league_id}/franchises/{franchise_id}/history")
    async def franchise_history(league_id: str, franchise_id: str):
        tenures = service.repository.tenures(league_id, franchise_id=franchise_id)
        return {**_metadata(), "league_id": league_id, "franchise_id": franchise_id,
                "tenures": jsonable_encoder(tenures)}

    @router.get("/api/fois/leagues/{league_id}/compare")
    async def compare(league_id: str, gm_id: list[str] = Query(default=[])):
        if len(gm_id) < 2:
            raise HTTPException(422, "At least two gm_id values are required.")
        scores = [gm_score(league_id, item) for item in gm_id]
        return {**_metadata(scores[0]), "comparisons": [_summary(score) for score in scores],
                "disclosure": "GM quality and current team quality are separate measures."}

    # v1.6 compatibility adapters.
    @router.get("/api/fois/leagues/{league_id}/franchises/{franchise_id}")
    async def franchise(league_id: str, franchise_id: str):
        score = service.repository.get(league_id, franchise_id, FOIS_MODEL_VERSION)
        if score is None:
            raise HTTPException(404, "No FOIS score exists for this franchise.")
        return jsonable_encoder(score)

    @router.get("/api/fois/leagues/{league_id}/franchises/{franchise_id}/categories")
    async def categories(league_id: str, franchise_id: str):
        score = await franchise(league_id, franchise_id)
        return {"categories": score["category_scores"]}

    @router.get("/api/fois/leagues/{league_id}/franchises/{franchise_id}/metrics")
    async def metrics(league_id: str, franchise_id: str):
        score = await franchise(league_id, franchise_id)
        return {"metrics": [metric for row in score["category_scores"] for metric in row["metric_scores"]]}

    @router.get("/api/fois/leagues/{league_id}/franchises/{franchise_id}/results")
    async def legacy_results(league_id: str, franchise_id: str):
        score = await franchise(league_id, franchise_id)
        row = next((item for item in score["category_scores"] if item["category_key"] == "results"), None)
        if row is None:
            raise HTTPException(404, "No Results score exists for this franchise.")
        return row

    @router.get("/api/fois/leagues/{league_id}/completeness")
    async def completeness(league_id: str):
        scores = league_scores(league_id)
        return {**_metadata(scores[0] if scores else None), "league_id": league_id,
                "franchises": [{"franchise_id": row.franchise_id,
                                 "completeness": row.completeness,
                                 "confidence": row.confidence,
                                 "provisional": row.provisional} for row in scores]}

    @router.get("/fois", response_class=HTMLResponse)
    async def fois_page(league_id: str = Query(default="")) -> HTMLResponse:
        try:
            data = require_data()
        except HTTPException as exc:
            if exc.status_code != 503:
                raise
            data = {}
        loaded_league = data.get("league") or {}
        loaded_league_id = str(loaded_league.get("league_id") or "")
        requested_league_id = league_id.strip()
        persisted_leagues = service.repository.league_ids(FOIS_MODEL_VERSION)
        selected_league_id = (
            requested_league_id
            or loaded_league_id
            or (persisted_leagues[0] if len(persisted_leagues) == 1 else "")
        )
        scores = (
            service.repository.league(selected_league_id, FOIS_MODEL_VERSION)
            if selected_league_id else ()
        )
        valid_selection = bool(
            selected_league_id
            and (scores or selected_league_id == loaded_league_id)
        )
        if not valid_selection:
            scores = ()

        ranked_scores = sorted(scores, key=lambda row: (
            -(row.overall_score if row.overall_score is not None else -1),
            -row.confidence, row.gm_id or "",
        ))
        cards = "".join(
            f'<article class="card"><p class="eyebrow">{exact_rank(rank, len(ranked_scores))}</p><h3>{escape(score.gm_name or "GM")}</h3>'
            f'<p class="score">{score.overall_score if score.overall_score is not None else "Insufficient Evidence"} '
            f'{escape(score.overall_letter_grade or "")}</p><p>Confidence: {score.confidence:.0f}%</p>'
            f'<p>Current Team Score: {score.current_team_score if score.current_team_score is not None else "Not yet supported by available evidence"}</p>'
            f'<a href="/fois/gms/{escape(score.gm_id or "")}?league_id={escape(score.league_id)}" data-api-profile="/api/fois/leagues/{escape(score.league_id)}/gms/{escape(score.gm_id or "")}">Open Executive Profile</a></article>'
            for rank, score in enumerate(ranked_scores, 1)
        )
        status = service.status()
        if not selected_league_id:
            content = ('<section class="empty-state" data-dtos-component="empty-state">'
                       '<h2>No valid league is loaded</h2><p>Synchronize a league before opening Front Office Intelligence.</p></section>')
        elif not valid_selection:
            content = ('<section class="empty-state" data-dtos-component="empty-state">'
                       '<h2>League unavailable</h2><p>The requested league is not loaded and has no persisted FOIS profiles.</p></section>')
        elif status.get("state") in {"running", "waiting"} and not scores:
            content = ('<section class="empty-state" data-dtos-component="empty-state">'
                       '<h2>FOIS generation pending</h2><p>Executive profiles will appear after cached FOIS generation completes.</p></section>')
        elif not scores:
            content = ('<section class="empty-state" data-dtos-component="empty-state">'
                       '<h2>FOIS data unavailable</h2><p>No persisted executive profiles exist for this league.</p></section>')
        else:
            content = f'<section id="executive-profiles" class="card-grid">{cards}</section>'

        body = (
            '<nav class="ds-breadcrumbs" aria-label="FOIS sections">'
            '<a href="#gm-rankings">GM Rankings</a><a href="#executive-profiles">Executive Profiles</a>'
            '<a href="/history">Franchise and GM History</a></nav>'
            '<section id="gm-rankings"><h2>GM Rankings</h2>'
            '<p class="muted">GM Quality Is Not Team Quality. Rankings preserve evidence confidence and completeness.</p>'
            f'{content}</section>'
        )
        return page("Front Office Intelligence System", body) if page else HTMLResponse(body)

    @router.get("/fois/gms/{gm_id}", response_class=HTMLResponse)
    async def gm_profile_page(gm_id: str, league_id: str = Query(default="")) -> HTMLResponse:
        data = require_data()
        selected_league = league_id.strip() or str((data.get("league") or {}).get("league_id") or "")
        score = gm_score(selected_league, gm_id)
        rankings = sorted(league_scores(selected_league), key=lambda row: (
            -(row.overall_score if row.overall_score is not None else -1),
            -row.confidence, row.gm_id or "",
        ))
        rank = next((index for index, row in enumerate(rankings, 1) if row.gm_id == gm_id), None)
        categories = "".join(
            f'<article class="card"><h3>{escape(item.category_name)}</h3>'
            f'<p class="score">{item.normalized_score if item.normalized_score is not None else "Insufficient evidence"} {escape(item.letter_grade or "")}</p>'
            f'<p>{escape(item.explanation)}</p><p>Confidence {item.confidence:.0f}% · Evidence completeness {item.completeness:.0f}%</p></article>'
            for item in score.category_scores
        )
        strengths = "".join(f"<li>{escape(item)}</li>" for item in score.strengths) or "<li>No evidence-supported strength is established yet.</li>"
        weaknesses = "".join(f"<li>{escape(item)}</li>" for item in score.weaknesses) or "<li>No evidence-supported weakness is established yet.</li>"
        details = technical_details((("GM identity", score.gm_id), ("FOIS model", score.model_version), ("Brain snapshot", score.brain_snapshot_id), ("Generated", score.generated_at)))
        body = f'''<a class="back" href="/fois?league_id={escape(selected_league)}">← GM Rankings</a><p class="eyebrow">Executive Profile</p><h2>{escape(score.gm_name or "General Manager")}</h2>
<div class="summary-grid"><article class="metric"><b>{exact_rank(rank, len(rankings))}</b><span>League Rank</span></article><article class="metric"><b>{score.overall_score if score.overall_score is not None else "Not ranked"}</b><span>Executive Score</span></article><article class="metric"><b>{score.confidence:.0f}%</b><span>Confidence</span></article><article class="metric"><b>{human_status(score.evidence_state)}</b><span>Evidence State</span></article></div>
<section class="card"><h3>Executive Summary</h3><p>{escape(score.executive_summary)}</p><p><b>Management momentum:</b> {escape(human_status(score.management_momentum))}</p></section>
<div class="card-grid">{categories}</div><div class="grid"><section class="card"><h3>Evidence-supported strengths</h3><ul>{strengths}</ul></section><section class="card"><h3>Evidence-supported opportunities</h3><ul>{weaknesses}</ul></section></div>{details}'''
        return page(f"{score.gm_name or 'GM'} — Executive Profile", body) if page else HTMLResponse(body)

    return router
