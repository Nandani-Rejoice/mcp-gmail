# curl --request POST \
#   --data "code=4/1AVMBsJhXDsdUxAOgm-ZgG8wZxGjqn9o8KX_4989gF61j9FgqrqlTgjvhmOE" \
#   --data "client_id=23829735023-i1hh0alk7ubcgspp24iqim59815thai1.apps.googleusercontent.com" \
#   --data "client_secret=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" \ 
#   --data "redirect_uri=urn:ietf:wg:oauth:2.0:oob" \
#   --data "grant_type=authorization_code" \
#   https://oauth2.googleapis.com/token
#   refresh token= 1//0gjIZ_jtYT9qZCgYIARAAGBASNwF-L9IrnzWZNI4ZHGhiIRIscvFt26CbvOro44DgFPcLWOGv57sNyPugWQqcHm1Ld4B5JCDmwdw

# POST https://gmail.googleapis.com/gmail/v1/users/{userId}/watch



# import requests

# data = {
#     "code": "4/1AVMBsJhXDsdUxAOgm-ZgG8wZxGjqn9o8KX_4989gF61j9FgqrqlTgjvhmOE",
#     "client_id": "23829735023-i1hh0alk7ubcgspp24iqim59815thai1.apps.googleusercontent.com",
#     "client_secret": "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",
#     "redirect_uri": "urn:ietf:wg:oauth:2.0:oob",
#     "grant_type": "authorization_code"
# }

# resp = requests.post("https://oauth2.googleapis.com/token", data=data)
# print(resp.json())



from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
PUBSUB_TOPIC = "projects/mcp-gmail-integration-470309/topics/MyTopic"

def get_gmail_service():
    creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    return build("gmail", "v1", credentials=creds)

def start_watch(service):
    request = {
        "labelIds": ["INBOX"],  # watch only inbox
        "topicName": PUBSUB_TOPIC
    }
    response = service.users().watch(userId="me", body=request).execute()
    print("✅ Gmail watch started:", response)
    return response

if __name__ == "__main__":
    service = get_gmail_service()
    start_watch(service)

from google.cloud import pubsub_v1

PROJECT_ID = "mcp-gmail-integration-470309"
SUBSCRIPTION_ID = "MySub"

def callback(message):
    print(f"📬 New Gmail notification received: {message.data}")
    message.ack()  # acknowledge message

subscriber = pubsub_v1.SubscriberClient()
subscription_path = subscriber.subscription_path(PROJECT_ID, SUBSCRIPTION_ID)

streaming_pull_future = subscriber.subscribe(subscription_path, callback=callback)
print(f"🚀 Listening for Gmail notifications on {subscription_path}...")

# Keep main thread alive
try:
    streaming_pull_future.result()
except KeyboardInterrupt:
    streaming_pull_future.cancel()



def fetch_email(service, message_id):
    msg = service.users().messages().get(
        userId="me", id=message_id, format="metadata", 
        metadataHeaders=["From", "Subject"]
    ).execute()
    return msg
  



