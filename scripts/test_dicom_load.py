"""DICOM 加载测试 (无 GL): 加载 test_data 并校验体数据。

用法:
    python scripts/test_dicom_load.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from app.core.dicom_loader import load_dicom_series  # noqa: E402

TEST_DATA = os.path.join(ROOT, "test_data")


def main():
    volumes = load_dicom_series(TEST_DATA)
    print(f"加载序列数: {len(volumes)}\n")
    for i, v in enumerate(volumes):
        z, y, x = v.shape
        print(
            f"[{i}] 病人={v.patient.get('name')}/{v.patient.get('id')} "
            f"模态={v.modality} 描述={v.series_description or '-'}"
        )
        print(f"    尺寸(z,y,x)={z}x{y}x{x} 间距={tuple(round(s,3) for s in v.spacing)}")
        print(f"    WW/WL={v.window:.0f}/{v.level:.0f} 值范围=[{v.data.min():.0f}, {v.data.max():.0f}]")

        img = v.to_vtk_image()
        dims = img.GetDimensions()
        assert dims == (x, y, z), (dims, (x, y, z))
        print(f"    vtkImageData dims={dims} OK")

    # 关键校验: CT 序列去重后切片数
    cts = [v for v in volumes if v.modality == "CT"]
    assert len(cts) == 2, f"期望 2 个 CT 序列, 实际 {len(cts)}"
    z_counts = sorted(v.shape[0] for v in cts)
    assert z_counts == [195, 240], f"期望 CT 切片数 [195, 240], 实际 {z_counts}"
    print(f"\nCT 切片数校验通过: {z_counts} (含去重)")

    segs = [v for v in volumes if v.modality == "SEG"]
    print(f"SEG 序列: {len(segs)} 个, 帧数={[v.shape[0] for v in segs]}")
    print("\nDICOM 加载测试: OK")


if __name__ == "__main__":
    main()
