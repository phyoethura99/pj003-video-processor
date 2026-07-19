import streamlit as st
import os
import subprocess
import json
import math
import concurrent.futures
import asyncio
import edge_tts
from pathlib import Path

# TTS Voices, Recap Styles, and Emotions from PDF analysis
VOICES = [
    {"id": "v1", "name": "ကို စိုင်းစိုင်း", "gender": "ယောက်ျားလေး"},
    {"id": "v2", "name": "မဖွေးဖွေး", "gender": "မိန်းကလေး"},
    {"id": "v3", "name": "ကို နေတိုး", "gender": "ယောက်ျားလေး"},
    {"id": "v4", "name": "ကို အောင်ရဲလင်း", "gender": "ယောက်ျားလေး"},
    {"id": "v5", "name": "ကို မြင့်မြတ်", "gender": "ယောက်ျားလေး"},
    {"id": "v6", "name": "မဝတ်မှုံ ရွှေရည်", "gender": "မိန်းကလေး"},
    {"id": "v7", "name": "ကို ဒေါင်း", "gender": "ယောက်ျားလေး"},
    {"id": "v8", "name": "မသက်မွန်မြင့်", "gender": "မိန်းကလေး"},
    {"id": "v9", "name": "ကို လူ မင်း", "gender": "ယောက်ျားလေး"},
    {"id": "v10", "name": "မအိန္ဒြာကျော်ဇင်", "gender": "မိန်းကလေး"},
    {"id": "v11", "name": "မရွှေမှုံ ရတီ", "gender": "မိန်းကလေး"},
    {"id": "v12", "name": "ကို ပြေတီဦး", "gender": "ယောက်ျားလေး"},
    {"id": "v13", "name": "မသင်ဇာဝင့်ကျော်", "gender": "မိန်းကလေး"},
    {"id": "v14", "name": "ကို ပိုင်တံခွန်", "gender": "ယောက်ျားလေး"}
]

RECAP_STYLES = [
    {"id": "Normal", "name": "ပုံမှန်အသံ", "speed": 0, "pitch": 0},
    {"id": "NyoGyi_25", "name": "ကျားကြီး ၁", "speed": 0, "pitch": 25},
    {"id": "NyoGyi_35", "name": "ကျားကြီး ၂", "speed": 0, "pitch": 35},
    {"id": "NyoGyi_45", "name": "ကျားကြီး ၃", "speed": 0, "pitch": 45},
    {"id": "Nilar_40", "name": "နီလာ ချွဲသံ", "speed": 0, "pitch": 40},
    {"id": "Combo_15", "name": "ပေါင်းစပ် ၁၅", "speed": 15, "pitch": 15},
    {"id": "Combo_30", "name": "ပေါင်းစပ် ၃၀", "speed": 30, "pitch": 30},
    {"id": "Combo_50", "name": "ပေါင်းစပ် ၅၀", "speed": 50, "pitch": 50},
    {"id": "Pitch_20", "name": "အသံသေး ၂၀", "speed": 0, "pitch": 20},
    {"id": "Pitch_50", "name": "အသံသေး ၅၀", "speed": 0, "pitch": 50}
]

EMOTIONS = [
    {"id": "EXCITING", "name": "စိတ်လှုပ်ရှား 🤩", "s": 15, "p": 10},
    {"id": "CALM", "name": "တည်ငြိမ် 😌", "s": -10, "p": -5},
    {"id": "PROFESSIONAL", "name": "သတင်း 💼", "s": 0, "p": -2},
    {"id": "NARRATIVE", "name": "ဇာတ်ကြောင်း 📖", "s": -5, "p": 0},
    {"id": "HAPPY", "name": "ပျော်ရွှင် 😊", "s": 10, "p": 15},
    {"id": "SERIOUS", "name": "လေးနက် 😠", "s": -5, "p": -10},
    {"id": "WHISPER", "name": "တီးတိုး 🤫", "s": -15, "p": -20},
    {"id": "SAD", "name": "ဝမ်းနည်း 😢", "s": -15, "p": -15},
    {"id": "SARCASTIC", "name": "ရွဲ့ပြော 🙄", "s": -10, "p": 5},
    {"id": "ANGRY", "name": "ဒေါသထွက် 🤬", "s": 20, "p": -10},
    {"id": "FEAR", "name": "ကြောက်လန့် 😨", "s": 10, "p": 20}
]

st.set_page_config(page_title="Video & Text Processor", layout="wide")

def count_paragraphs(text):
    """Count paragraphs in text (separated by double newlines)"""
    paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
    return paragraphs

def generate_tts(text, output_path, voice_id="v1", speed=0, pitch=0):
    """Generate TTS audio using edge_tts"""
    # Use a default English voice for now (in production, map to actual Myanmar voices)
    real_voice = "en-US-AriaNeural"
    
    # Format rate and pitch for edge_tts
    rate_str = f"+{speed}%" if speed >= 0 else f"{speed}%"
    pitch_str = f"+{pitch}Hz" if pitch >= 0 else f"{pitch}Hz"
    
    async def _generate():
        communicate = edge_tts.Communicate(text, real_voice, rate=rate_str, pitch=pitch_str)
        await communicate.save(output_path)
        
    asyncio.run(_generate())
    return output_path

def get_video_duration(video_path):
    """Get video duration in seconds"""
    cmd = [
        'ffprobe', '-v', 'error', '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1:noprint_wrappers=1', video_path
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return float(result.stdout)

def get_audio_duration(audio_path):
    """Get audio duration in seconds"""
    cmd = [
        'ffprobe', '-v', 'error', '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1:noprint_wrappers=1', audio_path
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return float(result.stdout)

def split_video(video_path, num_segments):
    """Split video into equal segments"""
    duration = get_video_duration(video_path)
    segment_duration = duration / num_segments
    
    segments = []
    for i in range(num_segments):
        start_time = i * segment_duration
        output_path = f"temp_segment_{i}.mp4"
        cmd = [
            'ffmpeg', '-y', '-i', video_path, '-ss', str(start_time),
            '-t', str(segment_duration), '-c:v', 'libx264', '-c:a', 'aac', output_path
        ]
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        segments.append(output_path)
    return segments, segment_duration

def process_segment(index, text, video_segment, audio_dir, final_segments_dir, voice_id, speed, pitch, play_dur, freeze1_dur, freeze1_zoom, freeze2_dur, freeze2_zoom):
    """Process a single segment with TTS and video editing"""
    # 1. Generate TTS
    audio_path = os.path.join(audio_dir, f"audio_{index}.mp3")
    generate_tts(text, audio_path, voice_id, speed, pitch)
    
    audio_duration = get_audio_duration(audio_path)
    
    # 2. Get original video segment duration
    orig_segment_duration = get_video_duration(video_segment)
    
    # 3. Create output path
    output_segment = os.path.join(final_segments_dir, f"segment_{index}.mp4")
    
    # 4. Build FFmpeg filter complex for play/freeze/zoom cycles
    # Calculate the number of cycles needed
    cycle_duration = play_dur + freeze1_dur + freeze2_dur
    num_cycles = math.ceil(audio_duration / cycle_duration)
    
    # Define zoom filters
    zoom_in_filter = "zoompan=z='min(zoom+0.0015,1.1)':d=1:s=hd720:fps=30"
    zoom_out_filter = "zoompan=z='max(zoom-0.0015,1.0)':d=1:s=hd720:fps=30"
    no_zoom_filter = "null"
    
    freeze1_zoom_filter = no_zoom_filter
    if freeze1_zoom == "Zoom In":
        freeze1_zoom_filter = zoom_in_filter
    elif freeze1_zoom == "Zoom Out":
        freeze1_zoom_filter = zoom_out_filter
    
    freeze2_zoom_filter = no_zoom_filter
    if freeze2_zoom == "Zoom In":
        freeze2_zoom_filter = zoom_in_filter
    elif freeze2_zoom == "Zoom Out":
        freeze2_zoom_filter = zoom_out_filter
    
    # Build filter complex
    filter_parts = []
    concat_inputs = []
    
    # First, speed adjust the entire video
    speed_factor = audio_duration / orig_segment_duration
    filter_parts.append(f"[0:v]setpts=PTS*{speed_factor}[v_speed_adjusted];")
    
    # Create play/freeze cycles
    for i in range(num_cycles):
        current_cycle_start = i * cycle_duration
        
        # Play segment
        play_start = current_cycle_start
        play_end = current_cycle_start + play_dur
        filter_parts.append(
            f"[v_speed_adjusted]trim=start={play_start}:end={play_end},setpts=PTS-STARTPTS[vplay_{i}];"
        )
        concat_inputs.append(f"[vplay_{i}]")
        
        # Freeze 1
        freeze1_start = current_cycle_start + play_dur
        filter_parts.append(
            f"[v_speed_adjusted]trim=start={freeze1_start},select=eq(n\\,0),setpts=PTS-STARTPTS,loop=loop=-1:size=1:start=0,trim=duration={freeze1_dur},{freeze1_zoom_filter}[vfreeze1_{i}];"
        )
        concat_inputs.append(f"[vfreeze1_{i}]")
        
        # Freeze 2
        freeze2_start = current_cycle_start + play_dur + freeze1_dur
        filter_parts.append(
            f"[v_speed_adjusted]trim=start={freeze2_start},select=eq(n\\,0),setpts=PTS-STARTPTS,loop=loop=-1:size=1:start=0,trim=duration={freeze2_dur},{freeze2_zoom_filter}[vfreeze2_{i}];"
        )
        concat_inputs.append(f"[vfreeze2_{i}]")
    
    # Concatenate all segments
    filter_parts.append(f"{''.join(concat_inputs)}concat=n={len(concat_inputs)}:v=1:a=0[vcombined];")
    
    # Add audio and trim to audio duration
    filter_complex = ''.join(filter_parts) + f"[vcombined][1:a]concat=n=1:v=1:a=1,trim=duration={audio_duration}[v]"
    
    # 5. Execute FFmpeg command
    cmd = [
        'ffmpeg', '-y', '-i', video_segment, '-i', audio_path,
        '-filter_complex', filter_complex,
        '-map', '[v]', '-shortest', output_segment
    ]
    
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return output_segment

def merge_videos(video_list, output_path):
    """Merge multiple video segments into one"""
    # Create a file with list of videos to concatenate
    concat_file = "concat_list.txt"
    with open(concat_file, 'w') as f:
        for video in video_list:
            f.write(f"file '{os.path.abspath(video)}'\n")
    
    cmd = [
        'ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', concat_file,
        '-c', 'copy', output_path
    ]
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    os.remove(concat_file)

def main():
    st.title("🎬 Video & Text Processor with TTS")
    st.markdown("""
    This application processes text and video together:
    - Splits text into paragraphs
    - Generates TTS audio for each paragraph
    - Splits video into segments matching paragraph count
    - Applies custom play/freeze/zoom effects
    - Merges everything into a final video
    """)

    with st.sidebar:
        st.header("⚙️ Settings")
        
        st.subheader("1️⃣ Voice Settings")
        selected_voice = st.selectbox("Select Voice", options=[v["name"] for v in VOICES])
        voice_id = next(v["id"] for v in VOICES if v["name"] == selected_voice)
        
        col1, col2 = st.columns(2)
        with col1:
            selected_style = st.selectbox("Recap Style", options=[s["name"] for s in RECAP_STYLES])
            style_data = next(s for s in RECAP_STYLES if s["name"] == selected_style)
        with col2:
            selected_emotion = st.selectbox("Emotion", options=[e["name"] for e in EMOTIONS])
            emotion_data = next(e for e in EMOTIONS if e["name"] == selected_emotion)
            
        final_speed = style_data["speed"] + emotion_data["s"]
        final_pitch = style_data["pitch"] + emotion_data["p"]
        
        st.caption(f"📊 Applied Speed: {final_speed}%, Pitch: {final_pitch}Hz")
        
        st.markdown("---")
        st.subheader("2️⃣ Video Editing")
        play_duration = st.slider("▶️ Play Duration (seconds)", min_value=1, max_value=5, value=3)
        
        col3, col4 = st.columns(2)
        with col3:
            freeze1_duration = st.slider("❄️ Freeze 1 Duration (seconds)", min_value=1, max_value=3, value=1)
            freeze1_zoom = st.selectbox("Freeze 1 Zoom", options=["None", "Zoom In", "Zoom Out"])
        with col4:
            freeze2_duration = st.slider("❄️ Freeze 2 Duration (seconds)", min_value=1, max_value=3, value=1)
            freeze2_zoom = st.selectbox("Freeze 2 Zoom", options=["None", "Zoom In", "Zoom Out"])
            
        st.markdown("---")
        st.subheader("3️⃣ Content")
        text_input = st.text_area("📝 Enter Text (Unlimited words)", height=300)
        video_file = st.file_uploader("🎥 Upload Video (Max 2GB, 1 Hour)", type=["mp4", "mov", "avi"])

    if st.button("🚀 Start Processing", key="process_btn"):
        if not text_input or not video_file:
            st.error("❌ Please provide both text and a video file.")
            return
        
        # Create temp directories
        temp_dir = "temp_processing"
        audio_dir = os.path.join(temp_dir, "audio")
        video_dir = os.path.join(temp_dir, "video")
        final_segments_dir = os.path.join(temp_dir, "final_segments")
        
        os.makedirs(audio_dir, exist_ok=True)
        os.makedirs(video_dir, exist_ok=True)
        os.makedirs(final_segments_dir, exist_ok=True)
        
        # Save uploaded video
        video_path = os.path.join(video_dir, "input_video.mp4")
        with open(video_path, "wb") as f:
            f.write(video_file.read())
        
        # Count paragraphs
        paragraphs = count_paragraphs(text_input)
        num_paragraphs = len(paragraphs)
        
        st.info(f"📊 Processing {num_paragraphs} paragraphs...")
        
        # Split video
        video_segments, segment_duration = split_video(video_path, num_paragraphs)
        
        # Process segments in parallel
        final_video_segments = [None] * num_paragraphs
        progress_bar = st.progress(0)
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            future_to_index = {
                executor.submit(process_segment, i, paragraphs[i], video_segments[i], audio_dir, final_segments_dir, voice_id, final_speed, final_pitch, play_duration, freeze1_duration, freeze1_zoom, freeze2_duration, freeze2_zoom): i 
                for i in range(num_paragraphs)
            }
            
            completed = 0
            for future in concurrent.futures.as_completed(future_to_index):
                index = future_to_index[future]
                try:
                    final_video_segments[index] = future.result()
                    completed += 1
                    progress_bar.progress(completed / num_paragraphs)
                except Exception as e:
                    st.error(f"❌ Error processing segment {index}: {str(e)}")
        
        # Merge final video
        st.info("🎞️ Merging video segments...")
        output_video = "final_output.mp4"
        merge_videos(final_video_segments, output_video)
        
        # Provide download
        with open(output_video, "rb") as f:
            st.download_button(
                label="📥 Download Final Video",
                data=f.read(),
                file_name="output_video.mp4",
                mime="video/mp4"
            )
        
        st.success("✅ Processing complete!")
        
        # Cleanup
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)

if __name__ == "__main__":
    main()
