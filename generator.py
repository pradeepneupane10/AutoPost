import os, sys, json, re, subprocess, shutil
from dotenv import load_dotenv
from google import genai
from youtube_transcript_api import YouTubeTranscriptApi
import yt_dlp

sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOWNLOADS_DIR = os.path.join(BASE_DIR, "downloads")
CLIPS_DIR = os.path.join(BASE_DIR, "clips")
os.makedirs(DOWNLOADS_DIR, exist_ok=True)
os.makedirs(CLIPS_DIR, exist_ok=True)

if shutil.which("ffmpeg"):
    FFMPEG_BIN = "ffmpeg"
else:
    FFMPEG_BIN = r"C:\Users\om prakash\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.1-full_build\bin\ffmpeg.exe"

load_dotenv(os.path.join(BASE_DIR, ".env"))

def get_secret(key, default=None):
    try:
        import streamlit as st
        if hasattr(st, "secrets") and key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass
    return os.getenv(key, default)

def get_client():
    key = get_secret("GEMINI_API_KEY")
    if not key:
        raise ValueError("GEMINI_API_KEY not found in environment or secrets!")
    return genai.Client(api_key=key)

def extract_video_id(url):
    match = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11})", url)
    if not match:
        raise ValueError("Invalid YouTube URL")
    return match.group(1)

def analyze_best_clip_direct_gemini(url):
    """Directly asks Gemini to watch and analyze the YouTube video URL without getting IP blocked!"""
    print(f"[*] Asking Gemini Multimodal AI to watch and analyze YouTube video directly...")
    client = get_client()
    
    prompt = """
You are a viral short-form video creator specializing in YouTube Shorts, TikTok, and Instagram Reels.
Watch this YouTube video and find the SINGLE BEST, most viral, high-retention highlight segment between 30 and 55 seconds.

Criteria:
1. Instant Hook: Starts with an intense, curious, or emotional hook immediately.
2. Value/Payoff: Has a clear, fascinating story, visual action, or explanation.
3. Natural Ending: Complete thought without an abrupt mid-sentence cutoff.
4. Duration: Between 25.0 and 55.0 seconds.

Return strictly a JSON object with this exact structure (no markdown fences, pure JSON):
{
  "start_time": <start time in seconds as float, e.g. 124.5>,
  "end_time": <end time in seconds as float, e.g. 165.0>,
  "title": "Short catchy title (4-7 words)",
  "caption": "Viral post caption with relevant hashtags",
  "reason": "Why this clip will hook viewers"
}
"""
    response = client.models.generate_content(
        model="gemini-3.6-flash",
        contents=[
            genai.types.Part.from_uri(
                file_uri=url,
                mime_type="video/*"
            ),
            prompt
        ]
    )
    raw = response.text.strip()
    raw = re.sub(r"^```json\s*", "", raw)
    raw = re.sub(r"^```\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    
    clip_meta = json.loads(raw)
    print(f"[+] Best Clip Selected by Gemini: {clip_meta['title']}")
    print(f"    Time: {clip_meta['start_time']}s -> {clip_meta['end_time']}s (Duration: {clip_meta['end_time'] - clip_meta['start_time']:.1f}s)")
    return clip_meta

def download_video(url, video_id):
    output_path = os.path.join(DOWNLOADS_DIR, f"{video_id}.mp4")
    if os.path.exists(output_path):
        print(f"[+] Video already downloaded: {output_path}")
        return output_path

    print(f"[*] Downloading video: {url}...")
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': os.path.join(DOWNLOADS_DIR, f"{video_id}.%(ext)s"),
        'merge_output_format': 'mp4',
        'ffmpeg_location': FFMPEG_BIN,
        'quiet': True,
        'no_warnings': True
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])
    print(f"[+] Download complete: {output_path}")
    return output_path

def cut_and_convert_to_vertical(input_video, start_time, duration, output_path):
    print(f"[*] Cutting & converting video to 9:16 Vertical Short...")
    filter_complex = (
        "[0:v]split=2[bg][fg];"
        "[bg]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=20:5[bg_blur];"
        "[fg]scale=1080:-2[fg_scaled];"
        "[bg_blur][fg_scaled]overlay=(W-w)/2:(H-h)/2[outv]"
    )
    cmd = [
        FFMPEG_BIN,
        "-y",
        "-ss", str(start_time),
        "-t", str(duration),
        "-i", input_video,
        "-filter_complex", filter_complex,
        "-map", "[outv]",
        "-map", "0:a",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-c:a", "aac",
        output_path
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    print(f"[+] Vertical Short successfully generated: {output_path}")

def main(url):
    video_id = extract_video_id(url)
    
    # Analyze video directly with Gemini AI (bypasses YouTube IP blocking completely!)
    clip_info = analyze_best_clip_direct_gemini(url)
    
    start_time = float(clip_info['start_time'])
    end_time = float(clip_info['end_time'])
    duration = end_time - start_time
    
    raw_video = download_video(url, video_id)
    clean_title = re.sub(r'[^a-zA-Z0-9_-]', '_', clip_info['title'])[:30]
    out_clip_path = os.path.join(CLIPS_DIR, f"{clean_title}.mp4")
    cut_and_convert_to_vertical(raw_video, start_time, duration, out_clip_path)
    
    meta_path = os.path.join(CLIPS_DIR, f"{clean_title}_post_info.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(clip_info, f, indent=2, ensure_ascii=False)
        
    return out_clip_path, meta_path, clip_info

if __name__ == "__main__":
    test_url = sys.argv[1] if len(sys.argv) > 1 else "https://www.youtube.com/watch?v=bcNDKu8kuQ0"
    main(test_url)
