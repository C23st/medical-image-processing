"""P5 三维重建测试 (无 GL): 面绘制管线输出 / 体绘制构建 / 参数面板集成。

用法:
    D:\\Anaconda_Envs\\medimg\\python.exe scripts/test_reconstruct.py
"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import vtk  # noqa: E402

from app.core.dicom_loader import load_dicom_series  # noqa: E402

TEST_DATA = os.path.join(ROOT, "test_data")


def test_surface():
    print("== 面绘制 (Marching Cubes) ==")
    volumes = load_dicom_series(TEST_DATA)
    ct = next(v for v in volumes if v.modality == "CT" and v.patient["id"] == "PANCREAS_0001")
    image = ct.to_vtk_image(apply_direction=True)
    assert image.GetDirectionMatrix() is not None
    for name, thresh in (("骨", 300.0), ("软组织", 40.0), ("皮肤", -150.0)):
        mc = vtk.vtkFlyingEdges3D()
        mc.SetInputData(image)
        mc.SetValue(0, thresh)
        mc.Update()
        n = mc.GetOutput().GetNumberOfPoints()
        print(f"  阈值 {thresh:6.1f} ({name}): {n} 个顶点")
        assert n > 0
    print("  面绘制管线: OK")


def test_volume():
    print("\n== 体绘制管线构建 ==")
    volumes = load_dicom_series(TEST_DATA)
    ct = next(v for v in volumes if v.modality == "CT" and v.patient["id"] == "PANCREAS_0001")
    image = ct.to_vtk_image(apply_direction=True)
    lo, hi = image.GetScalarRange()
    assert lo < hi
    ctf = vtk.vtkColorTransferFunction()
    ctf.AddRGBPoint(lo, 0, 0, 0)
    ctf.AddRGBPoint(hi, 1, 1, 1)
    otf = vtk.vtkPiecewiseFunction()
    otf.AddPoint(lo, 0.0)
    otf.AddPoint(hi, 0.5)
    prop = vtk.vtkVolumeProperty()
    prop.SetColor(ctf)
    prop.SetScalarOpacity(otf)
    mapper = vtk.vtkSmartVolumeMapper()
    mapper.SetInputData(image)
    volume = vtk.vtkVolume()
    volume.SetMapper(mapper)
    volume.SetProperty(prop)
    assert volume.GetProperty() is not None and volume.GetMapper() is not None
    assert prop.GetRGBTransferFunction() is ctf and prop.GetScalarOpacity() is otf
    print(f"  数据范围 [{lo:.0f}, {hi:.0f}], 体绘制对象构建: OK")


def test_panel():
    print("\n== 参数面板集成 ==")
    from PySide6.QtWidgets import QApplication

    from app.widgets.params_panel import ParamsPanel

    app = QApplication.instance() or QApplication([])
    p = ParamsPanel()
    assert p.count() == 4
    assert p.recon_combo.currentData() == "surface"  # 默认面绘制
    assert p._recon_form.isRowVisible(p._recon_thresh_row) is True
    assert p._recon_form.isRowVisible(p._recon_opacity_row) is False

    got = {}
    p.reconstruct_apply.connect(lambda m, d: got.update({m: d}))
    p.recon_combo.setCurrentIndex(1)  # 体绘制
    assert p._recon_form.isRowVisible(p._recon_thresh_row) is False
    assert p._recon_form.isRowVisible(p._recon_opacity_row) is True
    p._emit_reconstruct_apply()
    assert got.get("volume", {}).get("opacity") is not None
    print("  重建页签/参数显隐/信号: OK")


if __name__ == "__main__":
    test_surface()
    test_volume()
    test_panel()
    print("\n三维重建测试: OK")
