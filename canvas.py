import os
import requests
from datetime import datetime, timezone, timedelta

# get canvas items 
def fetch_canvas_calendar(domain: str, token: str, days_ahead: int = 35) -> list: 
    headers = {"Authorization": f"Bearer {token}"} 
    now = datetime.now(timezone.utc)
    end_date = now + timedelta(days=days_ahead)

    url = f"https://{domain}/api/v1/planner/items"
    params = { 
        "start_date": (now - timedelta(days=2)).isoformat(), 
        "end_date": end_date.isoformat(), 
        "per_page": 50
    }

    all_items = []
    while url: 
        resp = requests.get(url, headers=headers, params=params)
        resp.raise_for_status() 
        all_items.extend(resp.json())
        url = resp.links.get("next", {}).get("url")
        params = {}

    return all_items