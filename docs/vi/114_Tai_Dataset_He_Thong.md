# Hướng dẫn tải toàn bộ dataset của dự án (từ link public, không cần git)

> Tài liệu này mô tả **mọi nguồn dữ liệu** mà dự án sử dụng và cách tải trực tiếp
> bằng HTTP (browser / curl / PowerShell) mà không cần clone repo hay Git LFS.
>
> Toàn bộ link bên dưới đã được kiểm tra trả về `HTTP 200` kèm kích thước chính xác.
> Ngày kiểm tra: 2026-08-25.

## Tổng quan các nhóm dữ liệu

| Nhóm | Nội dung | Nguồn công khai |
|---|---|---|
| A | Connectome FlyWire v783 + weights + kết quả thí nghiệm | Repo GitHub `tuanwannafly/drosophila-pd-flygym`, nhánh `plan/phase-A` |
| B | Bản gốc học thuật của FlyWire v783 (đầy đủ nhất) | Zenodo `10.5281/zenodo.10676866`, Codex FlyWire |
| C | Annotations neuron FlyWire | Repo `flyconnectome/flywire_annotations` |
| D | Văn liệu sinh học PD/Drosophila | DOI của từng bài báo (bảng ở mục 5) |

## 1. Nhóm A — Dataset chính của dự án

Repo lưu file lớn bằng **Git LFS**. Khi tải qua HTTP phải dùng đúng loại URL:

- File thường → `https://raw.githubusercontent.com/tuanwannafly/drosophila-pd-flygym/plan/phase-A/<đường_dẫn>`
- File LFS (`.pt`, `.parquet`, `.mp4`) → `https://media.githubusercontent.com/media/tuanwannafly/drosophila-pd-flygym/plan/phase-A/<đường_dẫn>`

⚠️ Không dùng URL `raw.githubusercontent.com` cho file LFS — sẽ nhận được
file con trỏ ~134 byte thay vì nội dung thật.

### Bảng tải đầy đủ (kích thước đã xác minh)

| # | File | Đích đến trong repo | Loại | Kích thước (bytes) |
|---|---|---|---|---|
| 1 | `data/2025_Completeness_783.csv` | `data/` | raw | 3,465,987 |
| 2 | `data/2025_Connectivity_783.parquet` | `data/` | **LFS** | 100,804,642 |
| 3 | `data/flywire_annotations.tsv` | `data/` | raw | ~32,7 triệu* |
| 4 | `data/sez_neurons.pickle` | `data/` | raw | 5,114 |
| 5 | `data/benchmark-results.csv` | `data/` | raw | 209 |
| 6 | `data/plastic_weights.pt` | `data/` | **LFS** | 60,369,156 |
| 7 | `data/plastic_weights_fly0.pt` | `data/` | **LFS** | 60,369,181 |
| 8 | `data/plastic_weights_fly1.pt` | `data/` | **LFS** | 60,369,181 |
| 9 | `data/eye_L_0.png` | `data/` | raw | 18,260 |
| 10 | `data/eye_L_20.png` | `data/` | raw | ~24,556 |
| 11 | `data/eye_R_0.png` | `data/` | raw | ~18,658 |
| 12 | `data/eye_R_20.png` | `data/` | raw | ~23,396 |
| 13 | `datasets/experimental_locomotion_db.json` | `datasets/` | raw | 16,785 |
| 14 | `results/brain_driven/pink1_locomotion.json` | `results/brain_driven/` | raw | 36,791 |
| 15 | `results/brain_driven/pink1_age25_locomotion.json` | `results/brain_driven/` | raw | ~38k |
| 16 | `results/brain_driven/parkin_locomotion.json` | `results/brain_driven/` | raw | ~38k |
| 17 | `results/brain_driven/dj1_locomotion.json` | `results/brain_driven/` | raw | ~38k |
| 18 | `results/brain_driven/lrrk2_locomotion.json` | `results/brain_driven/` | raw | ~38k |
| 19 | `results/brain_driven/complexI_locomotion.json` | `results/brain_driven/` | raw | ~38k |
| 20 | `results/brain_driven/pink1_parkin_OE_age25_locomotion.json` | `results/brain_driven/` | raw | ~38k |

\* File văn bản có thể chênh vài trăm KB giữa các bản vì chuyển đổi dòng (CRLF/LF).

Tổng dung lượng nhóm A: **~270 MB**.

### Tải dữ liệu ngoài Git

Các đường dẫn raw cũ của branch `plan/phase-A` không còn được dùng: chúng
trỏ vào một snapshot GitHub không còn tồn tại sau khi tách dữ liệu lớn khỏi
repo. Dùng hướng dẫn chuẩn tại
[`data/DOWNLOADS.md`](../../data/DOWNLOADS.md) và đối chiếu
[`data/source_manifest.json`](../../data/source_manifest.json).

Clone mới và bộ test mặc định không cần tải nhóm dữ liệu này. Chỉ tải những
file cần cho workflow đang chạy; không dùng `git add -f` cho các file lớn.

### Kiểm tra sau khi tải

Nếu đã tải dữ liệu ngoài, kiểm tra kích thước/hash theo `data/source_manifest.json`:

```powershell
Get-FileHash data\2025_Connectivity_783.parquet -Algorithm SHA256
Get-FileHash data\flywire_annotations.tsv -Algorithm SHA256
Get-FileHash data\2025_Completeness_783.csv -Algorithm SHA256
```

### Phương án thay thế: tải cả thư mục dưới dạng ZIP

```text
https://codeload.github.com/tuanwannafly/drosophila-pd-flygym/zip/refs/heads/plan/phase-A
```

Lưu ý: ZIP từ GitHub **chứa con trỏ LFS**, không chứa nội dung thật của
`.pt/.parquet/.mp4`. Các file đó vẫn phải tải riêng qua bảng ở trên.

## 2. Nhóm B — Nguồn gốc học thuật FlyWire v783 (tùy chọn, bản đầy đủ)

Các file nhóm A được dẫn xuất từ release chính thức của FlyWire Consortium
(Dorkenwald et al., Nature 2024). Nếu cần bản gốc đầy đủ:

| Dữ liệu | Link public | Ghi chú |
|---|---|---|
| Connectivity v783 (Zenodo) | <https://zenodo.org/records/10676866> | `proofread_connections_783.feather` 852 MB; `flywire_synapses_783.feather` 9.5 GB; MD5 công bố trên trang |
| Download portal Codex FAFB v783 | <https://codex.flywire.ai/api/download?dataset=fafb&data_version=783> | Danh mục file + metadata; một số sản phẩm cần đăng nhập Google |
| Trang chủ FlyWire | <https://flywire.ai/> | Điều khoản sử dụng & citation |

## 3. Nhóm C — Annotations neuron FlyWire

Bản gốc (`Supplemental_file1_neuron_annotations.tsv`, ~31.7 MB):

```text
https://raw.githubusercontent.com/flyconnectome/flywire_annotations/main/supplemental_files/Supplemental_file1_neuron_annotations.tsv
```

Repo dự án dùng bản đã xử lý tại `data/flywire_annotations.tsv` (bảng nhóm A).
Schlegel et al., Nature 2024 là citation cho annotations.

## 4. Paper PDF (Zenodo DOI của dự án)

```text
https://doi.org/10.5281/zenodo.19152238
```

Record: *Emergent Individuality and Neural Integration in Whole-Brain Connectome
Simulations of Drosophila melanogaster*, Rojas Aliaga E. M. (2026),
license CC-BY-4.0, file `paper_emergent_individuality.pdf` (~2.3 MB).

## 5. Nhóm D — Văn liệu sinh học (số liệu tham chiếu)

Các nguồn này không cần tải file — truy cập qua DOI để đọc/ghi chú số liệu
dùng cho calibration và E4 concordance:

| ID trong DB | Bài báo | DOI |
|---|---|---|
| Mendes_2013 | Mendes CS et al., 2013, eLife — gait quantification | `10.7554/eLife.00231` |
| Park_2006 | Park J et al., 2006, Nature — PINK1/parkin climbing | `10.1038/nature04788` |
| Coulom_2004 | Coulom H & Birman S, 2004, J. Neurosci — rotenone model | `10.1523/JNEUROSCI.24-48-10993.2004` |
| Riemensperger_2011 | Riemensperger T et al., PNAS — dopamine deficiency walking | `10.1073/pnas.1010930108` (PMID 21187381) |
| Chen_2014 | Chen AY et al., GBB — alpha-synuclein A30P walking | `10.1111/gbb.12172` (PMID 25113870) |

Danh sách đầy đủ nằm trong `datasets/experimental_locomotion_db.json`
(trường `metadata.literature_sources`).

## 6. Quy tắc provenance (theo `reproducibility/dataset_policy.md`)

Sau khi tải xong, mỗi dataset cần ghi nhận: nguồn (URL), ngày tải,
kích thước byte, và SHA-256:

```powershell
Get-FileHash data\*.pt, data\*.parquet -Algorithm SHA256 | Format-Table Hash, Path
```

Không chỉnh sửa nội dung file tải về; mọi bản xử lý phải lưu thành file mới
kèm ghi chú biến đổi. Dữ liệu này là dữ liệu mô phỏng/connectome tính toán,
không phải bằng chứng sinh học Parkinson.

## 7. Xử lý sự cố

| Triệu chứng | Nguyên nhân | Khắc phục |
|---|---|---|
| File `.pt/.parquet` chỉ ~134 byte, mở ra thấy chữ "git-lfs" | Đã dùng URL raw cho file LFS | Dùng URL `media.githubusercontent.com/media/...` |
| `404 Not Found` | Sai tên branch hoặc đường dẫn | Branch đúng là `plan/phase-A`; kiểm tra lại bảng mục 1 |
| Download bị ngắt giữa chừng | Mạng không ổn định với file >60 MB | Dùng `curl.exe -L -C - -o <file> <url>` để resume |
| ZIP giải nén thiếu nội dung file lớn | ZIP GitHub chứa con trỏ LFS | Tải riêng từng file LFS theo bảng mục 1 |
