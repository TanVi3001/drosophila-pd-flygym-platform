"""Schema constants for the read-only Web viewer pose interchange format."""

from __future__ import annotations

from typing import Any


VECTOR3_SCHEMA: dict[str, Any] = {
    "type": "array",
    "minItems": 3,
    "maxItems": 3,
    "items": {"type": "number"},
}

QUATERNION_SCHEMA: dict[str, Any] = {
    "type": "array",
    "minItems": 4,
    "maxItems": 4,
    "items": {"type": "number"},
}

SERIES_VALUE_SCHEMA: dict[str, Any] = {
    "oneOf": [
        {"type": "number"},
        {"type": "array", "items": {"type": "number"}},
        {"type": "null"},
    ]
}

FRAME_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": [
        "frame_index",
        "time",
        "thorax",
        "position",
        "orientation",
        "COM",
        "joint_angles",
        "joint_velocity",
        "joint_acceleration",
        "contacts",
        "trajectory",
        "visibility",
    ],
    "properties": {
        "frame_index": {"type": "integer", "minimum": 0},
        "time": {"type": "number", "minimum": 0},
        "thorax": VECTOR3_SCHEMA,
        "position": VECTOR3_SCHEMA,
        "orientation": QUATERNION_SCHEMA,
        "COM": {"oneOf": [VECTOR3_SCHEMA, {"type": "null"}]},
        "joint_angles": {"type": "object", "additionalProperties": SERIES_VALUE_SCHEMA},
        "joint_velocity": {"type": "object", "additionalProperties": SERIES_VALUE_SCHEMA},
        "joint_velocities": {"type": "object", "additionalProperties": SERIES_VALUE_SCHEMA},
        "joint_acceleration": {"type": "object", "additionalProperties": SERIES_VALUE_SCHEMA},
        "contacts": {"type": "object"},
        "trajectory": {"type": "object"},
        "visibility": {"type": "object", "additionalProperties": {"type": "boolean"}},
    },
    "additionalProperties": True,
}

MESH_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["renderer", "render_mode", "scientific_mesh", "visibility"],
    "properties": {
        "renderer": {"type": "string"},
        "render_mode": {"type": "string"},
        "scientific_mesh": {"type": "boolean"},
        "asset": {"oneOf": [{"type": "object"}, {"type": "null"}]},
        "asset_status": {"type": "string"},
        "body_parts": {"type": "array", "items": {"type": "string"}},
        "body_hierarchy": {"type": "array", "items": {"type": "object"}},
        "segments": {"type": "array", "items": {"type": "object"}},
        "mesh_instances": {"type": "array", "items": {"type": "object"}},
        "bones": {"type": "array", "items": {"type": "object"}},
        "materials": {"type": "object"},
        "visibility": {"type": "object", "additionalProperties": {"type": "boolean"}},
    },
    "additionalProperties": True,
}

VIEWER_POSE_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://github.com/tuanwannafly/drosophila-pd-flygym/blob/main/docs/api/viewer_pose.schema.json",
    "title": "Fly Studio Viewer Pose",
    "type": "object",
    "required": ["metadata", "fps", "frame_count", "joint_names", "mesh", "frames"],
    "properties": {
        "metadata": {"type": "object"},
        "fps": {"type": "number", "exclusiveMinimum": 0},
        "frame_count": {"type": "integer", "minimum": 1},
        "joint_names": {"type": "array", "items": {"type": "string"}},
        "mesh": MESH_SCHEMA,
        "frames": {"type": "array", "minItems": 1, "items": FRAME_SCHEMA},
    },
    "additionalProperties": True,
}


def schema() -> dict[str, Any]:
    """Return the immutable-by-convention schema mapping for callers."""

    return VIEWER_POSE_SCHEMA


__all__ = ["FRAME_SCHEMA", "MESH_SCHEMA", "VIEWER_POSE_SCHEMA", "schema"]
