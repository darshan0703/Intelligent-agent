import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

_url = os.getenv("SUPABASE_URL", "")
_key = os.getenv("SUPABASE_KEY", "")

supabase = None
if _url and _key:
    try:
        supabase = create_client(_url, _key)
    except Exception as e:
        print(f"Warning: Failed to initialize Supabase client: {e}")