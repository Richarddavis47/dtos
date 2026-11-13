"""Customer explanation controls over unchanged account and specialist evidence."""
from dataclasses import asdict, replace
from html.parser import HTMLParser
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from components.commissioner import commissioner_desk, front_office_summary
from components.front_office_intelligence import front_office_center
from services.front_office_intelligence import build_front_office_center
from src.core.competitive_window.models import CompetitiveWindowClassification
from tests import test_accounts_v11061 as account_controls
from tests import test_commissioner as commissioner_controls
from tests import test_fois_presentation as fois_controls
from tests import test_personal_rankings as ranking_controls
from tests.test_trade_intelligence import fixture_data


class VisibleText(HTMLParser):
    """Native closed disclosures retain evidence but not default body copy."""
    def __init__(self, html):
        super().__init__()
        self.stack = []
        self.text = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        if tag not in {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}:
            self.stack.append((tag, dict(attrs)))

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == tag:
                del self.stack[index:]
                break

    def handle_data(self, data):
        for index, (tag, attrs) in enumerate(self.stack):
            if tag in {"style", "script"} or "hidden" in attrs:
                return
            if tag == "details" and "open" not in attrs:
                if index + 1 >= len(self.stack) or self.stack[index + 1][0] != "summary":
                    return
        self.text.append(data)

    @property
    def value(self):
        return " ".join(" ".join(self.text).split())


class CustomerSpecialistPresentationTests(unittest.TestCase):
    def test_missing_outlook_is_not_a_franchise_classification_and_original_is_retained(self):
        view = build_front_office_center(fixture_data(), 1)
        active = view["active"]
        window = replace(active.competitive_window,
                         classification=CompetitiveWindowClassification.UNAVAILABLE,
                         reasons=("Compatible league/week/scoring projection publication unavailable.",))
        active = replace(active, competitive_window=window,
                         executive_summary="Alpha is currently classified as Unavailable.")
        view = {**view, "active": active}
        before = asdict(active)
        html = front_office_center(view)
        visible = VisibleText(html).value
        self.assertIn("Outlook not established", visible)
        self.assertIn("not enough supported evidence", visible)
        self.assertNotIn("classified as Unavailable", visible)
        self.assertIn("Alpha is currently classified as Unavailable.", html)
        self.assertIn("Projections are not ready for this league, week and scoring.", html)
        self.assertIn("Observed franchise activity", visible)
        self.assertIn("not a qualified offer", visible)
        self.assertIn('href="/teams/1"', html)
        self.assertEqual(asdict(active), before)

    def test_supported_profile_preserves_score_and_possible_partner_evidence_without_recalculation(self):
        view = build_front_office_center(fixture_data(), 1)
        before = asdict(view["active"])
        with patch("services.front_office_intelligence.build_front_office_center", side_effect=AssertionError("render must not prepare")):
            html = front_office_center(view)
        for partner in view["compatibilities"]:
            self.assertIn(f"Roster-context fit: {partner.score}/100", html)
            self.assertIn("Why this partner may fit", html)
        self.assertNotIn("Show Evidence & Forecast", html)
        self.assertEqual(asdict(view["active"]), before)

    def test_commissioner_keeps_zero_and_moves_unsupported_assessments_out_of_default_cards(self):
        fixture = commissioner_controls.CommissionerDeskTests()
        fixture.setUp()
        view = fixture.build()
        summary = dict(view["front_office_summary"])
        summary["lineup_evidence"] = SimpleNamespace(optimal_lineup_projection=0, projection_week=4,
                                                    projection_covered=0, roster_count=0,
                                                    limitations=("Projection coverage is incomplete.",))
        view = {**view, "front_office_summary": summary}
        html = front_office_summary(view)
        visible = VisibleText(html).value
        self.assertIn("0 projected points", visible)
        self.assertIn("Projection coverage is incomplete.", visible)
        self.assertNotIn("Score unavailable", visible)
        self.assertIn("Other assessment limits", visible)
        self.assertIn("No result is established for:", html)
        full = commissioner_desk(view)
        self.assertNotIn("Future explanation hook", full)
        self.assertIn("Detailed Evidence", full)
        self.assertNotIn("Four engines / one answer", full)

    def test_recorded_pick_headline_does_not_claim_inventory_completeness(self):
        fixture = commissioner_controls.CommissionerDeskTests()
        fixture.setUp()
        view = fixture.build()
        before = tuple(view["headlines"])
        html = commissioner_desk(view)
        visible = VisibleText(html).value
        self.assertIn("largest recorded pick list", visible)
        self.assertIn("does not establish a complete pick inventory", visible)
        self.assertNotIn("largest future-pick inventory", visible)
        self.assertNotIn("Current complete future-pick ledger", visible)
        self.assertEqual(tuple(view["headlines"]), before)

    def test_account_routes_use_account_language_without_claiming_control_verification(self):
        fixture = account_controls.AccountOnboardingPresentationTests()
        fixture.setUp()
        self.addCleanup(fixture.tearDown)
        with patch.dict("os.environ", fixture.fixture, clear=False):
            account = fixture.client.get("/account", headers=fixture.headers)
            connect = fixture.client.get("/account/sleeper", headers=fixture.headers)
            leagues = fixture.client.get("/account/leagues", headers=fixture.headers)
        self.assertEqual(account.status_code, 200)
        self.assertIn("Sleeper account:", account.text)
        self.assertIn("control not independently verified", account.text)
        self.assertIn("does not provide proof that you control", connect.text)
        self.assertNotIn("resolved Sleeper identity", VisibleText(connect.text).value)
        self.assertIn("matches exactly one team", leagues.text)
        self.assertIn('name="csrf_token"', connect.text)
        self.assertNotIn("presentation-secret", account.text)

    def test_custom_editor_keeps_exact_method_contract_and_does_not_write_on_open(self):
        fixture = ranking_controls.PersonalRankingsHTTPTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        before = fixture.state()
        response = fixture.client.get('/account/my-dtos')
        after = fixture.state()
        self.assertEqual(response.status_code, 200)
        self.assertIn("Your order sets your personal values", response.text)
        self.assertIn("Absolute Slot uses each saved rank", response.text)
        self.assertIn("Relative Priced-Order uses the order of assets with Market prices", response.text)
        self.assertIn('id="personal-method-confirm"', response.text)
        self.assertIn('id="personal-method-preview"', response.text)
        self.assertNotIn("new preference revision", response.text)
        self.assertEqual(before['revision'], after['revision'])
        self.assertEqual(before['mode'], after['mode'])
        self.assertEqual([r['asset_id'] for r in before['rows']], [r['asset_id'] for r in after['rows']])

    def test_fois_pending_missing_and_retained_remain_distinct_without_regrading(self):
        fixture = fois_controls.FOISPresentationTests()
        fixture.setUp()
        self.addCleanup(fixture.tearDown)
        status = fixture.service.status()
        self.assertEqual(status['state'], 'waiting')
        with patch.object(fixture.service, 'generate', side_effect=AssertionError('no generation')):
            with fixture._client() as client:
                waiting = client.get('/fois')
                with patch.object(fixture.service, 'status', return_value={**status, 'state': 'running'}):
                    pending = client.get('/fois')
        self.assertIn("Manager profiles are not prepared yet", waiting.text)
        self.assertIn("No saved manager profiles are available for this league yet", waiting.text)
        self.assertNotIn("are being prepared", waiting.text)
        self.assertIn("Manager profiles are being prepared", pending.text)
        self.assertNotIn("Manager grades are not available", pending.text)
        with fixture._client(Mock(return_value={})) as client:
            missing = client.get('/fois')
        self.assertIn("Choose a league first", missing.text)
        score = fixture._persist_profiles('active-league', 1)[0]
        retained = replace(score, evidence_integrity_version=None,
                           evidence_state="retained_not_revalidated")
        self.assertFalse(retained.evidence_revalidated)
        fixture.repository.save(retained, 'retained-customer-control')
        before = fixture.repository.league('active-league', score.model_version)
        with patch.object(fixture.service, 'generate', side_effect=AssertionError('no generation')):
            with fixture._client() as client:
                rendered = client.get('/fois')
                profile = client.get('/fois/gms/gm-0')
        self.assertIn('RETAINED / NOT REVALIDATED', rendered.text)
        self.assertIn('Category grades and supporting evidence', profile.text)
        self.assertNotIn('Supported Weight', VisibleText(profile.text).value)
        self.assertEqual(before, fixture.repository.league('active-league', score.model_version))
