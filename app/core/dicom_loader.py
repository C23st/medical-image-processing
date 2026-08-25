"""DICOM 序列加载器: 扫描目录, 按序列分组并构建体数据。

支持:
  - 单帧序列 (每个切片一个文件, 按 ImagePositionPatient 排序)
  - 多帧序列 (NumberOfFrames > 1, 单个文件含全部帧)
  - 按 SOPInstanceUID 去重 (避免重复文件导致体数据错位)
"""
from __future__ import annotations

import os

import numpy as np
import pydicom

from .volume import VolumeData


def _val(ds, name, default=None):
    try:
        v = getattr(ds, name)
    except Exception:
        return default
    if v is None or v == "":
        return default
    return v


def load_dicom_series(directory):
    """递归扫描目录, 按 SeriesInstanceUID 分组, 返回 list[VolumeData]。

    仅保留含 PixelData 的序列; CT/MR 排在前面, 其余 (SEG 等) 靠后。
    """
    grouped = {}
    for root, _dirs, files in os.walk(directory):
        for fn in files:
            if not fn.lower().endswith(".dcm"):
                continue
            path = os.path.join(root, fn)
            try:
                ds = pydicom.dcmread(path, force=True)
            except Exception:
                continue
            if not hasattr(ds, "PixelData"):
                continue
            sid = str(_val(ds, "SeriesInstanceUID", "unknown"))
            grouped.setdefault(sid, []).append(ds)

    volumes = []
    for sid, items in grouped.items():
        vol = _build_volume(items)
        if vol is not None:
            volumes.append(vol)

    volumes.sort(
        key=lambda v: (
            v.modality not in ("CT", "MR"),
            v.patient.get("id", ""),
            v.series_description,
        )
    )
    return volumes


def _build_volume(items):
    # 去重 (按 SOPInstanceUID)
    seen = set()
    unique = []
    for ds in items:
        uid = str(_val(ds, "SOPInstanceUID", id(ds)))
        if uid in seen:
            continue
        seen.add(uid)
        unique.append(ds)
    items = unique
    if not items:
        return None

    first = items[0]
    modality = str(_val(first, "Modality", "OT"))

    # 方向余弦 -> 切片法向量 (用于排序; P5/P6 再构造方向矩阵)
    row = np.array([1.0, 0.0, 0.0])
    col = np.array([0.0, 1.0, 0.0])
    try:
        iop = [float(v) for v in first.ImageOrientationPatient]
        row = np.array(iop[0:3])
        col = np.array(iop[3:6])
    except Exception:
        pass
    normal = np.cross(row, col)
    n = np.linalg.norm(normal)
    if n > 0:
        normal = normal / n
    # 方向余弦矩阵 (3x3, 列分别为 x/y/z 轴方向余弦)
    direction = np.column_stack([row, col, normal])

    nframes = int(_val(first, "NumberOfFrames", 0) or 0)

    if nframes > 1:
        # 多帧: 单文件含全部帧
        data = first.pixel_array.astype(np.float32)
        if data.ndim == 2:
            data = data[np.newaxis, ...]
        z, y, x = data.shape
        slope = float(_val(first, "RescaleSlope", 1) or 1)
        intercept = float(_val(first, "RescaleIntercept", 0) or 0)
        data = data * slope + intercept
        sx, sy = _pixel_spacing(first)
        sz = float(_val(first, "SpacingBetweenSlices", 0) or _val(first, "SliceThickness", 0) or 1.0)
        origin = _position(first)
        positions = _frame_positions(first, nframes)
    else:
        # 单帧: 每切片一个文件, 按沿法向位置排序
        def pos(ds):
            p = np.array(_position(ds))
            return float(np.dot(p, normal))

        items = sorted(items, key=pos)
        arrays = []
        for ds in items:
            arr = ds.pixel_array.astype(np.float32)
            slope = float(_val(ds, "RescaleSlope", 1) or 1)
            intercept = float(_val(ds, "RescaleIntercept", 0) or 0)
            arrays.append(arr * slope + intercept)
        data = np.stack(arrays, axis=0)
        z, y, x = data.shape
        sx, sy = _pixel_spacing(first)
        if len(items) > 1:
            positions = [pos(ds) for ds in items]
            dz = float(np.median(np.abs(np.diff(positions))))
            if dz <= 0:
                dz = float(_val(first, "SliceThickness", 1.0) or 1.0)
        else:
            dz = float(_val(first, "SliceThickness", 1.0) or 1.0)
        sz = dz
        origin = _position(items[0])
        positions = [_position(ds) for ds in items]

    window, level = _window_level(first)
    patient = {
        "name": str(_val(first, "PatientName", "Unknown")),
        "id": str(_val(first, "PatientID", "Unknown")),
        "study_date": str(_val(first, "StudyDate", "")),
        "series_uid": str(_val(first, "SeriesInstanceUID", "")),
        "series_number": str(_val(first, "SeriesNumber", "")),
    }
    series_description = str(_val(first, "SeriesDescription", "") or "")

    return VolumeData(
        data=data,
        spacing=(sx, sy, sz),
        origin=tuple(float(v) for v in origin),
        direction=direction,
        modality=modality,
        patient=patient,
        window=window,
        level=level,
        series_description=series_description,
        slice_positions=np.asarray(positions, dtype=float) if positions is not None else None,
    )


def _frame_positions(ds, nframes):
    """读取多帧 SEG/增强对象的逐帧 ImagePositionPatient。"""
    try:
        fg = ds.PerFrameFunctionalGroupsSequence
        positions = []
        for fr in fg:
            p = fr.PlanePositionSequence[0].ImagePositionPatient
            positions.append([float(v) for v in p])
        if len(positions) == nframes:
            return positions
    except Exception:
        pass
    return None


def _pixel_spacing(ds):
    try:
        sx, sy = float(ds.PixelSpacing[0]), float(ds.PixelSpacing[1])
        return sx, sy
    except Exception:
        return 1.0, 1.0


def _position(ds):
    try:
        return [float(v) for v in ds.ImagePositionPatient]
    except Exception:
        return [0.0, 0.0, 0.0]


def _window_level(ds):
    try:
        ww = _val(ds, "WindowWidth", None)
        wl = _val(ds, "WindowCenter", None)
        if ww is None or wl is None:
            return None, None
        if isinstance(ww, (list, tuple, pydicom.multival.MultiValue)):
            ww = ww[0]
        if isinstance(wl, (list, tuple, pydicom.multival.MultiValue)):
            wl = wl[0]
        return float(ww), float(wl)
    except Exception:
        return None, None
