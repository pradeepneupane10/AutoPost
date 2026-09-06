import os, sys, json, urllib.parse, requests
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding='utf-8')
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

CLIENT_KEY = os.getenv("TIKTOK_CLIENT_KEY")
CLIENT_SECRET = os.getenv("TIKTOK_CLIENT_SECRET")
REDIRECT_URI = os.getenv("TIKTOK_REDIRECT_URI", "https://example.com/callback")
TOKEN_FILE = os.path.join(BASE_DIR, "tiktok_tokens.json")

def get_auth_url():
    """Generates the authorization link for user to log in and authorize the app."""
    scope = "user.info.basic,video.upload,video.publish"
    params = {
        "client_key": CLIENT_KEY,
        "scope": scope,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "state": "random_auth_state_123"
    }
    auth_url = f"https://www.tiktok.com/v2/auth/authorize/?{urllib.parse.urlencode(params)}"
    return auth_url

def exchange_code_for_token(code):
    """Exchanges authorization code from redirect URL for an access token."""
    url = "https://open.tiktokapis.com/v2/oauth/token/"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    data = {
        "client_key": CLIENT_KEY,
        "client_secret": CLIENT_SECRET,
        "code": code.strip(),
        "grant_type": "authorization_code",
        "redirect_uri": REDIRECT_URI
    }
    resp = requests.post(url, headers=headers, data=data)
    res_json = resp.json()
    if "access_token" in res_json:
        with open(TOKEN_FILE, "w", encoding="utf-8") as f:
            json.dump(res_json, f, indent=2)
        return True, "Successfully authorized and saved token!"
    else:
        return False, f"Auth Error: {res_json}"

def upload_video_to_tiktok(video_path, caption):
    """Uploads video using TikTok Content Posting Direct API."""
    if not os.path.exists(TOKEN_FILE):
        return False, "TikTok account not authorized yet. Please authorize first!"
    
    with open(TOKEN_FILE, "r", encoding="utf-8") as f:
        token_data = json.load(f)
    
    access_token = token_data.get("access_token")
    video_size = os.path.getsize(video_path)
    
    # 1. Initialize video upload
    init_url = "https://open.tiktokapis.com/v2/post/publish/video/init/"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json; charset=UTF-8"
    }
    
    payload = {
        "post_info": {
            "title": caption[:150], # TikTok caption limit
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
    
    # 2. Upload video bytes to upload_url
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

if __name__ == "__main__":
    print("Auth URL:", get_auth_url())
