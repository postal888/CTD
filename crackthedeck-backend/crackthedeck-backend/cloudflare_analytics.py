"""
CrackTheDeck — Cloudflare Analytics proxy endpoints.

Fetches analytics data from Cloudflare GraphQL API and returns it
for the admin dashboard. Requires CF_API_TOKEN and CF_ZONE_ID env vars.

Usage in admin_api.py:
    from cloudflare_analytics import cf_router
    # Include in main app alongside admin router
"""

import os
import logging
from datetime import datetime, timedelta, timezone
import httpx
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse

from admin_api import require_admin

logger = logging.getLogger("cloudflare_analytics")

cf_router = APIRouter(prefix="/api/admin/cloudflare", tags=["admin-cloudflare"])

CF_API_TOKEN = os.getenv("CF_API_TOKEN", "")
CF_ZONE_ID = os.getenv("CF_ZONE_ID", "80c5c88ae0dd54a867522ed42ee39364")
CF_GRAPHQL_URL = "https://api.cloudflare.com/client/v4/graphql"


async def _cf_query(query: str, variables: dict) -> dict:
    """Execute a Cloudflare GraphQL query."""
    if not CF_API_TOKEN:
        raise HTTPException(503, "Cloudflare API token not configured (set CF_API_TOKEN)")
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            CF_GRAPHQL_URL,
            json={"query": query, "variables": variables},
            headers={
                "Authorization": f"Bearer {CF_API_TOKEN}",
                "Content-Type": "application/json",
            },
        )
    if resp.status_code != 200:
        logger.error(f"Cloudflare API error {resp.status_code}: {resp.text[:500]}")
        raise HTTPException(502, f"Cloudflare API returned {resp.status_code}")
    data = resp.json()
    if data.get("errors"):
        logger.error(f"Cloudflare GraphQL errors: {data['errors']}")
        raise HTTPException(502, data["errors"][0].get("message", "GraphQL error"))
    return data.get("data", {})


# ---------------------------------------------------------------------------
# Overview: requests, bandwidth, unique visitors, threats — last 7 days
# ---------------------------------------------------------------------------

OVERVIEW_QUERY = """
query OverviewAnalytics($zoneTag: string!, $since: string!, $until: string!) {
  viewer {
    zones(filter: {zoneTag: $zoneTag}) {
      httpRequests1dGroups(
        limit: 30
        filter: {date_geq: $since, date_leq: $until}
        orderBy: [date_ASC]
      ) {
        dimensions { date }
        sum {
          requests
          bytes
          cachedBytes
          cachedRequests
          threats
          pageViews
        }
        uniq { uniques }
      }
    }
  }
}
"""


@cf_router.get("/overview")
async def cf_overview(days: int = 7, admin: str = Depends(require_admin)):
    """Get daily aggregated analytics for the last N days."""
    now = datetime.now(timezone.utc)
    since = (now - timedelta(days=days)).strftime("%Y-%m-%d")
    until = now.strftime("%Y-%m-%d")

    data = await _cf_query(OVERVIEW_QUERY, {
        "zoneTag": CF_ZONE_ID,
        "since": since,
        "until": until,
    })

    zones = data.get("viewer", {}).get("zones", [])
    if not zones:
        return JSONResponse({"days": [], "totals": {}})

    groups = zones[0].get("httpRequests1dGroups", [])

    days_data = []
    totals = {"requests": 0, "bytes": 0, "cached_bytes": 0, "cached_requests": 0,
              "threats": 0, "page_views": 0, "unique_visitors": 0}

    for g in groups:
        s = g.get("sum", {})
        u = g.get("uniq", {})
        day = {
            "date": g["dimensions"]["date"],
            "requests": s.get("requests", 0),
            "bytes": s.get("bytes", 0),
            "cached_bytes": s.get("cachedBytes", 0),
            "cached_requests": s.get("cachedRequests", 0),
            "threats": s.get("threats", 0),
            "page_views": s.get("pageViews", 0),
            "unique_visitors": u.get("uniques", 0),
        }
        days_data.append(day)
        for k in totals:
            totals[k] += day[k]

    # Cache hit rate
    if totals["requests"] > 0:
        totals["cache_rate"] = round(totals["cached_requests"] / totals["requests"] * 100, 1)
    else:
        totals["cache_rate"] = 0

    return JSONResponse({"days": days_data, "totals": totals})


# ---------------------------------------------------------------------------
# Top paths, countries, browsers
# ---------------------------------------------------------------------------

TOP_N_QUERY = """
query TopAnalytics($zoneTag: string!, $since: string!, $until: string!) {
  viewer {
    zones(filter: {zoneTag: $zoneTag}) {
      httpRequests1dGroups(
        limit: 1000
        filter: {date_geq: $since, date_leq: $until}
      ) {
        sum {
          countryMap { clientCountryName requests bytes }
          browserMap { uaBrowserFamily pageViews }
          responseStatusMap { edgeResponseStatus requests }
        }
      }
    }
  }
}
"""


@cf_router.get("/top")
async def cf_top(days: int = 7, admin: str = Depends(require_admin)):
    """Get top countries, browsers, and status codes."""
    now = datetime.now(timezone.utc)
    since = (now - timedelta(days=days)).strftime("%Y-%m-%d")
    until = now.strftime("%Y-%m-%d")

    data = await _cf_query(TOP_N_QUERY, {
        "zoneTag": CF_ZONE_ID,
        "since": since,
        "until": until,
    })

    zones = data.get("viewer", {}).get("zones", [])
    if not zones:
        return JSONResponse({"countries": [], "browsers": [], "status_codes": []})

    groups = zones[0].get("httpRequests1dGroups", [])

    # Aggregate across all days
    countries = {}
    browsers = {}
    statuses = {}

    for g in groups:
        s = g.get("sum", {})
        for c in s.get("countryMap", []):
            name = c["clientCountryName"]
            countries[name] = countries.get(name, 0) + c["requests"]
        for b in s.get("browserMap", []):
            name = b["uaBrowserFamily"]
            browsers[name] = browsers.get(name, 0) + b["pageViews"]
        for st in s.get("responseStatusMap", []):
            code = str(st["edgeResponseStatus"])
            statuses[code] = statuses.get(code, 0) + st["requests"]

    return JSONResponse({
        "countries": sorted([{"name": k, "requests": v} for k, v in countries.items()],
                            key=lambda x: -x["requests"])[:15],
        "browsers": sorted([{"name": k, "requests": v} for k, v in browsers.items()],
                           key=lambda x: -x["requests"])[:10],
        "status_codes": sorted([{"code": k, "requests": v} for k, v in statuses.items()],
                               key=lambda x: -x["requests"]),
    })
