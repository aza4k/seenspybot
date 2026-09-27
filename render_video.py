import os
import sys
import time
import numpy as np
import cv2
from playwright.sync_api import sync_playwright

def render():
    html_path = "file:///" + os.path.abspath("video_canvas.html").replace("\\", "/")
    output_mp4 = os.path.abspath("SeenSPY_Quick_Replies.mp4")

    print(f"Loading HTML: {html_path}")
    print(f"Output MP4: {output_mp4}")

    fps = 30
    duration = 8.0  # seconds
    total_frames = int(duration * fps)
    width = 1080
    height = 1080

    print("Launching Chromium...")
    p = sync_playwright().start()
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": width, "height": height}, device_scale_factor=1)

    page.goto(html_path)
    page.wait_for_load_state("networkidle")
    time.sleep(0.5)

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(output_mp4, fourcc, fps, (width, height))

    print(f"Rendering {total_frames} frames ({duration}s @ {fps}fps)...")
    start_time = time.time()

    for i in range(total_frames):
        t = i / fps
        page.evaluate(f"window.seek({t})")

        # Take screenshot as JPEG bytes in memory (super fast)
        buf = page.screenshot(type="jpeg", quality=95)
        # Decode into OpenCV BGR frame
        arr = np.frombuffer(buf, dtype=np.uint8)
        frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)

        out.write(frame)

        if (i + 1) % 30 == 0 or i == total_frames - 1:
            elapsed = time.time() - start_time
            pct = ((i + 1) / total_frames) * 100
            print(f"Progress: {i+1}/{total_frames} frames ({pct:.0f}%) - {elapsed:.1f}s elapsed")

    out.release()
    browser.close()
    p.stop()

    file_size_mb = os.path.getsize(output_mp4) / (1024 * 1024)
    print(f"SUCCESS! Video created: {output_mp4} ({file_size_mb:.2f} MB)")

if __name__ == "__main__":
    render()
