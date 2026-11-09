import pytest
from backend.services.reframe_engine import apply_smoothing_and_deadzone

def test_tracker_raw_jitter_stable():
    # 1. raw face position jitter -> crop position should remain stable
    width, height = 1920, 1080
    crop_w, crop_h = 607, 1080
    alpha = 0.15
    
    # Target center is perfectly still at (960, 540) but has +/- 10px jitter
    target_centers = [
        (960, 540), (965, 542), (955, 538), (962, 541), (958, 539)
    ] * 5
    
    coords = apply_smoothing_and_deadzone(target_centers, width, height, crop_w, crop_h, alpha)
    
    # First coordinate establishes base
    base_x = coords[0][0]
    
    # Ensure all subsequent coordinates are exactly the base_x (no movement due to deadzone)
    for c in coords:
        assert c[0] == base_x

def test_tracker_small_movement_inside_deadzone():
    # 2. small movement inside dead-zone -> no crop update
    width, height = 1920, 1080
    crop_w, crop_h = 607, 1080
    alpha = 0.15
    dead_zone_x = width * 0.05 # 96 pixels
    
    # Target moves slowly but stays within 96 pixels of the original center
    target_centers = [
        (960 + i * 5, 540) for i in range(15) # Moves 75 pixels total
    ]
    
    coords = apply_smoothing_and_deadzone(target_centers, width, height, crop_w, crop_h, alpha)
    
    base_x = coords[0][0]
    
    # Crop should not update at all since it's within the dead zone
    for c in coords:
        assert c[0] == base_x

def test_tracker_large_movement_smooth_transition():
    # 3. large movement outside dead-zone -> smooth transition
    width, height = 1920, 1080
    crop_w, crop_h = 607, 1080
    alpha = 0.15
    
    # Sudden large jump (pan)
    target_centers = [(960, 540)] * 5 + [(1400, 540)] * 15
    
    coords = apply_smoothing_and_deadzone(target_centers, width, height, crop_w, crop_h, alpha)
    
    # Check that movement is smooth (max delta between frames is small compared to the 440px jump)
    max_delta = 0
    for i in range(1, len(coords)):
        delta = abs(coords[i][0] - coords[i-1][0])
        if delta > max_delta:
            max_delta = delta
            
    # The jump is 440px. With smoothing, the max per-frame jump should be much smaller.
    assert max_delta > 0 # It did move
    assert max_delta < 150 # But it moved smoothly (not jumping the full 440 immediately)
