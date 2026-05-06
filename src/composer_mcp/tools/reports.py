"""Scheduled PDF reports (a.k.a. dashboard subscriptions).

Composer exposes scheduled PDF exports per dashboard at
`/api/dashboards/{id}/reports`. Each entry has a name, a schedule
(`{frequency: DAILY|WEEKLY|MONTHLY, dayOfWeek, dayOfMonth, timeOfDay,
startDate, endDate}`), a format (`PDF`), and optional recipients.

This module covers the read side. Creating subscriptions via the API works
(POST same path, body shape per the v25 OpenAPI), but most teams configure
them via the UI Subscribe dialog because that path also wires up email
templating and consents.
"""

from __future__ import annotations

from ..client import ComposerClient


async def list_dashboard_reports(client: ComposerClient, dashboard_id: str) -> list[dict]:
    """List scheduled PDF reports configured on a dashboard.

    Returns entries shaped like:
      {name, schedule: {frequency, dayOfWeek?, dayOfMonth?, timeOfDay,
                        startDate, endDate}, format, enabled}
    """
    items = await client.get_list(f"/dashboards/{dashboard_id}/reports")
    return [
        {
            "id": r.get("id"),
            "name": r.get("name"),
            "schedule": r.get("schedule") or r.get("cron") or r.get("frequency"),
            "format": r.get("format"),
            "enabled": r.get("enabled", True),
        }
        for r in items
        if isinstance(r, dict)
    ]


async def create_dashboard_report(
    client: ComposerClient,
    dashboard_id: str,
    name: str,
    schedule: dict,
    format: str = "PDF",
    recipients: list[str] | None = None,
) -> dict:
    """Create a scheduled PDF subscription on a dashboard.

    `schedule` shape (mirrors what the UI Subscribe dialog produces):

      Daily:  {"frequency": "DAILY",  "timeOfDay": "07:00:00",
               "startDate": "2026-05-06", "endDate": "2026-06-17"}
      Weekly: {"frequency": "WEEKLY", "dayOfWeek": "MONDAY",
               "timeOfDay": "08:00:00", "startDate": ..., "endDate": ...}
      Monthly:{"frequency": "MONTHLY", "dayOfMonth": 1,
               "timeOfDay": "09:00:00", "startDate": ..., "endDate": ...}

    Recipients accepted as plain email strings.
    """
    body: dict = {"name": name, "schedule": schedule, "format": format}
    if recipients:
        body["recipients"] = [{"email": r} for r in recipients]
    return await client.post(f"/dashboards/{dashboard_id}/reports", body)
