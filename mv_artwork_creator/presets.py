from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AnglePreset:
    id: str
    label: str


@dataclass(frozen=True)
class ShotPreset:
    id: str
    label: str


ANGLE_PRESETS: dict[str, AnglePreset] = {
    "front": AnglePreset("front", "Front"),
    "front_45_left": AnglePreset("front_45_left", "Front 45 left"),
    "front_45_right": AnglePreset("front_45_right", "Front 45 right"),
    "left_side": AnglePreset("left_side", "Left side"),
    "right_side": AnglePreset("right_side", "Right side"),
    "back_45_left": AnglePreset("back_45_left", "Back 45 left"),
    "back_45_right": AnglePreset("back_45_right", "Back 45 right"),
    "back": AnglePreset("back", "Back"),
}

SHOT_PRESETS: dict[str, ShotPreset] = {
    "portrait": ShotPreset("portrait", "Portrait"),
    "half_body": ShotPreset("half_body", "Half-body"),
    "full_body": ShotPreset("full_body", "Full-body"),
}

DEFAULT_REFERENCE_MATRIX: list[tuple[str, str]] = [
    ("front", "portrait"),
    ("front", "half_body"),
    ("front", "full_body"),
    ("front_45_left", "portrait"),
    ("front_45_left", "half_body"),
    ("front_45_left", "full_body"),
    ("front_45_right", "portrait"),
    ("front_45_right", "half_body"),
    ("front_45_right", "full_body"),
    ("left_side", "portrait"),
    ("left_side", "half_body"),
    ("left_side", "full_body"),
    ("right_side", "portrait"),
    ("right_side", "half_body"),
    ("right_side", "full_body"),
    ("back_45_left", "half_body"),
    ("back_45_left", "full_body"),
    ("back_45_right", "half_body"),
    ("back_45_right", "full_body"),
    ("back", "half_body"),
    ("back", "full_body"),
]

DEFAULT_TEST_PRESET = "front:portrait"


def parse_preset(value: str) -> tuple[str, str]:
    if ":" not in value:
        raise ValueError(f"Preset must use angle:shot format: {value}")
    angle_id, shot_id = [part.strip() for part in value.split(":", 1)]
    if angle_id not in ANGLE_PRESETS:
        raise ValueError(f"Unknown angle preset: {angle_id}")
    if shot_id not in SHOT_PRESETS:
        raise ValueError(f"Unknown shot preset: {shot_id}")
    return angle_id, shot_id


def resolve_matrix(presets: list[str] | None, test_mode: bool, test_preset: str | None) -> list[tuple[str, str]]:
    if test_mode:
        return [parse_preset(test_preset or DEFAULT_TEST_PRESET)]
    if presets:
        return [parse_preset(preset) for preset in presets]
    return list(DEFAULT_REFERENCE_MATRIX)
