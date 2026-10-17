"""Cell formats: aspect ratios, photo print sizes and playing card sizes."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CellFormat:
    key: str
    label: str
    width: float  # mm for exact sizes, ratio units otherwise
    height: float
    exact: bool  # True: cells are exactly this size; False: only this shape, sized by the grid


# (group label, formats); the default "fill the page" format has the key "".
FORMAT_GROUPS: list[tuple[str, list[CellFormat]]] = [
    (
        "Aspect ratio",
        [
            CellFormat("1:1", "Square 1:1", 1, 1, False),
            CellFormat("5:4", "5:4", 5, 4, False),
            CellFormat("4:3", "4:3", 4, 3, False),
            CellFormat("3:2", "3:2", 3, 2, False),
            CellFormat("16:9", "16:9", 16, 9, False),
        ],
    ),
    (
        "Photo prints",
        [
            CellFormat("passport", "Passport photo 35 × 45 mm", 35, 45, True),
            CellFormat("passport-us", "US passport photo 2 × 2″", 50.8, 50.8, True),
            CellFormat("9x12", "9 × 12 cm (4:3)", 90, 120, True),
            CellFormat("9x13", "9 × 13 cm (3.5 × 5″)", 88.9, 127, True),
            CellFormat("10x13", "10 × 13 cm (4:3)", 102, 136, True),
            CellFormat("10x15", "10 × 15 cm (4 × 6″)", 101.6, 152.4, True),
            CellFormat("13x18", "13 × 18 cm (5 × 7″)", 127, 177.8, True),
            CellFormat("15x20", "15 × 20 cm (6 × 8″)", 152.4, 203.2, True),
            CellFormat("20x25", "20 × 25 cm (8 × 10″)", 203.2, 254, True),
        ],
    ),
    (
        "Playing cards",
        [
            CellFormat("poker", "Poker 63.5 × 88.9 mm", 63.5, 88.9, True),
            CellFormat("bridge", "Bridge 57.2 × 88.9 mm", 57.15, 88.9, True),
            CellFormat("mtg", "Magic, Pokémon 63 × 88 mm", 63, 88, True),
            CellFormat("yugioh", "Yu-Gi-Oh! 59 × 86 mm", 59, 86, True),
            CellFormat("tarot", "Tarot 70 × 120 mm", 70, 120, True),
            CellFormat("mini-euro", "Mini Euro 44 × 68 mm", 44, 68, True),
            CellFormat("mini-american", "Mini American 41 × 63 mm", 41, 63, True),
        ],
    ),
]

FORMATS: dict[str, CellFormat] = {f.key: f for _, group in FORMAT_GROUPS for f in group}
