import streamlit as st
import os
import json
import time
import io
import tempfile
import subprocess
from dotenv import load_dotenv
from audio_recorder_streamlit import audio_recorder
from openai import OpenAI

# ---------------------------------------------------------
# 1. Page Configuration & Mobile UI Styling
# ---------------------------------------------------------
st.set_page_config(
    page_title="AI Second Brain",
    page_icon="🧠",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# Custom CSS for a premium mobile app feel
st.markdown("""
<style>
    /* Mobile container constraint */
    .block-container {
        max-width: 480px !important;
        padding-top: 1.5rem !important;
        padding-bottom: 4rem !important;
        margin: 0 auto;
    }
    
    /* Hide Streamlit branding/menus */
    #MainMenu, footer, header {
        visibility: hidden;
        height: 0;
    }

    /* App Header */
    .app-header {
        text-align: center;
        margin-bottom: 1.5rem;
    }
    .app-title {
        font-size: 1.8rem;
        font-weight: 800;
        color: #0f172a;
        letter-spacing: -0.5px;
        margin: 0;
    }
    .app-subtitle {
        font-size: 0.9rem;
        color: #64748b;
        margin-top: 0.3rem;
    }

    /* Premium Recording & Upload Card */
    .recorder-box {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        background: linear-gradient(145deg, #ffffff 0%, #f8fafc 100%);
        border: 1px solid #e2e8f0;
        border-radius: 28px;
        padding: 2rem 1.5rem;
        margin-bottom: 1.5rem;
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.05), 0 8px 10px -6px rgba(0, 0, 0, 0.01);
    }
    .record-prompt {
        font-size: 1.15rem;
        font-weight: 700;
        color: #334155;
        margin-bottom: 1.5rem;
    }

    /* Mobile UI Section Card */
    .mobile-card {
        background: #ffffff;
        border: 1px solid #f1f5f9;
        border-radius: 20px;
        padding: 1.25rem;
        margin-bottom: 1rem;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.03), 0 2px 4px -2px rgba(0, 0, 0, 0.03);
    }
    .card-title {
        font-size: 1rem;
        font-weight: 700;
        color: #0f172a;
        margin-bottom: 0.75rem;
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }
    .card-body {
        font-size: 0.9rem;
        color: #475569;
        line-height: 1.5;
    }
    .tag-badge {
        display: inline-block;
        background: #f1f5f9;
        color: #475569;
        border-radius: 8px;
        padding: 4px 10px;
        font-size: 0.75rem;
        font-weight: 600;
        margin-right: 6px;
        margin-top: 6px;
    }
    
    /* Progress bar smooth rounded styling */
    .stProgress > div > div > div > div {
        border-radius: 12px;
    }
    
    /* Native looking Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 2rem;
        justify-content: center;
    }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# 2. Environment & OpenRouter Setup
# ---------------------------------------------------------
load_dotenv()

API_KEY = os.getenv("OPENROUTER_API_KEY")
if not API_KEY:
    try:
        API_KEY = st.secrets.get("OPENROUTER_API_KEY")
    except Exception:
        API_KEY = None

if not API_KEY:
    st.error("⚠️ `OPENROUTER_API_KEY` not found. Please set it in your `.env` file or Streamlit Secrets.")
    st.stop()

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=API_KEY,
)

# ---------------------------------------------------------
# 3. Header & Audio Input Options
# ---------------------------------------------------------
st.markdown("""
<div class="app-header">
    <h1 class="app-title">🧠 Neo Brain</h1>
    <p class="app-subtitle">Multilingual Capture & Segregation</p>
</div>
""", unsafe_allow_html=True)

audio_data_to_process = None
audio_file_extension = ".wav"

tab1, tab2 = st.tabs(["🎙️ Record", "📁 Upload File"])

with tab1:
    st.markdown("""
    <div class="recorder-box">
        <div class="record-prompt">Tap to Capture</div>
    """, unsafe_allow_html=True)

    audio_bytes = audio_recorder(
        text="",  
        recording_color="#ef4444", 
        neutral_color="#3b82f6",   
        icon_size="3x",            
        pause_threshold=2.0,
        sample_rate=16000,
        key="main_recorder"        
    )
    st.markdown('</div>', unsafe_allow_html=True)
    
    if audio_bytes:
        audio_data_to_process = audio_bytes
        audio_file_extension = ".wav"

with tab2:
    st.markdown('<div class="recorder-box">', unsafe_allow_html=True)
    uploaded_file = st.file_uploader("Select an audio file", type=["wav", "mp3", "m4a", "ogg", "flac"])
    
    if uploaded_file:
        st.audio(uploaded_file)
        if st.button("Process Uploaded File", use_container_width=True, type="primary"):
            audio_data_to_process = uploaded_file.getvalue()
            # Extract the actual extension (e.g., .m4a)
            _, ext = os.path.splitext(uploaded_file.name) 
            audio_file_extension = ext.lower()
            
    st.markdown('</div>', unsafe_allow_html=True)

# ---------------------------------------------------------
# 4. Processing Pipeline
# ---------------------------------------------------------
if audio_data_to_process:
    # Guard: Prevent empty/accidental clicks
    if len(audio_data_to_process) < 1000:
        st.error("⚠️ Recording too short. Please try speaking for a few seconds.")
        st.stop()

    if audio_data_to_process == audio_bytes:
        st.audio(audio_bytes, format="audio/wav")
        
    # --- AUTOMATIC FORMAT CONVERSION (.m4a to .mp3) using native FFmpeg ---
    if audio_file_extension == ".m4a":
        with st.spinner("🔄 Converting Apple .m4a to .mp3 for Mistral..."):
            try:
                # Write the m4a bytes to a temporary file
                with tempfile.NamedTemporaryFile(delete=False, suffix=".m4a") as f_in:
                    f_in.write(audio_data_to_process)
                    temp_in_path = f_in.name
                
                temp_out_path = temp_in_path.replace(".m4a", ".mp3")
                
                # Run FFmpeg command directly on the system
                subprocess.run(
                    ["ffmpeg", "-y", "-i", temp_in_path, temp_out_path], 
                    stdout=subprocess.DEVNULL, 
                    stderr=subprocess.DEVNULL,
                    check=True
                )
                
                # Read the new mp3 file back into memory
                with open(temp_out_path, "rb") as f_out:
                    audio_data_to_process = f_out.read()
                
                audio_file_extension = ".mp3"
                
                # Clean up the temporary files from the server
                os.remove(temp_in_path)
                os.remove(temp_out_path)
                
            except Exception as e:
                st.error(f"Failed to convert audio. Ensure ffmpeg is in packages.txt. Error: {e}")
                st.stop()
    # ----------------------------------------------------------------------

    progress_bar = st.progress(10, text="📦 Step 1/4: Preparing audio stream...")
    
    # Step 1: Multilingual Transcription via Voxtral
    progress_bar.progress(35, text="🎧 Step 2/4: Transcribing audio (Voxtral)...")
    
    formatted_transcript = ""
    try:
        clean_filename = f"recording{audio_file_extension}"
        
        # Explicitly map the MIME type so OpenAI SDK sends correct headers
        mime_map = {
            ".wav": "audio/wav",
            ".mp3": "audio/mpeg",
            ".ogg": "audio/ogg",
            ".flac": "audio/flac"
        }
        mime_type = mime_map.get(audio_file_extension, "audio/wav")
        
        # Tuple format: (name, bytes, mime_type)
        file_payload = (clean_filename, audio_data_to_process, mime_type)
        
        transcription = client.audio.transcriptions.create(
            model="meta/muse-voice-transcribe-1.0",
            file=file_payload,
            response_format="json" 
        )
        
        if hasattr(transcription, "segments") and transcription.segments:
            for seg in transcription.segments:
                speaker = getattr(seg, "speaker", None) or "Speaker"
                formatted_transcript += f"[{speaker}]: {seg.text.strip()}\n"
        else:
            formatted_transcript = getattr(transcription, "text", str(transcription))
            
    except Exception as e:
        progress_bar.empty()
        st.error(f"Transcription failed: {e}")
        formatted_transcript = None

    # Step 2: Intelligence Segregation via stealth/ox-alpha
    if formatted_transcript and formatted_transcript.strip():
        progress_bar.progress(70, text="⚡ Step 3/4: Segregating memory & extracting tasks...")

        prompt = f"""
        Analyze the following conversational transcript.
        Extract metadata, tasks, decisions, and searchable tags.
        
        Return ONLY a valid JSON object with the following schema:
        {{
            "summary": "Concise 2-sentence summary of the discussion",
            "category": "Context category (e.g., Team Sync, Technical Architecture, Casual, Planning)",
            "sentiment": "Overall sentiment (e.g., Productive, Urgent, Neutral)",
            "action_items": [
                "Task description (Assigned to: Speaker name/role, Deadline: if implied)"
            ],
            "key_decisions": [
                "Key consensus or agreement made"
            ],
            "keywords": ["tag1", "tag2", "tag3", "tag4"]
        }}
        
        Transcript:
        {formatted_transcript}
        """
        
        try:
            response = client.chat.completions.create(
                model="~z-ai/glm-flash-latest",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
            )
            
            progress_bar.progress(90, text="🎨 Step 4/4: Formatting results...")
            data = json.loads(response.choices[0].message.content)
            
            progress_bar.progress(100, text="✨ Processing complete!")
            time.sleep(0.4)
            progress_bar.empty() 
            
            with st.expander("📄 View Raw Transcript", expanded=False):
                st.text(formatted_transcript)
            
            # ---------------------------------------------------------
            # 5. Mobile App Result Cards
            # ---------------------------------------------------------
            category = data.get("category", "Note")
            sentiment = data.get("sentiment", "Neutral")
            summary = data.get("summary", "No summary generated.")
            action_items = data.get("action_items", [])
            decisions = data.get("key_decisions", [])
            keywords = data.get("keywords", [])

            st.markdown(f"""
            <div class="mobile-card">
                <div style="display:flex; justify-content:space-between; margin-bottom:8px;">
                    <span class="tag-badge" style="background:#e0f2fe; color:#0369a1;">📁 {category}</span>
                    <span class="tag-badge" style="background:#f3e8ff; color:#7e22ce;">🎭 {sentiment}</span>
                </div>
                <div class="card-title">📝 Executive Summary</div>
                <div class="card-body">{summary}</div>
            </div>
            """, unsafe_allow_html=True)

            action_html = "".join([f"<li style='margin-bottom:4px;'>{item}</li>" for item in action_items]) or "<li>No immediate action items detected.</li>"
            st.markdown(f"""
            <div class="mobile-card">
                <div class="card-title">✅ Action Items & To-Dos</div>
                <div class="card-body">
                    <ul style="padding-left: 1.2rem; margin: 0;">
                        {action_html}
                    </ul>
                </div>
            </div>
            """, unsafe_allow_html=True)

            if decisions:
                decisions_html = "".join([f"<li style='margin-bottom:4px;'>{d}</li>" for d in decisions])
                st.markdown(f"""
                <div class="mobile-card">
                    <div class="card-title">🤝 Key Decisions</div>
                    <div class="card-body">
                        <ul style="padding-left: 1.2rem; margin: 0;">
                            {decisions_html}
                        </ul>
                    </div>
                </div>
                """, unsafe_allow_html=True)

            if keywords:
                tags_html = "".join([f"<span class='tag-badge'>#{tag}</span>" for tag in keywords])
                st.markdown(f"""
                <div class="mobile-card">
                    <div class="card-title">🏷️ Search Tags</div>
                    <div>{tags_html}</div>
                </div>
                """, unsafe_allow_html=True)

        except Exception as e:
            progress_bar.empty()
            st.error(f"Intelligence processing failed: {e}")
