"""JSON, CSV, NPZ, metadata, and manifest export for recorded rollouts."""

from __future__ import annotations

import csv
from datetime import UTC, datetime
import gc
import hashlib
import json
from pathlib import Path
import tempfile
from typing import Any, Callable
from zipfile import ZIP_DEFLATED, ZipFile

import numpy as np

from .exceptions import RolloutExportError
from .types import ExportedRollout, ObservationFrame, RolloutData


LEGACY_ARTIFACT_PROFILE = "LEGACY"
MEMORY_SAFE_ARTIFACT_PROFILE = "GATE24E_MEMORY_SAFE"


def _json_value(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return value


def export_rollout(
    rollout: RolloutData,
    output_dir: str | Path,
    *,
    prefix: str = "rollout",
) -> ExportedRollout:
    """Write one complete recorded rollout package without running simulation."""

    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    files: dict[str, Path] = {}
    try:
        json_path = target / f"{prefix}.json"
        json_path.write_text(json.dumps(rollout.to_dict(), indent=2, allow_nan=False), encoding="utf-8")
        files["rollout_json"] = json_path

        csv_path = target / f"{prefix}.csv"
        _write_csv(rollout.frames, csv_path)
        files["rollout_csv"] = csv_path

        npz_path = target / f"{prefix}.npz"
        np.savez_compressed(npz_path, **_npz_arrays(rollout))
        files["rollout_npz"] = npz_path

        metadata_path = target / "metadata.json"
        metadata_path.write_text(json.dumps(_json_value(rollout.metadata), indent=2, allow_nan=False), encoding="utf-8")
        files["metadata"] = metadata_path

        manifest = {
            "schema_version": rollout.schema_version,
            "created_at": datetime.now(UTC).isoformat(),
            "frame_count": rollout.frame_count,
            "files": {},
            "metadata": _json_value(rollout.metadata),
            "scientific_scope": "Recorded FlyGym observations and software provenance only; not biological validation.",
        }
        for key, path in files.items():
            manifest["files"][key] = {
                "path": path.name,
                "byte_size": path.stat().st_size,
                "sha256": _sha256(path),
            }
        manifest_path = target / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2, allow_nan=False), encoding="utf-8")
        files["manifest"] = manifest_path
    except (OSError, TypeError, ValueError) as exc:
        raise RolloutExportError(f"Unable to export rollout to {target}") from exc

    return ExportedRollout(
        output_dir=target.as_posix(),
        files={key: path.as_posix() for key, path in files.items()},
        manifest=manifest,
    )


def export_memory_safe_rollout(
    rollout: RolloutData,
    output_dir: str | Path,
    *,
    prefix: str = "rollout",
) -> ExportedRollout:
    """Export the Gate24 long-rollout profile without frame-list materialization.

    The legacy JSON and CSV writers remain intentionally untouched.  This
    profile writes each numeric channel to a temporary ``.npy`` memmap and
    packages those files into a compressed NPZ archive.  No call to
    ``RolloutData.to_dict`` or ``ObservationFrame.to_dict`` is made.
    """

    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    if rollout.frame_count <= 0:
        raise RolloutExportError("A memory-safe rollout must contain at least one frame")

    try:
        with tempfile.TemporaryDirectory(prefix=".memory-safe-", dir=target) as temporary:
            temporary_root = Path(temporary)
            specs = _memory_safe_channel_specs(rollout)
            mapped: dict[str, np.memmap] = {}
            mapped_paths: dict[str, Path] = {}
            try:
                for name, dtype, shape, _getter in specs:
                    path = temporary_root / f"{name}.npy"
                    mapped[name] = np.lib.format.open_memmap(
                        path,
                        mode="w+",
                        dtype=dtype,
                        shape=(rollout.frame_count, *shape),
                    )
                    mapped_paths[name] = path

                for frame_index, frame in enumerate(rollout.frames):
                    for name, _dtype, shape, getter in specs:
                        value = np.asarray(getter(frame), dtype=mapped[name].dtype)
                        if value.shape != shape:
                            raise RolloutExportError(
                                f"Channel {name!r} changed shape at frame {frame_index}: "
                                f"expected {shape}, got {value.shape}"
                            )
                        mapped[name][frame_index] = value
                for array in mapped.values():
                    array.flush()
                    mmap_handle = getattr(array, "_mmap", None)
                    if mmap_handle is not None:
                        mmap_handle.close()
                del array
            finally:
                mapped.clear()
                gc.collect()

            npz_path = target / f"{prefix}.npz"
            _write_npz_from_npy(mapped_paths, npz_path)

        metadata = _json_value({
            **rollout.metadata,
            "artifact_profile": MEMORY_SAFE_ARTIFACT_PROFILE,
            "full_frame_rollout_json": False,
            "viewer_export": "SKIPPED_NOT_REQUIRED_FOR_GATE24E_PRIMARY_VALIDATION",
            "viewer_is_scientific_metric": False,
            "video": False,
            "optional_postprocess": "SKIPPED_OPTIONAL_POSTPROCESS",
        })
        metadata_path = target / "metadata.json"
        metadata_path.write_text(json.dumps(metadata, indent=2, allow_nan=False) + "\n", encoding="utf-8")

        index = {
            "schema_version": "flygym-rollout-index-1",
            "artifact_profile": MEMORY_SAFE_ARTIFACT_PROFILE,
            "frame_count": rollout.frame_count,
            "npz_path": npz_path.name,
            "npz_sha256": _sha256(npz_path),
            "metadata": metadata,
            "full_frame_rollout_json": False,
        }
        index_path = target / "rollout_index.json"
        index_path.write_text(json.dumps(index, indent=2, allow_nan=False) + "\n", encoding="utf-8")

        files = {
            npz_path.name: npz_path,
            metadata_path.name: metadata_path,
            index_path.name: index_path,
        }
        manifest = _memory_safe_manifest(rollout, files)
        manifest_path = target / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        files[manifest_path.name] = manifest_path
    except (OSError, TypeError, ValueError, KeyError, RuntimeError) as exc:
        raise RolloutExportError(f"Unable to export memory-safe rollout to {target}") from exc

    return ExportedRollout(
        output_dir=target.as_posix(),
        files={
            "rollout_npz": npz_path.as_posix(),
            "metadata": metadata_path.as_posix(),
            "rollout_index": index_path.as_posix(),
            "manifest": manifest_path.as_posix(),
        },
        manifest=manifest,
    )


def refresh_memory_safe_manifest(output_dir: str | Path) -> Path:
    """Refresh a memory-safe manifest after scalar post-processing completes."""

    target = Path(output_dir)
    manifest_path = target / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Memory-safe manifest not found: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"] = {
        path.relative_to(target).as_posix(): {
            "path": path.relative_to(target).as_posix(),
            "byte_size": path.stat().st_size,
            "sha256": _sha256(path),
        }
        for path in sorted(target.rglob("*"))
        if path.is_file() and path != manifest_path
    }
    manifest["updated_at"] = datetime.now(UTC).isoformat()
    manifest_path.write_text(json.dumps(manifest, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return manifest_path


def _write_csv(frames: list[ObservationFrame], path: Path) -> None:
    fields = ["timestamp_s", "step", "thorax", "com", "orientation", "body_positions", "body_orientations", "joint_positions", "joint_velocity", "joint_acceleration", "contact", "actuator"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for frame in frames:
            row = frame.to_dict()
            writer.writerow({
                key: (json.dumps(value, separators=(",", ":")) if isinstance(value, (list, dict)) else value)
                for key, value in row.items()
            })


def _npz_arrays(rollout: RolloutData) -> dict[str, np.ndarray]:
    arrays: dict[str, np.ndarray] = {
        "timestamp_s": np.asarray([frame.timestamp_s for frame in rollout.frames], dtype=float),
        "step": np.asarray([frame.step for frame in rollout.frames], dtype=np.int64),
    }
    for name in ("thorax", "com", "orientation", "body_positions", "body_orientations", "joint_positions", "joint_velocity", "joint_acceleration"):
        values = [getattr(frame, name) for frame in rollout.frames]
        if values and all(value is not None for value in values):
            arrays[name] = np.stack(values)
    if "timestamp_s" in arrays:
        arrays["time_s"] = arrays["timestamp_s"].copy()
    if "thorax" in arrays:
        arrays["thorax_positions"] = arrays["thorax"].copy()
    if "orientation" in arrays:
        arrays["thorax_quaternions"] = arrays["orientation"].copy()
    for key in ("found", "forces", "torques", "positions", "normals", "tangents"):
        values = [frame.contact.get(key) if frame.contact is not None else None for frame in rollout.frames]
        if values and all(value is not None for value in values):
            arrays[f"contact_{key}"] = np.stack(values)
    actuator_keys = sorted({key for frame in rollout.frames for key in frame.actuator})
    for key in actuator_keys:
        values = [frame.actuator.get(key) for frame in rollout.frames]
        if values and all(value is not None for value in values):
            arrays[f"actuator_{key}"] = np.stack(values)
    return arrays


ChannelGetter = Callable[[ObservationFrame], Any]
ChannelSpec = tuple[str, np.dtype, tuple[int, ...], ChannelGetter]


def _memory_safe_channel_specs(rollout: RolloutData) -> list[ChannelSpec]:
    """Describe legacy NPZ channels without collecting per-channel values."""

    specs: list[ChannelSpec] = []
    specs.extend([
        ("timestamp_s", np.dtype(float), (), lambda frame: frame.timestamp_s),
        ("step", np.dtype(np.int64), (), lambda frame: frame.step),
    ])
    for name in (
        "thorax",
        "com",
        "orientation",
        "body_positions",
        "body_orientations",
        "joint_positions",
        "joint_velocity",
        "joint_acceleration",
    ):
        spec = _spec_if_complete(rollout, name, lambda frame, key=name: getattr(frame, key))
        if spec is not None:
            specs.append(spec)
    specs.extend([
        ("time_s", np.dtype(float), (), lambda frame: frame.timestamp_s),
    ])
    if any(frame.thorax is not None for frame in rollout.frames):
        spec = _spec_if_complete(rollout, "thorax_positions", lambda frame: frame.thorax)
        if spec is not None:
            specs.append(spec)
    if any(frame.orientation is not None for frame in rollout.frames):
        spec = _spec_if_complete(rollout, "thorax_quaternions", lambda frame: frame.orientation)
        if spec is not None:
            specs.append(spec)
    for key in ("found", "forces", "torques", "positions", "normals", "tangents"):
        spec = _spec_if_complete(
            rollout,
            f"contact_{key}",
            lambda frame, key=key: frame.contact.get(key) if frame.contact is not None else None,
        )
        if spec is not None:
            specs.append(spec)
    actuator_keys = sorted({key for frame in rollout.frames for key in frame.actuator})
    for key in actuator_keys:
        spec = _spec_if_complete(
            rollout,
            f"actuator_{key}",
            lambda frame, key=key: frame.actuator.get(key),
        )
        if spec is not None:
            specs.append(spec)
    return specs


def _spec_if_complete(
    rollout: RolloutData,
    name: str,
    getter: ChannelGetter,
) -> ChannelSpec | None:
    first: np.ndarray | None = None
    dtype: np.dtype | None = None
    for frame in rollout.frames:
        raw = getter(frame)
        if raw is None:
            return None
        value = np.asarray(raw)
        if first is None:
            first = value
            dtype = value.dtype
        elif value.shape != first.shape:
            raise RolloutExportError(
                f"Channel {name!r} has inconsistent shapes: {first.shape} and {value.shape}"
            )
        else:
            dtype = np.result_type(dtype, value.dtype)
    if first is None:
        return None
    shape = first.shape
    return name, np.dtype(dtype), shape, getter


def _write_npz_from_npy(files: dict[str, Path], output: Path) -> None:
    """Create an NPZ by streaming already materialized NPY channels."""

    partial = output.with_name(output.name + ".part")
    if partial.exists():
        partial.unlink()
    try:
        with ZipFile(partial, "w", compression=ZIP_DEFLATED, compresslevel=6, allowZip64=True) as archive:
            for name, path in files.items():
                archive.write(path, f"{name}.npy")
        partial.replace(output)
    finally:
        if partial.exists():
            partial.unlink()


def _memory_safe_manifest(rollout: RolloutData, files: dict[str, Path]) -> dict[str, Any]:
    return {
        "schema_version": rollout.schema_version,
        "artifact_profile": MEMORY_SAFE_ARTIFACT_PROFILE,
        "created_at": datetime.now(UTC).isoformat(),
        "frame_count": rollout.frame_count,
        "files": {
            name: {
                "path": path.name,
                "byte_size": path.stat().st_size,
                "sha256": _sha256(path),
            }
            for name, path in files.items()
        },
        "metadata": _json_value(rollout.metadata),
        "full_frame_rollout_json": False,
        "viewer_required": False,
        "scientific_scope": (
            "Recorded FlyGym observations and software provenance only; "
            "not biological validation."
        ),
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


__all__ = [
    "LEGACY_ARTIFACT_PROFILE",
    "MEMORY_SAFE_ARTIFACT_PROFILE",
    "export_memory_safe_rollout",
    "export_rollout",
    "refresh_memory_safe_manifest",
]
