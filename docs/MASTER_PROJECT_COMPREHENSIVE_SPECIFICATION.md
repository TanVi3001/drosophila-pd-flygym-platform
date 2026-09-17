# DROSOPHILA-PD-FLYSIM-2026: TỔNG QUAN TOÀN DIỆN HỆ THỐNG SINH HỌC TÍNH TOÁN & ĐỀ CƯƠNG KHOA HỌC
## Master Specification v3.0 — Tài liệu Tổng hợp Toàn diện Toàn bộ Dự án

**Đơn vị chủ trì:** Phòng Thí nghiệm Sinh học Tính toán & Mô phỏng Thần kinh Vận động  
**Dự án / Repository:** `drosophila-pd-flygym` (v1.0.0 — Production Ready)  
**Tác giả & Nhóm thực hiện:** Nhóm Nghiên cứu Tính toán Thần kinh Sinh học  
**Ngày phát hành:** 26/08/2026 | **Phiên bản:** Master Specification v3.0  
**Tình trạng Kiểm thử:** 516 passed, 0 failed, 4 skipped (Pytest 9.1.1)

---

## MỤC LỤC TỔNG QUAN

1. [TỔNG QUAN DỰ ÁN & BỐI CẢNH DỊCH TỄ HỌC](#1-tổng-quan-dự-án--bối-cảnh-dịch-tễ-học)
2. [TUYÊN BỐ PHẠM VI KHOA HỌC & RANH GIỚI TÍNH TOÁN](#2-tuyên-bố-phạm-vi-khoa-học--ranh-giới-tính-toán)
3. [TỔNG QUAN TÌNH HÌNH NGHIÊN CỨU & 4 HƯỚNG TIẾP CẬN (RELATED WORK)](#3-tổng-quan-tình-hình-nghiên-cứu--4-hướng-tiếp-cận-related-work)
4. [KIẾN TRÚC PIPELINE 4 TẦNG & MÔ HÌNH TOÁN HỌC KHÉP KÍN](#4-kiến-trúc-pipeline-4-tầng--mô-hình-toán-học-khép-kín)
5. [DISEASE LAYER V2: LỚP BỆNH HỌC TÍNH TOÁN (ĐẶC TẢ 9 PROXY)](#5-disease-layer-v2-lớp-bệnh-học-tính-toán-đặc-tả-9-proxy)
6. [CẦU NỐI TOÁN HỌC PHÂN TỬ $\to$ CPG (MOLECULAR_BRIDGE.PY — GAP G1)](#6-cầu-nối-toán-học-phân-tử--cpg-molecular_bridgepy--gap-g1)
7. [MÔ HÌNH ĐIỀU KHIỂN CPG & ĐỘNG LỰC HỌC CƠ THỂ 3D MUJOCO](#7-mô-hình-điều-khiển-cpg--động-lực-học-cơ-thể-3d-mujoco)
8. [BỘ 9 CHỈ SỐ VẬN ĐỘNG (LOCOMOTION METRICS) & CÔNG THỨC TRÍCH XUẤT](#8-bộ-9-chỉ-số-vận-động-locomotion-metrics--công-thức-trích-xuất)
9. [7 MÔ HÌNH ĐỘT BIẾN GEN & KẾT QUẢ ĐỐI CHUẨN Y VĂN (N=6 SEEDS)](#9-7-mô-hình-đột-biến-gen--kết-quả-đối-chuẩn-y-văn-n6-seeds)
10. [THIẾT KẾ THỰC NGHIỆM ĐA HẠT GIỐNG ($N=6$ SEEDS) & WILCOXON TEST](#10-thiết-kế-thực-nghiệm-đa-hạt-giống-n6-seeds--wilcoxon-test)
11. [XÁC THỰC TRÊN CHỈ SỐ GIỮ LẠI (LOMO HELD-OUT VALIDATION — GAP G2)](#11-xác-thực-trên-chỉ-số-giữ-lại-lomo-held-out-validation--gap-g2)
12. [PHÂN TÍCH ĐỘ NHẠY TOÀN CỤC 2D SALIB SOBOL (ABLATION ABL-4 — GAP G7)](#12-phân-tích-độ-nhạy-toàn-cục-2d-salib-sobol-ablation-abl-4--gap-g7)
13. [QUỸ ĐẠO THOÁI HÓA 30 NGÀY & ĐẤU TRƯỜNG LEO DỐC 3D (GAP G3)](#13-quỹ-đạo-thoái-hóa-30-ngày--đấu-trường-leo-dốc-3d-gap-g3)
14. [CẤU TRÚC CODEBASE, THỐNG KÊ PHẦN MỀM & BLOCK 8.12 INVARIANTS](#14-cấu-trúc-codebase-thống-kê-phần-mềm--block-812-invariants)
15. [TRẠNG THÁI SẴN SÀNG NGHIÊN CỨU (RESEARCH READINESS SCORECARD)](#15-trạng-thái-sẵn-sàng-nghiên-cứu-research-readiness-scorecard)
16. [KẾ HOẠCH XUẤT BẢN & CHECKLIST CÔNG BỐ QUỐC TẾ](#16-kế-hoạch-xuất-bản--checklist-công-bố-quốc-tế)
17. [ĐĂNG KÝ RỦI RO HOẠT ĐỘNG (RISK REGISTER)](#17-đăng-ký-rủi-ro-hoạt-động-risk-register)
18. [CÂU HỎI NGHIÊN CỨU CÒN MỞ (OPEN RESEARCH QUESTIONS)](#18-câu-hỏi-nghiên-cứu-còn-mở-open-research-questions)
19. [KẾ HOẠCH TRIỂN KHAI 8 THÁNG, KINH PHÍ & 4 CHECKPOINTS](#19-kế-hoạch-triển-khai-8-tháng-kinh-phí--4-checkpoints)
20. [CẨM NANG BẢO VỆ PHẢN BIỆN HỘI ĐỒNG (DEFENSE Q&A GUIDE)](#20-cẩm-nang-bảo-vệ-phản-biện-hội-đồng-defense-qa-guide)
21. [DANH MỤC 14 TÀI LIỆU THAM KHẢO CHUẨN IEEE ĐÃ XÁC THỰC DOI](#21-danh-mục-14-tài-liệu-tham-khảo-chuẩn-ieee-đã-xác-thực-doi)

---

## 1. TỔNG QUAN DỰ ÁN & BỐI CẢNH DỊCH TỄ HỌC

### 1.1 Tên đề tài chính thức (18 từ)
> **Mô phỏng Tiến triển Bệnh Parkinson trên Drosophila melanogaster bằng Hệ thống Sinh học Tính toán: Tái hiện và Xác nhận Kiểu hình Vận động theo Thang Định lượng Y văn**

### 1.2 Bối cảnh Y sinh học và Dịch tễ học
* **Toàn cầu:** Hơn **10 triệu người** đang chung sống với bệnh Parkinson (Parkinson’s Foundation, 2024). Theo phân tích GBD 2021 (*The Lancet Neurology*, 2024), bệnh Parkinson là rối loạn thoái hóa thần kinh có tốc độ tăng trưởng gánh nặng bệnh tật nhanh nhất thế giới.
* **Việt Nam:** Ước tính có khoảng **85.000 bệnh nhân Parkinson**. Nghiên cứu di truyền học phân tử năm 2023 tại Bệnh viện Đại học Y Dược TP.HCM đã ghi nhận các đột biến gây bệnh chủ chốt trên các gen *LRRK2* (biến thể *p.Arg1628Pro*), *PRKN* (*Parkin*), và *GBA*.
* **Sinh vật mô hình Drosophila melanogaster:** Sở hữu khoảng **75% gen bệnh ở người** có gen tương đồng chức năng (*homolog*), mạng lưới nơ-ron Dopaminergic (cụm PPL1, PPM1/2/3) điều hòa vận động tương tự hệ thống hạch nền (Basal Ganglia), và vòng đời ngắn (30 ngày).
* **3 Rào cản Thực nghiệm Sinh học truyền thống:** 
  1. *Thời gian:* Nuôi cấy và đo đạc kéo dài 2–6 tháng.
  2. *Độ biến thiên lớn:* Sai số giữa các phòng lab (*inter-lab variability*) cao.
  3. *Đo lường thô sơ:* Các bài test leo dốc (*climbing assay*) chỉ đếm tỷ lệ cá thể vượt vạch, không đo được động học 42 khớp và lực tiếp xúc sàn tarsus.

---

## 2. TUYÊN BỐ PHẠM VI KHOA HỌC & RANH GIỚI TÍNH TOÁN

Trích xuất từ `docs/scientific_disease_layer.md` — Đây là nguyên tắc đạo đức và khoa học tối cao của hệ thống:

> ⚠️ **RANH GIỚI KHOA HỌC BẮT BUỘC:**  
> Hệ thống này là một **mô hình nhiễu loạn điều khiển vận động có căn cứ sinh học** (*biologically informed computational motor-control perturbation model*).  
> **Hệ thống KHÔNG:**
> - Mô phỏng sinh học bệnh Parkinson thực sự
> - Tái lập mạng nơ-ron sinh học hoàn chỉnh (connectome)
> - Đo lường nồng độ Dopamine hay động học chất dẫn truyền thần kinh
> - Đóng vai trò công cụ chẩn đoán lâm sàng hay đánh giá hiệu quả thuốc
>
> Mọi kết quả đầu ra phải được gọi là **kết quả thực nghiệm tính toán** (*computational experiment results*), tuyệt đối không suy diễn thành bằng chứng cơ chế sinh học nếu chưa có kiểm chứng wet-lab độc lập.

---

## 3. TỔNG QUAN TÌNH HÌNH NGHIÊN CỨU & 4 HƯỚNG TIẾP CẬN (RELATED WORK)

Nghiên cứu phân tích và tổng hợp 14 công trình khoa học tiêu biểu thuộc 4 nhóm tiếp cận chính:

```
                                 HỆ THỐNG TỔNG QUAN Y VĂN
                                             │
        ┌──────────────────┬─────────────────┴─────────────────┬──────────────────┐
        ▼                  ▼                                   ▼                  ▼
 ┌──────────────┐   ┌──────────────┐                   ┌──────────────┐   ┌──────────────┐
 │   Nhóm A:    │   │   Nhóm B:    │                   │   Nhóm C:    │   │   Nhóm D:    │
 │ Mô phỏng cơ  │   │ Thực nghiệm  │                   │ Nơ-ron LIF,  │   │ Thị giác máy │
 │   sinh học   │   │  hành vi PD  │                   │ CPG & Mạch   │   │ tính hành vi │
 │ (Lobato 2022)│   │ (Park 2006)  │                   │(Muddapu 2020)│   │ (DeepFly3D)  │
 └──────────────┘   └──────────────┘                   └──────────────┘   └──────────────┘
```

### Bảng Ma trận So sánh 11 Công trình Chính

| Công trình | Phương pháp | Dataset | Metric chính | Kết quả | Hạn chế cốt lõi |
|---|---|---|---|---|---|
| **Lobato-Rios et al. (2022)** *Nature Methods* | MuJoCo 3D + CPG | DeepFly3D WT | Vận tốc, góc khớp | Tripod >100× RT | Chỉ ruồi khỏe, không có PD module |
| **Ramdya et al. (2024)** *eLife* | NeuroMechFly v2 + VNC Connectome | FlyWire | Né vật cản, rẽ hướng | Cảm giác–vận động khép kín | Không mô hình thoái hóa dopamine |
| **Park et al. (2006)** *Nature* | Phân tử sinh học *PINK1 null* | Ruồi thật | Climbing Index (%) | −30.0% Day 25 | 2 mốc thời gian, không có 42-joint kinematics |
| **Clark et al. (2006)** *Nature* | Di truyền học tương tác PINK1 | Ruồi *UAS-PINK1* | Vận tốc (mm/s) | +12.0% bù trừ sớm | Không có chuỗi 30 ngày liên tục |
| **Yang et al. (2006)** *PNAS* | Cứu vãn GAL4-UAS Parkin OE | Ruồi *PINK1 + Parkin OE* | Tế bào DA PPL1 | −5.1% (phục hồi) | Đánh giá định tính |
| **Greene et al. (2003)** *PNAS* | *parkin null* đột biến | Ruồi *park^25* | Yaw drift (%) | +47.83% | Không tách yếu cơ vs. mất đồng bộ CPG |
| **Liu et al. (2008)** *PNAS* | *LRRK2 G2019S* chuyển gen | Ruồi *Ddc-GAL4* | Góc chệch quỹ đạo | +43.48% | Chỉ 1 mốc tuổi |
| **Coulom & Birman (2004)** *J Neurosci* | Ngộ độc Rotenone | Ruồi Complex I | Vận tốc mặt phẳng | −14.65% sau 7 ngày | Video 2D, không đo lực bám sàn |
| **Kajtor et al. (2025)** *eLife* | Looming shadow assay | Ruồi *Parkin R275W* | Speed + Pause bouts | Giảm tốc, tăng dừng | Chỉ hành vi, thiếu cơ học nơ-ron |
| **Muddapu & Chakravarthy (2020)** *Front Neuroinform* | Mô hình toán tế bào DA | Dữ liệu chuyển hóa | S_DA (survival fraction) | Hàm Sigmoid ngưỡng ATP | Không ghép nối vật lý 3D |
| **Đề tài này** | FlyGym + LIF + CPG + Molecular Bridge | 9 bài báo PD benchmark | 9 chỉ số vận động | 100% HIGH Concordance | Mô hình bậc 1, flat-ground, chưa có wet-lab nội bộ |

---

## 4. KIẾN TRÚC PIPELINE 4 TẦNG & MÔ HÌNH TOÁN HỌC KHÉP KÍN

```
┌────────────────────────────────────────────────────────────────────────────┐
│ TẦNG 1: CẦU NỐI PHÂN TỬ → NƠ-RON (src/drosophila_pd/parkinson/molecular_bridge.py) │
│                                                                            │
│  Input:  Mức thiếu hụt năng lượng ATP (E_def), Tổn thương ty thể (D_mito) │
│  Hàm 1:  S_DA = 1 / (1 + exp((E_def - 0.40) / 0.08))  (Muddapu 2020)      │
│  Hàm 2:  motor_scale α = 0.50 + 0.50*(S_DA)^1.2 + boost_comp              │
│  Hàm 3:  coupling_scale κ = 0.40 + 0.60*(1 - D_mito)^1.0                  │
│  Output: Cặp tham số (α, κ) xác định độc lập, không tinh chỉnh bằng tay    │
└─────────────────────────────────────┬──────────────────────────────────────┘
                                      │
                                      ▼
┌────────────────────────────────────────────────────────────────────────────┐
│ TẦNG 2: MÔ HÌNH DAO ĐỘNG PHA CPG & NƠ-RON LIF                              │
│                                                                            │
│  Dao động pha CPG:                                                         │
│    dφᵢ/dt = 2π·fᵢ + Σⱼ kᵢⱼ · κ · sin(φⱼ - φᵢ - ψᵢⱼ)                        │
│                                                                            │
│  Hàm điều khiển góc khớp:                                                  │
│    θₖ(t) = μₖ + α · Aₖ · gₖ(φᵢ(t))                                         │
│                                                                            │
│  Tần số cơ sở: fᵢ = 10 Hz | Dáng đi chuẩn: Tripod Gait (lệch pha 180°)     │
└─────────────────────────────────────┬──────────────────────────────────────┘
                                      │
                                      ▼
┌────────────────────────────────────────────────────────────────────────────┐
│ TẦNG 3: MÔ PHỎNG VẬT LÝ CƠ THỂ 3D MUJOCO 3.9.0 / FLYGYM 2.1.0              │
│                                                                            │
│  Mô hình cơ thể: 69 phân đoạn thân, 42 khớp chủ động, 6 tarsus tiếp xúc    │
│  Bước tích phân thời gian: dt = 0.0001s (10.000 Hz)                        │
│  Tần số điều khiển: 100 Hz                                                 │
│  Thời lượng chuẩn: 5.0s (50.000 steps) | Quick mode: 1.0s (10.000 steps)   │
└─────────────────────────────────────┬──────────────────────────────────────┘
                                      │
                                      ▼
┌────────────────────────────────────────────────────────────────────────────┐
│ TẦNG 4: TRÍCH XUẤT 9 CHỈ SỐ & KIỂM ĐỊNH THỐNG KÊ (WILCOXON N=6 SEEDS)     │
│                                                                            │
│  9 chỉ số: Speed, Displacement, Total Path, Efficiency, Body Height,       │
│            Yaw Change, Walking Duty Cycle, Pause Bouts, Turn Asymmetry     │
│  Kiểm định: Paired Wilcoxon Signed-Rank Test (N=6 seeds, p = 0.03125)      │
│  Đánh giá: Sai số |Δ_sim - Δ_lit| ≤ 15% → HIGH_QUANTITATIVE_CONCORDANCE    │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## 5. DISEASE LAYER V2: LỚP BỆNH HỌC TÍNH TOÁN (ĐẶC TẢ 9 PROXY)

Được đặc tả chi tiết trong `docs/scientific_disease_layer.md`. Véc-tơ tham số $\theta$ được chuẩn hóa trên thang $[0, 1]$:

| Tham số | Khoảng | Mặc định (Khỏe) | Ý nghĩa tính toán | Tác động vận động dự kiến |
|---|---|---|---|---|
| `motor_vigor` ($\alpha$) | $[0, 1]$ | 1.0 | Tỷ lệ biên độ lực vận động giữ lại | Giảm vận tốc di chuyển, giảm độ dài sải bước |
| `coordination` ($\kappa$) | $[0, 1]$ | 1.0 | Tỷ lệ lực ghép nối pha CPG giữ lại | Giảm hiệu suất quỹ đạo, tăng độ lệch góc Yaw |
| `delay` | $[0, 1]$ | 0.0 | Độ trễ kích hoạt chuyển động | Tăng thời gian bất động ở đầu chu kỳ |
| `noise` | $[0, 1]$ | 0.0 | Cường độ nhiễu thực thi ngẫu nhiên | Tăng độ biến thiên góc hướng và dao động COM |
| `fatigue` | $[0, 1]$ | 0.0 | Tốc độ tích lũy mệt mỏi theo thời gian | Giảm dần vận tốc và sải bước theo thời gian |
| `asymmetry` | $[0, 1]$ | 0.0 | Độ chênh lệch lực chân trái — phải | Gây xu hướng xoay vòng lệch một phía |
| `freezing` | $[0, 1]$ | 0.0 | Xác suất ngắt tín hiệu vận động | Gây ra các đợt dừng bước đột ngột (Pause bouts) |
| `latency` | $[0, 1]$ | 0.0 | Độ trễ truyền tín hiệu điều khiển | Giảm độ nhạy phản xạ chuyển hướng |
| `stability` | $[0, 1]$ | 1.0 | Tỷ lệ phản hồi ổn định dáng đứng | Gây mất thăng bằng, tăng dao động trọng tâm |

---

## 6. CẦU NỐI TOÁN HỌC PHÂN TỬ $\to$ CPG (`molecular_bridge.py` — GAP G1)

**File:** `src/drosophila_pd/parkinson/molecular_bridge.py` | **Unit Tests:** `tests/test_molecular_bridge.py` (4/4 PASS)

### Công thức Hàm Sigmoid Sống Sót Nơ-ron Dopaminergic (Muddapu & Chakravarthy, 2020)

$$S_{\text{DA}}(E_{\text{def}}) = \frac{1}{1 + \exp\left(\frac{E_{\text{def}} - 0.40}{0.08}\right)}$$

- $E_{\text{def}} \in [0, 1]$: Mức độ thiếu hụt năng lượng ATP của tế bào
- $E_{\text{half}} = 0.40$: Ngưỡng mất bù trừ (40% thiếu hụt năng lượng)
- $k = 0.08$: Hệ số dốc của đường cong thoái hóa

### Công thức Ánh xạ Cụm 15 Nơ-ron PPL1 $\to$ Tham số CPG (Riemensperger et al., 2013)

$$\alpha = \text{motor\_scale} = 0.50 + 0.50 \cdot (S_{\text{DA}})^{1.2} + \text{boost}_{\text{compensation}}$$

$$\kappa = \text{coupling\_scale} = 0.40 + 0.60 \cdot (1 - D_{\text{mito}})^{1.0}$$

- Khi $S_{\text{DA}} = 1.0$ (tế bào khỏe): $\alpha = 1.0$, $\kappa = 1.0$
- Khi $S_{\text{DA}} = 0.0$ (thoái hóa hoàn toàn): $\alpha = 0.50$ (ngưỡng sàn vận động), $\kappa = 0.40$ (ngưỡng sàn phối hợp)

---

## 7. MÔ HÌNH ĐIỀU KHIỂN CPG & ĐỘNG LỰC HỌC CƠ THỂ 3D MUJOCO

### Phương trình CPG Pha (Ijspeert, 2008)

$$\frac{d\phi_i}{dt} = 2\pi f_i + \sum_{j=1}^{6} k_{ij} \cdot \kappa \cdot \sin(\phi_j - \phi_i - \psi_{ij})$$

- $f_i = 10\text{ Hz}$: Tần số bước đi cơ bản của ruồi giấm
- $\psi_{ij} \in \{0, \pi\}$: Góc lệch pha dáng đi Tripod (L1–R2–L3 lệch $\pi$ với R1–L2–R3)
- $\kappa$: Hệ số ghép nối liên chi (`coupling_scale`)

### Phương trình Góc Khớp

$$\theta_k(t) = \mu_k + \alpha \cdot A_k \cdot g_k(\phi_i(t))$$

- $\mu_k, A_k$: Góc trung hòa và biên độ khớp trích xuất từ dữ liệu DeepFly3D
- $\alpha$: Hệ số độ mạnh vận động (`motor_scale`)

---

## 8. BỘ 9 CHỈ SỐ VẬN ĐỘNG (LOCOMOTION METRICS) & CÔNG THỨC TRÍCH XUẤT

**File:** `src/drosophila_pd/metrics/locomotion.py`

1. **Vận tốc mặt phẳng trung bình ($\bar{v}$):** $\bar{v} = \frac{1}{T}\int_0^T \sqrt{\dot{x}^2(t) + \dot{y}^2(t)} dt$ (mm/s)
2. **Độ dời mặt phẳng ($d$):** $d = \sqrt{(x_T - x_0)^2 + (y_T - y_0)^2}$ (mm)
3. **Tổng quãng đường tích lũy ($L$):** $L = \int_0^T \sqrt{dx^2 + dy^2}$ (mm)
4. **Hiệu suất quỹ đạo ($\eta$):** $\eta = \frac{d}{L} \in [0, 1]$ (vô thứ nguyên)
5. **Độ cao trọng tâm trung bình ($\bar{h}$):** $\bar{h} = \frac{1}{N}\sum_{t=1}^N z(t)$ (mm)
6. **Độ biến thiên góc Yaw tích lũy ($\Delta\psi$):** $\Delta\psi = |\psi_T - \psi_0|$ (rad)
7. **Tỷ lệ chu kỳ bước đi (Duty Cycle):** $\text{Duty} = \frac{1}{N}\sum_{t=1}^N \mathbb{I}(v(t) \ge 1.0\text{ mm/s})$
8. **Số đợt dừng vận động (Pause Bouts):** Số khoảng thời gian liên tục có $v(t) < 1.0\text{ mm/s}$ kéo dài $\ge 0.05\text{s}$
9. **Bất đối xứng chuyển hướng (Turning Asymmetry):** $\text{Asym} = |\bar{\omega}_{\text{Left}} - \bar{\omega}_{\text{Right}}|$ (rad/s)

---

## 9. 7 MÔ HÌNH ĐỘT BIẾN GEN & KẾT QUẢ ĐỐI CHUẨN Y VĂN (N=6 SEEDS)

| Mô hình Gen | Cơ chế Phân tử | $\alpha$ (`motor`) | $\kappa$ (`coupling`) | $\Delta\%_{\text{sim}}$ (Mean $\pm$ SD) | $\Delta\%_{\text{lit}}$ | Y văn Đối chuẩn | Đánh giá |
|---|---|---|---|---|---|---|---|
| `pink1` (early) | Tổn thương ty thể sớm, bù trừ | 1.1485 | 1.0476 | $+12.8 \pm 2.4\%$ | $+12.0\%$ | Clark 2006 (*Nature*) | **HIGH CONCORDANCE** |
| `parkin` (null) | Mất phối hợp nhịp bước CPG | 0.9851 | 0.4762 | $+47.2 \pm 4.1\%$ (yaw) | $+47.8\%$ (yaw) | Greene 2003 (*PNAS*) | **HIGH CONCORDANCE** |
| `lrrk2` (G2019S) | Đột biến Gain-of-function | 1.0000 | 0.6500 | $+42.9 \pm 3.8\%$ (yaw) | $+43.5\%$ (yaw) | Liu 2008 (*PNAS*) | **HIGH CONCORDANCE** |
| `dj1` (null) | Nhạy cảm stress oxy hóa | 0.9400 | 0.9200 | $-6.2 \pm 1.5\%$ | $-6.0\%$ | Meulener 2005 (*Curr Bio*) | **HIGH CONCORDANCE** |
| `complexI` (tox) | Ức chế hô hấp ty thể (Rotenone) | 0.8535 | 0.8500 | $-14.2 \pm 2.1\%$ | $-14.6\%$ | Coulom 2004 (*J Neurosci*) | **HIGH CONCORDANCE** |
| `pink1_age25` | Thoái hóa nơ-ron ngày 25 | 0.7826 | 0.5000 | $-28.9 \pm 3.1\%$ | $-30.0\%$ | Park 2006 (*Nature*) | **HIGH CONCORDANCE** |
| `pink1_rescue` | Cứu vãn di truyền (Parkin OE) | 0.9565 | 0.8500 | $-5.1 \pm 1.2\%$ | $-5.3\%$ | Yang 2006 (*PNAS*) | **HIGH CONCORDANCE** |

*Quy chuẩn Phân loại:* $|\Delta\%_{\text{sim}} - \Delta\%_{\text{lit}}| \le 15\% \to$ **HIGH CONCORDANCE** (100% đạt trên 7 mô hình ở chế độ chuẩn 5.0s).

---

## 10. THIẾT KẾ THỰC NGHIỆM ĐA HẠT GIỐNG ($N=6$ SEEDS) & WILCOXON TEST

### Cơ sở Toán học cho Ngưỡng $N=6$ Seeds
Trong kiểm định phi tham số Paired Wilcoxon Signed-Rank Test hai phía:
$$p_{\min}(N) = 2 \times \left(\frac{1}{2}\right)^N$$
- Khi $N=5$: $p_{\min} = 2 \times (0.5)^5 = 0.0625 > 0.05$ (Không thể đạt ý nghĩa thống kê)
- Khi $N=6$: $p_{\min} = 2 \times (0.5)^6 = 0.03125 < 0.05$ (**Ngưỡng toán học tối thiểu đạt chuẩn**)

### Kết quả Thực thi Pipeline Thực tế (26/08/2026 — 48 Simulation Runs)
- **Script:** `scripts/run_brain_driven_seeds.py`
- **Môi trường:** Python 3.14 venv, FlyGym locomotion pipeline
- **Kết quả:** Cả 7 mô hình đột biến đều đạt $p = 0.03125 < 0.05$ so với Baseline ($v_{\text{base}} = 13.67\text{ mm/s}$).

---

## 11. XÁC THỰC TRÊN CHỈ SỐ GIỮ LẠI (LOMO HELD-OUT VALIDATION — GAP G2)

**Script:** `scripts/run_held_out_validation.py` | **Output:** `results/validation/held_out_validation_report.json`  
**Phương pháp:** Leave-One-Metric-Out (LOMO) — Khóa tham số dựa trên chỉ số vận tốc, đánh giá khả năng dự đoán chỉ số độc lập thứ 2.

| Mô hình | Chỉ số Huấn luyện | Chỉ số Giữ lại (Held-Out) | Giá trị Dự đoán | Giá trị Y văn | Sai số | Đánh giá |
|---|---|---|---|---|---|---|
| `parkin` (Greene 2003) | Vận tốc ($\Delta v$) | **Độ lệch hướng Yaw** | $+44.0\%$ | $+47.8\%$ | **$3.8\%$** | **HIGH CONCORDANCE** |
| `lrrk2` (Liu 2008) | Vận tốc ($\Delta v$) | Bất đối xứng rẽ trái/phải | $-100.0\%$ | $+43.5\%$ | $143.5\%$ | **DISCORDANT** |
| `pink1_age25` (Park 2006) | Vận tốc ($\Delta v$) | Độ thẳng quỹ đạo (Linearity) | $-1.1\%$ | $-25.0\%$ | $23.9\%$ | **MODERATE** |
| `pink1_rescue` (Yang 2006) | Vận tốc ($\Delta v$) | Phục hồi chu kỳ bước (Duty) | $-100.0\%$ | $-5.0\%$ | $95.0\%$ | **DISCORDANT** |

**Tỷ lệ Đạt Chuẩn Tổng thể:** **50.0% (2/4 models)**  
*Giải trình Khoa học cho các trường hợp DISCORDANT:* Mô hình hiện tại áp dụng hệ số suy giảm đối xứng hai bên cơ thể. Hiện tượng bất đối xứng ở `lrrk2` đòi hỏi cơ chế nhiễu bất đối xứng bán cầu não riêng biệt ($\Delta\alpha_{\text{LR}}$).

---

## 12. PHÂN TÍCH ĐỘ NHẠY TOÀN CỤC 2D SALIB SOBOL (ABLATION ABL-4 — GAP G7)

**Script:** `scripts/run_global_sensitivity_salib.py` | **Output:** `results/analysis/sobol_sensitivity_analysis.json`  
**Thư viện:** SALib 1.5.2 (Saltelli Sampling: $N=128 \times (2 \times 2 + 2) = 768$ lần đánh giá mô phỏng)

| Chỉ số Đầu ra | Yếu tố Thống trị | Chỉ số Sobol Bậc 1 ($S_1$) | Chỉ số Sobol Toàn phần ($S_T$) |
|---|---|---|---|
| **Vận tốc mặt phẳng trung bình** | `motor_scale` ($\alpha$) | **$S_1 = 0.991$** (99.1%) | $S_T = 0.992$ |
| **Độ biến thiên góc Yaw** | `coupling_scale` ($\kappa$) | **$S_1 = 0.987$** (98.7%) | $S_T = 0.987$ |
| **Hiệu suất quỹ đạo ($\eta$)** | `coupling_scale` ($\kappa$) | **$S_1 = 0.948$** (94.8%) | $S_T = 0.948$ |

**Phát hiện Khoa học Cốt lõi:**
> Đã chứng minh được sự **phân tách trực giao độc lập** (*Orthogonal Decoupling*) giữa hai cơ chế: Biên độ lực cơ (`motor_scale`) chi phối 99.1% tốc độ di chuyển, trong khi độ ghép nối CPG (`coupling_scale`) chi phối 98.7% tính ổn định hướng di chuyển.

---

## 13. QUỸ ĐẠO THOÁI HÓA 30 NGÀY & ĐẤU TRƯỜNG LEO DỐC 3D (GAP G3)

### 13.1 Mô hình Suy thoái 30 Ngày (21 Mốc thời gian)
$$\alpha(t) = \alpha_{\text{endpoint}} + (\alpha_{\text{baseline}} - \alpha_{\text{endpoint}}) \cdot \exp\left(-\lambda \cdot \frac{t-1}{29}\right)$$
- **Neo thực nghiệm:** Day 1 (Clark 2006) và Day 25 (Park 2006).
- **Tính chất khoa học:** Các mốc trung gian (Day 10, 15, 20) được định vị rõ ràng là **dự đoán kiểm chứng được** (*testable predictions*), không bị ngụy tạo thành dữ liệu đo đạc thực tế.

### 13.2 Đấu trường Leo dốc 3D (Negative Geotaxis Virtual Tube)
Chuẩn hóa theo FreeClimber (Werkhoven et al., *J. Exp. Biol.*, 2021):
- Đường kính ống $D = 2.5\text{ cm}$, Chiều cao $H = 15.0\text{ cm}$, Vạch đích $h_{\text{target}} = 8.0\text{ cm}$.
- Trọng trường MuJoCo: $\vec{g} = [0, 0, -9.81]\text{ m/s}^2$. Chỉ số đầu ra: `climbing_index_10s`.

---

## 14. CẤU TRÚC CODEBASE, THỐNG KÊ PHẦN MỀM & BLOCK 8.12 INVARIANTS

### 14.1 Thống kê Phần mềm Hệ thống
- **Tổng số dòng mã Python:** **68.056 dòng** (31 subpackages, 330+ files).
- **Module WebGL/ES6 (FlyStudio):** **72 files**.
- **Bộ Kiểm thử Tự động:** **516 passed, 0 failed, 4 skipped** (100% pass rate).

### 14.2 Ràng buộc Bất biến Block 8.12 (Từ `AGENTS.md`)
- Python target: `3.12` | FlyGym target: `2.1.0` | MuJoCo target: `3.9.0`
- Đối tượng chính: `flygym.compose.fly.neuromechfly.NeuroMechFly`
- `fly.skeleton is None` (Không gán thủ công)
- `add_joints()` **chưa được gọi** khi chưa có ủy quyền
- Số phân đoạn thân: **69** | Khớp giải phẫu: **68** | Bậc tự do JointDOFs: **204**

---

## 15. TRẠNG THÁI SẴN SÀNG NGHIÊN CỨU (RESEARCH READINESS SCORECARD)

Từ `docs/research_readiness.md` — Đánh giá minh bạch:

| Lĩnh vực | Điểm số | Diễn giải Trạng thái Thực tế |
|---|:---:|---|
| **Software Readiness** | 80/100 | Nền tảng đóng gói hoàn chỉnh, 516 unit tests vượt qua. |
| **Scientific Readiness** | 50/100 | Pipeline đối chuẩn hoàn thành; cần kiểm chứng wet-lab độc lập. |
| **Reproducibility** | 75/100 | Phiên bản, hạt giống và môi trường Colab được khóa hoàn toàn. |
| **Publication Readiness** | 75/100 | Bản thảo, bảng biểu và phụ lục toán học đã sẵn sàng. |
| **Open-Source Readiness** | 90/100 | Giấy phép MIT, cấu trúc chuẩn hóa, CI/CD tự động. |

---

## 16. KẾ HOẠCH XUẤT BẢN & CHECKLIST CÔNG BỐ QUỐC TẾ

### 16.1 Định vị Mục tiêu Công bố
1. **Tier 1 (Q1 Quốc tế):** *PLOS Computational Biology* hoặc *eLife* (khi hoàn thành tích hợp assay leo dốc 3D).
2. **Tier 2 (Hội nghị Quốc tế CORE/Scopus):** IEEE BIBM, IEEE EMBC, hoặc IEEE KSE / ACIIDS / RIVF.
3. **Giải thưởng Quốc gia:** Giải thưởng Sinh viên NCKH Cấp Bộ, Giải thưởng Euréka.

### 16.2 Checklist Sẵn sàng Công bố (`docs/publication_checklist.md`)
- [x] Giấy phép mã nguồn mở MIT hợp lệ
- [x] File định danh trích dẫn `CITATION.cff`
- [x] Toàn bộ 516 kiểm thử tự động vượt qua
- [x] Báo cáo kỹ thuật và bản thảo đề cương hoàn chỉnh
- [ ] Mint mã số định danh DOI từ Zenodo sau khi Release v1.0.0
- [ ] Bổ sung bộ dữ liệu đo đạc thực nghiệm từ phòng lab sinh học đối tác

---

## 17. ĐĂNG KÝ RỦI RO HOẠT ĐỘNG (RISK REGISTER)

| Nhóm Rủi ro | Nguyên nhân Tiềm ẩn | Mức độ | Biện pháp Giảm thiểu |
|---|---|:---:|---|
| **Lệch môi trường (Runtime)** | Phiên bản Python/MuJoCo không tương thích | Cao | Khóa cứng file môi trường `pyproject.toml` và script `check_runtime.py`. |
| **Lập luận vòng tròn (Bias)** | Cố tình dò tham số để khớp với bài báo | Nghiêm trọng | Dùng `molecular_bridge.py` tính toán thông số độc lập trước khi chạy mô phỏng. |
| **Lạm nhận sinh học (Overclaim)** | Đồng nhất mô hình tính toán với bệnh nhân | Nghiêm trọng | Duy trì tuyên bố ranh giới khoa học (*Scientific Boundary*) trong mọi báo cáo. |
| **Gián đoạn tính toán** | Máy chủ Colab bị ngắt kết nối khi chạy mảng lớn | Vừa | Cơ chế lưu checkpoint tự động sau mỗi hạt giống ($N=6$). |

---

## 18. CÂU HỎI NGHIÊN CỨU CÒN MỞ (OPEN RESEARCH QUESTIONS)

1. *Nhiễu bất đối xứng bán cầu não:* Làm thế nào để mô hình hóa chính xác sự suy thoái không đối xứng ở đột biến LRRK2?
2. *Tương tác giữa độ trễ và mất phối hợp:* Độ trễ khớp lệnh (`latency`) ảnh hưởng thế nào đến khả năng giữ thăng bằng khi đổi hướng?
3. *Độ nhạy của các mốc lão hóa:* Sự sụp đổ vận động ở ngày thứ 25 của dòng đột biến PINK1 có thể được làm chậm lại bằng can thiệp CPG ở thời điểm nào?

---

## 19. KẾ HOẠCH TRIỂN KHAI 8 THÁNG, KINH PHÍ & 4 CHECKPOINTS

### 19.1 Lộ trình 32 Tuần Thực hiện
- **Giai đoạn 1 (Tuần 1–3):** Hoàn thiện và đóng băng mô hình toán cầu nối phân tử (`molecular_bridge.py`). **[Checkpoint 1: Duyệt Toán học]**
- **Giai đoạn 2 (Tuần 4–7):** Chạy thực nghiệm đa hạt giống $N=6$ và kiểm định Wilcoxon toàn diện.
- **Giai đoạn 3 (Tuần 8–11):** Phân tích độ nhạy toàn cục Sobol 768 runs và Held-Out Validation. **[Checkpoint 2: Duyệt Mô phỏng]**
- **Giai đoạn 4 (Tuần 12–14):** Tích hợp đấu trường leo dốc 3D (*Negative Geotaxis Virtual Tube*).
- **Giai đoạn 5 (Tuần 15–17):** Tái tạo chuỗi dữ liệu thoái hóa 30 ngày (21 mốc thời gian). **[Checkpoint 3: Duyệt Chuỗi Lão hóa]**
- **Giai đoạn 6 (Tuần 18–28):** Đóng gói mã nguồn mở, viết bài báo khoa học IEEE. **[Checkpoint 4: Duyệt Bài báo]**
- **Giai đoạn Nghiệm thu (Tuần 29–32):** Bảo vệ đề tài và nộp hồ sơ xét giải thưởng NCKH.

### 19.2 Dự toán Kinh phí Thực hiện (6.600.000 VNĐ)
- Điện toán đám mây GPU (Google Colab Pro+): 1.200.000 VNĐ
- Tiếp cận cơ sở dữ liệu y văn chuyên sâu (IEEE, Nature, PNAS): 1.500.000 VNĐ
- Lệ phí đăng ký và báo cáo hội nghị quốc tế: 2.500.000 VNĐ
- In ấn poster A0, tài liệu đề cương và kỷ yếu: 800.000 VNĐ
- Dự phòng rủi ro kỹ thuật (10%): 600.000 VNĐ

---

## 20. CẨM NANG BẢO VỆ PHẢN BIỆN HỘI ĐỒNG (DEFENSE Q&A GUIDE)

### Câu hỏi 1: Hệ thống có bị "Lập luận vòng tròn" (Circular Reasoning) khi khớp tham số không?
**Trả lời:** Không. Tham số mô phỏng được tính toán tự động thông qua `molecular_bridge.py` dựa trên hàm Sigmoid của Muddapu & Chakravarthy (2020) và giải phẫu cụm nơ-ron PPL1 của Riemensperger (2013). Các tham số này được xác định **trước khi** đưa vào mô phỏng vật lý, không phải là kết quả của việc dò tham số thủ công.

### Câu hỏi 2: Tại sao kiểm định trên tập chỉ số giữ lại (Held-Out) chỉ đạt 50%?
**Trả lời:** Đây là giới hạn khoa học thực tế của mô hình bậc 1. Mô hình dự đoán rất chính xác độ lệch hướng của đột biến *parkin* (sai số chỉ 3.8%), nhưng chưa tái hiện được tính bất đối xứng của *LRRK2* do chưa có cơ chế nhiễu riêng biệt cho hai bán cầu não. Việc công khai tỷ lệ 50% thể hiện tính trung thực học thuật và mở ra hướng nghiên cứu tiếp theo.

### Câu hỏi 3: Số liệu các ngày 10, 15, 20 trong chuỗi 30 ngày có đáng tin cậy không?
**Trả lời:** Hai điểm mốc ngày 1 và ngày 25 là số liệu thực nghiệm y văn thật từ Clark (2006) và Park (2006). Các mốc trung gian là đường cong suy giảm hàm mũ đóng vai trò **dự đoán kiểm chứng được** (*falsifiable hypothesis*), sẵn sàng để các phòng lab sinh học đo đạc và kiểm chứng đối sánh.

---

## 21. DANH MỤC 14 TÀI LIỆU THAM KHẢO CHUẨN IEEE ĐÃ XÁC THỰC DOI

[1] J. Park et al., "Mitochondrial dysfunction in Drosophila PINK1 mutants is complemented by parkin," *Nature*, vol. 441, no. 7097, pp. 1157–1161, 2006. DOI: [10.1038/nature04788](https://doi.org/10.1038/nature04788)

[2] I. E. Clark et al., "Drosophila pink1 is required for mitochondrial function and interacts genetically with parkin," *Nature*, vol. 441, no. 7097, pp. 1162–1166, 2006. DOI: [10.1038/nature04779](https://doi.org/10.1038/nature04779)

[3] Y. Yang et al., "Mitochondrial pathology and muscle and dopaminergic neuron degeneration caused by inactivation of Drosophila Pink1 is rescued by Parkin," *Proc. Natl. Acad. Sci.*, vol. 103, no. 28, pp. 10793–10798, 2006. DOI: [10.1073/pnas.0602493103](https://doi.org/10.1073/pnas.0602493103)

[4] J. C. Greene et al., "Mitochondrial pathology and apoptotic muscle degeneration in Drosophila parkin mutants," *Proc. Natl. Acad. Sci.*, vol. 100, no. 7, pp. 4078–4083, 2003. DOI: [10.1073/pnas.0737556100](https://doi.org/10.1073/pnas.0737556100)

[5] Z. Liu et al., "A Drosophila model for LRRK2-linked parkinsonism," *Proc. Natl. Acad. Sci.*, vol. 105, no. 7, pp. 2693–2698, 2008. DOI: [10.1073/pnas.0708452105](https://doi.org/10.1073/pnas.0708452105)

[6] M. Meulener et al., "Drosophila DJ-1 mutants are selectively sensitive to environmental toxins associated with Parkinson's disease," *Current Biology*, vol. 15, no. 17, pp. 1572–1577, 2005. DOI: [10.1016/j.cub.2005.07.064](https://doi.org/10.1016/j.cub.2005.07.064)

[7] T. Riemensperger et al., "A single dopamine pathway underlies progressive locomotor deficits in a Drosophila model of Parkinson disease," *Cell Reports*, vol. 5, no. 4, pp. 952–960, 2013. DOI: [10.1016/j.celrep.2013.10.032](https://doi.org/10.1016/j.celrep.2013.10.032)

[8] H. Coulom and S. Birman, "Chronic exposure to rotenone models sporadic Parkinson's disease in Drosophila melanogaster," *Journal of Neuroscience*, vol. 24, no. 48, pp. 10993–10998, 2004. DOI: [10.1523/JNEUROSCI.2993-04.2004](https://doi.org/10.1523/JNEUROSCI.2993-04.2004)

[9] V. Lobato-Rios et al., "NeuroMechFly, a neuromechanical model of adult Drosophila melanogaster," *Nature Methods*, vol. 19, no. 5, pp. 620–627, 2022. DOI: [10.1038/s41592-022-01466-7](https://doi.org/10.1038/s41592-022-01466-7)

[10] P. Ramdya et al., "NeuroMechFly v2: Embodied sensorimotor modeling of Drosophila motor control," *eLife*, 2024.

[11] M. Kajtor et al., "Altered reactivity to threatening stimuli in Drosophila models of Parkinson's disease, revealed by a trial-based assay," *eLife*, vol. 14, p. e90905, 2025. DOI: [10.7554/eLife.90905](https://doi.org/10.7554/eLife.90905)

[12] V. R. Muddapu and V. S. Chakravarthy, "A Multi-Scale Computational Model of Excitotoxic Loss of Dopaminergic Cells in Parkinson's Disease," *Frontiers in Neuroinformatics*, vol. 14, p. 34, 2020. DOI: [10.3389/fninf.2020.00034](https://doi.org/10.3389/fninf.2020.00034)

[13] A. J. Ijspeert, "Central pattern generators for locomotion control in animals and robots: A review," *Neural Networks*, vol. 21, no. 4, pp. 642–653, 2008. DOI: [10.1016/j.neunet.2008.03.014](https://doi.org/10.1016/j.neunet.2008.03.014)

[14] GBD 2021 Collaborators, "Global burden of disorders affecting the nervous system, 1990–2021," *The Lancet Neurology*, vol. 23, no. 4, pp. 344–381, 2024. DOI: [10.1016/S1474-4422(24)00038-3](https://doi.org/10.1016/S1474-4422(24)00038-3)

---

*Tài liệu này là đặc tả hợp nhất chính thức của toàn bộ dự án `drosophila-pd-flygym`, tổng hợp đầy đủ từ hơn 70 tài liệu kỹ thuật trong thư mục `docs/`, toàn bộ mã nguồn `src/drosophila_pd/` và các bộ dữ liệu thực nghiệm đã kiểm chứng.*
