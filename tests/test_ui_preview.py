"""The dev-only UI preview server: real templates, canned API."""

import json
from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient

from scripts.ui_preview import build_app
from scripts.ui_preview_fixtures import EMPTY_FIXTURES, FIXTURES

SOME_ID = "11111111-1111-4111-8111-111111111111"


def _client(scenario: str = "normal") -> AsyncClient:
    transport = ASGITransport(app=build_app(scenario))
    return AsyncClient(transport=transport, base_url="http://preview", follow_redirects=False)


@pytest.mark.parametrize("path", ["/dashboard", "/proxies", "/pools", "/projects", "/settings"])
async def test_pages_render_without_a_session(path):
    resp = await _client().get(path)
    assert resp.status_code == 200
    assert "<html" in resp.text.lower()


async def test_api_answers_from_fixtures():
    resp = await _client().get("/api/v1/stats/overview")
    assert resp.status_code == 200
    assert resp.json() == FIXTURES[("GET", "stats/overview")]


async def test_uuid_segments_match_id_placeholders():
    resp = await _client().get(f"/api/v1/projects/{SOME_ID}/stats")
    assert resp.status_code == 200
    assert resp.json() == FIXTURES[("GET", "projects/{id}/stats")]


async def test_detail_endpoints_answer_with_the_matching_list_item():
    """GET projects/<id> must describe the project that was clicked, not always the first one."""
    projects = FIXTURES[("GET", "projects")]["data"]
    second = projects[1]
    resp = await _client().get(f"/api/v1/projects/{second['id']}")
    assert resp.status_code == 200
    assert resp.json()["name"] == second["name"]


@pytest.mark.parametrize(("granularity", "count"), [("5min", 12), ("1hour", 24), ("1day", 7)])
async def test_timeseries_is_generated_relative_to_now(granularity, count):
    resp = await _client().get(f"/api/v1/stats/timeseries?granularity={granularity}&hours=24")
    body = resp.json()
    assert body["granularity"] == granularity
    assert len(body["data"]) == count
    point = body["data"][-1]
    assert set(point) == set(FIXTURES[("GET", "stats/timeseries")]["data"][0])
    assert point["successful_requests"] + point["failed_requests"] == point["total_requests"]
    newest = datetime.fromisoformat(point["period_start"].replace("Z", "+00:00"))
    assert datetime.now(UTC) - newest < timedelta(days=2)


async def test_timeseries_is_empty_in_the_empty_scenario():
    resp = await _client("empty").get("/api/v1/stats/timeseries?granularity=1hour")
    assert resp.json() == {"granularity": "1hour", "data": []}


async def test_proxy_list_honours_pool_status_and_search_filters():
    everything = FIXTURES[("GET", "ips")]["data"]
    dead = (await _client().get("/api/v1/ips?status=dead")).json()
    assert dead["data"] and all(p["last_health_status"] == "dead" for p in dead["data"])
    assert dead["meta"]["total"] == len(dead["data"]) < len(everything)
    pool_id = FIXTURES[("GET", "pools")]["data"][0]["id"]
    members = (await _client().get(f"/api/v1/ips?pool_id={pool_id}")).json()
    assert 0 < len(members["data"]) < len(everything)
    host = everything[0]["host"]
    found = (await _client().get(f"/api/v1/ips?search={host}")).json()
    assert [p["host"] for p in found["data"]] == [host]


async def test_no_content_fixture_returns_204():
    resp = await _client().delete(f"/api/v1/ips/{SOME_ID}")
    assert resp.status_code == 204


async def test_empty_scenario_serves_an_empty_instance():
    resp = await _client("empty").get("/api/v1/ips")
    assert resp.status_code == 200
    assert resp.json() == EMPTY_FIXTURES[("GET", "ips")]


async def test_offline_scenario_fails_every_api_call_but_still_serves_pages():
    client = _client("offline")
    assert (await client.get("/api/v1/stats/overview")).status_code == 503
    assert (await client.get("/dashboard")).status_code == 200


async def test_scenario_can_be_switched_at_runtime():
    client = _client()
    assert (await client.get("/__scenario/offline")).status_code == 200
    assert (await client.get("/api/v1/pools")).status_code == 503
    assert (await client.get("/__scenario/bogus")).status_code == 404


async def test_unknown_endpoint_is_a_json_404_not_a_crash():
    resp = await _client().get("/api/v1/does/not/exist")
    assert resp.status_code == 404
    assert "no fixture" in resp.json()["detail"]


def test_every_empty_fixture_has_a_normal_twin():
    assert set(EMPTY_FIXTURES) <= set(FIXTURES)


def test_fixture_keys_use_only_the_id_placeholder():
    """The server turns EVERY uuid segment into {id}; a key like pools/{pool_id} can never match."""
    for _method, pattern in FIXTURES:
        assert "{" not in pattern.replace("{id}", ""), pattern


def test_fixtures_include_a_hostile_long_name():
    """Review Focus 3: the UI must survive markup and very long names."""
    blob = json.dumps(list(FIXTURES.values()))
    assert "<script>" in blob
    assert any(len(p["name"]) > 60 for p in FIXTURES[("GET", "pools")]["data"])
