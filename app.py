import streamlit as st
import os, glob, json, subprocess
from generator import main as generate_clip
import tiktok_uploader

st.set_page_config(page_title="AI Auto Shorts & TikTok Generator", page_icon="🎬", layout="wide")

st.title("🎬 AI Auto Shorts & TikTok Post Generator")
st.caption("Paste any YouTube URL -> Gemini AI extracts the greatest clip -> Formats to 9:16 Vertical Short -> Direct Post to TikTok!")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CLIPS_DIR = os.path.join(BASE_DIR, "clips")

# --- SIDEBAR TIKTOK AUTHENTICATION ---
with st.sidebar:
    st.header("🎵 TikTok Integration")
    token_file = os.path.join(BASE_DIR, "tiktok_tokens.json")
    
    if os.path.exists(token_file):
        st.success("✅ TikTok Account Linked!")
        if st.button("🔄 Re-authenticate / Switch Account"):
            os.remove(token_file)
            st.rerun()
    else:
        st.warning("⚠️ TikTok not linked yet.")
        auth_url = tiktok_uploader.get_auth_url()
        st.markdown(f"[👉 **Click here to Authorize TikTok**]({auth_url})")
        st.info("After authorizing, you will be redirected to an address like: `https://example.com/callback?code=XXXXX`\n\nCopy the `code=` value from your browser URL bar and paste it below:")
        
        auth_code = st.text_input("Paste TikTok Authorization Code:")
        if st.button("Save & Link TikTok"):
            if auth_code:
                success, msg = tiktok_uploader.exchange_code_for_token(auth_code)
                if success:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)
            else:
                st.error("Please paste the code!")

# --- MAIN PAGE ---
col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("1. Generate New Short")
    yt_url = st.text_input("YouTube Video URL", placeholder="https://www.youtube.com/watch?v=...")
    
    if st.button("🚀 Generate Best Clip", type="primary", use_container_width=True):
        if not yt_url:
            st.error("Please enter a valid YouTube URL!")
        else:
            with st.spinner("Processing video... Fetching transcript, AI picking viral highlight, downloading & vertical re-framing..."):
                try:
                    generate_clip(yt_url)
                    st.success("✅ Clip generated successfully!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error during processing: {e}")

with col2:
    st.subheader("2. Clips Library & Instant Post")
    mp4_files = glob.glob(os.path.join(CLIPS_DIR, "*.mp4"))
    
    if not mp4_files:
        st.info("No clips generated yet. Paste a link on the left to create your first clip!")
    else:
        for vid in sorted(mp4_files, key=os.path.getmtime, reverse=True):
            base_name = os.path.splitext(vid)[0]
            json_meta = base_name + "_post_info.json"
            
            meta = {}
            if os.path.exists(json_meta):
                with open(json_meta, "r", encoding="utf-8") as f:
                    meta = json.load(f)
            
            with st.expander(meta.get("title", os.path.basename(vid)), expanded=True):
                st.video(vid)
                if meta:
                    st.markdown(f"**🔥 Viral Reason:** {meta.get('reason', '')}")
                    caption_text = st.text_area(
                        "📋 Post Caption / Hashtags:", 
                        value=f"{meta.get('title', '')} {meta.get('caption', '')}", 
                        height=100, 
                        key=f"cap_{vid}"
                    )
                else:
                    caption_text = os.path.basename(vid)
                
                c_a, c_b, c_c = st.columns(3)
                with c_a:
                    with open(vid, "rb") as vf:
                        st.download_button("⬇️ Download", vf, file_name=os.path.basename(vid), mime="video/mp4", use_container_width=True)
                with c_b:
                    if st.button("📂 In Folder", key=f"f_{vid}", use_container_width=True):
                        subprocess.Popen(f'explorer /select,"{vid}"')
                with c_c:
                    if st.button("🎵 Upload to TikTok", key=f"tt_{vid}", type="primary", use_container_width=True):
                        with st.spinner("Uploading video to TikTok..."):
                            success, msg = tiktok_uploader.upload_video_to_tiktok(vid, caption_text)
                            if success:
                                st.success(msg)
                            else:
                                st.error(msg)
