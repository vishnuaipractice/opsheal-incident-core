import os
import subprocess
import imageio_ffmpeg
import time
import shutil

ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
base_dir = r"C:\vishnu\AI\Hackathons\IBM Bob 2.0 Hackathon LabLab ai\opsheal-incident-core"
video_path = os.path.join(base_dir, "live-demo.mp4")
scratch_dir = os.path.join(base_dir, "scratch", "live_demo")
os.makedirs(scratch_dir, exist_ok=True)

output_video_main = os.path.join(base_dir, "OpsHeal_Winning_Demo_Polished.mp4")
output_video_assets = os.path.join(base_dir, "submission_assets", "OpsHeal_Winning_Demo_Polished.mp4")

segments = [
    (3.200, 23.900, "01_hook_slide"),
    (44.800, 71.500, "02_bob_ide_pytest"),
    (77.600, 89.500, "03_bob_proof_outage_intro"),
    (101.500, 117.500, "04_browser_outage_setup"),
    (119.500, 147.200, "05_trigger_sev1_and_dlq"),
    (148.800, 153.500, "06_healer_click_and_recovery"),
    (161.800, 175.000, "07_swarm_execution_details"),
    (181.200, 195.200, "08_dlq0_and_ledger_invariant"),
    (197.800, 215.200, "09_chaos_injector_proof"),
    (225.200, 234.800, "10_quantified_mttr_metric"),
    (239.000, 246.500, "11_quantified_roi_slide_closing")
]

print(f"=== BUILDING POLISHED DEMO VIDEO ===")
print(f"Input: {video_path}")
print(f"Total cut segments: {len(segments)}")

total_dur = sum(e - s for s, e, _ in segments)
mins = int(total_dur // 60)
secs = total_dur % 60
print(f"Expected Duration: {total_dur:.2f} seconds ({mins}m {secs:.1f}s) - STRICTLY UNDER 3:00 LIMIT!")

filter_parts = []
concat_order = []

for idx, (s, e, name) in enumerate(segments):
    dur = e - s
    filter_parts.append(f"[0:v]trim=start={s:.3f}:end={e:.3f},setpts=PTS-STARTPTS[v{idx}];")
    filter_parts.append(f"[0:a]atrim=start={s:.3f}:end={e:.3f},asetpts=PTS-STARTPTS,afade=t=in:d=0.02,afade=t=out:st={dur-0.02:.3f}:d=0.02[a{idx}];")
    # Interleaved order: [v0][a0][v1][a1]...
    concat_order.append(f"[v{idx}][a{idx}]")

interleaved_inputs = "".join(concat_order)
filter_parts.append(f"{interleaved_inputs}concat=n={len(segments)}:v=1:a=1[v_concat][a_concat];")

fade_out_start = total_dur - 0.6
filter_parts.append(f"[a_concat]highpass=f=75,equalizer=f=3000:t=q:w=1.2:g=2,loudnorm=I=-16:TP=-1.5:LRA=11,afade=t=out:st={fade_out_start:.3f}:d=0.6[outa];")
filter_parts.append(f"[v_concat]fade=t=out:st={total_dur-0.5:.3f}:d=0.5[outv]")

filter_script = os.path.join(scratch_dir, "master_filter.txt")
with open(filter_script, "w", encoding="utf-8") as f:
    f.write(" ".join(filter_parts))

print(f"Filter graph generated: {filter_script}")

# Using -filter_complex_script or -/filter_complex
cmd = [
    ffmpeg_exe, "-y",
    "-i", video_path,
    "-filter_complex_script", filter_script,
    "-map", "[outv]",
    "-map", "[outa]",
    "-c:v", "libx264",
    "-preset", "veryfast",
    "-crf", "18",
    "-pix_fmt", "yuv420p",
    "-c:a", "aac",
    "-b:a", "192k",
    "-ar", "48000",
    "-movflags", "+faststart",
    output_video_main
]

print("\nStarting video rendering...")
start_time = time.time()
proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, errors="ignore")
elapsed = time.time() - start_time

if proc.returncode != 0:
    print("Render failed!")
    print(proc.stderr[-1000:])
    exit(1)

print(f"\nRender completed in {elapsed:.1f} seconds!")
print(f"Output File: {output_video_main}")
size_bytes = os.path.getsize(output_video_main)
print(f"Output Size: {size_bytes / (1024*1024):.2f} MB")

shutil.copy2(output_video_main, output_video_assets)
print(f"Copied to submission assets: {output_video_assets}")
