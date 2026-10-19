# TASK 02 — Checkpoint

Status: COMPLETE — 2026-10-19. Câu hỏi đã trả lời hoặc UNKNOWN có lý do/nguồn thiếu trong main report và TSV. Blockers chưa giải quyết; không scientific approval. Chỉ audit, không test/evaluation/Task03.

Repo `E:\research-\.workbench\ai-v2-dev`; branch `feature/evidence-audit-review`; HEAD `03b91b598eb63a72840cacd9dd7bb5fed7ebd4b1`, bằng Task01. Git status ban đầu: bốn untracked (hai Task01, master context, scripts/_verify_plos018_deep.py), không tracked diff. Root AGENTS đã đọc; ancestor/docs AGENTS được kiểm metadata, không thấy file. Giữ nguyên mọi thay đổi.

Cụm 1: đọc Task01 audit/checkpoint; support.py:1–310 (output có truncate, cần đọc lại 131–208); service.py:98–192,247–318; selection.py:72–183; workbench_q1_manuscript_protocol.md:1–93; workbench_active_scope.md:1–52.

Findings cuối (TSV là authoritative): F01 approval binding/contract scope; F02 reviewer string; F03 implemented gates/selection; F04 negative development comparison; F05 independent decision reference chưa xác minh; F14 exposure chỉ documented. Không kết luận runtime.

Task01 hashes ban đầu: checkpoint F899671385B6FF23C3C6FAF6184DE05F83091AD49527FF50371432372B11A1C9; audit 11B64809CACE9205EB25161F430DA8042D7A6331DA971F3947BA1C2608386765. Không sửa Task01.

Không mở: reports/workbench/shiu_v2_heldout_evaluation.json; mọi held-out/sealed labels/predictions/scores, registry trộn split. Không chạy scripts/imports.

UNKNOWN: upstream label lineage, mapping biological comparability, dependence, hash refresh, bundle completeness, exposure chronology, comparator inputs.

 Cụm 2–3 hoàn tất: đọc support:131–208; service:223–246,358–526,1000–1085,1499–1572,1682–1768; store:89–166; models:283–350; handoff:137–179,309–348,433–466; ranking:202–325; assays:1–110,128–228; benchmark:23–98,297–364,532–620; benchmark_baselines:57–132; reproduction:517–565. Đọc builder (chỉ source) build_shiu_benchmark_v2.py:1–205; public-data-validation-v2:1–116; AI V2 access policy/go-no-go/mapping packet; development summary:173–198. Task01 RQ1–3 đọc lại :38–56.

Findings bổ sung: T02-F06 builder lấy observed >0, bỏ numeric missing, không biological absence; F07 shared upstream không independent validation/circularity unresolved; F08 mapping context chỉ kiểm các key khai báo, review expertise chưa xác nhận; F09 source-row split/shared targets chưa đủ independence; F10 bundle v2 không có dedicated support/approval/selection fields hoặc export file tương ứng; F11 manifests có input/config/artifact/code/environment provenance nhưng không chứng minh portable reproduction; F12 common subset không thay full denominator; F13 chưa evidence độc lập cho comparator reliability/reconstruction.

Git metadata: public-data profile 839bd2f (17/09); active scope 2efb617 (22/09); go/no-go 03b91b5 (12/10). Đây là commit timestamps, không phải access timestamps. Lệnh combined metadata timeout 300s, không script nào chạy; dùng output riêng để xác nhận các commit trên. Không tìm AGENTS bổ sung trong các thư mục trực tiếp đã kiểm; recursive metadata search chưa chứng nhận hoàn tất.

Deliverables: TASK02_EVIDENCE_VALIDITY_AUDIT.md, TASK02_FINDINGS.tsv, TASK02_CHECKPOINT.md cùng thư mục publication_review. Main report 1.622 whitespace words; TSV 14 findings/9 columns/14 unique IDs, không empty fields khi kiểm read-only. Git HEAD/tracked diff không đổi; chỉ thêm ba Task02 ngoài bốn untracked ban đầu. Hai Task01 hashes cuối khớp hashes đầu. Không test, import, simulator, evaluator hay benchmark.

P0 F05 independent reference, F10 bundle chain completeness, F13 construct/comparator fit. Không correction bác bỏ Task01; F10 thu hẹp readiness của contribution proposal. UNKNOWN còn lại: access ledger/actors/method influence, upstream measurement/calibration, domain adjudication, dependency clusters, portable bundle instance và comparator parity. Đề xuất curator cung cấp sanitized metadata/development inventory; không tự truy cập mixed/sealed files.

Bước tiếp: DỪNG CHỜ REVIEW — chưa thực hiện Task03. Reviewer quyết định scope/protocol version; không tự sửa blocker.

Nếu được giao follow-up riêng: đọc AGENTS, checkpoint/main report, kiểm HEAD/status và phạm vi được phép trước; không tự tiếp tục UNKNOWN hoặc Task03.