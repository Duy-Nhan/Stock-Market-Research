"""Engine phân tích kỹ thuật top-down theo docs/analysis.md.

Mỗi nến i, mỗi khung dự báo (next_session, 1_2_weeks) → 4 nhóm bỏ phiếu độc lập (xu hướng, động lượng, khối lượng, cấu trúc giá),
mỗi nhóm bỏ phiếu -1/0/+1 dựa trên GIÁ TRỊ CHỈ BÁO CỤ THỂ; hướng và độ tin cậy suy ra từ mức đồng thuận (confluence).
Mọi phiếu tại nến i chỉ dùng dữ liệu <= i (nhân quả) — test no-lookahead.
Các quy tắc là HEURISTIC phổ biến trong phân tích kỹ thuật, KHÔNG được tinh chỉnh theo dữ liệu; hiệu quả thật được đo ở backtest.py.
Văn bản tiếng Việt do mẫu câu sinh ra từ chính các giá trị đã tính (không sinh tự do), để mỗi câu đều truy được về số liệu.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from . import candle_patterns as cpat
from . import chart_patterns as cht
from . import structure as stc
from .indicators import compute_all

ENGINE_VERSION = "1.0"
HORIZONS = ("next_session", "1_2_weeks")
GROUPS = ("trend", "momentum", "volume", "structure")
GROUP_VI = {"trend": "Xu hướng", "momentum": "Động lượng", "volume": "Khối lượng", "structure": "Cấu trúc giá"}
LOC_ATR = {"next_session": 0.75, "1_2_weeks": 1.0}
DIV_RECENT = 15   # phân kỳ chỉ xét nếu swing thứ hai được xác nhận trong 15 nến gần nhất
PAT_RECENT = 20   # mô hình giá đã xác nhận trong 20 nến gần nhất mới tham gia bỏ phiếu cấu trúc


def sgn(x: float, eps: float = 0.0) -> int:
    return 1 if x > eps else (-1 if x < -eps else 0)


def vn(x: Optional[float], d: int = 0) -> str:
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "—"
    s = f"{x:,.{d}f}"
    return s.replace(",", "§").replace(".", ",").replace("§", ".")


DIR_VI = {1: "tăng", -1: "giảm", 0: "đi ngang"}
READ_VI = {1: "ủng hộ tăng", -1: "ủng hộ giảm", 0: "trung lập"}


class Engine:
    def __init__(self, df: pd.DataFrame, ind: Optional[pd.DataFrame] = None, *, kind: str = "vn", dec: int = 0,
                 intraday: bool = False, k: int = stc.SWING_K):
        """df: cột t,o,h,l,c,v. ind: compute_all(df) (nếu None sẽ tự tính — chỉ nên truyền ind đã tính trên TOÀN BỘ lịch sử)."""
        self.df = df.reset_index(drop=True)
        self.n = len(self.df)
        self.kind, self.dec, self.intraday = kind, dec, intraday
        self.o, self.h, self.l, self.c = (self.df[x].to_numpy(float) for x in ("o", "h", "l", "c"))
        self.v = self.df["v"].to_numpy(float)
        self.has_volume = bool(self.v.sum() > 0)
        self.ind = (ind if ind is not None else compute_all(self.df, with_volume=self.has_volume)).reset_index(drop=True)
        g = lambda col: self.ind[col].to_numpy(float) if col in self.ind else np.full(self.n, np.nan)
        self.atr = g("atr14")
        self.st = stc.analyze(self.h, self.l, self.c, self.atr, k)
        self.vol_ratio = np.where(g("vol_ma20") > 0, self.v / g("vol_ma20"), np.nan) if self.has_volume else None
        self.candles = cpat.detect(self.o, self.h, self.l, self.c, self.atr, self.vol_ratio)
        self.charts = cht.detect(self.h, self.l, self.c, self.atr, self.vol_ratio, self.st["swings"])
        self._cand_at: Dict[int, List[Dict[str, Any]]] = {}
        for r in self.candles:
            self._cand_at.setdefault(r["index"], []).append(r)
        self._g = g

    # ------------------------------------------------------------------ truy vấn cấu trúc nhân quả
    def zones_at(self, i: int) -> Dict[str, List[Dict[str, float]]]:
        out = []
        for z in self.st["zones"]:
            e = None
            for ent in z["hist"]:
                if ent[0] <= i:
                    e = ent
                else:
                    break
            if e is None or e[2] < 2 or i - e[4] > 250:
                continue
            out.append({"center": e[1], "touches": e[2], "dist": e[1] - self.c[i]})
        above = sorted([z for z in out if z["dist"] > 0], key=lambda z: z["dist"])[:2]
        below = sorted([z for z in out if z["dist"] <= 0], key=lambda z: -z["dist"])[:2]
        return {"above": above, "below": below}

    def last_swings(self, i: int) -> Dict[str, Optional[Dict[str, Any]]]:
        hi = lo = hi2 = lo2 = None
        for s in self.st["swings"]:
            if s["confirmed_at"] > i:
                continue
            if s["type"] == "high":
                if hi is None or s["index"] > hi["index"]:
                    hi2, hi = hi, s
            else:
                if lo is None or s["index"] > lo["index"]:
                    lo2, lo = lo, s
        return {"high": hi, "high_prev": hi2, "low": lo, "low_prev": lo2}

    def divergence(self, i: int) -> Optional[Dict[str, Any]]:
        """Phân kỳ RSI với 2 swing cùng loại gần nhất đã xác nhận: giá tạo đỉnh cao hơn nhưng RSI thấp hơn (giảm) hoặc ngược lại (tăng)."""
        rsi = self._g("rsi14")
        ls = self.last_swings(i)
        res = None
        if ls["high"] and ls["high_prev"] and i - ls["high"]["confirmed_at"] <= DIV_RECENT:
            a, b = ls["high_prev"], ls["high"]
            if b["price"] > a["price"] and not np.isnan(rsi[a["index"]]) and not np.isnan(rsi[b["index"]]) and rsi[b["index"]] < rsi[a["index"]] - 1.0:
                res = {"type": "bearish", "price": (a["price"], b["price"]), "rsi": (float(rsi[a["index"]]), float(rsi[b["index"]]))}
        if ls["low"] and ls["low_prev"] and i - ls["low"]["confirmed_at"] <= DIV_RECENT:
            a, b = ls["low_prev"], ls["low"]
            if b["price"] < a["price"] and not np.isnan(rsi[a["index"]]) and not np.isnan(rsi[b["index"]]) and rsi[b["index"]] > rsi[a["index"]] + 1.0:
                cand = {"type": "bullish", "price": (a["price"], b["price"]), "rsi": (float(rsi[a["index"]]), float(rsi[b["index"]]))}
                if res is None or b["confirmed_at"] > ls["high"]["confirmed_at"]:
                    res = cand
        return res

    def chart_patterns_at(self, i: int) -> List[Dict[str, Any]]:
        out = []
        for p in self.charts:
            if p["formed_at"] > i:
                break
            s = cht.status_at(p, i)
            if s in ("forming", "confirmed") and i - p["formed_at"] <= 80:
                out.append({**p, "status": s})
        return out

    # ------------------------------------------------------------------ phiếu bầu
    def votes_at(self, i: int, horizon: str, with_text: bool = False) -> List[Dict[str, Any]]:
        g, c, d = self._g, self.c[i], self.dec
        a = self.atr[i]
        ema9, ema20, ema50 = g("ema9")[i], g("ema20")[i], g("ema50")[i]
        macd_h, rsi, adx = g("macd_hist")[i], g("rsi14")[i], g("adx14")[i]
        pdi, mdi, stk, pctb = g("plus_di14")[i], g("minus_di14")[i], g("stoch_k")[i], g("bb_pct_b")[i]
        dow = self.st["trend_state"][i]
        votes: List[Dict[str, Any]] = []

        def put(group: str, vote: int, text: str, ev: List[Tuple[str, Any]], na: bool = False) -> None:
            votes.append({"group": group, "group_vi": GROUP_VI[group], "vote": vote, "reading": "không áp dụng" if na else READ_VI[vote],
                          "text": text if with_text else "", "evidence": [{"name": k, "value": (None if v is None or (isinstance(v, float) and np.isnan(v)) else v)} for k, v in ev], "na": na})

        if horizon == "1_2_weeks":
            # --- Xu hướng: Dow + EMA20/EMA50 + vị trí giá so với EMA50
            if np.isnan(ema50) or np.isnan(dow):
                put("trend", 0, "Chưa đủ dữ liệu để xác định xu hướng (cần EMA50 và ≥ 2 đỉnh + 2 đáy swing).", [], na=True)
            else:
                s1, s2, s3 = int(dow), sgn(ema20 - ema50), sgn(c - ema50)
                tot = s1 + s2 + s3
                vt = 1 if tot >= 2 else (-1 if tot <= -2 else 0)
                dw = {1: "tăng (đỉnh–đáy cao dần)", -1: "giảm (đỉnh–đáy thấp dần)", 0: "hỗn hợp"}[s1]
                put("trend", vt, f"Xu hướng Dow {dw}; EMA20 ({vn(ema20, d)}) {'trên' if s2 > 0 else 'dưới' if s2 < 0 else 'bằng'} EMA50 ({vn(ema50, d)}); giá đóng cửa {vn(c, d)} {'trên' if s3 > 0 else 'dưới' if s3 < 0 else 'bằng'} EMA50.",
                    [("dow", int(dow)), ("ema20", ema20), ("ema50", ema50), ("close", c)])
            # --- Động lượng: MACD histogram và RSI cùng phía
            if np.isnan(macd_h) or np.isnan(rsi):
                put("momentum", 0, "Chưa đủ dữ liệu động lượng.", [], na=True)
            else:
                hs, rs = sgn(macd_h), sgn(rsi - 50, 2.0)
                vt = hs if (hs == rs and hs != 0) else 0
                put("momentum", vt, f"MACD histogram {vn(macd_h, 2)} ({'dương' if hs > 0 else 'âm' if hs < 0 else '0'}); RSI(14) = {vn(rsi, 1)} ({'trên' if rs > 0 else 'dưới' if rs < 0 else 'quanh'} 50). " + ("Hai chỉ báo cùng phía." if vt else "Hai chỉ báo không cùng phía hoặc RSI quanh 50 → trung lập."),
                    [("macd_hist", macd_h), ("rsi14", rsi)])
            # --- Khối lượng: OBV xác nhận hướng giá 10 nến
            obv = g("obv")
            if not self.has_volume or i < 10 or np.isnan(obv[i]):
                put("volume", 0, "Không có dữ liệu khối lượng đáng tin cậy cho khung này.", [], na=True)
            else:
                pdv, odv = sgn(c - self.c[i - 10]), sgn(obv[i] - obv[i - 10])
                vt = pdv if (pdv == odv and pdv != 0) else 0
                put("volume", vt, f"Trong 10 nến, giá {'tăng' if pdv > 0 else 'giảm' if pdv < 0 else 'đi ngang'} và OBV {'tăng' if odv > 0 else 'giảm' if odv < 0 else 'đi ngang'}: " + ("khối lượng xác nhận hướng giá." if vt else "khối lượng không xác nhận (hoặc phân kỳ) → trung lập."),
                    [("price_change_10", c - self.c[i - 10]), ("obv_change_10", obv[i] - obv[i - 10])])
        else:  # next_session
            # --- Xu hướng ngắn: giá/EMA9/EMA20
            if np.isnan(ema20):
                put("trend", 0, "Chưa đủ dữ liệu EMA20.", [], na=True)
            else:
                s1, s2, s3 = sgn(c - ema9), sgn(ema9 - ema20), sgn(c - ema20)
                tot = s1 + s2 + s3
                vt = 1 if tot >= 2 else (-1 if tot <= -2 else 0)
                put("trend", vt, f"Giá {vn(c, d)} {'trên' if s1 > 0 else 'dưới'} EMA9 ({vn(ema9, d)}), EMA9 {'trên' if s2 > 0 else 'dưới'} EMA20 ({vn(ema20, d)}), giá {'trên' if s3 > 0 else 'dưới'} EMA20.",
                    [("close", c), ("ema9", ema9), ("ema20", ema20)])
            # --- Động lượng theo chế độ thị trường (ADX): theo xu hướng khi ADX cao; hồi quy về trung bình khi ADX thấp
            if np.isnan(adx) or np.isnan(rsi):
                put("momentum", 0, "Chưa đủ dữ liệu ADX/RSI.", [], na=True)
            elif adx >= 25:
                vt = sgn(pdi - mdi)
                put("momentum", vt, f"ADX = {vn(adx, 1)} ≥ 25 (xu hướng mạnh): theo chiều lực chi phối, +DI = {vn(pdi, 1)} {'>' if vt > 0 else '<'} −DI = {vn(mdi, 1)}.", [("adx14", adx), ("plus_di14", pdi), ("minus_di14", mdi)])
            elif adx < 20:
                lo_ = rsi <= 30 or (not np.isnan(stk) and stk <= 20)
                hi_ = rsi >= 70 or (not np.isnan(stk) and stk >= 80)
                vt = 1 if (lo_ and not hi_) else (-1 if (hi_ and not lo_) else 0)
                put("momentum", vt, f"ADX = {vn(adx, 1)} < 20 (thị trường đi ngang): RSI = {vn(rsi, 1)}, Stoch %K = {vn(stk, 1)} → " + ("vùng quá bán theo quy ước (kỳ vọng hồi về trung bình)." if vt > 0 else "vùng quá mua theo quy ước (kỳ vọng hồi về trung bình)." if vt < 0 else "không ở vùng cực trị → trung lập."),
                    [("adx14", adx), ("rsi14", rsi), ("stoch_k", stk)])
            else:
                put("momentum", 0, f"ADX = {vn(adx, 1)} nằm giữa 20 và 25 (vùng chuyển tiếp) → không bỏ phiếu theo chế độ thị trường.", [("adx14", adx)])
            # --- Khối lượng: nến vừa rồi có khối lượng cao hơn trung bình?
            if self.vol_ratio is None or np.isnan(self.vol_ratio[i]):
                put("volume", 0, "Không có dữ liệu khối lượng đáng tin cậy cho khung này.", [], na=True)
            else:
                vr_, bar = float(self.vol_ratio[i]), sgn(c - self.o[i])
                vt = bar if (vr_ >= 1.25 and bar != 0) else 0
                put("volume", vt, f"Nến cuối {'tăng' if bar > 0 else 'giảm' if bar < 0 else 'đi ngang'} với khối lượng bằng {vn(vr_, 2)}× trung bình 20 nến: " + ("khối lượng cao (≥ 1,25×) đi cùng chiều nến." if vt else "khối lượng không nổi bật → trung lập."),
                    [("vol_ratio", vr_), ("bar_dir", bar)])
        # --- Cấu trúc giá (cả hai khung): mô hình giá đã xác nhận + nến + vị trí so với hỗ trợ/kháng cự (+ Bollinger khi đi ngang ở khung ngắn)
        contrib = 0
        parts: List[str] = []
        ev: List[Tuple[str, Any]] = []
        if horizon == "1_2_weeks":
            for p in self.chart_patterns_at(i):
                if p["status"] == "confirmed" and i - p["confirmed_at"] <= PAT_RECENT:
                    dir_ = p.get("breakout_dir", p["bias"]) if p["type"].endswith("triangle") else p["bias"]
                    if dir_:
                        contrib += dir_; parts.append(f"{p['label']} đã xác nhận ({DIR_VI[dir_]})"); ev.append(("chart_pattern", p["type"]))
        for j in (i, i - 1):
            for r in self._cand_at.get(j, []):
                if r["dir"] != 0 and (r["failed_at"] is None or r["failed_at"] > i):
                    contrib += r["dir"]; parts.append(f"nến {r['label']} ({DIR_VI[r['dir']]}) sau xu hướng {'tăng' if r['trend_before'] == 1 else 'giảm'}"); ev.append(("candle", r["name"]))
        z = self.zones_at(i)
        if not np.isnan(a) and a > 0:
            ds = (-z["below"][0]["dist"] / a) if z["below"] else None
            dr = (z["above"][0]["dist"] / a) if z["above"] else None
            loc = LOC_ATR[horizon]
            near_s = ds is not None and ds <= loc
            near_r = dr is not None and dr <= loc
            if near_s and not near_r:
                contrib += 1; parts.append(f"giá sát hỗ trợ {vn(z['below'][0]['center'], d)} (cách {vn(ds, 2)} ATR)"); ev.append(("support", z["below"][0]["center"]))
            elif near_r and not near_s:
                contrib -= 1; parts.append(f"giá sát kháng cự {vn(z['above'][0]['center'], d)} (cách {vn(dr, 2)} ATR)"); ev.append(("resistance", z["above"][0]["center"]))
        if horizon == "next_session" and not np.isnan(pctb) and not np.isnan(adx) and adx < 25:
            if pctb < 0:
                contrib += 1; parts.append(f"giá đóng dưới biên dưới Bollinger (%B = {vn(pctb, 2)}) khi ADX < 25"); ev.append(("bb_pct_b", pctb))
            elif pctb > 1:
                contrib -= 1; parts.append(f"giá đóng trên biên trên Bollinger (%B = {vn(pctb, 2)}) khi ADX < 25"); ev.append(("bb_pct_b", pctb))
        vt = sgn(contrib)
        put("structure", vt, ("; ".join(parts).capitalize() + ".") if parts else "Không có mô hình nến/mô hình giá đã xác nhận và giá không sát hỗ trợ/kháng cự → trung lập.", ev)
        return votes

    @staticmethod
    def decide(votes: List[Dict[str, Any]]) -> Dict[str, Any]:
        vs = [v["vote"] for v in votes if not v["na"]]
        net = sum(vs)
        direction = 1 if net >= 2 else (-1 if net <= -2 else 0)
        n_agree = sum(1 for x in vs if direction != 0 and x == direction)
        n_opp = sum(1 for x in vs if direction != 0 and x == -direction)
        if direction == 0:
            conf, why = "low", ("Các nhóm mâu thuẫn nhau" if (any(x > 0 for x in vs) and any(x < 0 for x in vs)) else "Chưa đủ nhóm đồng thuận")
        elif n_agree >= 3 and n_opp == 0:
            conf, why = "high", f"{n_agree}/4 nhóm đồng thuận, không nhóm nào ngược chiều"
        elif n_agree >= 2 and n_opp <= 1:
            conf, why = "medium", f"{n_agree} nhóm đồng thuận, {n_opp} nhóm ngược chiều"
        else:
            conf, why = "low", f"{n_agree} nhóm đồng thuận, {n_opp} nhóm ngược chiều"
        return {"direction": direction, "confidence": conf, "net": net, "n_agree": n_agree, "n_opp": n_opp, "confluence_note": why}

    def signal_arrays(self, horizon: str, start: int = 0) -> Tuple[np.ndarray, np.ndarray]:
        """Hướng (-1/0/+1) và độ tin cậy (0/1/2) cho từng nến; NaN nếu chưa đủ dữ liệu cho nhóm nào."""
        d = np.full(self.n, np.nan)
        cf = np.full(self.n, np.nan)
        for i in range(max(start, 0), self.n):
            if np.isnan(self.atr[i]):
                continue
            r = self.decide(self.votes_at(i, horizon))
            d[i] = r["direction"]
            cf[i] = {"low": 0, "medium": 1, "high": 2}[r["confidence"]]
        return d, cf

    # ------------------------------------------------------------------ giải thích đầy đủ tại một nến (khung ngày)
    def explain(self, i: int, horizon: str) -> Dict[str, Any]:
        votes = self.votes_at(i, horizon, with_text=True)
        dec = self.decide(votes)
        c, a, d = self.c[i], self.atr[i], self.dec
        z = self.zones_at(i)
        ls = self.last_swings(i)
        direction = dec["direction"]
        mult = 1.5 if horizon == "next_session" else 2.0
        # mức vô hiệu hóa: mức hỗ trợ/kháng cự gần nhất phía ngược chiều, cách >= 0,5 ATR; nếu không có thì ATR
        inval = None
        basis = ""
        if direction > 0:
            cands = [("đáy swing gần nhất", ls["low"]["price"])] if ls["low"] else []
            cands += [("vùng hỗ trợ", zz["center"]) for zz in z["below"]]
            cands = [x for x in cands if c - x[1] >= 0.5 * a and c - x[1] <= 4 * a]
            if cands:
                basis, inval = max(cands, key=lambda x: x[1])
            else:
                basis, inval = f"{mult:g} ATR dưới giá đóng cửa", c - mult * a
        elif direction < 0:
            cands = [("đỉnh swing gần nhất", ls["high"]["price"])] if ls["high"] else []
            cands += [("vùng kháng cự", zz["center"]) for zz in z["above"]]
            cands = [x for x in cands if x[1] - c >= 0.5 * a and x[1] - c <= 4 * a]
            if cands:
                basis, inval = min(cands, key=lambda x: x[1])
            else:
                basis, inval = f"{mult:g} ATR trên giá đóng cửa", c + mult * a
        res_lv = z["above"][0]["center"] if z["above"] else None
        sup_lv = z["below"][0]["center"] if z["below"] else None
        # mục tiêu đo theo mô hình giá đã xác nhận cùng chiều (nếu có)
        pat_target = None
        for p in self.chart_patterns_at(i):
            if p["status"] == "confirmed" and p.get("target") is not None:
                dir_ = p.get("breakout_dir", p["bias"]) if p["type"].endswith("triangle") else p["bias"]
                if dir_ == direction and direction != 0:
                    pat_target = {"pattern": p["label"], "target": float(p["target"]), "method": "đo theo chiều cao mô hình (measured move)"}
        # kịch bản
        if direction > 0:
            main = f"Kịch bản chính (nghiêng về TĂNG): giá giữ trên {vn(inval, d)} ({basis})" + (f", vùng quan sát tiếp theo là kháng cự {vn(res_lv, d)}" if res_lv else "") + "."
            alt = f"Kịch bản thay thế: nếu giá đóng cửa dưới {vn(inval, d)}, nhận định tăng bị vô hiệu" + (f"; hỗ trợ kế tiếp quan sát quanh {vn(sup_lv, d)}" if sup_lv and sup_lv < inval else "") + "."
        elif direction < 0:
            main = f"Kịch bản chính (nghiêng về GIẢM): giá không vượt lên trên {vn(inval, d)} ({basis})" + (f", vùng quan sát tiếp theo là hỗ trợ {vn(sup_lv, d)}" if sup_lv else "") + "."
            alt = f"Kịch bản thay thế: nếu giá đóng cửa trên {vn(inval, d)}, nhận định giảm bị vô hiệu" + (f"; kháng cự kế tiếp quan sát quanh {vn(res_lv, d)}" if res_lv and res_lv > inval else "") + "."
        else:
            rng = f"giữa hỗ trợ {vn(sup_lv, d)} và kháng cự {vn(res_lv, d)}" if (sup_lv and res_lv) else "trong vùng hiện tại"
            main = f"Kịch bản chính (ĐI NGANG / CHƯA RÕ HƯỚNG): giá có xu hướng dao động {rng}."
            alt = "Kịch bản thay thế: đóng cửa vượt ra ngoài vùng trên kèm khối lượng cao có thể mở ra một xu hướng mới; cần chờ xác nhận."
        # luận điểm ngược chiều + cảnh báo
        counter = [f"{v['group_vi']}: {v['text']}" for v in votes if direction != 0 and v["vote"] == -direction]
        notes: List[str] = []
        dv = self.divergence(i)
        if dv:
            notes.append(("Phân kỳ giảm RSI: giá tạo đỉnh swing cao hơn (" + f"{vn(dv['price'][0], d)} → {vn(dv['price'][1], d)}) nhưng RSI thấp hơn ({vn(dv['rsi'][0], 1)} → {vn(dv['rsi'][1], 1)})." if dv["type"] == "bearish"
                          else "Phân kỳ tăng RSI: giá tạo đáy swing thấp hơn (" + f"{vn(dv['price'][0], d)} → {vn(dv['price'][1], d)}) nhưng RSI cao hơn ({vn(dv['rsi'][0], 1)} → {vn(dv['rsi'][1], 1)})."))
        adx_i = self._g("adx14")[i]
        if not np.isnan(adx_i) and adx_i < 20 and horizon == "1_2_weeks":
            notes.append(f"ADX = {vn(adx_i, 1)} < 20: xu hướng yếu, tín hiệu theo xu hướng kém tin cậy hơn.")
        forming = [f"{p['label']} đang hình thành (chưa xác nhận)" for p in self.chart_patterns_at(i) if p["status"] == "forming"]
        pats_active = [{"label": p["label"], "status": p["status"], "type": p["type"], "target": p.get("target"),
                        "neckline": p.get("neckline"), "invalid_level": p.get("invalid_level")} for p in self.chart_patterns_at(i)]
        cands_recent = [{"label": r["label"], "dir": r["dir"], "index": r["index"], "confirmed": r["confirmed_at"] is not None and r["confirmed_at"] <= i,
                         "failed": r["failed_at"] is not None and r["failed_at"] <= i} for j in (i, i - 1, i - 2) for r in self._cand_at.get(j, [])]
        return {
            "horizon": horizon, "direction": direction, "direction_vi": {1: "Tăng", -1: "Giảm", 0: "Đi ngang / chưa rõ"}[direction],
            "confidence": dec["confidence"], "confluence": {k: dec[k] for k in ("net", "n_agree", "n_opp", "confluence_note")},
            "groups": votes, "invalidation": None if inval is None else {"level": float(inval), "basis": basis},
            "scenario_main": main, "scenario_alt": alt, "counter_arguments": counter, "notes": notes + forming,
            "levels": {"support": sup_lv, "resistance": res_lv, "pattern_target": pat_target},
            "patterns_active": pats_active, "candles_recent": cands_recent,
            "atr14": float(a), "close": float(c),
        }
