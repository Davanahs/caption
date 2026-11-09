import streamlit as st
import asyncio
from pathlib import Path
from backend.new_files.metadata_generator import generate_metadata
from backend.models.models import Video, VideoMetadata
from backend.models.database import async_session

st.set_page_config(page_title="ClipForge Metadata Review", layout="centered")

st.title("📹 ClipForge – Pre‑Upload Metadata Review")

video_id = st.text_input("Video ID", placeholder="Enter the video UUID")
if video_id:
    # Load video transcript (simplified – assume transcript stored in Video.transcript)
    async def load_transcript():
        async with async_session() as db:
            result = await db.execute(select(Video).where(Video.id == video_id))
            video = result.scalar_one_or_none()
            return video.transcript if video else None
    transcript = asyncio.run(load_transcript())
    if not transcript:
        st.warning("Transcript not found – metadata generation may be limited.")
        transcript = ""

    if st.button("Generate Metadata"):
        with st.spinner("Calling OpenRouter for AI‑generated metadata …"):
            meta = asyncio.run(generate_metadata(video_id, transcript))
            # Store in session state for editing
            st.session_state.title = meta.get("title", "")
            st.session_state.description = meta.get("description", "")
            st.session_state.tags = ", ".join(meta.get("tags", []))
            st.session_state.hashtags = ", ".join(meta.get("hashtags", []))
            st.session_state.pinned_comment = meta.get("pinned_comment", "")
        st.success("Metadata generated! Edit the fields below before saving.")

    if "title" in st.session_state:
        with st.form(key="metadata_form"):
            title = st.text_input("Title (≤ 60 chars)", value=st.session_state.title, max_chars=60)
            description = st.text_area("Description (200‑300 words)", value=st.session_state.description, height=200)
            tags = st.text_input("Tags (comma‑separated)", value=st.session_state.tags)
            hashtags = st.text_input("Hashtags (comma‑separated)", value=st.session_state.hashtags)
            pinned_comment = st.text_area("Pinned Comment", value=st.session_state.pinned_comment, height=100)
            submitted = st.form_submit_button("Save Metadata")
            if submitted:
                payload = {
                    "title": title,
                    "description": description,
                    "tags": [t.strip() for t in tags.split(",") if t.strip()],
                    "hashtags": [h.strip() for h in hashtags.split(",") if h.strip()],
                    "pinned_comment": pinned_comment,
                }
                # POST to backend endpoint
                import httpx
                api_url = f"http://localhost:8000/api/publish/metadata/{video_id}"
                try:
                    r = httpx.post(api_url, json=payload, timeout=10)
                    r.raise_for_status()
                    st.success("Metadata saved successfully.")
                except Exception as e:
                    st.error(f"Failed to save metadata: {e}")
        st.markdown("---")
        if st.button("Publish to YouTube (skip UI – use existing publish flow)"):
            st.info("Use the existing Publish page to select a clip and publish. This button only demonstrates that metadata is now stored.")
