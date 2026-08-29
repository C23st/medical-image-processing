"""图像增强算法层: 灰度变换 / 直方图 / 空间滤波。

所有函数输入输出均为 float32 数组。
  - 灰度变换与直方图类: 输出归一化到 [0, 255] (便于窗宽窗位全范围显示)
  - 空间滤波类: 保持原始灰度范围 (HU 值)
"""
from __future__ import annotations

import cv2
import numpy as np
from scipy import ndimage
from skimage import exposure

# ---- 内部工具 ----
def _to_unit(img):
    """线性缩放到 [0, 1]。"""
    img = img.astype(np.float32)
    lo = float(img.min())
    hi = float(img.max())
    if hi - lo < 1e-8:
        return np.zeros_like(img, dtype=np.float32)
    return (img - lo) / (hi - lo)


def _normalize(img):
    """缩放到 [0, 255]。"""
    return (_to_unit(img) * 255.0).astype(np.float32)


# ---- 灰度变换 ----
def linear_stretch(img, low_pct=2.0, high_pct=98.0):
    """线性拉伸 (百分位截断): 将 [P_low, P_high] 线性映射到 [0, 255]。

    截掉两端极值 (噪声/空气/金属), 把主体灰度真正撑满量程。
    对窗宽窗位已覆盖全范围的 CT, 纯 min-max 拉伸视觉无变化, 百分位截断更有效。
    """
    img = img.astype(np.float32)
    lo = float(np.percentile(img, low_pct))
    hi = float(np.percentile(img, high_pct))
    if hi - lo < 1e-8:
        return np.zeros_like(img, dtype=np.float32)
    out = np.clip((img - lo) / (hi - lo), 0.0, 1.0)
    return (out * 255.0).astype(np.float32)


def log_transform(img):
    """对数变换 log(1 + x), 增强暗部细节。"""
    img = img.astype(np.float32)
    shifted = img - img.min() + 1.0
    return _normalize(np.log1p(shifted))


def gamma_transform(img, gamma=1.0):
    """伽马 (幂次) 变换; gamma<1 提亮, gamma>1 压暗。"""
    u = _to_unit(img)
    return _normalize(np.power(u, max(gamma, 1e-6)))


# ---- 直方图 ----
def hist_equalize(img):
    """全局直方图均衡化。"""
    return _normalize(exposure.equalize_hist(_to_unit(img)))


def clahe(img, clip_limit=0.02):
    """对比度受限自适应直方图均衡 (CLAHE)。"""
    return _normalize(exposure.equalize_adapthist(_to_unit(img), clip_limit=clip_limit))


# ---- 空间滤波 (保持灰度范围) ----
def mean_filter(img, size=3):
    """均值滤波 (平滑)。"""
    return ndimage.uniform_filter(img.astype(np.float32), size=size)


def median_filter(img, size=3):
    """中值滤波 (去椒盐噪声)。"""
    return ndimage.median_filter(img.astype(np.float32), size=size)


def gaussian_filter(img, sigma=1.0):
    """高斯滤波 (平滑)。"""
    return ndimage.gaussian_filter(img.astype(np.float32), sigma=sigma)


def sharpen(img, amount=1.0):
    """反锐化掩模锐化: img + amount * (img - gaussian(img))。"""
    img = img.astype(np.float32)
    blurred = ndimage.gaussian_filter(img, sigma=1.0)
    return img + amount * (img - blurred)


# ---- 频域滤波 ----
def fft_filter(img, kind="lowpass", cutoff=0.1, width=0.1, order=2):
    """频域滤波 (2D FFT + Butterworth 掩膜): 低通/高通/带通。

    cutoff/width 为归一化频率 (0~0.5 量级); 输出归一化到 [0,255] 便于显示。
    """
    img = img.astype(np.float32)
    rows, cols = img.shape
    cy, cx = rows // 2, cols // 2
    yy, xx = np.mgrid[0:rows, 0:cols]
    r = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2) / (max(rows, cols) * 0.5)

    c0 = max(cutoff, 1e-4)
    butter = 1.0 / (1.0 + (r / c0) ** (2 * order))
    if kind == "highpass":
        mask = 1.0 - butter
    elif kind == "bandpass":
        butter_hi = 1.0 / (1.0 + (r / max(cutoff + width, 1e-4)) ** (2 * order))
        mask = butter - butter_hi
    else:  # lowpass
        mask = butter

    fshift = np.fft.fftshift(np.fft.fft2(img)) * mask
    out = np.real(np.fft.ifft2(np.fft.ifftshift(fshift)))
    return _normalize(out)


# ---- 双边滤波 (保边去噪, 保持原始灰度范围) ----
def bilateral(img, sigma_space=9.0, sigma_color=75.0):
    """双边滤波 (OpenCV): 去噪同时保留边缘; 保持原始 HU 范围。"""
    img = img.astype(np.float32)
    lo, hi = float(img.min()), float(img.max())
    if hi - lo < 1e-8:
        return img
    u = np.clip((img - lo) / (hi - lo) * 255.0, 0, 255).astype(np.uint8)
    d = max(3, min(int(sigma_space) * 2 + 1, 21))  # 奇数直径
    out = cv2.bilateralFilter(u, d, float(sigma_color), float(sigma_space))
    return (out.astype(np.float32) / 255.0 * (hi - lo) + lo).astype(np.float32)


# ---- 同态滤波 ----
def homomorphic(img, gamma_low=0.4, gamma_high=1.5, cutoff=0.1):
    """同态滤波: 压缩动态范围并增强对比度 (对数域 + 高通增强 + 指数还原)。"""
    img = img.astype(np.float32)
    shifted = img - img.min() + 1.0  # 平移到正区间, 避免对负数取对数
    rows, cols = img.shape
    cy, cx = rows // 2, cols // 2
    yy, xx = np.mgrid[0:rows, 0:cols]
    d2 = (xx - cx) ** 2 + (yy - cy) ** 2
    d0 = max(rows, cols) * max(cutoff, 1e-3)
    h = (gamma_high - gamma_low) * (1.0 - np.exp(-d2 / (d0 * d0))) + gamma_low
    fshift = np.fft.fftshift(np.fft.fft2(np.log(shifted))) * h
    log_out = np.clip(np.real(np.fft.ifft2(np.fft.ifftshift(fshift))), -50.0, 50.0)
    out = np.exp(log_out) - 1.0
    return _normalize(out)


# ---- 方法注册表 ----
# key -> (显示名, 函数, 默认参数)
METHODS = {
    "linear": ("线性拉伸", linear_stretch, {"low_pct": 2.0, "high_pct": 98.0}),
    "log": ("对数变换", log_transform, {}),
    "gamma": ("伽马变换", gamma_transform, {"gamma": 1.0}),
    "hist_eq": ("直方图均衡", hist_equalize, {}),
    "clahe": ("CLAHE", clahe, {"clip_limit": 0.02}),
    "mean": ("均值滤波", mean_filter, {"size": 3}),
    "median": ("中值滤波", median_filter, {"size": 3}),
    "gaussian": ("高斯滤波", gaussian_filter, {"sigma": 1.0}),
    "sharpen": ("锐化", sharpen, {"amount": 1.0}),
    "fft": ("频域滤波", fft_filter, {"kind": "lowpass", "cutoff": 0.1, "width": 0.1}),
    "bilateral": ("双边滤波", bilateral, {"sigma_space": 9.0, "sigma_color": 75.0}),
    "homomorphic": ("同态滤波", homomorphic, {"gamma_low": 0.4, "gamma_high": 1.5, "cutoff": 0.1}),
}

# 逐切片处理的方法 (滤波/CLAHE 保持 2D 语义且更快)
_SLICE_WISE = {"clahe", "mean", "median", "gaussian", "sharpen", "fft", "bilateral", "homomorphic"}

# 保持原始灰度 (HU) 范围的方法: 增强后窗宽窗位应沿用原始值
_PRESERVE_RANGE = {"mean", "median", "gaussian", "sharpen", "bilateral"}


def preserves_range(method):
    """该方法增强后是否保持原始灰度 (HU) 范围 (窗宽窗位沿用原值)。"""
    return method in _PRESERVE_RANGE


def apply(data, method, params=None):
    """对体数据 (z, y, x) 应用增强, 返回同形状 float32 数组。

    全局类方法直接作用于整个体数据; 滤波类逐切片 (2D) 处理。
    """
    if method not in METHODS:
        raise ValueError(f"未知增强方法: {method}")

    _label, func, defaults = METHODS[method]
    p = dict(defaults)
    if params:
        p.update(params)
    data = np.asarray(data, dtype=np.float32)

    if method in _SLICE_WISE:
        out = np.empty_like(data, dtype=np.float32)
        for z in range(data.shape[0]):
            out[z] = func(data[z], **p)
        return out
    return func(data, **p).astype(np.float32)
