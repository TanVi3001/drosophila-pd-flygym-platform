# TASK 01 — Scientific scope & contribution audit

## 1. Metadata

**CLOSED — người dùng đã chấp nhận kết quả audit và hướng Workbench methods để phát triển tiếp.** Ngày 19/10/2026. Không phê duyệt scientific validity hoặc publication readiness; chưa thực hiện Task 02. Đây là chấp nhận deliverable/hướng phát triển, không phải independent scientific review hay phê duyệt protocol mới. Repo root: `E:\research-\.workbench\ai-v2-dev`; branch `feature/evidence-audit-review`; HEAD `03b91b598eb63a72840cacd9dd7bb5fed7ebd4b1`. Tool CWD `E:\Task` không phải Git repo; dùng repo bàn giao đã xác minh.

Working tree ban đầu: hai untracked `PROJECT_PAPER_MASTER_CONTEXT_VI_2026-10-19.md`, `scripts/_verify_plos018_deep.py`; không thay đổi. Đã đọc root AGENTS và kiểm tra chỉ dẫn thư mục. Chỉ ghi hai deliverables TASK01; không test/evaluation/approval. Bản này đã tự rà soát lần hai theo yêu cầu người dùng; không phải independent review.

Quy ước nguồn dưới đây: **R = `E:\research-\.workbench\ai-v2-dev\`**; đường dẫn trong bảng được nối với R. Đây là locator, không xác nhận dữ liệu đã được publish.

## 2. Hướng đề xuất

| Lựa chọn | Evidence readiness / novelty / kiểm chứng |
|---|---|
| **Workbench methods — chọn** | Có cơ chế gate/selection; hiệu quả chưa đo. Có thể kiểm chứng reliability; novelty domain-specific còn cần đối chiếu. |
| AI drafting methods | Pilot synthetic; comparator thiếu, overlap và provenance chưa giải quyết. RAG/citation không tự mới. |
| Workbench + AI phụ | Hợp kiến trúc nhưng tăng nghĩa vụ evidence; giữ AI ở phụ lục tích hợp, không cần thiết cho central claim. |

Không chọn vì tên roadmap: tài liệu active-scope còn ghi score Workbench trùng summary của effect-only/original-model, nên **không có bằng chứng superiority**. Nếu cơ chế chỉ tương đương cấu hình workflow tool có sẵn, đóng góp có thể chỉ là software integration; cần reviewer quyết định giá trị phương pháp.

Parkinson không thuộc claim chính. Development artifact không hỗ trợ graph superiority trong setup hiện tại; không dùng làm tiền đề paper.

## 3. Problem, central claim, contributions

**Problem:** Khi chuyển giả thuyết Drosophila thành computational screening, mapping/assay không tương thích, approval cũ và thiếu provenance có thể tạo khuyến nghị không đủ căn cứ. Cần thủ tục kiểm soát ranh giới suy luận và tái dựng quyết định.

**Central claim mục tiêu, chưa đạt:** Trong phạm vi assay/backend khai báo, procedure evidence-gated giúp giảm khuyến nghị sai phạm vi và tái dựng quyết định đáng tin cậy hơn workflow chỉ ghi provenance, mà không đạt kết quả bằng cách từ chối mọi case hợp lệ.

Contribution candidates:
1. Binding mapping–context–StudySpec–assessment–approval–job bằng hash và eligibility contract.
2. Selection có budget, paired uncertainty, stability và abstention minh bạch; không biến missing/QC failure thành negative.
3. Evidence bundle và giao thức đánh giá failure/reproduction có ranh giới suy luận.

Đây là **tổ hợp phương pháp dự kiến**, không phải phát minh hash/bootstrap. FlyGym/NeuroMechFly, upstream Shiu LIF/connectome/model/data là nền kế thừa; CLI/API/SQLite/worker là hạ tầng. Independent reproduction và evaluation đầy đủ vẫn là kế hoạch.

## 4. RQs và falsification

**RQ1 — Reliability:** Gate có giảm quyết định sai phạm vi?
- H: ít invalid recommendations hơn provenance-only workflow cùng inputs/backend; vẫn giữ valid-case coverage.
- Comparator: workflow tương đương bỏ compatibility/hash gate, không dùng một hệ thống cố ý kém.
- Endpoint: số invalid recommendations / số invalid cases được adjudicate; số valid cases được accept / tổng valid cases, abstention báo riêng. Case là đơn vị; lỗi biến thể cùng nguồn phải cluster.
- Bác bỏ: không giảm lỗi hoặc lợi ích chỉ do từ chối toàn bộ valid cases; ngưỡng phải chốt trước evaluation.
- Giới hạn: lỗi kiểm soát và software behavior, không biological validity; chưa có fault catalogue được duyệt.

**RQ2 — Reproduction:** Operator khác có tái dựng quyết định?
- H: bundle đầy đủ tăng tỷ lệ tái dựng đúng selection/exclusions so với logs/config thông thường.
- Comparator: cùng task, logs/config thông thường đủ chạy lại; operator thực sự khác, allocation/counterbalancing định trước để tránh learning effects.
- Endpoint: decision agreement và provenance completeness; tolerances numerical khai báo trước.
- Bác bỏ: không cải thiện hoặc thường cần sửa tay không được ghi nhận.
- Giới hạn: computational reproduction; model agreement không phải biological validation.

**RQ3 — Ranking utility, có điều kiện:** Policy có hữu ích hơn effect-only/random?
- H: tăng P@5 trên common assessable denominator; so thêm original-model/heuristic và null phù hợp.
- Endpoint: P@5; coverage, abstention, AP, false negatives riêng, không trộn thành reliability score.
- Không hỗ trợ H nếu ΔP@5 ≤ 0; CI phủ 0 là inconclusive. Chỉ diễn giải superiority theo ngưỡng/CI được duyệt trước, không suy từ point estimate đơn lẻ.
- Giới hạn: response-presence retrospective, không prospective wet-lab utility. Chưa được mở/chạy held-out; không đổi primary endpoint protocol hiện có âm thầm. Chuyển trọng tâm sang RQ1/RQ2 cần owner/reviewer quyết định version mới trước thiết kế/chạy.

## 5. Preliminary novelty

Đối chiếu trực tiếp ngày 19/10/2026, không systematic review:
- [NeuroMechFly v2, 2024](https://doi.org/10.1038/s41592-024-02497-y): đọc abstract; [FlyGym chính thức](https://neuromechfly.org/): đọc homepage Key features/API transition. Embodied sensorimotor simulation là upstream; Workbench không được nhận novelty đó.
- [Shiu et al., 2024](https://doi.org/10.1038/s41586-024-07763-9): đọc abstract; LIF brain model và validation của tác giả không chuyển thành validation Workbench.
- [AiiDA 1.0, 2020](https://doi.org/10.1038/s41597-020-00638-4): đọc abstract, provenance model/workflow mô tả trên HTML. Automation, provenance, error handling/plugin đã có. Khác biệt cần chứng minh là domain-specific eligibility binding và decision policy, không chỉ lưu manifest.
- [ALCE, 2023](https://doi.org/10.18653/v1/2023.emnlp-main.398): đọc abstract/metadata, chưa đọc metric methods đầy đủ. Retrieval+citation evaluation đã có; citation identity không bảo đảm claim support. Chưa đủ cơ sở novelty AI.

**Feature difference ≠ method novelty ≠ measured added value.** Chưa đo added value; chưa kiểm chứng độc đáo cơ chế. Không suy công trình khác thiếu gate chỉ vì abstract không nói. Cần so tiếp AiiDA domain extensions, Snakemake/Nextflow/RO-Crate và ALCE metric methods; không cần mở rộng literature audit trong task này.

## 6. Claim–evidence

IMPLEMENTED chỉ dựa static inspection; MEASURED là artifact lịch sử, không rerun. HUMAN_REVIEWED không đồng nghĩa independent.

| Claim | Trạng thái | Nguồn tại R | Hỗ trợ thực tế | Không suy ra / còn thiếu |
|---|---|---|---|---|
| Approval ràng buộc scope/hash | IMPLEMENTED | `src/drosophila_pd/workbench/service.py`:169–192,247–263 | So sánh hash/status; chỉ contract support-gated-1 | Reviewer chỉ là chuỗi không rỗng, không xác thực danh tính/độc lập; chưa kiểm bypass/runtime |
| Budget/uncertainty/abstention | IMPLEMENTED | `src/drosophila_pd/workbench/selection.py`: `select_candidates`; service `select_study` | LCB, budget, exclusions; incomplete collection không recommend | Chưa chứng minh utility/calibration; thiếu ablations |
| Graph chưa có superiority so B0 | MEASURED | `results/ai_v2_dev/task1c_robustness_v1/summary.json`:173–197 | B4–B0: ΔAP −0.11515; ΔP@5=0; unsupported | Development-only; không bác connectome biology; mapping review pending trong run |
| AI chỉ tạo draft trước approval riêng | IMPLEMENTED | `src/drosophila_pd/ai_v2/workbench_workflow.py`: create_draft/approve/submit/run | Các transition tách biệt | Không xác nhận reviewer độc lập hay vận hành an toàn toàn hệ thống |
| Synthetic pilot có measurement | MEASURED; HUMAN_REVIEWED (artifact tự khai) | `.workbench/ai-v2-comparisons/paired-20261009T131833878Z/metrics.json`: status/systems | 11 cases; comparison_complete=false; owner-reviewed-not-independent | Không biological/RAG superiority; thiếu comparator đầy đủ và review độc lập |
| Source-derived design có overlap | UNVERIFIED (documented) | `.workbench/evidence/protocol_evidence_eval_draft_20261011_v2/readiness.md`:24–26 | Tài liệu v2 báo evidence của mọi case v1 đã nằm trong protocol_text | Không phải kiểm corpus v2; extraction diagnostics ≠ retrieval utility; cần reviewed design |
| Main value/reproduction | PROPOSED; UNVERIFIED | `docs/workbench_publication_roadmap.md`: Gates C–D; `docs/workbench_active_scope.md`: Current evidence state | Yêu cầu evaluation/operator; tài liệu ghi comparison partial | Chưa completed comparative/independent result; thiếu approved protocol |

## 7. Ưu tiên và phạm vi Task 02 đề xuất

Phân loại theo central claim reliability; không coi mọi thiếu sót là blocker:

| Vấn đề | Mức / lý do; evidence cần audit tiếp |
|---|---|
| Response labels | BLOCKS_SECONDARY_CLAIM: ranking cần đúng target; truy source/row/label rule, phân biệt absent với unmeasured. |
| Units/dependence | UNKNOWN_PENDING_AUDIT: source-family/shared targets có thể làm CI lạc quan; cần cluster inventory. Seed repeats không phải independent studies. |
| Mapping/assay comparability | BLOCKS_MAIN_CLAIM: muốn đo “sai phạm vi” phải có adjudication độc lập; cần rubric, reviewer và disagreement record. |
| Feature–label circularity | BLOCKS_SECONDARY_CLAIM: cần lineage chứng minh feature không encode label/chung nguồn calibration. |
| Held-out exposure | BLOCKS_SECONDARY_CLAIM: active-scope:36–44 ghi partial score preparation; LOCKED_NOT_RUN thuộc artifact/track khác, không phải mâu thuẫn đã xác nhận. Cần access/version chronology; không mở sealed content. |
| Denominator/coverage | BLOCKS_MAIN_CLAIM nếu thiếu valid-case denominator chống reject-all; BLOCKS_SECONDARY_CLAIM cho ranking thiếu common assessability matrix. |
| AI source overlap | BLOCKS_SECONDARY_CLAIM nếu claim retrieval utility; chỉ LIMITATION cho phụ lục tích hợp. Cần input–corpus exposure map được phép truy cập. |
| Provenance/version | UNKNOWN_PENDING_AUDIT: nối run/prompt/schema/raw/processed; BLOCKS_MAIN_CLAIM nếu không định danh được artifact reliability. |

Thứ tự trước evaluation: owner/reviewer chốt claim → audit lineage/units/mappings/exposure → quyết định denominator/comparators/endpoints → protocol mới được duyệt. Task02 chỉ nên audit các nguồn và ranh giới này, trả evidence ledger/blocker decisions; không mặc định được chạy evaluation.

## 8. Giới hạn audit

Không mở held-out/sealed, chạy script tự load, test, provider, simulator/evaluator. Không kiểm toàn bộ call graph hoặc source-label records. Raw/processed schema paired metrics đều ghi VALID 11/11 mỗi LLM arm; bàn giao §10 nêu tài liệu khác ghi raw 0/11: chưa adjudicate run/version. PLOS 9 REVIEWED/11 PENDING, approval/freeze/run và review hiện tại: **theo tài liệu bàn giao, chưa xác minh hiện tại**. Gate plans không phải completed experiments; software correctness không phải scientific validity. Không xác nhận rank/acceptance hay readiness.

**TASK 01 ĐÃ ĐÓNG — chưa thực hiện Task 02; chờ chỉ dẫn riêng.**