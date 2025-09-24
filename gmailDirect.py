import json
import base64
import time
from fastapi import FastAPI
from contextlib import asynccontextmanager
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.cloud import pubsub_v1
import os
import base64
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

TOKEN_FILE = "token.json"
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
TOPIC_NAME = "projects/mcp-gmail-integration-470309/topics/MyTopic"

creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
service = build("gmail", "v1", credentials=creds)

body = {
    "labelIds": ["INBOX"],
    "topicName": TOPIC_NAME
}

response = service.users().watch(userId="me", body=body).execute()
print("Gmail watch started:", response)


os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "D//mcp-gmail//service-account.json"

# ---------------------------
# Config
# ---------------------------
TOKEN_FILE = "token.json"
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
LAST_HISTORY_FILE = "last_history.txt"

PROJECT_ID = "mcp-gmail-integration-470309"
SUBSCRIPTION_ID = "MyTopic-sub"  # Your Pub/Sub subscription name

# ---------------------------
# History Helpers
# ---------------------------
def get_last_history_id():
    try:
        with open(LAST_HISTORY_FILE, "r") as f:
            return int(f.read().strip())
    except (FileNotFoundError, ValueError):
        return None

def save_last_history_id(history_id: int):
    with open(LAST_HISTORY_FILE, "w") as f:
        f.write(str(history_id))

# ---------------------------
# Gmail Helpers
# ---------------------------
def get_gmail_service():
    creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    return build("gmail", "v1", credentials=creds)

def fetch_new_emails(service, history_id):
    try:
        response = service.users().history().list(
            userId="me", startHistoryId=history_id, historyTypes=["messageAdded"]).execute()
        messages = []
        if "history" in response:
            for record in response["history"]:
                if "messagesAdded" in record:
                    for m in record["messagesAdded"]:
                        msg_id = m["message"]["id"]
                        full_msg = service.users().messages().get(
                            userId="me", id=msg_id, format="metadata", metadataHeaders=["Subject", "From"]
                        ).execute()
                        snippet = full_msg.get("snippet", "<no snippet>")
                        subject, sender = "", ""
                        for header in full_msg["payload"].get("headers", []):
                            if header["name"] == "Subject":
                                subject = header["value"]
                            if header["name"] == "From":
                                sender = header["value"]
                        if "INBOX" in full_msg.get("labelIds", []):
                            messages.append({"from": sender, "subject": subject, "snippet": snippet})
        return messages
    except Exception as e:
        print("⚠️ Error fetching emails:", str(e))
        return []

# ---------------------------
# FastAPI app (optional for health checks)
# ---------------------------
app = FastAPI()

@app.get("/health")
async def health():
    return {"status": "running"}

def safe_base64_decode(data_raw):
    """Safely decode base64-encoded string/bytes from Pub/Sub."""
    if not data_raw:
        return None

    # Ensure data is bytes
    if isinstance(data_raw, str):
        data_bytes = data_raw.encode("utf-8")
    else:
        data_bytes = data_raw

    # Add padding if missing
    missing_padding = len(data_bytes) % 4
    if missing_padding != 0:
        data_bytes += b"=" * (4 - missing_padding)  # use bytes

    try:
        decoded_str = base64.b64decode(data_bytes).decode("utf-8")
        return json.loads(decoded_str)
    except Exception as e:
        print(f"⚠️ Could not decode Pub/Sub message: {e}")
        return None

# ---------------------------
# Pub/Sub message handling
# ---------------------------


def handle_pubsub_message(message):
    try:
        # Print raw Pub/Sub data
        print("\n🔔 Pub/Sub message received:", message)

        # Try decoding safely
        try:
            decoded = message.data.decode("utf-8")
            print("📩 Decoded Pub/Sub data:", decoded)
            payload = json.loads(decoded)
            print("📩 Decoded Pub/Sub payload:", json.dumps(payload))
        except Exception as e:
            print(f"⚠️ Could not decode Pub/Sub message as UTF-8/JSON: {e}")
            payload = None

        # If payload has historyId, fetch Gmail history
        if payload and "historyId" in payload:
            history_id = payload["historyId"]
            email_address = payload.get("emailAddress", "<unknown>")
            print(f"ℹ️ Handling historyId {history_id} for {email_address}")

            # Get Gmail service
            service = get_gmail_service()

            # Fetch history from Gmail
            try:
                response = service.users().history().list(
                    userId="me",
                    startHistoryId=history_id,
                    historyTypes=["messageAdded", "labelAdded", "labelRemoved", "messageDeleted"]
                ).execute()

                print("📄 Full Gmail history response:")
                print(json.dumps(response))

                # Also print messages from history
                if "history" in response:
                    for record in response["history"]:
                        print("🔹 History record:", json.dumps(record))
                        if "messagesAdded" in record:
                            for m in record["messagesAdded"]:
                                msg_id = m["message"]["id"]
                                full_msg = service.users().messages().get(
                                    userId="me",
                                    id=msg_id,
                                    format="metadata",
                                    metadataHeaders=["Subject", "From"]
                                ).execute()
                                
                                print("✉️ Full message metadata:", json.dumps(full_msg))
                else:
                    print("ℹ️ No history records found for this historyId.")

            except Exception as e:
                print(f"⚠️ Error fetching Gmail history: {e}")

            # Save the last historyId
            save_last_history_id(history_id)

    except Exception as e:
        print("⚠️ Error processing Pub/Sub message:", str(e))
    finally:
        message.ack()


# ---------------------------
# Main function
# ---------------------------
if __name__ == "__main__":
    # Initialize Gmail service to start watch (optional)
    service = get_gmail_service()

    # Start Pub/Sub subscriber
    subscriber = pubsub_v1.SubscriberClient()
    subscription_path = subscriber.subscription_path(PROJECT_ID, SUBSCRIPTION_ID)
    print(f"🚀 Listening for Gmail notifications on {subscription_path}...")

    streaming_pull_future = subscriber.subscribe(subscription_path, callback=handle_pubsub_message)

    try:
        streaming_pull_future.result()  # Blocks indefinitely
    except KeyboardInterrupt:
        print("\n🛑 Stopping Gmail Pub/Sub listener")
        streaming_pull_future.cancel()
