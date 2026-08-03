"""
NutriAgent Backend — Restaurant Health Scoring.

Simple keyword-based health scoring for restaurant/food names.
First version: keyword matching. Future: AI-powered classification.
"""

from __future__ import annotations

# Scoring rules (higher = healthier)
POSITIVE_KEYWORDS = {
    "轻食": 30,
    "健身餐": 30,
    "沙拉": 25,
    "低脂": 20,
    "营养": 20,
    "素食": 20,
    "蒸菜": 20,
    "鲜榨": 15,
    "水果": 15,
    "有机": 15,
    "全麦": 15,
    "粗粮": 15,
    "粥": 10,
    "汤": 10,
    "果汁": 10,
    "酸奶": 10,
    "豆浆": 10,
    "三明治": 10,
    "寿司": 10,
}

NEGATIVE_KEYWORDS = {
    "奶茶": -30,
    "炸鸡": -20,
    "烧烤": -15,
    "火锅": -10,
    "油炸": -20,
    "麻辣": -10,
    "烤串": -15,
    "汉堡": -10,
    "可乐": -20,
    "甜点": -15,
    "冰淇淋": -15,
    "啤酒": -15,
    "白酒": -20,
    "烤肉": -10,
    "辣条": -20,
}

DEFAULT_SCORE = 50


def calculate_health_score(name: str, category: str = "") -> int:
    """
    Calculate health score (0-100) based on keyword matching.

    Args:
        name: Restaurant/food name
        category: AMap POI type category

    Returns:
        Integer score 0-100.
    """
    score = DEFAULT_SCORE
    text = f"{name} {category}".lower()

    for keyword, points in POSITIVE_KEYWORDS.items():
        if keyword in text:
            score += points

    for keyword, points in NEGATIVE_KEYWORDS.items():
        if keyword in text:
            score += points

    # Clamp to 0-100
    return max(0, min(100, score))
