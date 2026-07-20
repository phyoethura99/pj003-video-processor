import streamlit as st
import os
import subprocess
import math
import concurrent.futures
import asyncio
import edge_tts
import time
import shutil
import gc

# ─────────────────────────────────────────────
# Timer Utility
# ─────────────────────────────────────────────

def format_time(seconds):
    """Format seconds into mm:ss or mm:ss.ms format."""
    mins = int(seconds // 60)
    secs = int(seconds % 60)
    ms = int((seconds % 1) * 10)
    if mins > 0:
        return f"{mins}:{secs:02d}"
    return f"{secs}.{ms}s"


def estimate_time(num_paragraphs, total_duration):
    """Estimate total processing time based on input parameters."""
    CHUNK_DURATION = 30
    num_chunks = math.ceil(total_duration / CHUNK_DURATION)
    # TTS: ~1s per paragraph (network I/O)
    tts_time = num_paragraphs * 1.0
    # Split video: instant (copy only) ~2s
    split_time = 2.0
    # Speed adjust: ~3s per segment with 2 workers
    speed_time = num_paragraphs * 3.0 / 2
    # Merge segments: instant (copy) ~1s
    merge_time = 1.0
    # Process chunks: ~8s per chunk with 2 workers
    chunk_time = num_chunks * 8.0 / 2
    # Final merge: instant ~1s
    final_merge_time = 1.0
    total = tts_time + split_time + speed_time + merge_time + chunk_time + final_merge_time
    return total


def format_estimate(total_seconds):
    """Format estimated time for display."""
    mins = int(total_seconds // 60)
    secs = int(total_seconds % 60)
    if mins > 0:
        return f"~{mins}:{secs:02d}"
    return f"~{secs}s"


# ─────────────────────────────────────────────
# TTS Voices, Recap Styles, and Emotions
# ─────────────────────────────────────────────

@st.cache_resource
def get_voices():
    return [
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

@st.cache_resource
def get_recap_styles():
    return [
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

@st.cache_resource
def get_emotions():
    return [
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

VOICES = get_voices()
RECAP_STYLES = get_recap_styles()
EMOTIONS = get_emotions()

st.set_page_config(page_title="Video & Text Processor", layout="wide")


def count_paragraphs(text):
    paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
    return paragraphs


# ─────────────────────────────────────────────
# TTS Generation
# ─────────────────────────────────────────────

async def generate_all_tts(paragraphs, audio_dir, voice_id, speed, pitch):
    """Generate TTS for all paragraphs in parallel."""
    tasks = []
    for i, paragraph in enumerate(paragraphs):
        tasks.append(generate_tts_async(paragraph, os.path.join(audio_dir, f"audio_{i}.mp3"), voice_id, speed, pitch))
    await asyncio.gather(*tasks)


async def generate_tts_async(text, output_path, voice_id, speed, pitch):
    """Async TTS generation for parallel execution."""
    voice_num = int(voice_id.replace('v', ''))
    real_voice = "my-MM-ThihaNeural" if voice_num % 2 == 0 else "my-MM-NilarNeural"
    rate_str = f"+{speed}%" if speed >= 0 else f"{speed}%"
    pitch_str = f"+{pitch}Hz" if pitch >= 0 else f"{pitch}Hz"
    communicate = edge_tts.Communicate(text, real_voice, rate=rate_str, pitch=pitch_str)
    await communicate.save(output_path)
    return output_path


# ─────────────────────────────────────────────
# Probe Helpers
# ─────────────────────────────────────────────

def get_video_duration(video_path):
    cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
           '-of', 'default=noprint_wrappers=1:nokey=1', video_path]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return float(result.stdout.strip())


def get_video_resolution(video_path):
    cmd = ['ffprobe', '-v', 'error', '-select_streams', 'v:0',
           '-show_entries', 'stream=width,height', '-of', 'csv=s=x:p=0', video_path]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    res = result.stdout.strip().split('x')
    w, h = int(res[0]), int(res[1])
    if w > 1920:
        h = int(h * (1920 / w))
        w = 1920
    return w, h


def get_audio_duration(audio_path):
    cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
           '-of', 'default=noprint_wrappers=1:nokey=1', audio_path]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return float(result.stdout.strip())


# ─────────────────────────────────────────────
# Step 1: Split video into segments (video only, no audio)
# ─────────────────────────────────────────────

def split_video(video_path, num_segments, output_dir):
    """Split video into segments using fast copy (instant, no re-encoding).
    Audio is stripped to avoid conflicts."""
    duration = get_video_duration(video_path)
    segment_duration = duration / num_segments
    segments = []
    for i in range(num_segments):
        start_time = i * segment_duration
        output_path = os.path.join(output_dir, f"segment_{i}.mp4")
        cmd = ['ffmpeg', '-y', '-ss', str(start_time), '-t', str(segment_duration),
               '-i', video_path, '-c:v', 'copy', '-an',
               '-avoid_negative_ts', 'make_zero', output_path]
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        segments.append(output_path)
    return segments, segment_duration


# ─────────────────────────────────────────────
# Step 2: Speed-adjust each segment to match TTS audio
# ─────────────────────────────────────────────

def speed_adjust_segment(index, video_segment, audio_path, adjusted_dir):
    """Speed-adjust VIDEO ONLY to match TTS audio duration.
    TTS audio is kept at original speed (no atempo).
    Returns the path to the adjusted segment (video+audio combined).
    Cleans up the original segment after success."""
    audio_duration = get_audio_duration(audio_path)
    orig_duration = get_video_duration(video_segment)
    output_path = os.path.join(adjusted_dir, f"adjusted_{index}.mp4")

    if abs(audio_duration - orig_duration) < 0.5:
        # No speed adjustment needed, just copy video+audio
        cmd = ['ffmpeg', '-y', '-i', video_segment,
               '-i', audio_path, '-c:v', 'copy', '-c:a', 'copy',
               '-shortest', output_path]
    else:
        speed_factor = audio_duration / orig_duration
        filter_complex = f"[0:v]setpts=PTS*{speed_factor}[v_speed];[v_speed][1:a]concat=n=1:v=1:a=1[v_concat][a_concat]"

        cmd = ['ffmpeg', '-y', '-i', video_segment, '-i', audio_path,
               '-filter_complex', filter_complex, '-map', '[v_concat]', '-map', '[a_concat]',
               '-c:v', 'libx264', '-preset', 'ultrafast', '-c:a', 'aac',
               '-shortest', output_path]

    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode == 0 and os.path.exists(output_path):
        if os.path.exists(video_segment):
            os.remove(video_segment)
        return output_path
    else:
        raise Exception(f"Speed adjust failed for segment {index}: {result.stderr}")


# ─────────────────────────────────────────────
# Step 3: Merge all speed-adjusted segments
# ─────────────────────────────────────────────

def merge_speed_adjusted_segments(adjusted_segments, output_path):
    """Merge all speed-adjusted segments into a single video."""
    concat_file = output_path + "_concat.txt"
    with open(concat_file, 'w') as f:
        for seg in adjusted_segments:
            f.write(f"file '{os.path.abspath(seg)}'\n")
    cmd = ['ffmpeg', '-y', '-f', 'concat', '-safe', '0',
           '-i', concat_file, '-c', 'copy', output_path]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if os.path.exists(concat_file):
        os.remove(concat_file)
    if result.returncode != 0:
        raise Exception(f"Merge speed-adjusted segments failed: {result.stderr}")
    for seg in adjusted_segments:
        if os.path.exists(seg):
            os.remove(seg)


# ─────────────────────────────────────────────
# Step 4: Split one chunk (for pipeline)
# ─────────────────────────────────────────────

def split_single_chunk(index, merged_path, chunk_duration, total_duration, output_dir):
    """Split a single chunk from merged video using fast copy (instant)."""
    start_time = index * chunk_duration
    remaining = min(chunk_duration, total_duration - start_time)
    output_path = os.path.join(output_dir, f"chunk_{index}.mp4")
    cmd = ['ffmpeg', '-y', '-ss', str(start_time), '-t', str(remaining),
           '-i', merged_path, '-c:v', 'copy', '-c:a', 'copy',
           '-avoid_negative_ts', 'make_zero', output_path]
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return output_path, remaining


# ─────────────────────────────────────────────
# Step 5: Apply cycle repeat to a single chunk
# ─────────────────────────────────────────────

def build_cycle_filter(video_path, audio_path, chunk_duration,
                       play_dur, freeze1_dur, freeze2_dur,
                       freeze1_zoom, freeze2_zoom):
    """Build FFmpeg filter complex for cycle repeat on a chunk."""
    width, height = get_video_resolution(video_path)
    fps = 30
    cycle_duration = play_dur + freeze1_dur + freeze2_dur
    num_cycles = math.ceil(chunk_duration / cycle_duration)

    if width > 1280:
        height = int(height * (1280 / width))
        width = 1280

    res_str = f"{width}x{height}"

    f1_frames = freeze1_dur * fps
    f2_frames = freeze2_dur * fps

    def make_zoom_filter(duration_frames, zoom_type):
        if zoom_type == "Zoom In":
            return (f"scale={width}:{height},setsar=1,"
                    f"zoompan=z='min(1+0.15*on/{duration_frames},1.15)':"
                    f"d={duration_frames}:s={res_str}:fps={fps}")
        elif zoom_type == "Zoom Out":
            return (f"scale={width}:{height},setsar=1,"
                    f"zoompan=z='max(1.15-0.15*on/{duration_frames},1.0)':"
                    f"d={duration_frames}:s={res_str}:fps={fps}")
        return None

    f1_z = make_zoom_filter(f1_frames, freeze1_zoom)
    f2_z = make_zoom_filter(f2_frames, freeze2_zoom)

    filter_parts = []
    concat_inputs = []

    for i in range(num_cycles):
        curr = i * cycle_duration

        # Play section
        filter_parts.append(
            f"[0:v]trim=start={curr}:end={min(curr + play_dur, chunk_duration)},"
            f"setpts=PTS-STARTPTS[vplay_{i}];")
        concat_inputs.append(f"[vplay_{i}]")

        # Freeze 1
        f1_start = curr + play_dur
        if f1_start < chunk_duration:
            if f1_z:
                filter_parts.append(
                    f"[0:v]trim=start={f1_start},select=eq(n\\,0),"
                    f"setpts=PTS-STARTPTS,{f1_z}[vf1_{i}];")
            else:
                filter_parts.append(
                    f"[0:v]trim=start={f1_start},select=eq(n\\,0),"
                    f"setpts=PTS-STARTPTS,loop=loop=-1:size=1:start=0,"
                    f"trim=duration={freeze1_dur}[vf1_{i}];")
            concat_inputs.append(f"[vf1_{i}]")

        # Freeze 2
        f2_start = curr + play_dur + freeze1_dur
        if f2_start < chunk_duration:
            if f2_z:
                filter_parts.append(
                    f"[0:v]trim=start={f2_start},select=eq(n\\,0),"
                    f"setpts=PTS-STARTPTS,{f2_z}[vf2_{i}];")
            else:
                filter_parts.append(
                    f"[0:v]trim=start={f2_start},select=eq(n\\,0),"
                    f"setpts=PTS-STARTPTS,loop=loop=-1:size=1:start=0,"
                    f"trim=duration={freeze2_dur}[vf2_{i}];")
            concat_inputs.append(f"[vf2_{i}]")

    # Concatenate video parts, then combine with audio
    filter_parts.append(
        f"{''.join(concat_inputs)}concat=n={len(concat_inputs)}:v=1:a=0[vcomb];")
    filter_parts.append(
        f"[vcomb][1:a]concat=n=1:v=1:a=1,trim=duration={chunk_duration}[v]")

    return ''.join(filter_parts)


def process_chunk_with_retry(index, chunk_path, chunk_duration,
                             final_dir,
                             play_dur, freeze1_dur, freeze2_dur,
                             freeze1_zoom, freeze2_zoom,
                             max_retries=3):
    """Process a single chunk with cycle repeat and zoom effects."""
    audio_path = os.path.join(final_dir, f"chunk_audio_{index}.mp3")
    cmd = ['ffmpeg', '-y', '-i', chunk_path, '-vn', '-acodec', 'libmp3lame',
           '-ab', '128k', audio_path]
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    for attempt in range(max_retries):
        try:
            output_path = os.path.join(final_dir, f"chunk_processed_{index}.mp4")
            filter_complex = build_cycle_filter(
                chunk_path, audio_path, chunk_duration,
                play_dur, freeze1_dur, freeze2_dur,
                freeze1_zoom, freeze2_zoom
            )

            cmd = ['ffmpeg', '-y', '-i', chunk_path, '-i', audio_path,
                   '-filter_complex', filter_complex, '-map', '[v]',
                   '-c:v', 'libx264', '-preset', 'ultrafast', '-c:a', 'aac',
                   '-shortest', output_path]
            result = subprocess.run(cmd, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, text=True)

            if result.returncode == 0 and os.path.exists(output_path):
                if os.path.exists(chunk_path):
                    os.remove(chunk_path)
                if os.path.exists(audio_path):
                    os.remove(audio_path)
                return output_path
            else:
                raise Exception(f"FFmpeg failed: {result.stderr}")
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2)
                continue
            else:
                raise e


# ─────────────────────────────────────────────
# Step 6: Merge all processed chunks into final video
# ─────────────────────────────────────────────

def merge_videos(video_list, output_path):
    valid_videos = [v for v in video_list if v is not None and os.path.exists(v)]
    if not valid_videos:
        raise Exception("No valid segments to merge.")
    concat_file = "concat_list.txt"
    with open(concat_file, 'w') as f:
        for video in valid_videos:
            f.write(f"file '{os.path.abspath(video)}'\n")
    cmd = ['ffmpeg', '-y', '-f', 'concat', '-safe', '0',
           '-i', concat_file, '-c', 'copy', output_path]
    result = subprocess.run(cmd, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True)
    if os.path.exists(concat_file):
        os.remove(concat_file)
    if result.returncode != 0:
        raise Exception(f"Merge Error: {result.stderr}")


# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────

def main():
    st.title("🎬 Video & Text Processor with TTS")

    # ── Estimated time display (sidebar) ──
    est_placeholder = None

    with st.sidebar:
        st.header("⚙️ Settings")
        selected_voice = st.selectbox("Select Voice", options=[v["name"] for v in VOICES])
        voice_id = next(v["id"] for v in VOICES if v["name"] == selected_voice)
        col1, col2 = st.columns(2)
        with col1:
            selected_style = st.selectbox("Recap Style", options=[s["name"] for s in RECAP_STYLES])
            style_data = next(s for s in RECAP_STYLES if s["name"] == selected_style)
        with col2:
            selected_emotion = st.selectbox("Emotion", options=[e["name"] for e in EMOTIONS])
            emotion_data = next(e for e in EMOTIONS if e["name"] == selected_emotion)
        final_speed, final_pitch = (style_data["speed"] + emotion_data["s"],
                                    style_data["pitch"] + emotion_data["p"])
        st.caption(f"📊 Speed: {final_speed}%, Pitch: {final_pitch}Hz")
        st.markdown("---")
        play_duration = st.slider("▶️ Play Duration (s)", 1, 5, 3)
        col3, col4 = st.columns(2)
        with col3:
            freeze1_duration = st.slider("❄️ Freeze 1 (s)", 1, 3, 1)
            freeze1_zoom = st.selectbox("Zoom 1", ["None", "Zoom In", "Zoom Out"])
        with col4:
            freeze2_duration = st.slider("❄️ Freeze 2 (s)", 1, 3, 1)
            freeze2_zoom = st.selectbox("Zoom 2", ["None", "Zoom In", "Zoom Out"])
        st.markdown("---")
        text_input = st.text_area("📝 Enter Text", height=200)
        if text_input:
            paragraphs = count_paragraphs(text_input)
            st.info(f"📊 Paragraphs: {len(paragraphs)} | Characters: {len(text_input)}")
        video_file = st.file_uploader("🎥 Upload Video", type=["mp4", "mov", "avi"])

        # ── Show estimated time before processing ──
        if video_file and text_input:
            video_file.seek(0, os.SEEK_END)
            # Can't probe without saving first, so estimate based on paragraphs
            num_paras = len(count_paragraphs(text_input))
            rough_duration = num_paras * 25  # rough estimate: ~25s per paragraph
            est = estimate_time(num_paras, rough_duration)
            st.info(f"⏱️ Estimated: {format_estimate(est)}")

    if st.button("🚀 Start Processing"):
        if not text_input or not video_file:
            st.error("❌ Provide text and video.")
            return

        # Setup temp directories
        temp_dir = "temp_processing"
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)

        audio_dir = os.path.join(temp_dir, "audio")
        video_dir = os.path.join(temp_dir, "video")
        adjusted_dir = os.path.join(temp_dir, "adjusted")
        chunks_dir = os.path.join(temp_dir, "chunks")
        final_dir = os.path.join(temp_dir, "final_chunks")
        for d in [audio_dir, video_dir, adjusted_dir, chunks_dir, final_dir]:
            os.makedirs(d, exist_ok=True)

        video_path = os.path.join(video_dir, "input_video.mp4")

        # Chunk-by-chunk write to save RAM
        with open(video_path, "wb") as f:
            while chunk := video_file.read(8192):
                f.write(chunk)

        paragraphs = count_paragraphs(text_input)
        num_paragraphs = len(paragraphs)
        progress_bar = st.progress(0)

        # Get actual video duration for accurate estimate
        actual_duration = get_video_duration(video_path)
        estimated_total = estimate_time(num_paragraphs, actual_duration)

        # Free RAM
        del video_file
        gc.collect()

        # Timer tracking
        total_start = time.time()

        with st.status("🚀 Processing...", expanded=True) as status:

            # ── Step 1+2: TTS + Split Video (PARALLEL) ──
            step_start = time.time()
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                tts_future = executor.submit(
                    lambda: asyncio.run(
                        generate_all_tts(paragraphs, audio_dir, voice_id,
                                         final_speed, final_pitch)
                    )
                )
                split_future = executor.submit(
                    split_video, video_path, num_paragraphs, video_dir
                )
                tts_future.result()
                st.write("✅ TTS generation complete.")
                video_segments, _ = split_future.result()
                st.write(f"✅ Split into {num_paragraphs} segments.")

            step12_elapsed = time.time() - step_start
            st.write(f"⏱️ TTS + Split: {format_time(step12_elapsed)}")

            # Delete original uploaded video
            if os.path.exists(video_path):
                os.remove(video_path)
                st.write("🗑️ Original video removed.")

            # ── Step 3: Speed-adjust each segment ──
            step_start = time.time()
            st.write("⚡ Speed-adjusting segments to match TTS audio...")
            adjusted_segments = [None] * num_paragraphs
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                futures = {
                    executor.submit(
                        speed_adjust_segment,
                        i, video_segments[i],
                        os.path.join(audio_dir, f"audio_{i}.mp3"),
                        adjusted_dir
                    ): i for i in range(num_paragraphs)
                }
                for future in concurrent.futures.as_completed(futures):
                    idx = futures[future]
                    try:
                        adjusted_segments[idx] = future.result()
                        st.write(f"✅ Segment {idx+1}/{num_paragraphs} speed-adjusted")
                        progress_bar.progress((idx + 1) / num_paragraphs / 4)
                    except Exception as e:
                        st.error(f"❌ Speed adjust failed for segment {idx+1}: {e}")
            gc.collect()
            step3_elapsed = time.time() - step_start
            st.write(f"✅ All segments speed-adjusted. ({format_time(step3_elapsed)})")

            # ── Step 4: Merge all speed-adjusted segments ──
            step_start = time.time()
            st.write("🔗 Merging speed-adjusted segments...")
            merged_video = os.path.join(temp_dir, "merged_video.mp4")
            merge_speed_adjusted_segments(adjusted_segments, merged_video)
            step4_elapsed = time.time() - step_start
            st.write(f"✅ Segments merged. ({format_time(step4_elapsed)})")
            gc.collect()

            # ── Step 5+6: Split into chunks + Process (PIPELINE) ──
            CHUNK_DURATION = 30
            merged_duration = get_video_duration(merged_video)
            num_chunks = math.ceil(merged_duration / CHUNK_DURATION)
            st.write(f"🧩 Processing {num_chunks} chunks...")

            processed_chunks = [None] * num_chunks
            completed_chunks = 0
            step56_start = time.time()

            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                # Submit first 2 chunks to start the pipeline
                # Split all chunks first (instant copy), then process in parallel
                chunk_paths = []
                chunk_durations = []
                for i in range(num_chunks):
                    start_time = i * CHUNK_DURATION
                    remaining = min(CHUNK_DURATION, merged_duration - start_time)
                    chunk_path = os.path.join(chunks_dir, f"chunk_{i}.mp4")
                    cmd = ['ffmpeg', '-y', '-ss', str(start_time), '-t', str(remaining),
                           '-i', merged_video, '-c:v', 'copy', '-c:a', 'copy',
                           '-avoid_negative_ts', 'make_zero', chunk_path]
                    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    chunk_paths.append(chunk_path)
                    chunk_durations.append(remaining)

                st.write(f"✅ Split into {num_chunks} chunks ({CHUNK_DURATION}s each).")

                # Process chunks in parallel (2 workers)
                futures = {
                    executor.submit(
                        process_chunk_with_retry,
                        i, chunk_paths[i], chunk_durations[i],
                        final_dir,
                        play_duration, freeze1_duration, freeze2_duration,
                        freeze1_zoom, freeze2_zoom
                    ): i for i in range(num_chunks)
                }
                for future in concurrent.futures.as_completed(futures):
                    idx = futures[future]
                    try:
                        processed_chunks[idx] = future.result()
                        completed_chunks += 1
                        st.write(f"✅ Chunk {idx+1}/{num_chunks} processed")
                        progress_bar.progress(
                            0.5 + 0.5 * completed_chunks / num_chunks)
                    except Exception as e:
                        st.error(f"❌ Chunk {idx+1} failed: {e}")
            gc.collect()
            step56_elapsed = time.time() - step56_start
            st.write(f"✅ All chunks processed. ({format_time(step56_elapsed)})")

            # Cleanup merged video
            if os.path.exists(merged_video):
                os.remove(merged_video)

            # ── Step 7: Merge processed chunks into final video ──
            step_start = time.time()
            st.write("🎞️ Merging final video...")
            output_video = "final_output.mp4"
            try:
                merge_videos(processed_chunks, output_video)
                step7_elapsed = time.time() - step_start
                status.update(label="✅ Complete!", state="complete")
            except Exception as e:
                st.error(f"❌ Final merge failed: {e}")
                status.update(label="❌ Failed", state="error")
                return

        # ── Final timer summary ──
        total_elapsed = time.time() - total_start
        st.success(f"🎉 Completed in **{format_time(total_elapsed)}** (Estimated: {format_estimate(estimated_total)})")

        # Download button
        if os.path.exists(output_video):
            st.download_button(
                "📥 Download Final Video",
                data=open(output_video, "rb"),
                file_name="output_video.mp4",
                mime="video/mp4"
            )

        # Final cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)
        if os.path.exists(output_video):
            os.remove(output_video)


if __name__ == "__main__":
    main()
