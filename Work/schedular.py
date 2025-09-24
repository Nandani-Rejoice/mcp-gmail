import os
import time
import re

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from db import fetch_client_emails
from datetime import datetime
from auth import get_gmail_service


# Initialize the Gmail service
service = get_gmail_service()

# ------------------------------------------------------------
# Gmail API Setup
# ------------------------------------------------------------
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

def get_gmail_service():
    if not os.path.exists("token.json"):
        raise Exception("⚠️ Missing token.json. Run Gmail OAuth flow first.")
    creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    return build("gmail", "v1", credentials=creds)

# ------------------------------------------------------------
# Polling Logic
# ------------------------------------------------------------
last_history_id = None
no_email_counter = 0  # counts iterations with no new emails
HEARTBEAT_INTERVAL = 20  # how many cycles before logging "still running"

def fetch_new_emails(service):
    global last_history_id
    try:
        profile = service.users().getProfile(userId="me").execute()
        new_email = profile["emailAddress"]
        
        # Fetch client emails once 
        client_emails = fetch_client_emails()

        if last_history_id is None:
            last_history_id = profile["historyId"]
            print(f"✅ Gmail Trigger initialized for {new_email}, historyId={last_history_id}")
            return []

        history = service.users().history().list(
            userId="me",
            startHistoryId=last_history_id,
            historyTypes=["messageAdded"]
        ).execute()

        messages = []
        if "history" in history:
            for record in history["history"]:
                if "messagesAdded" in record:
                    for msg in record["messagesAdded"]:
                        msg_id = msg["message"]["id"]
                        full_msg = service.users().messages().get(
                            userId="me", id=msg_id, format="metadata", metadataHeaders=["Subject", "From","LabelIds","Date"]
                        ).execute()

                        subject, sender, date = "", "", ""
                        for header in full_msg["payload"].get("headers", []):
                            if header["name"] == "Subject":
                                subject = header["value"]
                            if header["name"] == "From":
                                sender = re.search(r'<(.*?)>', header["value"])  # Extract the email address
                                if sender:
                                    sender = sender.group(1)  # Get the email from the regex match
                                else:
                                    sender = header["value"]  # Fallback to full value if no angle brackets
                            if header["name"] == "Date":
                                date = header["value"]

                         # Convert the date to the required format (YYYY-MM-DD HH:MM:SS.ssssss)
                        if date:
                            try:
                                # Parse the Gmail date string into a datetime object
                                parsed_date = datetime.strptime(date, "%a, %d %b %Y %H:%M:%S %z")

                                # Convert to the format required by Supabase (YYYY-MM-DD HH:MM:SS.ssssss)
                                formatted_date = parsed_date.strftime("%Y-%m-%d %H:%M:%S") + "." + str(parsed_date.microsecond).zfill(6)
                            except ValueError as e:
                                print(f"⚠️ Error parsing date: {e}")
                                formatted_date = None
                        else:
                                formatted_date = None

                         # Check if the email has the "IMPORTANT" label
                        is_important = "IMPORTANT" in full_msg.get("labelIds", [])

                        # Only continue if sender is in client emails
                        if sender not in client_emails:
                            print(f"❌ Skipping {sender}, not in client list {client_emails}")
                            continue  # Skip this email and move to the next one

                        snippet = full_msg.get("snippet", "")
                        messages.append({
                            "id": msg_id,
                            "from": sender,
                            "subject": subject,
                            "body": snippet,
                            "emailAddress": new_email,
                            "is_important": is_important,
                            "date": formatted_date
                        })

        if "historyId" in history:
            last_history_id = history["historyId"]

        return messages

    except HttpError as error:
        print(f"⚠️ Gmail API error: {error}")
        # If rate limit error, wait longer before retrying
        if error.resp.status in [429, 503]:
            print("⏳ Rate limit hit, waiting 10 seconds...")
            time.sleep(10)
        return []

# ------------------------------------------------------------
# Main Poll Loop
# ------------------------------------------------------------

if __name__ == "__main__":
    service = get_gmail_service()
    print("🚀 Starting Gmail Trigger (poll every 3s)...")

    try:
        while True:
            new_emails = fetch_new_emails(service)
            if new_emails:
                no_email_counter = 0  # reset counter when new email arrives
                print(f"📬 {len(new_emails)} new email(s):")
                print(new_emails)
                for email in new_emails:
                    pass
            else:
                no_email_counter += 1
                # Log a heartbeat every HEARTBEAT_INTERVAL cycles (~HEARTBEAT_INTERVAL * 3 seconds)
                if no_email_counter % HEARTBEAT_INTERVAL == 0:
                    print(f"⏱ Still running... no new emails in the last {HEARTBEAT_INTERVAL*3} seconds")

            time.sleep(3)  # Safe fast polling
    except KeyboardInterrupt:
        print("\n🛑 Gmail Trigger stopped by user")
