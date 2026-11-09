# Định nghĩa chỉ báo kỹ thuật

> Tài liệu công thức duy nhất cho `pipeline/indicators.py` và hiển thị trên giao diện.
> Mọi thay đổi công thức hay tham số phải sửa tài liệu này **trước**, kèm cập nhật test.
> Trạng thái (Giai đoạn 1, 2026-11-09): triển khai tại `pipeline/indicators.py`; **đã đối chiếu với TA-Lib 0.8.3** bằng `pipeline/tests/test_indicators.py` trên dữ liệu thật (FPT, VCB, GAS, XAUUSD; nến ngày). Kết quả: SMA, EMA, RSI, ATR, Bollinger, Stochastic, OBV khớp từ nến đầu tiên có giá trị (rtol 1e-6); MACD và ADX/±DI **hội tụ** về TA-Lib sau ~300 nến (sai khác chỉ ở cách khởi tạo, xem ghi chú từng chỉ báo). Tài liệu này mô tả công thức; việc đối chiếu với TA-Lib chứng minh nhất quán với một triển khai phổ biến, **không** thay thế việc đối chiếu với sách gốc của Wilder/Appel/Bollinger.

Ký hiệu: O, H, L, C, V = mở/cao/thấp/đóng/khối lượng của nến t; n = chu kỳ.
Khối lượng V = **khối lượng khớp lệnh** (không gồm thỏa thuận), xem `docs/data-sources.md` §2.

## 1. Xu hướng

**SMA(n)** = trung bình cộng n giá đóng cửa gần nhất.

**EMA(n)**: `EMA_t = α·C_t + (1−α)·EMA_{t−1}`, `α = 2/(n+1)`. Khởi tạo bằng SMA(n) của n nến đầu. Tham số mặc định: 9, 20, 50, 200.
Cần ≥ n nến mới có giá trị hợp lệ; EMA hội tụ đầy đủ thường cần nhiều nến hơn n. Giao diện không hiển thị giá trị trong giai đoạn khởi tạo.

**MACD(12, 26, 9)** (Appel): `MACD = EMA12(C) − EMA26(C)`; `Signal = EMA9(MACD)`; `Histogram = MACD − Signal`.

**ADX(14)** (Wilder): 
- `+DM = H_t − H_{t−1}` nếu lớn hơn `L_{t−1} − L_t` và > 0, ngược lại 0; `−DM` đối xứng.
- `TR = max(H−L, |H−C_{t−1}|, |L−C_{t−1}|)`.
- Làm mượt kiểu Wilder dạng trung bình (RMA): `A_t = (A_{t−1}·(n−1) + x_t)/n`, khởi tạo bằng trung bình n giá trị đầu (tại chỉ số n với DM/TR bắt đầu từ chỉ số 1). Dạng tổng `S_t = S_{t−1} − S_{t−1}/n + x_t` tương đương (S = n·A) khi cùng cách khởi tạo; tỷ số DI không đổi.
- **Khác biệt đã biết với TA-Lib:** TA-Lib khởi tạo tổng DM/TR bằng n−1 giá trị đầu, nên ±DI/ADX lệch ở đoạn đầu rồi hội tụ (hệ số (1−1/n)^k). Dự án giữ cách khởi tạo bằng n giá trị đầu cho nhất quán với ATR/RSI; giá trị ADX trong ~100 nến đầu của một chuỗi không nên dùng để kết luận.
- `+DI = 100·smooth(+DM)/smooth(TR)`, `−DI` tương tự; `DX = 100·|+DI − −DI|/(+DI + −DI)`; `ADX = làm mượt Wilder của DX`.
- Diễn giải thông dụng (Wilder): ADX cao = xu hướng mạnh (không cho biết chiều); các ngưỡng 20/25 chỉ là quy ước phổ biến, không phải quy luật.

## 2. Động lượng

**RSI(14)** (Wilder): `RS = AvgGain/AvgLoss` (trung bình làm mượt Wilder của mức tăng/giảm của C), `RSI = 100 − 100/(1+RS)`. Nếu AvgLoss = 0 thì RSI = 100.
Ngưỡng thông dụng 70/30 (quá mua/quá bán) là quy ước; trong xu hướng mạnh RSI có thể ở vùng "quá mua/quá bán" kéo dài — không được phát tín hiệu đảo chiều chỉ từ ngưỡng. Phân kỳ RSI–giá cần quy tắc định lượng riêng (xem `docs/patterns.md`, sẽ viết ở Giai đoạn 3).

**Stochastic (14,3,3)**: `%K_raw = 100·(C − LowestLow_14)/(HighestHigh_14 − LowestLow_14)`; `%K = SMA3(%K_raw)` (slow); `%D = SMA3(%K)`. Nếu mẫu số bằng 0 → giá trị không xác định, **trả NaN và không phát tín hiệu** (TA-Lib trả 0 trong trường hợp này; sai khác chỉ ở trường hợp biên, có test).

## 3. Biến động

**Bollinger Bands (20, 2)** (Bollinger): `Mid = SMA20(C)`; `Upper/Lower = Mid ± 2·σ`, σ là **độ lệch chuẩn tổng thể (chia N)** của 20 giá đóng gần nhất. Cần xác nhận cách tính σ khớp với thư viện tham chiếu trong test (một số thư viện dùng chia N−1 — sai khác phải được ghi rõ).
`%B = (C − Lower)/(Upper − Lower)`, `Bandwidth = (Upper − Lower)/Mid`.

**ATR(14)** (Wilder): `ATR = làm mượt Wilder của TR` (TR định nghĩa ở ADX). Dùng đo biên độ biến động, đặt mức vô hiệu hóa (ví dụ k·ATR) — k là quy ước người phân tích chọn, phải nêu rõ.

## 4. Khối lượng

**Volume MA(20)** = SMA20(V). "Khối lượng cao/thấp" luôn so với đường này (tỷ lệ V/MA), không dùng nhận xét tuyệt đối.

**OBV**: `OBV_0 = V_0` (quy ước khởi tạo của TA-Lib); `OBV_t = OBV_{t−1} + V_t` nếu `C_t > C_{t−1}`; `− V_t` nếu `C_t < C_{t−1}`; giữ nguyên nếu bằng. Giá trị tuyệt đối vô nghĩa; chỉ xem xu hướng và phân kỳ.

**Lưu ý dữ liệu khối lượng** (`docs/data-quality.md` §3–4): khối lượng = khớp lệnh (không gồm thỏa thuận); khối lượng nến phút chỉ tham khảo (tổng ngày lệch tới ±10–40% ở một số phiên); mã ít thanh khoản (CMG, FUEVFVND, E1VFVN30) không có nến cho phút không giao dịch nên Volume MA/OBV/VWAP nội phiên của các mã này tính trên các nến có giao dịch.

**VWAP (nội phiên)**: `Σ(TP·V)/ΣV` tính từ nến đầu phiên, `TP = (H+L+C)/3`, reset mỗi ngày. Chỉ áp dụng cho khung nội ngày và cổ phiếu/ETF có volume; **không áp dụng GC=F/XAU** cho hiển thị nội phiên cho đến khi xác định rõ ý nghĩa volume của futures (volume futures khác thanh khoản spot).

## 5. Hỗ trợ / kháng cự và Fibonacci

**Pivot điểm (cổ điển)** từ nến ngày trước: `P = (H+L+C)/3`; `R1 = 2P − L`; `S1 = 2P − H`; `R2 = P + (H−L)`; `S2 = P − (H−L)`.

**Swing high/low (fractal k nến)**: nến t là swing high nếu `H_t` lớn hơn H của k nến trước và k nến sau (k mặc định = 2); swing low đối xứng. Swing chỉ được xác nhận **sau k nến** — không được vẽ/nhìn thấy trước thời điểm đó (tránh nhìn trước tương lai, look-ahead bias, đặc biệt trong chế độ replay).

**Đường xu hướng/vùng hỗ trợ–kháng cự**: dựng từ ≥ 2 swing đã xác nhận cùng loại (đường xu hướng) hoặc ≥ 2 lần giá phản ứng trong vùng (vùng ngang, độ rộng đo bằng bội số ATR). Tham số ghi trong `docs/patterns.md` (Giai đoạn 3).

**Fibonacci retracement**: từ swing low → swing high (hoặc ngược lại) đã xác nhận, các mức 23,6%, 38,2%, 50%, 61,8%, 78,6% của biên độ. (Mức 50% không phải tỷ lệ Fibonacci nhưng được dùng theo quy ước.) Cần ghi rõ cặp swing được chọn; đây là công cụ mang tính quy ước, cần nêu trong phần nhận định rằng độ tin cậy thống kê hạn chế.

## 6. Quy tắc triển khai

1. Mọi chỉ báo tính từ **cùng một mảng OHLCV đã chuẩn hóa**; nến chưa hoàn thành (nến đang chạy) được gắn cờ `partial`, và chỉ báo trên nến này được ghi rõ là tạm thời.
2. Không dùng dữ liệu tương lai: giá trị chỉ báo tại nến t chỉ dùng nến ≤ t. Test bắt buộc: tính trên toàn chuỗi và tính trên chuỗi cắt tại t phải cho cùng giá trị tại t.
3. Giá điều chỉnh: **đã xác minh** nguồn trả giá đã điều chỉnh (`docs/data-quality.md` §1); toàn bộ chỉ báo của một mã dùng chuỗi đó (`docs/methodology.md` §7b). Chỉ báo được tính trên TOÀN BỘ lịch sử đã lưu rồi mới cắt N nến cuối để xuất (tránh sai do khởi tạo); khi lịch sử bị điều chỉnh lại, phải tính lại toàn bộ.
4. Test: đối chiếu với TA-Lib/pandas-ta trên dữ liệu thật đã lưu, dung sai số học nêu rõ; ghi lại sai khác nếu có.

## 7. Nguồn tham khảo

- Wilder, J. W. (1978). *New Concepts in Technical Trading Systems* — RSI, ATR, ADX (làm mượt Wilder).
- Appel, G. — MACD (nguồn gốc đề xuất 12/26/9).
- Bollinger, J. (2001). *Bollinger on Bollinger Bands*.
- Murphy, J. J. (1999). *Technical Analysis of the Financial Markets* — tổng hợp các chỉ báo, hỗ trợ/kháng cự, xu hướng.
- Granville, J. — OBV (ý tưởng gốc).
- *(Chưa đối chiếu trực tiếp từng trang sách trong đợt này; số trang/phiên bản cụ thể sẽ bổ sung khi viết test và khi định nghĩa được dùng trong báo cáo.)*
