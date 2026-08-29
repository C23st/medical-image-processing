"""离屏测试: 分割页参数显隐逻辑。"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from PySide6.QtWidgets import QApplication  # noqa: E402

from app.widgets.params_panel import ParamsPanel  # noqa: E402

app = QApplication.instance() or QApplication([])
p = ParamsPanel()
rows = {"thresh": p._thresh_row, "tol": p._tol_row}

for idx, name in [(0, "阈值分割"), (1, "Otsu"), (2, "区域生长")]:
    p.seg_combo.setCurrentIndex(idx)
    th = p._seg_form.isRowVisible(rows["thresh"])
    tl = p._seg_form.isRowVisible(rows["tol"])
    print(f"{name}: 阈值栏可见={th}, 容差栏可见={tl}")

# 断言: 阈值分割 -> 阈值可见/容差隐藏; Otsu -> 都隐藏; 区域生长 -> 阈值隐藏/容差可见
assert p._seg_form.isRowVisible(rows["thresh"]) is False
assert p._seg_form.isRowVisible(rows["tol"]) is True
p.seg_combo.setCurrentIndex(0)
assert p._seg_form.isRowVisible(rows["thresh"]) is True
assert p._seg_form.isRowVisible(rows["tol"]) is False
p.seg_combo.setCurrentIndex(1)
assert p._seg_form.isRowVisible(rows["thresh"]) is False
assert p._seg_form.isRowVisible(rows["tol"]) is False
print("参数显隐逻辑: OK")
