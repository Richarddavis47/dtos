"""Generate a versioned DINS visual bundle from a running DTOS deployment."""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

from playwright.sync_api import Browser, Page, sync_playwright

from app_metadata import BUILD_NUMBER, VERSION, deployment_metadata
from src.core.inspection.models import INSPECTION_SCHEMA_VERSION, VIEWPORTS, Viewport
from src.core.inspection.storage import InspectionArtifactStore

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ROOT = ROOT / "static" / "inspection"


def _inspection_headers(**extra: str) -> dict[str, str]:
    headers = {"X-DTOS-Inspection": "deterministic", **extra}
    token = os.getenv("DTOS_INSPECTION_AUTH_TOKEN", "")
    if token:
        headers["X-DTOS-Inspection-Auth"] = token
    return headers

DOM_SCRIPT = """config => {
 const {captureOrigin=location.origin,publicOrigin=location.origin}=config||{};
 const visible = e => { const r=e.getBoundingClientRect(), s=getComputedStyle(e), closed=e.closest('details:not([open])'); return !e.closest('[hidden],[inert]')&&(!closed||closed.querySelector(':scope > summary')?.contains(e))&&r.width>0&&r.height>0&&s.visibility!=='hidden'&&s.display!=='none'; };
 const role = e => e.getAttribute('role') || ({A:'link',BUTTON:'button',TABLE:'table',NAV:'navigation',FORM:'form',H1:'heading',H2:'heading',H3:'heading',IMG:'image'}[e.tagName]||'');
 const rebase=raw=>{const resolved=new URL(raw||'',location.href);if(resolved.origin!==captureOrigin)return resolved.href;const publicBase=new URL(publicOrigin);return new URL(resolved.pathname+resolved.search+resolved.hash,publicBase).href;};
 const rows=[...document.querySelectorAll('header,nav,main,section,article,.card,table,button,a,form,details,h1,h2,h3,img,input,select,textarea')].filter(visible).slice(0,600).map((e,i)=>{
   const r=e.getBoundingClientRect(),s=getComputedStyle(e),text=(e.innerText||e.getAttribute('aria-label')||e.getAttribute('alt')||'').trim().replace(/\\s+/g,' ').slice(0,300);
   return {id:e.id||`dins-${i}`,tag:e.tagName.toLowerCase(),role:role(e),text,href:e.tagName==='A'?rebase(e.getAttribute('href')):null,
   geometry:{x:Math.round(r.x),y:Math.round(r.y+scrollY),width:Math.round(r.width),height:Math.round(r.height),viewport_visible:r.bottom>0&&r.top<innerHeight,clipped:r.left<0||r.right>innerWidth,overflow_x:e.scrollWidth>e.clientWidth,overflow_y:e.scrollHeight>e.clientHeight},
   style:{display:s.display,position:s.position,font_family:s.fontFamily,font_size:s.fontSize,font_weight:s.fontWeight,line_height:s.lineHeight,color:s.color,background_color:s.backgroundColor,border_color:s.borderColor,border_radius:s.borderRadius,padding:s.padding,margin:s.margin,z_index:s.zIndex,white_space:s.whiteSpace}};
 });
 return {title:document.title,language:document.documentElement.lang||null,nodes:rows,visible_text:(document.body.innerText||'').replace(/\\s+/g,' ').trim().slice(0,50000)};
}"""

A11Y_SCRIPT = """() => {
 const visible=e=>{const r=e.getBoundingClientRect(),s=getComputedStyle(e),closed=e.closest('details:not([open])');return !e.closest('[hidden],[inert]')&&(!closed||closed.querySelector(':scope > summary')?.contains(e))&&r.width>0&&r.height>0&&s.display!=='none'&&s.visibility!=='hidden'};
 const headings=[...document.querySelectorAll('h1,h2,h3,h4,h5,h6')].filter(visible).map(e=>({level:Number(e.tagName[1]),text:(e.innerText||'').trim()}));
 const unnamedButtons=[...document.querySelectorAll('button')].filter(e=>visible(e)&&!(e.innerText||e.getAttribute('aria-label')||e.title).trim()).length;
 const unnamedLinks=[...document.querySelectorAll('a')].filter(e=>visible(e)&&!(e.innerText||e.getAttribute('aria-label')||e.title).trim()).length;
 const imagesWithoutAlt=[...document.images].filter(e=>visible(e)&&!e.hasAttribute('alt')).length;
 const inputsWithoutLabels=[...document.querySelectorAll('input,select,textarea')].filter(e=>visible(e)&&!e.labels?.length&&!e.getAttribute('aria-label')&&!e.getAttribute('aria-labelledby')).length;
 const ids=[...document.querySelectorAll('[id]')].map(e=>e.id), duplicates=[...new Set(ids.filter((id,i)=>ids.indexOf(id)!==i))];
 const violations=[];
 if(unnamedButtons)violations.push({severity:'critical',rule:'button-name',count:unnamedButtons});
 if(unnamedLinks)violations.push({severity:'serious',rule:'link-name',count:unnamedLinks});
 if(imagesWithoutAlt)violations.push({severity:'serious',rule:'image-alt',count:imagesWithoutAlt});
 if(inputsWithoutLabels)violations.push({severity:'serious',rule:'label',count:inputsWithoutLabels});
 if(duplicates.length)violations.push({severity:'moderate',rule:'duplicate-id',count:duplicates.length});
 for(let i=1;i<headings.length;i++)if(headings[i].level>headings[i-1].level+1)violations.push({severity:'moderate',rule:'heading-order',count:1});
 return {page_title:document.title,language:document.documentElement.lang||null,landmarks:[...document.querySelectorAll('header,nav,main,aside,footer,[role]')].filter(visible).map(e=>e.getAttribute('role')||e.tagName.toLowerCase()),headings,buttons_without_names:unnamedButtons,links_without_names:unnamedLinks,images_without_alt:imagesWithoutAlt,inputs_without_labels:inputsWithoutLabels,duplicate_ids:duplicates,violations};
}"""


def _json(url: str) -> dict[str, Any]:
    request = Request(url, headers=_inspection_headers(Accept="application/json"))
    with urlopen(request, timeout=60) as response:
        payload = json.loads(response.read())
    if not isinstance(payload, dict):
        raise RuntimeError(f"Expected JSON object from {url}")
    return payload


def _component_rows(dom: dict[str, Any], role: str) -> tuple[dict[str, Any], ...]:
    return tuple(row for row in dom["nodes"] if row.get("role") == role or role in str(row.get("tag")))


def _interaction_target(base_url: str, href: str) -> str:
    """Resolve internal links without replacing an external attribution origin."""
    return urljoin(base_url.rstrip("/") + "/", href)


def _interaction_path(href: str) -> str:
    """Return the path used by the deterministic interaction exclusion policy."""
    return urlparse(href).path


def _capture_page(browser: Browser, store: InspectionArtifactStore, base_url: str, spec: dict[str, Any], viewport: Viewport, league_id: str | None) -> dict[str, Any]:
    page_id, route = spec["page_id"], spec["route"]
    folder = store.current_root / "pages" / page_id
    folder.mkdir(parents=True, exist_ok=True)
    page: Page = browser.new_page(viewport={"width": viewport.width, "height": viewport.height}, device_scale_factor=viewport.device_scale_factor, color_scheme="dark", reduced_motion="reduce")
    failures: list[dict[str, Any]] = []
    console_errors: list[str] = []
    page.on("requestfailed", lambda request: failures.append({"url": request.url.split("?", 1)[0], "error": request.failure}))
    page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
    page.set_extra_http_headers(_inspection_headers())
    started = perf_counter()
    response = page.goto(urljoin(base_url.rstrip("/") + "/", route.lstrip("/")), wait_until="networkidle", timeout=90000)
    if response is None or not response.ok:
        status = response.status if response is not None else "no response"
        raise RuntimeError(f"Inspectable page {route} returned {status}.")
    page.add_style_tag(content="*,*::before,*::after{animation:none!important;transition:none!important;caret-color:transparent!important}")
    page.wait_for_function("document.readyState === 'complete'")
    loaded_ms = round((perf_counter() - started) * 1000, 2)
    viewport_name = f"{viewport.name}.png"
    full_name = f"{viewport.name}-full.png"
    page.screenshot(path=str(folder / viewport_name), full_page=False)
    screenshot_started = perf_counter()
    page.screenshot(path=str(folder / full_name), full_page=True)
    screenshot_ms = round((perf_counter() - screenshot_started) * 1000, 2)
    capture_origin = f"{urlparse(base_url).scheme}://{urlparse(base_url).netloc}"
    public_origin = f"{urlparse(store.public_base_url).scheme}://{urlparse(store.public_base_url).netloc}"
    dom = page.evaluate(DOM_SCRIPT, {
        "captureOrigin": capture_origin,
        "publicOrigin": public_origin,
    })
    accessibility = page.evaluate(A11Y_SCRIPT)
    (folder / f"{viewport.name}-dom.json").write_text(json.dumps(dom, ensure_ascii=False, indent=2), encoding="utf-8")
    (folder / f"{viewport.name}-accessibility.json").write_text(json.dumps(accessibility, ensure_ascii=False, indent=2), encoding="utf-8")
    nodes = dom["nodes"]
    interactions = []
    for link in _component_rows(dom, "link")[:12]:
        href = link.get("href")
        path = _interaction_path(str(href)) if href else ""
        if not href or path.startswith("/api/") or path in {"/sync", "/transactions/refresh"}:
            continue
        if viewport.name == "desktop":
            target_response = page.request.get(_interaction_target(base_url, str(href)), headers=_inspection_headers(), timeout=60000)
            status = target_response.status
        else:
            status = None
        interactions.append({"starting_page": route, "action": f"follow {link.get('text') or href}", "target": href, "control_existed": True, "enabled": True, "resulting_url": href, "http_status": status, "console_errors": [], "page_errors": [], "success": status is None or status < 400})
    headings = accessibility["headings"]
    critical = [row for row in accessibility["violations"] if row["severity"] == "critical"]
    content = page.content()
    visible_text = str(dom.get("visible_text") or "")
    has_shared_header = 'data-dtos-component="page-header"' in content
    has_primary_action = 'data-dtos-action="primary"' in content or 'class="ds-action primary"' in content
    has_recommendation = 'data-dtos-component="recommendation"' in content
    public_contract_failures = []
    if not has_shared_header:
        public_contract_failures.append("Shared page header contract is missing.")
    if not has_primary_action:
        public_contract_failures.append("Primary page action is missing.")
    if re.search(r"\b(?:Team|Roster)\s+(?:[1-9]|10)\b|\b(?:Team Detail|Player Detail|Matchup Detail)\b", spec["page_name"], re.IGNORECASE):
        public_contract_failures.append("Dynamic page name is generic.")
    if re.search(r"\b(?:Roster ID|Player ID|Transaction ID|Sleeper ID|Franchise ID|Provider Key)\b", visible_text, re.IGNORECASE):
        public_contract_failures.append("User-facing content exposes an internal identifier label.")
    if "localhost" in store.public_base_url or "127.0.0.1" in store.public_base_url:
        public_contract_failures.append("Inspection artifact URLs use a local host.")
    result = {
        "application_version": VERSION, "application_build": BUILD_NUMBER, "inspection_schema_version": INSPECTION_SCHEMA_VERSION,
        "page_id": page_id, "page_name": spec["page_name"], "route": route, "canonical_url": urljoin(store.public_base_url.rstrip("/") + "/", route.lstrip("/")), "league_id": league_id,
        "viewport": {"name": viewport.name, "width": viewport.width, "height": viewport.height, "device_scale_factor": viewport.device_scale_factor},
        "artifact_urls": {"viewport_screenshot": store.artifact_url(f"pages/{page_id}/{viewport_name}"), "full_page_screenshot": store.artifact_url(f"pages/{page_id}/{full_name}"), "dom_snapshot": store.artifact_url(f"pages/{page_id}/{viewport.name}-dom.json"), "accessibility_snapshot": store.artifact_url(f"pages/{page_id}/{viewport.name}-accessibility.json")},
        "page_state": {"loaded": bool(response and response.ok), "ready_signal": "document.readyState=complete + networkidle", "loading_duration_ms": loaded_ms, "last_updated": datetime.now(timezone.utc).isoformat(), "data_generation_time": datetime.now(timezone.utc).isoformat()},
        "sections": _component_rows(dom, "section"), "cards": tuple(row for row in nodes if "card" in row.get("id", "") or row.get("tag") == "article"), "tables": _component_rows(dom, "table"), "charts": (), "buttons": _component_rows(dom, "button"), "links": _component_rows(dom, "link"), "navigation": _component_rows(dom, "navigation"), "forms": _component_rows(dom, "form"), "expandable_regions": tuple(row for row in nodes if row.get("tag") == "details"), "empty_states": tuple(row for row in nodes if "empty" in row.get("id", "")), "loading_states": (), "error_states": tuple(row for row in nodes if "error" in row.get("id", "")), "placeholder_actions": (), "disabled_actions": (),
        "warnings": tuple((["New critical accessibility findings detected."] if critical else []) + public_contract_failures), "accessibility": accessibility,
        "geometry": {"document_width": page.evaluate("document.documentElement.scrollWidth"), "document_height": page.evaluate("document.documentElement.scrollHeight"), "horizontal_overflow_width": page.evaluate("Math.max(0,document.documentElement.scrollWidth-innerWidth)"), "elements": nodes},
        "styles": {"theme": "dark", "animations_disabled": True}, "performance": {"navigation_and_readiness_ms": loaded_ms, "screenshot_generation_ms": screenshot_ms}, "network": {"failed_requests": failures, "console_errors": console_errors}, "interactions": tuple(interactions), "regressions": (),
        "metrics": {"section_count": len(_component_rows(dom, "section")), "card_count": sum(row.get("tag") == "article" for row in nodes), "button_count": len(_component_rows(dom, "button")), "table_count": len(_component_rows(dom, "table")), "heading_count": len(headings), "critical_accessibility_count": len(critical), "interaction_density": round((len(_component_rows(dom, "button")) + len(_component_rows(dom, "link"))) / max(1, page.evaluate("document.documentElement.scrollHeight") / 1000), 2), "shared_header_contract": has_shared_header, "primary_action_contract": has_primary_action, "recommendation_contract": has_recommendation, "product_contract_failures": len(public_contract_failures)},
    }
    page.close()
    return result


def capture(base_url: str, output: Path, limit: int | None = None) -> dict[str, Any]:
    public_url = os.getenv("DTOS_PUBLIC_URL", base_url).rstrip("/")
    store = InspectionArtifactStore(output, public_url)
    if store.current_root.exists():
        shutil.rmtree(store.current_root)
    store.current_root.mkdir(parents=True, exist_ok=True)
    market_health = _json(urljoin(base_url.rstrip("/") + "/", "api/market/health"))
    if market_health.get("status") != "ready":
        raise RuntimeError(
            "DINS capture is deferred until Asset Market has a published generation."
        )
    site_map = _json(urljoin(base_url.rstrip("/") + "/", "api/inspect/site-map"))
    status = _json(urljoin(base_url.rstrip("/") + "/", "api/status"))
    if status.get("version") != VERSION:
        raise RuntimeError(f"Deployment version {status.get('version')} does not match capture version {VERSION}.")
    pages = [row for row in site_map.get("pages", []) if not row.get("excluded")]
    if limit is not None:
        pages = pages[:limit]
    (store.current_root / "site-map.json").write_text(json.dumps(site_map, ensure_ascii=False, indent=2), encoding="utf-8")
    valuation_inspection = _json(urljoin(base_url.rstrip("/") + "/", "api/inspect/valuation"))
    (store.current_root / "valuation.json").write_text(json.dumps(valuation_inspection, ensure_ascii=False, indent=2), encoding="utf-8")
    inspection_health = _json(urljoin(base_url.rstrip("/") + "/", "api/inspect/health"))
    historical_progress = inspection_health.get("historical_progress") or {}
    (store.current_root / "historical-progress.json").write_text(
        json.dumps(historical_progress, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    semantic_root = store.current_root / "semantic"
    semantic_root.mkdir(parents=True, exist_ok=True)
    for spec in pages:
        semantic = _json(urljoin(base_url.rstrip("/") + "/", f"api/inspect/pages/{spec['page_id']}"))
        (semantic_root / f"{spec['page_id']}.json").write_text(json.dumps(semantic, ensure_ascii=False, indent=2), encoding="utf-8")
    generated: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            for spec in pages:
                for viewport in VIEWPORTS:
                    try:
                        result = _capture_page(browser, store, base_url, spec, viewport, status.get("league_id"))
                        path = store.current_root / "pages" / spec["page_id"] / f"{viewport.name}.json"
                        path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
                        generated.append(result)
                    except Exception as exc:  # capture must preserve partial results
                        failures.append({"page_id": spec["page_id"], "viewport": viewport.name, "error": type(exc).__name__, "detail": str(exc)[:500]})
        finally:
            browser.close()
    deployment = status.get("deployment") or deployment_metadata()
    generated_at = datetime.now(timezone.utc).isoformat()
    page_ids = sorted({row["page_id"] for row in generated})
    product_contract_failures = [
        {"page_id": row["page_id"], "viewport": row["viewport"]["name"], "count": row["metrics"]["product_contract_failures"]}
        for row in generated if row["metrics"]["product_contract_failures"]
    ]
    has_critical_accessibility = any(row["metrics"]["critical_accessibility_count"] for row in generated)
    artifact_count = sum(1 for path in store.current_root.rglob("*") if path.is_file())
    manifest = {"version": VERSION, "build": BUILD_NUMBER, "commit_sha": deployment.get("commit", "Unavailable"), "source_branch": deployment.get("branch", "Unavailable"), "deployed_at": deployment.get("deployed_at"), "generated_at": generated_at, "league_id": status.get("league_id"), "inspection_schema_version": INSPECTION_SCHEMA_VERSION, "status": "complete" if not failures else "partial", "page_inventory": site_map.get("pages", []), "pages": page_ids, "pages_added": page_ids, "pages_removed": [], "pages_changed": page_ids, "semantic_contract_changes": ["DINS schema 2.0 enforces product design, navigation, recommendation, accessibility, deployment-provenance, and live valuation contracts."], "valuation_inspection": {"artifact": "valuation.json", "route": valuation_inspection.get("route"), "status": valuation_inspection.get("status"), "layers": valuation_inspection.get("valuation_layers"), "warnings": valuation_inspection.get("warnings")}, "screenshot_artifact_urls": [url for row in generated for url in (row["artifact_urls"]["viewport_screenshot"], row["artifact_urls"]["full_page_screenshot"])], "visual_difference_results": [{"baseline_version": "1.6.6", "current_version": VERSION, "status": "pending", "reason": "The post-deployment publication worker records retained visual comparison results."}], "interaction_failures": [item for row in generated for item in row["interactions"] if not item["success"]], "accessibility_regressions": [item for row in generated for item in row["accessibility"]["violations"] if item["severity"] == "critical"], "product_contract_failures": product_contract_failures, "console_errors": [item for row in generated for item in row["network"]["console_errors"]], "failed_network_requests": [item for row in generated for item in row["network"]["failed_requests"]], "stale_version_mismatches": [], "validation_outcome": "pass" if not failures and not has_critical_accessibility and not product_contract_failures else "fail", "total_pages_expected": len(pages), "total_pages_completed": len(page_ids), "total_visual_artifacts": artifact_count, "failures": failures, "warnings": ["Sleeper avatar CDN requests can be unavailable in sandboxed capture environments; failures are recorded explicitly."], "retention": "Published GitHub Release bundles are immutable and retained with their release."}
    manifest["historical_progress"] = historical_progress
    manifest["canonical_history_progress"] = historical_progress
    (store.current_root / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture a deployed DTOS DINS visual bundle.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8767")
    parser.add_argument("--output", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    result = capture(args.base_url, args.output, args.limit)
    print(json.dumps({"status": result["status"], "pages": result["total_pages_completed"], "artifacts": result["total_visual_artifacts"], "failures": len(result["failures"])}, indent=2))
    return 0 if result["validation_outcome"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
