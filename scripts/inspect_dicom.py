"""解析 test_data 下的 DICOM 数据: 按 病人/检查/序列 分组并报告体数据信息。

用法:
    D:\\Anaconda_Envs\\medimg\\python.exe scripts/inspect_dicom.py
"""
import os
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import numpy as np  # noqa: E402
import pydicom  # noqa: E402
from pydicom.errors import InvalidDicomError  # noqa: E402

TEST_DATA = os.path.join(ROOT, "test_data")


def tag(ds, name):
    try:
        v = getattr(ds, name)
        return str(v)
    except Exception:
        return "-"


def collect_series():
    series = defaultdict(list)
    errors = 0
    for dirpath, _, filenames in os.walk(TEST_DATA):
        for fn in filenames:
            if not fn.lower().endswith(".dcm"):
                continue
            path = os.path.join(dirpath, fn)
            try:
                ds = pydicom.dcmread(path, stop_before_pixels=False)
            except (InvalidDicomError, Exception) as e:  # noqa: BLE001
                errors += 1
                continue
            key = (
                tag(ds, "PatientID"),
                tag(ds, "StudyInstanceUID"),
                tag(ds, "SeriesInstanceUID"),
            )
            series[key].append((path, ds))
    return series, errors


def analyze(series):
    for key, items in series.items():
        pid, study, sid = key
        # 排序
        def sort_key(it):
            ds = it[1]
            try:
                return float(ds.ImagePositionPatient[2])
            except Exception:
                try:
                    return float(ds.InstanceNumber)
                except Exception:
                    return 0.0

        items.sort(key=sort_key)
        n = len(items)
        first = items[0][1]
        rows, cols = first.Rows, first.Columns
        modality = tag(first, "Modality")
        try:
            sx, sy = float(first.PixelSpacing[0]), float(first.PixelSpacing[1])
        except Exception:
            sx = sy = 0.0
        # 层间距
        zs = []
        for _, ds in items:
            try:
                zs.append(float(ds.ImagePositionPatient[2]))
            except Exception:
                zs.append(0.0)
        zs = np.array(zs)
        dz = float(np.median(np.diff(zs))) if len(zs) > 1 else 0.0

        print(f"\n=== 序列 === 病人ID={pid} 模态={modality}")
        print(f"  切片数={n}  尺寸={cols}x{rows}  PixelSpacing=({sx:.3f},{sy:.3f}) 层间距={dz:.3f}")
        print(f"  SliceThickness={tag(first, 'SliceThickness')}  Orientation={tag(first, 'ImageOrientationPatient')}")
        print(f"  SeriesDescription={tag(first, 'SeriesDescription')}  Manufacturer={tag(first, 'Manufacturer')}")
        try:
            print(f"  RescaleSlope={first.RescaleSlope}  RescaleIntercept={first.RescaleIntercept}  BitsStored={first.BitsStored}")
        except Exception:
            pass
        try:
            arr = items[0][1].pixel_array
            print(f"  PixelArray dtype={arr.dtype}  min={arr.min()} max={arr.max()}")
        except Exception as e:
            print(f"  PixelArray 读取失败: {e}")
        # 体积合计
        total = n * rows * cols
        print(f"  体积大小 {cols}x{rows}x{n} = {total/1e6:.1f}M 体素")


def main():
    series, errors = collect_series()
    print(f"发现 {len(series)} 个序列, 读取错误 {errors} 个文件")
    analyze(series)


if __name__ == "__main__":
    main()
