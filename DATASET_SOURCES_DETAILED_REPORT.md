# BÁO CÁO CHI TIẾT CÁC NGUỒN DATASET ĐÃ TẢI VÀ TÍCH HỢP TRÊN MÁY
## Project: `drosophila-pd-flygym` (DROSOPHILA-PD-FLYSIM-2026)

> **Thời điểm rà soát:** 28/08/2026  
> **Tổng số file dữ liệu:** 100+ files  
> **Tổng dung lượng lưu trữ:** ~307.30 MB  
> **Các định dạng chính:** `.parquet`, `.tsv`, `.csv`, `.json`, `.pt` (PyTorch Weights), `.pickle`, `.png`

---

## MỤC LỤC

1. [TỔNG QUAN HỆ SINH THÁI DỮ LIỆU CỦA DỰ ÁN](#1-tổng-quan-hệ-sinh-thái-dữ-liệu-của-dự-án)
2. [NHÓM 1: DỮ LIỆU CONNECTOME & NƠ-RON TOÀN NÃO (FLYWIRE CONNECTOME)](#2-nhóm-1-dữ-liệu-connectome--nơ-ron-toàn-não-flywire-connectome)
3. [NHÓM 2: TRỌNG SỐ MẠNG NƠ-RON THÍCH ỨNG (PLASTIC NEURAL WEIGHTS)](#3-nhóm-2-trọng-số-mạng-nơ-ron-thích-ứng-plastic-neural-weights)
4. [NHÓM 3: DỮ LIỆU THỊ GIÁC & CẢM GIÁC HAI MẮT (VISUAL OMMA-TIDIA DATA)](#4-nhóm-3-dữ-liệu-thị-giác--cảm-giác-hai-mắt-visual-omma-tidia-data)
5. [NHÓM 4: CƠ SỞ DỮ LIỆU THỰC NGHIỆM ĐA TẦNG BỆNH PARKINSON](#5-nhóm-4-cơ-sở-dữ-liệu-thực-nghiệm-đa-tầng-bệnh-parkinson)
6. [NHÓM 5: THAM SỐ CẦU NỐI PHÂN TỬ & CHUỖI LÃO HÓA 30 NGÀY](#6-nhóm-5-tham-số-cầu-nối-phân-tử--chuỗi-lão-hóa-30-ngày)
7. [NHÓM 6: DỮ LIỆU KẾT QUẢ MÔ PHỎNG ĐA HẠT GIỐNG & KIỂM ĐỊNH THỐNG KÊ](#7-nhóm-6-dữ-liệu-kết-quả-mô-phỏng-đa-hạt-giống--kiểm-định-thống-kê)
8. [NHÓM 7: CẤU TRÚC ĐĂNG KÝ DATASET CHUẨN TRONG REPO (DATASET ADAPTER)](#8-nhóm-7-cấu-trúc-đăng-ký-dataset-chuẩn-trong-repo-dataset-adapter)
9. [BẢNG TỔNG HỢP TOÀN BỘ FILE DỮ LIỆU TRÊN MÁY](#9-bảng-tổng-hợp-toàn-bộ-file-dữ-liệu-trên-máy)

---

## 1. TỔNG QUAN HỆ SINH THÁI DỮ LIỆU CỦA DỰ ÁN

Dự án `drosophila-pd-flygym` tích hợp hệ thống dữ liệu đa tầng (multi-scale biological data) kết nối từ **cấp độ Synapse / Connectome toàn não**, **mạng nơ-ron điều khiển thích ứng**, **cơ sở dữ liệu động học y văn wet-lab**, cho đến **kết quả mô phỏng động lực học vật lý 3D**:

```
┌────────────────────────────────────────────────────────────────────────┐
│ 1. CONNECTOME & ANATOMY (FlyWire v783 - 130.7 MB)                      │
│    - 2025_Connectivity_783.parquet (Synaptic Wiring Matrix)           │
│    - flywire_annotations.tsv (Cell types, 3D Coordinates, Transmitters)│
│    - 2025_Completeness_783.csv (138,639 proofread neurons)             │
│    - sez_neurons.pickle (106 Subesophageal Zone Motor Clusters)        │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ 2. EMBODIED NEURAL WEIGHTS & SENSORY INPUT (172.8 MB)                  │
│    - plastic_weights.pt / plastic_weights_fly0/1.pt (Torch Weights)    │
│    - eye_L/R_0/20.png (Retinal Ommatidia Visual Fields)                │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ 3. WET-LAB BENCHMARK GROUND TRUTH (experimental_locomotion_db.json)    │
│    - 300 fps Joint Kinematics (6 legs, 5 joints, 11 stance-swing phases)│
│    - Longitudinal 40-day disease trajectories (WT, pink1, park, LRRK2) │
│    - Ground reaction forces & Tarsal pad adhesion (micronewtons)       │
│    - Pharmacological Dose-Response (L-DOPA, Rosi, JNK Inhibitor)       │
│    - 284 Dopaminergic Neurons (PAM, PPL1, PPM3, PPL2 clusters)         │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ 4. SIMULATION & STATISTICAL RESULTS (3.8 MB)                           │
│    - 48 Multi-seed Physics Runs (multi_seed_raw.json, wilcoxon.json)   │
│    - LOMO Held-Out Cross-Validation (held_out_validation_report.json)  │
│    - SALib Sobol Global Sensitivity (768 evaluations)                  │
│    - 21 Aging Timepoints (aging_series/ bridge scale JSONs)            │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 2. NHÓM 1: DỮ LIỆU CONNECTOME & NƠ-RON TOÀN NÃO (FLYWIRE CONNECTOME)

Thư mục lưu trữ: `d:\research\drosophila-pd-flygym\data\`  
Tổng dung lượng: **130.70 MB**  
Nguồn gốc: **Dự án FlyWire Consortium (Princeton University / MRC LMB Cambridge / Nature 2024)**

### 2.1 `data/2025_Connectivity_783.parquet` (96.13 MB)
- **Mô tả:** Ma trận kết nối Synapse chi tiết toàn bộ não bộ ruồi giấm trưởng thành (*Full Adult Fly Brain - FAFB*), phiên bản phát hành v783 (tháng 01/2025).
- **Nội dung:** Chứa hàng triệu cặp kết nối thần kinh (pre-synaptic root_id $\to$ post-synaptic root_id), số lượng synap (syn_count), và trọng số dẫn truyền.
- **Vai trò:** Cung cấp cấu trúc mạng nơ-ron nền tảng để ánh xạ từ các cụm nơ-ron Dopaminergic (PPL1, PPM3, PAM) xuống các nơ-ron truyền lệnh vận động (Descending Neurons - DNs).

### 2.2 `data/flywire_annotations.tsv` (31.26 MB)
- **Mô tả:** Bảng chú giải tế bào học và phân loại nơ-ron toàn não ruồi giấm.
- **Số lượng cột:** 31 cột thuộc tính, bao gồm:
  - `supervoxel_id`, `root_id`: Mã định danh nơ-ron duy nhất trong FlyWire.
  - `pos_x`, `pos_y`, `pos_z`: Tọa độ không gian 3D của nơ-ron trong hệ tọa độ chuẩn FAFB.
  - `soma_x`, `soma_y`, `soma_z`: Tọa độ thân tế bào (*soma*).
  - `nucleus_id`: Mã định danh nhân tế bào.
  - `cell_type`, `class`, `subclass`: Phân loại nơ-ron (Dopaminergic, Cholinergic, GABAergic, Glutamatergic, v.v.).
  - `neuropil`: Vùng não định vị (Central Complex, Mushroom Body, Antennal Lobe, Optic Lobe, SEZ...).
- **Vai trò:** Cho phép lọc chính xác vị trí và đặc tính của các nơ-ron Dopamine PPL1, PPM3, PAM để mô phỏng sự suy thoái có chọn lọc trong bệnh Parkinson.

### 2.3 `data/2025_Completeness_783.csv` (3.31 MB)
- **Mô tả:** Bảng trạng thái kiểm định và hoàn thiện (*Proofreading completeness*) của toàn bộ nơ-ron trong Connectome v783.
- **Số lượng bản ghi:** **138.639 nơ-ron**.
- **Cấu trúc:** `root_id`, `Completed (True/False)`.
- **Vai trò:** Đảm bảo chỉ những nơ-ron đã được kiểm chứng bằng phương pháp chuyên gia (*manually proofread*) mới được đưa vào mô hình tính toán.

### 2.4 `data/sez_neurons.pickle` (5.1 KB)
- **Mô tả:** Danh mục nhị phân chứa **106 cụm nơ-ron vùng dưới thực quản** (*Subesophageal Zone - SEZ*).
- **Các nhóm nơ-ron chính:** `aDT6`, `amulet`, `aSG1`, `aSG7`, `aster`, `Asteroid`, `bamboo`, `basket`, `bluebell`, `bobber`...
- **Vai trò:** SEZ là trung tâm tích hợp cảm giác vị giác, cơ học và kích hoạt các phản xạ vận động chân trong hành vi kiếm ăn và bước đi.

---

## 3. NHÓM 2: TRỌNG SỐ MẠNG NƠ-RON THÍCH ỨNG (PLASTIC NEURAL WEIGHTS)

Thư mục lưu trữ: `d:\research\drosophila-pd-flygym\data\`  
Tổng dung lượng: **172.71 MB**  
Định dạng: **PyTorch Model Checkpoint (`.pt`)**

| Tên File | Dung lượng | Mô tả chức năng |
|---|:---:|---|
| `data/plastic_weights.pt` | 57.57 MB | Trọng số mạng nơ-ron cảm giác - vận động có tính dẻo (*Synaptic Plasticity*) chuẩn của ruồi số. |
| `data/plastic_weights_fly0.pt` | 57.57 MB | Bộ trọng số thích ứng của cá thể ruồi mẫu số 0 trong môi trường mô phỏng vật lý khép kín. |
| `data/plastic_weights_fly1.pt` | 57.57 MB | Bộ trọng số thích ứng của cá thể ruồi mẫu số 1 (sử dụng trong kiểm định tính bền vững giữa các cá thể). |

- **Vai trò trong hệ thống:** Được nạp vào bộ điều khiển nơ-ron của NeuroMechFly / FlyGym để điều chỉnh nhịp phát xung của CPG thích nghi với lực cản môi trường và độ ma sát mặt sàn.

---

## 4. NHÓM 3: DỮ LIỆU THỊ GIÁC & CẢM GIÁC HAI MẮT (VISUAL OMMA-TIDIA DATA)

Thư mục lưu trữ: `d:\research\drosophila-pd-flygym\data\`  
Tổng dung lượng: **82.8 KB** (4 files ảnh PNG)

- `data/eye_L_0.png` (17.8 KB) & `data/eye_R_0.png` (18.2 KB): Bản đồ thị trường võng mạc mắt ghép (trái/phải) ở góc nhìn ngang 0°.
- `data/eye_L_20.png` (24.0 KB) & `data/eye_R_20.png` (22.8 KB): Bản đồ thị trường võng mạc mắt ghép ở góc ngẩng 20°.
- **Vai trò:** Cung cấp thông tin cảm giác đầu vào cho mô hình thị giác hai mắt của FlyGym trong các bài test phản xạ né vật cản (*Looming stimulus assay* - Kajtor et al., 2025).

---

## 5. NHÓM 4: CƠ SỞ DỮ LIỆU THỰC NGHIỆM ĐA TẦNG BỆNH PARKINSON

File lưu trữ: `d:\research\drosophila-pd-flygym\datasets\experimental_locomotion_db.json`  
Dung lượng: **16.65 KB** (265 dòng JSON có cấu trúc)  
Phiên bản schema: `2.0.0`

Đây là cơ sở dữ liệu đối chuẩn thực nghiệm quan trọng nhất của dự án, tổng hợp đầy đủ số liệu định lượng từ **6 công trình khoa học quốc tế uy tín**:

### 5.1 Nguồn Gốc Y Văn Trích Xuất

| Mã Nguồn | Tác giả & Năm | Tạp chí | DOI | Dữ liệu đóng góp chính |
|---|---|---|---|---|
| `Mendes_2013` | Mendes CS et al. (2013) | *eLife* | [10.7554/eLife.00231](https://doi.org/10.7554/eLife.00231) | Theo dõi fTIR chân 300 fps, động học góc khớp 6 chân, dáng đi Tripod. |
| `Park_2006` | Park J et al. (2006) | *Nature* | [10.1038/nature04788](https://doi.org/10.1038/nature04788) | Chuỗi ngày suy thoái leo dốc *PINK1 null*, cứu vãn Parkin OE. |
| `Coulom_2004` | Coulom H & Birman S (2004) | *J. Neurosci* | [10.1523/JNEUROSCI.24-48-10993.2004](https://doi.org/10.1523/JNEUROSCI.24-48-10993.2004) | Độc tính Rotenone ức chế Complex I, đáp ứng phục hồi theo liều L-DOPA. |
| `Riemensperger_2013` | Riemensperger T et al. (2013) | *Cell Reports* | [10.1016/j.celrep.2013.10.024](https://doi.org/10.1016/j.celrep.2013.10.024) | Bất hoạt cụm Dopamine PAM (NP6510), suy giảm phản xạ leo dốc SING. |
| `Dumitrescu_2022` | Dumitrescu A et al. (2022) | *ACS Chem. Neurosci* | [10.1021/acschemneuro.2c00277](https://doi.org/10.1021/acschemneuro.2c00277) | Đo nồng độ Dopamine in vivo bằng Fast-Scan Cyclic Voltammetry (FSCV). |
| `Liessem_2026` | Liessem S et al. (2026) | *Current Biology* | [10.1016/j.cub.2025.12.015](https://doi.org/10.1016/j.cub.2025.12.015) | Mạch Dopamine cổng nơ-ron điều khiển bước MDN & DNg100, bất đối xứng rẽ. |

### 5.2 Các Phân Hệ Dữ Liệu Chi Tiết trong File

1. **Chuỗi Ngày Tiến Triển Bệnh Học (*Longitudinal Disease Timecourse* — Ngày 1 đến Ngày 40):**
   - *Wild-type (Canton-S) Healthy:* Vận tốc $19.2 \to 10.5\text{ mm/s}$, Điểm leo dốc $0.94 \to 0.68$, Dopamine relative $1.00 \to 0.72$.
   - *pink1^B9 null:* Vận tốc $17.1 \to 4.5\text{ mm/s}$, Điểm leo dốc $0.78 \to 0.18$, Dopamine relative $0.88 \to 0.42$.
   - *park^25 null:* Vận tốc $17.3 \to 5.8\text{ mm/s}$, Điểm leo dốc $0.80 \to 0.25$, Dopamine relative $0.89 \to 0.48$.
   - *TH-Gal4 > UAS-LRRK2^G2019S:* Vận tốc $18.0 \to 7.1\text{ mm/s}$, Điểm leo dốc $0.91 \to 0.35$.
   - *Rotenone 500 uM Chronic:* Vận tốc $17.5 \to 4.1\text{ mm/s}$ (Ngày 1 $\to$ Ngày 10), Điểm leo dốc $0.88 \to 0.18$.

2. **Chuỗi Động Học Góc Khớp 6 Chân 300 fps (*Joint Kinematics Time Series*):**
   - Chia 11 pha trong chu kỳ bước (0% $\to$ 100% Stance-Swing Cycle).
   - Dữ liệu 5 góc khớp cho từng chân: Chân trước (LF), Chân giữa (LM), Chân sau (LH) gồm `ThC_pitch`, `ThC_roll`, `CTr_pitch`, `FTi_pitch`, `TiTa_pitch`.
   - Bảng so sánh giữa *Wild-type* và *PINK1 late*: Tầm vận động giảm $-38.5\%$, Thời gian tiếp đất kéo dài $+22.4\%$, Độ nâng chân giảm $-41.2\%$, Nhiễu lệch pha liên chi $\text{SD} = 18.6\text{ ms}$.

3. **Lực Tiếp Xúc Mặt Sàn & Độ Bám Dính (*Ground Reaction Forces & Adhesion*):**
   - Trọng lượng chuẩn của ruồi: $9.81\text{ }\mu\text{N}$.
   - *Wild-type:* Lực nâng $F_z = 5.4\text{ }\mu\text{N}$, Lực đẩy $F_x = 2.8\text{ }\mu\text{N}$, Lực bám đệm tarsus = $3.8\text{ }\mu\text{N}$.
   - *pink1 Parkinson:* Lực nâng $F_z = 3.2\text{ }\mu\text{N}$, Lực đẩy $F_x = 1.4\text{ }\mu\text{N}$, Lực bám đệm tarsus = $2.1\text{ }\mu\text{N}$.

4. **Đường Cong Đáp Ứng Liều Dược Lý (*Pharmacological Dose-Response*):**
   - **L-DOPA (0.0 $\to$ 5.0 mM):** Phục hồi vận tốc từ $7.1 \to 15.2\text{ mm/s}$ ở liều tối ưu $1.0\text{ mM}$; xuất hiện hiện tượng múa giật (*Dyskinesia-like twitching*) ở liều $\ge 5.0\text{ mM}$.
   - **Rosiglitazone (0 $\to$ 100 uM):** Phục hồi vận tốc từ $8.2 \to 14.1\text{ mm/s}$ ở liều tối ưu $50.0\text{ }\mu\text{M}$.
   - **JNK Inhibitor SP600125 (0 $\to$ 20 uM):** Phục hồi vận tốc từ $8.6 \to 13.5\text{ mm/s}$ ở liều $20.0\text{ }\mu\text{M}$.

5. **Kiểm Kê 284 Nơ-ron Dopaminergic Đã Định Danh (*Dopaminergic Cluster Inventory*):**
   - Cụm **PAM** (130 nơ-ron/bán cầu): Chi phối hành vi leo dốc SING và phần thưởng đường (Gal4: `NP6510`, `R58E02`).
   - Cụm **PPL1** (12 nơ-ron/bán cầu): Chi phối hành vi ghi nhớ né tránh và phản ứng stress (Gal4: `MB504B`, `TH-Gal4`).
   - Cụm **PPM3** (8 nơ-ron/bán cầu): Chi phối vận tốc tiến và điều biến nơ-ron lệnh MDN (Gal4: `TH-Gal4`, `R20B05`).
   - Cụm **PPL2** (6 nơ-ron/bán cầu): Chi phối tích hợp cảm giác khứu giác.

---

## 6. NHÓM 5: THAM SỐ CẦU NỐI PHÂN TỬ & CHUỖI LÃO HÓA 30 NGÀY

Thư mục lưu trữ: `d:\research\drosophila-pd-flygym\data\bridge_scales\`  
Tổng số files: **28 files JSON**

### 6.1 Bảy Mô Hình Gen Đột Biến Cốt Lõi (`data/bridge_scales/*.json`)
- `pink1_bridge_scales.json`: $\alpha = 1.1485, \kappa = 1.0476$ (Bù trừ sớm)
- `parkin_bridge_scales.json`: $\alpha = 0.9851, \kappa = 0.4762$ (Mất đồng bộ CPG)
- `lrrk2_bridge_scales.json`: $\alpha = 1.0000, \kappa = 0.6500$ (Bất đối xứng rẽ)
- `dj1_bridge_scales.json`: $\alpha = 0.9400, \kappa = 0.9200$ (Stress oxy hóa)
- `complexI_bridge_scales.json`: $\alpha = 0.8535, \kappa = 0.8500$ (Ngộ độc Rotenone)
- `pink1_age25_bridge_scales.json`: $\alpha = 0.7826, \kappa = 0.5000$ (Thoái hóa ngày 25)
- `pink1_parkin_OE_age25_bridge_scales.json`: $\alpha = 0.9565, \kappa = 0.8500$ (Cứu vãn di truyền)

### 6.2 Chuỗi 21 Mốc Lão Hóa 30 Ngày (`data/bridge_scales/aging_series/*.json`)
Gồm 21 file định lượng tham số cho 3 nhánh phát triển theo 7 mốc ngày tuổi (Day 1, 5, 10, 15, 20, 25, 30):
1. **Nhánh Healthy Control:** `healthy_day01` $\to$ `healthy_day30` ($\alpha: 1.02 \to 0.95$)
2. **Nhánh PINK1 Progressive:** `pink1_day01` $\to$ `pink1_day30` ($\alpha: 1.02 \to 1.15 \to 0.70$)
3. **Nhánh Genetic Rescue (Parkin OE):** `pink1_parkin_OE_day01` $\to$ `pink1_parkin_OE_day30` ($\alpha: 1.02 \to 0.92$)

---

## 7. NHÓM 6: DỮ LIỆU KẾT QUẢ MÔ PHỎNG ĐA HẠT GIỐNG & KIỂM ĐỊNH THỐNG KÊ

Thư mục lưu trữ: `d:\research\drosophila-pd-flygym\results\` và `colab_results_7models\`  
Tổng dung lượng: **~3.80 MB**

### 7.1 Dữ Liệu Chạy Đa Hạt Giống 48 Runs (`results/brain_driven/seed_analysis/`)
- `multi_seed_raw.json` (218.5 KB): Chứa toàn bộ chuỗi tọa độ $x(t), y(t), z(t)$, góc Yaw $\psi(t)$, và 9 chỉ số vận động của 48 lần chạy mô phỏng vật lý (8 điều kiện $\times$ 6 seeds: 42, 101, 2024, 7, 999, 12345).
- `multi_seed_wilcoxon.json` (31.5 KB): Kết quả kiểm định thống kê Paired Wilcoxon Signed-Rank Test hai phía cho cả 7 mô hình ($p = 0.03125$).
- `multi_seed_ablation3.json` (13.3 KB): Kết quả thực nghiệm triệt tiêu Ablation Abl-3 đánh giá giá trị gia tăng của bộ chỉ số mở rộng.
- `multi_seed_summary.csv` (10.4 KB): Bảng tổng hợp Mean $\pm$ SD của các chỉ số vận động trên 6 hạt giống.

### 7.2 Dữ Liệu Kiểm Định Chéo Giữ Lại (`results/validation/held_out_validation_report.json` - 2.3 KB)
- Báo cáo kết quả Leave-One-Metric-Out (LOMO) Cross-Validation:
  - `parkin` Yaw Deviation: Dự đoán $+44.0\%$ vs Y văn $+47.8\%$ (Sai số $3.8\%$ — **HIGH CONCORDANCE**).
  - `lrrk2` Turning Asymmetry: Sai số $143.5\%$ (**DISCORDANT** — do thiếu nhiễu bất đối xứng bán cầu).
  - `pink1_age25` Linearity: Sai số $23.9\%$ (**MODERATE**).
  - `pink1_rescue` Duty Cycle: Sai số $95.0\%$ (**DISCORDANT**).

### 7.3 Dữ Liệu Phân Tích Độ Nhạy Toàn Cục Sobol (`results/analysis/sobol_sensitivity_analysis.json` - 1.8 KB)
- Kết quả chạy 768 lần đánh giá Saltelli Sampling trên thư viện SALib 1.5.2:
  - Vận tốc: $S_1(\alpha) = 0.991, S_1(\kappa) = 0.009$
  - Góc Yaw: $S_1(\kappa) = 0.987, S_1(\alpha) = 0.008$
  - Hiệu suất quỹ đạo: $S_1(\kappa) = 0.948$

### 7.4 Bảng Biểu & Hình Ảnh Bằng Chứng Khoa Học (`results/analysis/`)
- `figures/e1_parameter_response.png` (78.6 KB): Đáp ứng tham số 2D.
- `figures/e2_condition_comparison.png` (48.8 KB): So sánh 7 điều kiện bệnh học.
- `figures/e3_paired_seed_robustness.png` (78.9 KB): Độ bền vững qua các hạt giống ngẫu nhiên.
- `figures/e5_computational_reversibility.png` (76.5 KB): Đồ thị phục hồi tính toán của Parkin OE.
- `tables/evidence_manifest.csv` (1.7 KB): Bảng kê toàn bộ bằng chứng số liệu và mã hash.

---

## 8. NHÓM 7: CẤU TRÚC ĐĂNG KÝ DATASET CHUẨN TRONG REPO (DATASET ADAPTER)

Hệ thống cung cấp module phần mềm [`src/drosophila_pd/dataset_adapter/`](file:///D:/research/drosophila-pd-flygym/src/drosophila_pd/dataset_adapter/) và [`src/drosophila_pd/dataset_registry/`](file:///D:/research/drosophila-pd-flygym/src/drosophila_pd/dataset_registry/) để tự động phát hiện, kiểm tra tính toàn vẹn (checksum MD5/SHA256) và nạp các tập dataset vào pipeline nghiên cứu:

- `datasets/healthy/README.md`: Thư mục tiếp nhận các rollout của ruồi khỏe mạnh Wild-type.
- `datasets/pd_mild/README.md`: Tiếp nhận các rollout của giai đoạn bệnh nhẹ (Day 1–5).
- `datasets/pd_moderate/README.md`: Tiếp nhận các rollout giai đoạn trung bình (Day 10–15).
- `datasets/pd_severe/README.md`: Tiếp nhận các rollout giai đoạn nặng (Day 25–40).
- `research/campaigns/healthy_baseline/dataset_manifest.template.json`: Bản mẫu manifest chuẩn hóa cho từng dataset.

---

## 9. BẢNG TỔNG HỢP TOÀN BỘ FILE DỮ LIỆU TRÊN MÁY

| Nhóm Dữ Liệu | Thư mục | Số lượng files | Dung lượng | Mục đích khoa học chính |
|---|---|:---:|:---:|---|
| **1. Connectome toàn não** | `data/` | 4 files | **130.70 MB** | Ma trận synap FAFB v783, chú giải 138k nơ-ron, SEZ clusters |
| **2. Trọng số mạng nơ-ron** | `data/` | 3 files | **172.71 MB** | Checkpoint PyTorch cho mạng điều khiển cảm giác - vận động |
| **3. Dữ liệu thị giác** | `data/` | 4 files | **0.08 MB** | Trường thị giác mắt ghép ommatidia 2 mắt góc 0° và 20° |
| **4. CSDL thực nghiệm PD** | `datasets/` | 1 file | **0.02 MB** | Động học 300 fps, chuỗi 40 ngày, lực sàn, liều thuốc, 284 DA neurons |
| **5. Tham số cầu nối phân tử** | `data/bridge_scales/` | 28 files | **0.02 MB** | 7 mô hình gen đột biến + 21 mốc chuỗi lão hóa 30 ngày |
| **6. Kết quả mô phỏng & thống kê** | `results/`, `colab_*/` | 55+ files | **3.80 MB** | 48 multi-seed runs, Wilcoxon, LOMO validation, Sobol 768 runs, Figures |
| **7. Khung đăng ký Dataset** | `datasets/*/`, `configs/` | 5+ files | **0.01 MB** | Manifests, templates, README quy chuẩn tiếp nhận dữ liệu |
| **TỔNG CỘNG** | | **100+ files** | **~307.30 MB** | **Đầy đủ hạ tầng dữ liệu cho toàn bộ pipeline nghiên cứu** |

---

*Báo cáo này được lập tự động từ việc quét và kiểm tra thực tế toàn bộ các tệp dữ liệu có mặt trong workspace `d:\research\drosophila-pd-flygym` ngày 28/08/2026.*
