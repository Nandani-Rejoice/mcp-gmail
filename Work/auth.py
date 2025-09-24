import os
import json

from googleapiclient.discovery import Resource, build
from typing import List
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow


# Default settings
DEFAULT_CREDENTIALS_PATH = "credentials.json"
DEFAULT_TOKEN_PATH = "token.json"
DEFAULT_USER_ID = "me"

# Gmail API scopes
GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/gmail.labels",
]

# For simpler testing
GMAIL_MODIFY_SCOPE = ["https://www.googleapis.com/auth/gmail.modify"]

# Type alias for the Gmail service
GmailService = Resource


def get_gmail_service(
    credentials_path: str = DEFAULT_CREDENTIALS_PATH,
    token_path: str = DEFAULT_TOKEN_PATH,
    scopes: List[str] = GMAIL_SCOPES,
) -> GmailService:
    """
    Authenticate with Gmail API and return the service object.

    Args:
        credentials_path: Path to the credentials JSON file
        token_path: Path to save/load the token
        scopes: OAuth scopes to request

    Returns:
        Authenticated Gmail API service
    """
    creds = None

    # Look for token file with stored credentials
    if os.path.exists(token_path):
        with open(token_path, "r") as token:
            token_data = json.load(token)
            creds = Credentials.from_authorized_user_info(token_data)

    # If credentials don't exist or are invalid, authenticate
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # Check if credentials file exists
            if not os.path.exists(credentials_path):
                raise FileNotFoundError(
                    f"Credentials file not found at {credentials_path}. "
                    "Please download your OAuth credentials from Google Cloud Console."
                )

            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, scopes)
            creds = flow.run_local_server(port=0)

        # Save credentials for future runs
        token_json = json.loads(creds.to_json())
        with open(token_path, "w") as token:
            json.dump(token_json, token)

    # Build the Gmail service
    return build("gmail", "v1", credentials=creds)
