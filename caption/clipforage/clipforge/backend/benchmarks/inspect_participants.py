import cv2
from pathlib import Path

out_dir = Path("backend/benchmarks/audit_frames")
img_10 = cv2.imread(str(out_dir / "frame_010s.jpg"))
h, w = img_10.shape[:2]

# Crop left person (x ~ 0.10 to 0.40) and right person (x ~ 0.60 to 0.90)
crop_left = img_10[:, :w//2]
crop_right = img_10[:, w//2:]

cv2.imwrite(str(out_dir / "wide_left_person.jpg"), crop_left)
cv2.imwrite(str(out_dir / "wide_right_person.jpg"), crop_right)

# Also copy solo shots
img_25 = cv2.imread(str(out_dir / "frame_025s.jpg"))
img_45 = cv2.imread(str(out_dir / "frame_045s.jpg"))
cv2.imwrite(str(out_dir / "solo_25s.jpg"), img_25)
cv2.imwrite(str(out_dir / "solo_45s.jpg"), img_45)

print("Saved left/right and solo crops for visual inspection.")
