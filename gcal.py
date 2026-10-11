import os
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/calendar"]

# auth and returns gcal api client 
def get_gcal(creds_file="credentials.json", token_file="token.json"): 
    creds = None
    if os.path.exists(token_file): 
        creds = Credentials.from_authorized_user_file(token_file, SCOPES)

    if not creds or not creds.valid: 
        if creds and creds.expired and creds.refresh_token: 
            creds.refresh(Request())
        else: 
            if not os.path.exists(creds_file): 
                raise FileNotFoundError(f"Missing '{creds_file}'.")
            flow = InstalledAppFlow.from_client_secrets_file(creds_file, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(token_file, "w") as token: 
            token.write(creds.to_json())

    return build("calendar", "v3", credentials=creds)

# find or create calendar w name 
def create_calendar(service, name: str) -> str: 
    page_token = None
    while True: 
        res = service.calendarList().list(pageToken=page_token).execute() 
        for cal in res.get("items, []"): 
            if cal.get("summary") == name: 
                return cal["id"]
            page_token = res.get("nextPageToken")
            if not page_token: 
                break 

        new_cal = {"summary": name, "description": "Canvas due dates and deadlines"}
        return service.calendars().insert(body=new_cal).execute()["id"]