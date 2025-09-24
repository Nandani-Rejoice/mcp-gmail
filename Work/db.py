from supabase import create_client, Client

# ---------------------------
# Config
# ---------------------------
SUPABASE_URL = "https://iqeczjgesbyskcyrpyob.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImlxZWN6amdlc2J5c2tjeXJweW9iIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1MzQyOTk3OSwiZXhwIjoyMDY5MDA1OTc5fQ.J8-SzxPV748ZzmXAdlzHMsfif2lCxtMx5mfLGHkqVRQ"

# ---------------------------
# Supabase Setup
# ---------------------------
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def fetch_client_emails():
    """Fetch client emails from Supabase table 'clients'."""
    data = supabase.table("clients").select("contact_email").execute()
    emails = [row["contact_email"] for row in data.data]
    return emails

if __name__ == "__main__":
    client_emails = fetch_client_emails()
    print("📥 Client emails from Supabase:")
    for email in client_emails:
        print(" -", email)
