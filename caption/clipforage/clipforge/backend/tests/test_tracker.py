import pytest
from backend.services.performance_tracker import calculate_view_score

def test_calculate_view_score_zero_views():
    score, rate = calculate_view_score(0, 0, 0)
    assert score == 0.0
    assert rate == 0.0

def test_calculate_view_score_high_engagement():
    # views=10000, likes=3000, comments=2000
    # engagement_rate = (5000 / 10000) * 100 = 50.0%
    # view_score = (10000/100) + (3000/10) + (2000/5) + (50 * 5) = 100 + 300 + 400 + 250 = 1050.0
    score, rate = calculate_view_score(10000, 3000, 2000)
    assert rate == 50.0
    assert score == 1050.0

def test_calculate_view_score_low_engagement():
    score, rate = calculate_view_score(1000, 10, 0)
    assert rate == 1.0
    assert score == round((1000/100) + (10/10) + 0 + (1.0 * 5), 2)

def test_calculate_view_score_negative_views():
    score, rate = calculate_view_score(-10, 0, 0)
    assert score == 0.0
    assert rate == 0.0
