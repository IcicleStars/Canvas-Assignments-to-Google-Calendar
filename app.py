import os
from dotenv import load_dotenv
from canvas import fetch_canvas_calendar
from gcal import get_gcal, create_calendar

load_dotenv()

CANVAS_DOMAIN = os.getenv("CANVAS_DOMAIN", "").strip().rstrip("/")
CANVAS_TOKEN = os.getenv("CANVAS_TOKEN", "").strip()
CALENDAR_NAME = os.getenv("GOOGLE_CALENDAR_NAME", "Canvas Deadlines")


def sync_events(service, calendar_id, items):
    # get existing events and ignore
    existing_events = (
        service.events().list(
            calendarId=calendar_id,
            privateExtendedProperty="app=canvas_sync",
            showDeleted = False,
            maxResults=2500,
        )
        .execute()
        .get("items", [])
    )

    # exclude cancelled items from lookup map
    gcal_map = {
        e["extendedProperties"]["private"]["canvas_id"]: e
        for e in existing_events
        if e.get("status") != "cancelled" and "extendedProperties" in e and "private" in e["extendedProperties"]
    }

    created = 0
    updated = 0
    deleted = 0

    for item in items:
        item_id = item["id"]
        item_type = item["type"]
        title = item["title"]
        course_name = item["course_name"]
        is_submitted = item["is_submitted"]

        # remove submitted assignments from Google Calendar
        if is_submitted:
            if item_id in gcal_map:
                service.events().delete(
                    calendarId=calendar_id,
                    eventId=gcal_map[item_id]["id"],
                ).execute()
                deleted += 1
            continue

        # determine event summary and color based on item type
        if item_type == "EXAM":
            summary = f"[EXAM] {title} ({course_name})"
            color_id = "11"  # flamingo
        elif item_type == "EVENT":
            summary = f"[EVENT] {title} ({course_name})"
            color_id = "7"   # peacock
        else:
            summary = f"[DUE] {title} ({course_name})"
            color_id = "11"  # flamingo

        event_payload = {
            "summary": summary,
            "description": (
                f"Course: {course_name}\n"
                f"Type: {item_type}\n"
                f"Status: Pending\n"
                f"Link: {item['url']}"
            ),
            "start": {"dateTime": item["start_dt"].isoformat()},
            "end": {"dateTime": item["end_dt"].isoformat()},
            "colorId": color_id,
            "extendedProperties": {
                "private": {
                    "app": "canvas_sync",
                    "canvas_id": item_id,
                    "type": item_type,
                }
            },
        }

        if item_id in gcal_map:
            existing = gcal_map[item_id]
            needs_update = (
                existing.get("summary") != summary
                or existing.get("end", {}).get("dateTime") != item["end_dt"].isoformat()
                or existing.get("colorId") != color_id
            )
            if needs_update:
                service.events().update(
                    calendarId=calendar_id,
                    eventId=existing["id"],
                    body=event_payload,
                ).execute()
                updated += 1
        else:
            service.events().insert(
                calendarId=calendar_id,
                body=event_payload,
            ).execute()
            created += 1

    print(f"Sync complete: {created} items added, {updated} updated, {deleted} submitted items removed.")

# main function
if __name__ == "__main__":
    if not CANVAS_TOKEN or not CANVAS_DOMAIN:
        raise ValueError("Please provide CANVAS_DOMAIN and CANVAS_TOKEN in your .env file.")

    service = get_gcal()
    calendar_id = create_calendar(service, CALENDAR_NAME)
    items = fetch_canvas_calendar(CANVAS_DOMAIN, CANVAS_TOKEN, days_ahead=45)
    sync_events(service, calendar_id, items)