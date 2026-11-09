import asyncio

def is_low_score_clip(score: float) -> bool:
    """Matches backend/api/routes/clips.py:40 boundary condition."""
    return score < 5.0

def test_boundaries():
    print("Testing Boundary Conditions for Clip Score (< 5.0)")
    scores = [4.9, 4.99, 5.0, 5.01, 5.1]
    
    for score in scores:
        is_low = is_low_score_clip(score)
        action = "Eligible for low-score cleanup" if is_low else "Retained"
        print(f"Score {score:.2f} -> {action}")

if __name__ == "__main__":
    test_boundaries()
