import os
import requests
from datetime import datetime, timezone, timedelta
from dateutil import parser


def fetch_canvas_calendar(domain: str, token: str, days_ahead: int = 45) -> list:
    """Fetches assignments and calendar events across all active courses."""
    headers = {"Authorization": f"Bearer {token}"}
    now = datetime.now(timezone.utc)
    end_date = now + timedelta(days=days_ahead)

    # fetch active courses
    courses_url = f"https://{domain}/api/v1/courses"
    courses_resp = requests.get(
        courses_url,
        headers=headers,
        params={"enrollment_state": "active", "per_page": 50},
    )
    courses_resp.raise_for_status()
    courses = [
        c for c in courses_resp.json()
        if "name" in c and not c.get("access_restricted_by_date")
    ]

    items = []

    for course in courses:
        course_id = course["id"]
        course_name = course.get("course_code") or course.get("name", "Course")

        # fetch assignments
        assign_url = f"https://{domain}/api/v1/courses/{course_id}/assignments"
        assign_resp = requests.get(
            assign_url,
            headers=headers,
            params={
                "include[]": "submission",
                "per_page": 100,
                "order_by": "due_at",
            },
        )
        if assign_resp.status_code == 200:
            for a in assign_resp.json():
                due_at = a.get("due_at")
                if not due_at:
                    continue

                due_dt = parser.parse(due_at)
                if due_dt < (now - timedelta(days=2)) or due_dt > end_date:
                    continue

                title = a.get("name", "Assignment")
                title_lower = title.lower()

                # submission status
                sub = a.get("submission") or {}
                is_submitted = sub.get("workflow_state") in ["submitted", "graded"]

                # exams vs standard assignments
                sub_types = a.get("submission_types", [])
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
                    "start_dt": due_dt - timedelta(minutes=30),
                    "end_dt": due_dt,
                    "url": a.get(
                        "html_url",
                        f"https://{domain}/courses/{course_id}/assignments/{a['id']}",
                    ),
                })

        #  fetch calendar events
        cal_url = f"https://{domain}/api/v1/calendar_events"
        cal_resp = requests.get(
            cal_url,
            headers=headers,
            params={
                "context_codes[]": f"course_{course_id}",
                "type": "event",
                "start_date": (now - timedelta(days=2)).strftime("%Y-%m-%d"),
                "end_date": end_date.strftime("%Y-%m-%d"),
                "all_events": "true",
                "per_page": 50,
            },
        )
        if cal_resp.status_code == 200:
            for ev in cal_resp.json():
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

    return items