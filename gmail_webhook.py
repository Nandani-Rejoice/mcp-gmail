import json
import base64
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager

from pyngrok import ngrok
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

# ---------------------------
# Config
# ---------------------------
TOKEN_FILE = "token.json"
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
TOPIC_NAME = "projects/mcp-gmail-integration-470309/topics/MyTopic"
LAST_HISTORY_FILE = "last_history.txt"

NGROK_AUTHTOKEN = "32S5RlYCTbdV8Ur2G2L0CUmX1eY_3qFjBX8qzcnF5vu2Wtd8L"  # your free token


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


def start_watch(service):
    body = {
        "labelIds": ["INBOX"],
        "topicName": TOPIC_NAME
    }
    response = service.users().watch(userId="me", body=body).execute()
    print("🔔 Gmail watch started:", json.dumps(response, indent=2))
    return response

def fetch_new_emails(service, history_id):
    try:
        response = service.users().history().list(
            userId="me", startHistoryId=history_id, historyTypes=["messageAdded"]).execute()
        print("🔹 Raw history response:", json.dumps(response, indent=2))
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
                        # Only add emails that are truly new (not updates)
                        if "INBOX" in full_msg.get("labelIds", []):
                            messages.append({"from": sender, "subject": subject, "snippet": snippet})
        return messages
    except Exception as e:
        print("⚠️ Error fetching emails:", str(e))
        return []

# ---------------------------
# Lifespan: Gmail watch + Ngrok
# ---------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Gmail watch
    service = get_gmail_service()
    start_watch(service)

    # Ngrok
    ngrok.set_auth_token(NGROK_AUTHTOKEN)
    public_url = ngrok.connect(addr=8000, bind_tls=True,domain="nonhydraulic-euphuistically-shanika.ngrok-free.app") # type: ignore
    print(f"🚀 Ngrok tunnel active: {public_url}")
    print(f"👉 Webhook endpoint: {public_url}/gmail/notifications")

    yield

    # Cleanup
    ngrok.disconnect(public_url) # type: ignore
    ngrok.kill()

def pretty_print_pubsub(envelope: dict):
    message = envelope.get("message", {})
    meta = {
        "message_id": message.get("messageId") or message.get("message_id"),
        "publish_time": message.get("publishTime") or message.get("publish_time"),
        "subscription": envelope.get("subscription")
    }

    # Decode Pub/Sub data
    data_raw = message.get("data")
    payload = None
    if data_raw:
        try:
            decoded = base64.b64decode(data_raw).decode("utf-8")
            payload = json.loads(decoded)
        except Exception as e:
            decoded = f"<decode error: {e}>"
            payload = decoded
    else:
        decoded = "<no data>"

    print("\n📩 Pub/Sub Event Received:")
    print("🔹 Metadata:")
    print(json.dumps(meta, indent=2))
    print("🔹 Decoded Payload:")
    print(json.dumps(payload, indent=2) if isinstance(payload, dict) else payload)
    print("-------------------------------------------------\n")

    return payload

# ---------------------------
# FastAPI app
# ---------------------------
app = FastAPI(lifespan=lifespan)

@app.post("/gmail/notifications")
async def gmail_notifications(request: Request):
    try:
        envelope = await request.json()
    except Exception:
        return JSONResponse(
            content={"error": "Invalid JSON"},
            status_code=status.HTTP_400_BAD_REQUEST
        )

    # Pretty print Pub/Sub event (metadata + decoded payload)
    payload = pretty_print_pubsub(envelope)

    if isinstance(payload, dict):
        history_id = payload.get("historyId")
        email_address = payload.get("emailAddress")

        if history_id:
            last_history = get_last_history_id()
            if not last_history or history_id > last_history:
                service = get_gmail_service()
                new_emails = fetch_new_emails(service, history_id)

                if new_emails:  # Only log if there are new emails
                    print(f"📬 {len(new_emails)} new email(s) for {email_address}")
                    for e in new_emails:
                        snippet = e.get("snippet", "<no snippet>")
                        print(f"- {snippet}")
                else:
                    print(f"ℹ️ Notification received, but no new emails since historyId {history_id}")

                save_last_history_id(history_id)
            else:
                print(f"⏭️ Skipping duplicate/no-op notification for historyId {history_id}")

    return {"status": "ok"}

@app.get("/health")
async def health():
    return {"status": "running"}


# ---------------------------
# Run Uvicorn
# ---------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
