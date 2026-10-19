# TASK 02 — Evidence validity & evaluation fit audit

## 1. Metadata và coverage

**COMPLETE — 19/10/2026:** mọi câu hỏi đã được trả lời hoặc ghi UNKNOWN; blockers chưa giải quyết. Đây không phải scientific/publication approval hay protocol freeze.

Repo `E:\research-\.workbench\ai-v2-dev`; branch `feature/evidence-audit-review`; HEAD `03b91b598eb63a72840cacd9dd7bb5fed7ebd4b1`, không đổi so Task01. Ban đầu có bốn untracked: hai Task01, master-context và `_verify_plos018_deep.py`; không tracked diff. Không có baseline hash Task01 lịch sử để chứng minh nội dung untracked chưa từng đổi. Đã đọc root AGENTS, hai Task01; kiểm ancestor và các thư mục nguồn/tài liệu liên quan, không thấy chỉ dẫn bổ sung ở vị trí đã kiểm. Một recursive metadata command timeout; không coi đó là search hoàn tất.

Audit tĩnh, chọn lọc code/schema, builder source, documentation và development summary. Không chạy imports, tests, provider, simulator/evaluator hoặc benchmark. Không mở mixed registry/workbook, held-out/sealed contents hay access logs chưa được phân loại an toàn. Exact absolute paths/symbols nằm trong findings TSV; checkpoint ghi sections. VERIFIED_WITHIN_SCOPE nghĩa là đã đọc nguồn, không phải runtime/scientific validation; DOCUMENTED_ONLY không xác nhận sự kiện ngoài tài liệu.

## 2. Task01: kiểm lại ba tiền đề

1. **Approval binding (F01–02):** `approve_support_assessment` lưu study configuration hash + assessment hash. Assessment chứa capability, mapping hash/version, context outcomes, preflight. Reassessment xóa approval (`store.set_support_assessment`). Mapping ID immutable qua store API; materialization kiểm pinned version/hash nếu có và ghi actual mapping hash. `_require_support_freeze` chỉ enforce contract `support-gated-1`; không tự tính lại toàn bộ live inputs/backend code hashes. Approval không đồng nghĩa code/environment đã freeze; reviewer là string.
2. **Eligibility/selection (F03):** có capability/mapping/context/preflight, paired control/QC, minimum pairs, CI/stability, budget, deterministic ID tie-break và abstention. Đây là implementation, chưa đo added value.
3. **Comparative evidence (F04):** development summary xác nhận `GRAPH_SIGNAL_UNSUPPORTED`, B4−B0 ΔAP −0.1151465, ΔP@5=0. Workbench partial comparison/equal summaries chỉ xác nhận qua active-scope documentation; không mở report.

**Không phát hiện kết luận Task01 bị bác bỏ cần correction.** Các contribution candidates về binding/bundle vẫn là proposal. F10 thu hẹp mức readiness của bundle; không được chuyển proposal ấy thành kết quả reconstruction đã chứng minh. Giữ nguyên Task01.

## 3. A — Inventory “quyết định đúng”

| Type / input | Expected contract → output quan sát | Reference và giới hạn |
|---|---|---|
| Support: StudySpec, capability, mapping/context | unsupported/missing/pending phải chặn; control không ưu tiên → candidate status/reasons/run_allowed | support.assess_study_support; độc lập đọc contract/rubric. Backend hỗ trợ không phải biological support. |
| Approval invalidation: study/assessment/approval | stale/missing/hash mismatch chặn; reassess xóa approval → exception/event/approval record | service._require_support_freeze, store.set_support_assessment; contract compliance. |
| Execution eligibility: frozen study, materialized config, mapping/preflight | chỉ contract hợp lệ mới submit/run → job/validation error | service submit_job/materialization; correctness sinh học cần domain adjudication. |
| QC/assessability: backend payload/readout | thiếu/nonfinite/failed hoặc missing scalar không được đánh giá như negative → assay status, unpaired/QC failures | assays adapters, collection; finite không bảo đảm assay hợp nghĩa. |
| Ranking eligibility: paired observations/policy | đúng scope/control, đủ pairs, QC, uncertainty/stability → ranked/not_ranked | ranking.rank_candidates; independent rule oracle chỉ kiểm software; threshold có ý nghĩa cần chuyên môn. |
| Selection/abstention: support + collection + policy | support eligible, lower bound, budget; incomplete collection không recommend → selected/excluded/status/budget | selection.select_candidates, service.select_study; valid-case coverage cần reference độc lập. |
| Execution outcome: exit/error/cancel | COMPLETED/FAILED/CANCELLED → job/manifest | service._status_from_result; completion không đồng nghĩa QC/scientific success. |

**Circularity (F05):** dùng chính function đang audit để tạo expected decisions chỉ đo self-consistency. Reference cho lỗi contract phải tách implementation; quyết định “sai biological scope” cần rubric và adjudication độc lập, disagreement/expertise records. Chưa tìm thấy tập reference đó trong phạm vi đã đọc. Không decision nào được gọi scientifically correct chỉ vì khớp rule tác giả.

## 4. B–C — Lineage, construct, mapping/dependence

**F06–07:** builder `_build_cases` định nghĩa row = một source Excel row/cell type có aggregate numeric observed activation rate. Positive iff observed >0; zero thành negative; missing/nonnumeric bỏ qua, không gán negative. Documentation mô tả published experimental aggregate; audit không kiểm workbook hay quy trình đo upstream. Zero là reported zero, không chứng minh không có response sinh học; detection limit, sample size, missingness/reporting bias UNKNOWN. Label được code tác giả derive từ reported observed field, không phải adjudicated gate correctness.

Model MN9 rates/SD và shortest-path được lấy từ cùng bảng nhưng khác fields với observed label. Cùng source không tự chứng minh algebraic leakage. Chưa xác minh upstream calibration, feature transformations và label independence; cần lineage không chứa held-out rows. Nếu reference/feature đều từ model hoặc một phép biến đổi nhau thì chỉ model agreement; schema tự nó không ngăn trường hợp này. Profile v2 nói model/experiment cùng upstream publication, không upstream-independent validation. Không suy held-out composition từ aggregate counts.

**F08–09:** đúng namespace/ID không bảo đảm đúng population, species/snapshot/side, activation-versus-silencing, MN9 firing-versus-behavior. Mapping schema có dataset/version/intervention/readout/context; context chỉ so những keys được khai báo. Species/cell type/direction/assay equivalence không được bảo đảm chỉ bởi string equality. Profile v2 ghi annotation-release mismatch; development packet ghi shared targets và scientific review pending. Đây là documentation, không current registry audit.

Phân biệt: code lưu/enforce review; record tồn tại; chuyên gia hoàn tất; review độc lập. Chỉ mức đầu được kiểm code; packet mô tả record pending, không xác nhận hai mức cuối. Unit hiện dùng source row; thích hợp cho computational descriptive analysis nhưng chưa chứng minh độc lập. Source/study/cohort/assay, shared driver/target/intervention family và upstream calibration có thể tạo cluster. Packet nêu shared targets; cohort/animal/driver-family dependency map NOT_FOUND_WITHIN_INSPECTED_SCOPE. Case-level bootstrap/seed repeats không giải quyết các phụ thuộc đó.

## 5. D — Exposure timeline (không đọc dữ liệu)

| Mốc / track | Record; mức exposure; ảnh hưởng method; chắc chắn |
|---|---|
| 17/09/2026, Workbench v2; commit 839bd2f | Profile mô tả retrospective upstream model/experiment cùng publication. Upstream exposure documented; cá nhân nào đọc labels/predictions lúc nào UNKNOWN. |
| 22/09/2026, Workbench; commit 2efb617 | Active-scope ghi partial held-out score preparation và aggregate-summary equality. Predictions/aggregate preparation được tài liệu mô tả, access bởi ai UNKNOWN; “finding to investigate” không chứng minh đã đổi method. |
| Historical Task1, AI V2; ngày sự kiện UNKNOWN | Access policy §7 ghi đọc effect từ mixed artifact có non-development score rows. Khả năng exposure mixed scores đã được ghi nhận; read byte/semantic exposure và ảnh hưởng lựa chọn UNKNOWN; không kết luận label leakage. |
| 12/10/2026, AI V2 Task1C; commit 03b91b5 | Dev summary ghi LOCKED_NOT_RUN; go/no-go nói development-only audit. Track-specific documented non-run, không global untouched. Rule-change statement chỉ DOCUMENTED_ONLY. |

Commit dates là version-history anchors, không access timestamps. Không có exposure toàn cục được xác nhận bằng access log trong audit này; có documentary evidence và plausible exposure nêu trên. Access ledger/actor identities/method-choice chronology **chưa audit được**; không tìm record trong nguồn đã đọc không nghĩa untouched (F14). Cần sanitized metadata-only ledger qua owner/curator, không mở dữ liệu để chứng minh chưa mở.

## 6. E — Reconstruction

**F10 P0:** service ghi support/approval/selection riêng, nhưng EvidenceBundle v2 schema/export được kiểm không có dedicated fields/files tương ứng. Không chứng minh export tự chứa chuỗi study → mapping/support → approval → execution → QC → selection; không khẳng định mọi possible bundle instance đều thiếu metadata gián tiếp. Missing/unreadable manifests bị skip khi get bundle. Cần một development-only export inventory, gồm negative/no-job decisions, để xác minh completeness.

**F11:** manifest có config/input/artifact hashes, backend code revision/state, environment và optional pre-run. Selection lưu policy/hash, collection, source manifests; ranking có logic version; tie-break/LCB trong code. Numeric transformations/normalization phải reconcile với pinned logic/input, không chỉ schema version. Export chủ yếu JSON/manifests, không tự copy raw inputs/backend/environment; local paths, registry/store/events, external assets và operator state có thể cần ngoài bundle. Chưa audit một portable instance đầy đủ.

Bốn mức khác nhau: (1) giải thích từ saved record: có hạ tầng, cần completeness; (2) recompute từ saved inputs: chưa chứng minh; (3) rerun simulation: cần backend/data/environment, không thực hiện; (4) khác environment/operator: chưa có independent evidence được kiểm. `verify_reproduction` nhận operator role do caller khai, không authenticate độc lập. Hash kiểm identity/integrity của bytes đã hash, không chứng minh đúng biological content, đủ evidence hoặc authentic approval.

## 7. F — Comparator/denominator và verdict

F12–13: ranking comparators effect-only/random/original/heuristic/rewire trả lời C, không A/B. Code common-assessable intersection và full-system reports giữ coverage/unassessable, nhưng subset vẫn có thể loại case khó có lợi cho system; missing candidate/unpaired jobs ở collection và QC/not_ranked/budget ở selection phải nối lại full denominator. Calibration dùng assessable development subset; information parity và missingness parity chưa xác minh.

Reliability comparator Task01 (matched workflow bỏ gate) và reconstruction comparator (ordinary logs/config) phù hợp câu hỏi về nguyên tắc, chưa measured/validated. Human-reviewed outcome thuộc toàn workflow; autonomous component chỉ claim kiểm tra/enforce machine contract. P@5 hiện hữu không là primary endpoint hợp A/B; giữ endpoint Task01 ở mức proposal, không tự chọn endpoint mới. Independent valid/invalid-case reference và coverage chống reject-all còn thiếu.

| Evidence / hướng | Verdict |
|---|---|
| Code/contracts cho descriptive gate/abstention | SUPPORTED_FOR_DESCRIPTIVE_ANALYSIS; không measured reliability |
| Benchmark response-presence cho A/B | NOT_SUITABLE_FOR_THIS_CLAIM |
| Bundle/manifest cho B | POTENTIALLY_USABLE_AFTER_FIXES; independent reconstruction evidence INSUFFICIENT_INFORMATION |
| Dev ranking comparisons cho C | SUPPORTED_FOR_DESCRIPTIVE_ANALYSIS, không superiority |
| Retrospective ranking v2 cho C | POTENTIALLY_USABLE_AFTER_FIXES; current complete held-out comparison INSUFFICIENT_INFORMATION |
| Biological validity/independent prediction | INSUFFICIENT_INFORMATION |

## 8. Blockers và Task03 đề xuất, chưa thực hiện

P0: F05 independent decision reference; F10 end-to-end bundle completeness; F13 construct/comparator mismatch nếu dùng ranking để chứng minh central claim. P1: mapping/domain review, dependence, exposure chronology, input parity và denominator/version reconciliation. Đề xuất Task03 chỉ sau review: chốt bounded decisions/rubric, yêu cầu sanitized lineage/access/bundle inventory, reviewer quyết định endpoints/comparators và protocol version. Không tự sửa blocker, freeze hay chạy experiment.

**DỪNG CHỜ REVIEW — chưa thực hiện Task 03.**