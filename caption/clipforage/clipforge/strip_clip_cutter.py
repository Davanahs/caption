import re

with open("backend/services/clip_cutter.py", "r", encoding="utf-8") as f:
    content = f.read()

content = re.sub(r'class KalmanFilter2D:.*?def build_dynamic_crop_coords', 'def build_dynamic_crop_coords', content, flags=re.DOTALL)
content = re.sub(r'def build_dynamic_crop_coords\(.*?\)\s*->.*?:\n(    .*?\n)*\n', '\n', content, flags=re.DOTALL)
content = re.sub(r'def detect_best_crop_x\(.*?\)\s*->.*?:\n(    .*?\n)*\n', '\n', content, flags=re.DOTALL)
content = re.sub(r'async def reframe_to_vertical\(.*?\)\s*->.*?:\n(    .*?\n)*\n', '\n', content, flags=re.DOTALL)

with open("backend/services/clip_cutter.py", "w", encoding="utf-8") as f:
    f.write(content)
