"""Badges, worked out from a player's history (nothing extra is stored).

Each badge has a goal and shows progress until it's earned, e.g. "Champion 3/10".
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Stats:
    turns: int = 0
    best_yourself: int = 0  # best "be yourself" turn
    fooled: int = 0  # impersonations that fooled the AI
    wins: int = 0
    speed_wins: int = 0
    guesses_right: int = 0  # correct votes in Guess Who
    daily_days: int = 0  # days the daily challenge was played
    best_streak: int = 0
    countries_met: int = 0  # countries of everyone you've played a game with (you included)


@dataclass(frozen=True)
class Badge:
    id: str
    emoji: str
    name: str
    description: str
    earned: bool
    progress: int
    goal: int


# id, emoji, name, description, the stat, the goal
BADGES = (
    ("first_words", "🎤", "First Words", "Play your first turn", "turns", 1),
    ("winner", "🏆", "Winner", "Win a game", "wins", 1),
    ("champion", "👑", "Champion", "Win 10 games", "wins", 10),
    ("disguise", "🎭", "Master of Disguise", "Fool the AI while impersonating someone", "fooled", 1),
    ("perfect", "💯", "Perfect Pitch", "Score 90 or more as yourself", "best_yourself", 90),
    ("sherlock", "🔍", "Sherlock", "Guess the speaker right 5 times in Guess Who", "guesses_right", 5),
    ("speed", "⚡", "Speed Demon", "Win a speed round", "speed_wins", 1),
    ("on_fire", "🔥", "On Fire", "Play the daily challenge 3 days in a row", "best_streak", 3),
    ("devotee", "📅", "Daily Devotee", "Play the daily challenge on 7 days", "daily_days", 7),
    ("globetrotter", "🌍", "Globetrotter", "Play games with people from 3 countries", "countries_met", 3),
)


def badges(stats: Stats) -> list[Badge]:
    out = []
    for id_, emoji, name, description, stat, goal in BADGES:
        value = getattr(stats, stat)
        out.append(Badge(id_, emoji, name, description, value >= goal, min(value, goal), goal))
    return out
