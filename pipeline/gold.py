"""Quy đổi vàng thế giới -> đồng/lượng và độ chênh (premium) so với SJC.

Hằng số:
  - 1 troy ounce = 31,1034768 g (định nghĩa chuẩn).
  - 1 lượng = 37,5 g (đơn vị vàng miếng Việt Nam; 1 lượng = 10 chỉ, 1 chỉ = 3,75 g).
Cần đối chiếu hai hằng số này với nguồn chính thức khi hoàn thiện docs/methodology.md.
"""
from __future__ import annotations

TROY_OUNCE_G = 31.1034768
LUONG_G = 37.5


def world_price_vnd_per_luong(xau_usd_per_oz: float, usdvnd: float) -> float:
    return xau_usd_per_oz * usdvnd * LUONG_G / TROY_OUNCE_G


def premium(sjc_vnd_per_luong: float, xau_usd_per_oz: float, usdvnd: float) -> float:
    """premium = SJC / giá thế giới quy đổi - 1 (tỷ lệ; 0,12 = 12%)."""
    return sjc_vnd_per_luong / world_price_vnd_per_luong(xau_usd_per_oz, usdvnd) - 1
