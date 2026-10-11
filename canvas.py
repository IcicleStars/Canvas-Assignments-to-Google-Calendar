import os
import requests
from datetime import datetime, timezone, timedelta
from dateutil import parser


def fetch_canvas_calendar(domain: str, token: str, days_ahead: int = 70) -> list:
    """Fetches assignments and calendar events across all active courses."""
    headers = {"Authorization": f"Bearer {token}"}
    now = datetime.now(timezone.utc)
    end_date = now + timedelta(days=days_ahead)

    # fetch active courses to map course names
    courses_url = f"https://{domain}/api/v1/courses"
    courses_resp = requests.get(
        courses_url,
        headers=headers,
        params={"enrollment_state": "active", "per_page": 50},
    )
    courses_resp.raise_for_status()

    course_map = {}
    context_codes = []
    for c in courses_resp.json():
        if "id" in c and "name" in c:
            c_id = c["id"]
            course_map[f"course_{c_id}"] = c.get("course_code") or c.get("name", "Course")
            context_codes.append(f"course_{c_id}")

    items = []

    # fetch assignments directly from calendar events api (resolves section overrides)
    cal_url = f"https://{domain}/api/v1/calendar_events"
    params = {
        "type": "assignment",
        "start_date": (now - timedelta(days=2)).strftime("%Y-%m-%d"),
        "end_date": end_date.strftime("%Y-%m-%d"),
        "context_codes[]": context_codes,
        "all_events": "true",
        "per_page": 100,
    }

    while cal_url:
        resp = requests.get(cal_url, headers=headers, params=params)
        if resp.status_code != 200:
            break

        for a in resp.json():
            start_at = a.get("start_at") or a.get("end_at")
            if not start_at:
                continue

            due_dt = parser.parse(start_at)
            if due_dt < (now - timedelta(days=2)) or due_dt > end_date:
                continue

            title = a.get("title", "Assignment")
            title_lower = title.lower()
            context_code = a.get("context_code", "")
            course_name = course_map.get(context_code, "Course")

            # submission status
            assignment_data = a.get("assignment", {})
            sub = assignment_data.get("submission") or {}
            is_submitted = sub.get("workflow_state") in ["submitted", "graded"]

            # exams vs standard assignments
            sub_types = assignment_data.get("submission_types", [])
            is_paper_or_none = set(sub_types).issubset({"on_paper", "none", "not_graded"})
            is_exam = any(k in title_lower for k in ["exam", "midterm", "final"]) or (
                is_paper_or_none and "quiz" in title_lower
            )

            item_type = "EXAM" if is_exam else "ASSIGNMENT"

            items.append({
                "id": f"canvas_assign_{a['id']}",
                "title": title,
                "course_name": course_name,
                "type": item_type,
                "is_submitted": is_submitted,
                "start_dt": due_dt,
                "end_dt": due_dt + timedelta(minutes=1),
                "url": a.get("html_url", f"https://{domain}/calendar"),
            })

        cal_url = resp.links.get("next", {}).get("url")
        params = {}

    # fetch calendar events
    event_url = f"https://{domain}/api/v1/calendar_events"
    event_params = {
        "type": "event",
        "start_date": (now - timedelta(days=2)).strftime("%Y-%m-%d"),
        "end_date": end_date.strftime("%Y-%m-%d"),
        "context_codes[]": context_codes,
        "all_events": "true",
        "per_page": 100,
    }

    while event_url:
        resp = requests.get(event_url, headers=headers, params=event_params)
        if resp.status_code != 200:
            break

        for ev in resp.json():
            start_at = ev.get("start_at")
            end_at = ev.get("end_at") or start_at
            if not start_at:
                continue

            start_dt = parser.parse(start_at)
            end_dt = parser.parse(end_at)
            if end_dt <= start_dt:
                end_dt = start_dt + timedelta(hours=1)

            title = ev.get("title", "Event")
            title_lower = title.lower()
            context_code = ev.get("context_code", "")
            course_name = course_map.get(context_code, "Course")
            is_exam = any(k in title_lower for k in ["exam", "midterm", "final"])

            items.append({
                "id": f"canvas_event_{ev['id']}",
                "title": title,
                "course_name": course_name,
                "type": "EXAM" if is_exam else "EVENT",
                "is_submitted": False,
                "start_dt": start_dt,
                "end_dt": end_dt,
                "url": ev.get("html_url", f"https://{domain}/calendar"),
            })

        event_url = resp.links.get("next", {}).get("url")
        event_params = {}

    return items