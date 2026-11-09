import sys

packages = ["cv2", "torch", "torchvision", "numpy", "PIL", "scenedetect", "sklearn", "mediapipe", "scipy"]
for p in packages:
    try:
        mod = __import__(p)
        print(f"{p}: INSTALLED ({getattr(mod, '__version__', 'version unknown')})")
    except Exception as e:
        print(f"{p}: NOT AVAILABLE ({e})")
