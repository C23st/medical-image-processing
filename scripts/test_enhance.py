"""增强模块测试 (无 GL): 算法 + 参数面板构建。

用法:
    python scripts/test_enhance.py
"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import numpy as np  # noqa: E402

from app.core import enhance  # noqa: E402
from app.core.synthetic import synthetic_ct_phantom  # noqa: E402


def test_algorithms():
    print("== 算法测试 (合成体模) ==")
    vol = synthetic_ct_phantom()
    for key, (label, _func, defaults) in enhance.METHODS.items():
        out = enhance.apply(vol, key, defaults)
        assert out.shape == vol.shape, (key, out.shape)
        assert np.isfinite(out).all(), key
        print(f"  {key:8s} {label:6s} 范围=[{out.min():.2f}, {out.max():.2f}] 均值={out.mean():.2f}")


def test_params_panel():
    print("\n== 参数面板构建测试 ==")
    from PySide6.QtWidgets import QApplication

    from app.widgets.params_panel import ParamsPanel

    app = QApplication.instance() or QApplication(sys.argv)
    panel = ParamsPanel()
    assert panel.count() == 4, panel.count()

    received = {}
    panel.enhance_apply.connect(lambda m, p: received.update({m: p}))

    # 遍历所有方法, 触发参数可见性与 emit
    for i in range(panel.method_combo.count()):
        panel.method_combo.setCurrentIndex(i)
        panel._update_param_visibility()
        panel._emit_enhance_apply()
    assert "gamma" in received and "median" in received and "sharpen" in received
    print(f"  页签数={panel.count()} 方法数={panel.method_combo.count()} 信号捕获={len(received)} 种")
    print("  参数面板: OK")


if __name__ == "__main__":
    test_algorithms()
    test_params_panel()
    print("\n增强测试: OK")
