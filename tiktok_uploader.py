import os, sys, json, urllib.parse, requests
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding='utf-8')
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

def get_secret(key, default=None):
    try:
        import streamlit as st
        if hasattr(st, "secrets") and key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass
    return os.getenv(key, default)

CLIENT_KEY = get_secret("TIKTOK_CLIENT_KEY")
CLIENT_SECRET = get_secret("TIKTOK_CLIENT_SECRET")
REDIRECT_URI = get_secret("TIKTOK_REDIRECT_URI", "https://example.com/callback")
TOKEN_FILE = os.path.join(BASE_DIR, "tiktok_tokens.json")

def get_access_token():
    # Check Streamlit session state first (for Cloud persistent session)
    try:
        import streamlit as st
        if "tiktok_access_token" in st.session_state and st.session_state["tiktok_access_token"]:
            return st.session_state["tiktok_access_token"]
        if hasattr(st, "secrets") and "TIKTOK_ACCESS_TOKEN" in st.secrets:
            return st.secrets["TIKTOK_ACCESS_TOKEN"]
    except Exception:
        pass
        
    # Check local token file
    if os.path.exists(TOKEN_FILE):
        try:
            with open(TOKEN_FILE, "r", encoding="utf-8") as f:
                d = json.load(f)
                return d.get("access_token")
        except Exception:
            pass
    return None

def is_authorized():
    return get_access_token() is not None

def get_auth_url():
    key = get_secret("TIKTOK_CLIENT_KEY")
    redirect = get_secret("TIKTOK_REDIRECT_URI", "https://example.com/callback")
    scope = "user.info.basic,video.upload,video.publish"
    params = {
        "client_key": key,
        "scope": scope,
        "response_type": "code",
        "redirect_uri": redirect,
        "state": "random_auth_state_123"
    }
    auth_url = f"https://www.tiktok.com/v2/auth/authorize/?{urllib.parse.urlencode(params)}"
    return auth_url

def exchange_code_for_token(code):
    key = get_secret("TIKTOK_CLIENT_KEY")
    secret = get_secret("TIKTOK_CLIENT_SECRET")
    redirect = get_secret("TIKTOK_REDIRECT_URI", "https://example.com/callback")
    
    url = "https://open.tiktokapis.com/v2/oauth/token/"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    data = {
        "client_key": key,
        "client_secret": secret,
        "code": code.strip(),
        "grant_type": "authorization_code",
        "redirect_uri": redirect
    }
    resp = requests.post(url, headers=headers, data=data)
    res_json = resp.json()
    if "access_token" in res_json:
        token = res_json["access_token"]
        try:
            import streamlit as st
            st.session_state["tiktok_access_token"] = token
        except Exception:
            pass
        with open(TOKEN_FILE, "w", encoding="utf-8") as f:
            json.dump(res_json, f, indent=2)
        return True, "Successfully authorized and linked TikTok!", token
    else:
        return False, f"Auth Error: {res_json}", None

def upload_video_to_tiktok(video_path, caption):
    access_token = get_access_token()
    if not access_token:
        return False, "TikTok account not authorized yet. Please authorize first!"
        
    video_size = os.path.getsize(video_path)
    
    init_url = "https://open.tiktokapis.com/v2/post/publish/video/init/"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json; charset=UTF-8"
    }
    
    payload = {
        "post_info": {
            "title": caption[:150],
            "privacy_level": "PUBLIC_TO_EVERYONE",
            "disable_duet": False,
            "disable_stitch": False,
            "disable_comment": False
        },
        "source_info": {
            "source": "FILE_UPLOAD",
            "video_size": video_size,
            "chunk_size": video_size,
            "total_chunk_count": 1
        }
    }
    
    init_res = requests.post(init_url, headers=headers, json=payload).json()
    
    if init_res.get("error", {}).get("code") != "ok" and "data" not in init_res:
        return False, f"TikTok Init Error: {init_res}"
        
    upload_url = init_res["data"]["upload_url"]
    publish_id = init_res["data"]["publish_id"]
    
    with open(video_path, "rb") as vf:
        video_bytes = vf.read()
        
    put_headers = {
        "Content-Type": "video/mp4",
        "Content-Range": f"bytes 0-{video_size - 1}/{video_size}"
    }
    put_res = requests.put(upload_url, headers=put_headers, data=video_bytes)
    
    if put_res.status_code in [200, 201]:
        return True, f"Video uploaded successfully to TikTok! (Publish ID: {publish_id})"
    else:
        return False, f"Upload error {put_res.status_code}: {put_res.text}"
