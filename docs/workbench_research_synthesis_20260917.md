# Fly Research Workbench — tổng hợp nghiên cứu, gap và hướng tiếp theo

**Ngày cập nhật:** 17/09/2026  
**Phạm vi:** `drosophila-pd-flygym` + `drosophila-pd-neural-disease`
**Định vị hiện tại:** computational methods/workbench và retrospective public-data benchmark; chưa phải biological validation và chưa được tuyên bố Q1-ready.

## 1. Tóm tắt điều hành

Fly Research Workbench đang được phát triển thành một công cụ local web + CLI giúp nhà nghiên cứu Drosophila:

1. khai báo giả thuyết, dự đoán có thể bác bỏ và assay;
2. kiểm tra backend có thực sự hỗ trợ study hay không;
3. chạy các candidate và control với seed/provenance rõ ràng;
4. tách kết quả mô phỏng, độ ổn định tính toán và bằng chứng thực nghiệm;
5. QC, so sánh và ưu tiên ứng viên trong cùng study;
6. xuất evidence bundle để thảo luận với phòng lab.

Đóng góp có khả năng công bố không nằm ở việc xây lại FlyGym hoặc NeuroMechFly. Đóng góp nằm ở workflow tích hợp: capability checking, provenance, failure handling, held-out discipline, baseline comparison, scope-aware ranking và hồ sơ chuyển sang thực nghiệm.

Claim an toàn hiện tại:

> A reproducible, scope-bounded computational prioritization procedure evaluated against a checksum-pinned retrospective public-data benchmark.

Chưa được claim: mô phỏng bệnh Parkinson, tương đương ruồi thật, causal MN9 inference, driver-line validation, tiết kiệm chi phí wet-lab hoặc universal Drosophila validity.

## 2. Câu hỏi nghiên cứu và định vị bài báo

### Câu hỏi trung tâm

Một quy trình computational có provenance, QC và uncertainty rõ ràng có giúp ưu tiên candidate tốt hơn các cách đơn giản như effect-only, direct-connectivity heuristic hoặc random ordering trong một study Drosophila được khai báo trước hay không?

Đây là câu hỏi về **quy trình nghiên cứu và khả năng tái lập**, không phải tuyên bố rằng mô hình suy ra sự thật sinh học phổ quát.

### Định vị công bố

Hướng chính:

- methods/tool paper;
- benchmark paper nếu hoàn tất benchmark mở rộng và so sánh baseline;
- limitation/negative-result paper nếu chứng minh rõ giới hạn của LIF substrate thiếu neuromodulation.

Một venue Q1 sẽ đòi hỏi contribution rõ, evaluation không leakage, code/data có thể kiểm tra, failure case minh bạch và interpretation không vượt quá context of use. Q1 là mục tiêu nộp bài, không phải trạng thái có thể tự suy ra từ số test pass.

## 3. Tổng hợp bằng chứng nghiên cứu công khai

### Shiu et al. 2024

Shiu et al. xây dựng connectome-derived LIF model của não Drosophila và so sánh dự đoán với các quan sát thực nghiệm. Nguồn này phù hợp để tạo retrospective benchmark, nhưng model có các giới hạn quan trọng:

- basal firing được đơn giản hóa;
- gap junctions, morphology và một số receptor dynamics không được biểu diễn đầy đủ;
- dopamine, octopamine và serotonin không được mô hình hóa như một neuromodulation layer định lượng;
- kích hoạt/chặn synapse không đồng nghĩa với thoái hóa dopaminergic hoặc bệnh Parkinson.

Vì vậy, structural perturbation hoặc `proxy_burden` không được gọi là dopaminergic disease effect.

Nguồn: [Shiu et al., Nature](https://www.nature.com/articles/s41586-024-07763-9).

### Cande et al. 2018

Cande et al. cho thấy tác động của neuron lên hành vi phụ thuộc trạng thái hành vi trước kích thích và điều kiện assay. Do đó một kết quả “không thấy hiệu ứng” trong một điều kiện không đủ để loại bỏ vai trò của neuron.

Nguồn: [Cande et al., eLife](https://elifesciences.org/articles/34275).

### Thiết kế thí nghiệm

Các trường về đối chứng, experimental unit, randomization, blinding và primary outcome cần xuất hiện ngay trong study specification. Nhiều lần đo trên cùng một con ruồi không tự động trở thành các mẫu sinh học độc lập.

Nguồn: [NC3Rs experimental design](https://eda.nc3rs.org.uk/experimental-design), [experimental unit](https://eda.nc3rs.org.uk/experimental-design-unit).

### Các nguồn annotation/connectome

- [FlyWire annotations repository](https://github.com/flyconnectome/flywire_annotations): nguồn annotation cần được version-pin; không trộn Codex, FlyWire snapshot và systematic annotation mà không có mapping.
- [BANC project](https://github.com/htem/BANC-project): ứng viên cho cross-connectome brain+VNC analysis trong phase sau; chưa được coi là backend đã tích hợp hoặc validation tự động.
- `2025malecns`: registry của dữ liệu/connectome mở rộng; không được tự động thay baseline Shiu 2024.
- [NeuronBridge](https://www.janelia.org/node/69264): công cụ tìm liên hệ morphology–genetic tool, chỉ là điểm bắt đầu; cần kiểm tra specificity và stock availability.

## 4. Phạm vi scientific hiện tại

### Study A — sensory circuit / MN9

- backend: FlyWire-630-derived LIF;
- input: public sugar-sensing input set;
- readout: MN9 firing-rate path;
- intervention: activation và outgoing-synapse block theo preset;
- output: computational neural response và ranking;
- không chuyển firing rate thành xác suất hành vi;
- không suy ra driver-line specificity nếu chưa có review.

### Study B — motor/FlyGym

- backend: FlyGym/MuJoCo;
- output: trajectory, path speed, displacement, turning và gait metrics;
- có control không perturbation và kiểm tra orientation/symmetry;
- được trình bày như mechanical simulation benchmark nếu chưa có dữ liệu tương thích;
- không gọi là validation của bệnh hoặc neuron cụ thể.

### Study E1 — intensity sensitivity

E1 so sánh các mức input 50, 150 và 200 Hz trong computational MN9 assay.

### Study E2-v2 — matched temporal input

E2-v2 so sánh:

- sustained 75 Hz trong 1 giây;
- hai pulse 150 Hz, mỗi pulse 250 ms;
- no-input control;
- sustained 150 Hz reference.

Contrast chính là pulsed 150 Hz so với sustained 75 Hz. Rate-time product được khai báo là bằng nhau, nhưng actual spike count không được giả định bằng nhau.

## 5. Những gì đã triển khai trong repo

### Nền tảng Workbench

Đã có:

- `StudySpec`, `BackendAdapter`, `AssayAdapter`, `RunManifest`, `DecisionReport`;
- LIF/FlyGym adapters;
- SQLite job store và artifact directory theo run;
- subprocess với interpreter neural/platform tách biệt;
- seed, config hash, code/data provenance, command, environment và artifact hash;
- cancel/resume/failure handling;
- CLI/API dùng chung service;
- QC tách missing, silent, invalid và unknown-ID;
- template evidence bundle và fallback report không cần AI API.

### Tính đúng của dữ liệu và metric

Đã thêm hoặc kiểm tra:

- trial denominator lấy từ manifest thay vì số trial có spike;
- silent trial không bị loại khỏi mẫu số;
- neuron ID giữ dạng chuỗi;
- namespace/dataset/version mismatch bị từ chối;
- NaN/Inf/orientation lỗi không được xếp hạng;
- path speed được tách khỏi endpoint displacement speed;
- scale `0` được giữ đúng;
- `outgoing_synapse_block` không gọi là neuron death;
- lỗi backend được giữ trong artifact thay vì biến thành kết quả hợp lệ.

### Benchmark và baseline

Đã thêm:

- protocol freeze và protocol hash;
- development/held-out split;
- calibration chỉ dùng development cases;
- common assessable denominator;
- precision, recall, precision@k, average precision, false negatives, class balance và coverage;
- case-level bootstrap;
- random, effect-only, heuristic và original-model score;
- directed degree-preserving double-edge-swap null model.

Null model giữ in-degree, out-degree, outgoing weight multiset và declared edge stratum. Đây là structural null, không phải một connectome sinh học tương đương.

### Reproduction semantics

Verifier đã được sửa để không tự gắn nhãn `second_operator`. Các role hiện được phân biệt:

- `same_operator`;
- `automated`;
- `computational_public_data`;
- `second_operator` chỉ khi một người thứ hai thực sự chạy và ghi nhận.

AI có thể kiểm tra, tổng hợp và audit; AI không thể ký thay chuyên gia sinh học hoặc người vận hành độc lập.

## 6. Kết quả computational hiện tại

### Software verification

- platform full suite: **598 passed, 2 skipped**;
- neural full suite: **192 passed**;
- `compileall`: đạt ở hai repo;
- `pip check`: không có broken requirements;
- `git diff --check`: đạt, chỉ còn cảnh báo line-ending hiện hữu.

### E1 screening/confirmation

- screening: `40/40` jobs;
- confirmation: `120/120` jobs;
- confirmation seeds: `100–129`, tách khỏi screening seeds `0–9`;
- direction stability của các intervention: `1.0`.

Kết quả confirmation:

| Candidate | Mean delta MN9 | Bootstrap 95% CI | Rank |
|---|---:|---:|---:|
| 200 Hz | ~94.70 Hz | [92.866, 96.402] | 1 |
| 150 Hz | ~83.83 Hz | [81.233, 86.072] | 2 |
| 50 Hz | ~19.77 Hz | [17.200, 22.368] | 3 |

Đây là stability của computational model, không phải số ruồi và không phải biological replication.

### E2-v2 matched-input screening

- `40/40` jobs hoàn tất;
- bốn conditions;
- mười paired seeds mỗi condition;
- không có failed hoặc pending job.

Contrast chính:

- mean delta: `-9.4 Hz`;
- bootstrap 95% CI: `[-14.6, -3.5]`;
- direction stability: `0.7`;
- ranking threshold: `0.8`;
- kết luận: exploratory, **không được promote thành ranked priority**.

Artifact: [`ranking_primary_contrast_10000_bootstrap.json`](../results/workbench/e2_matched_input_screening_20260917/ranking_primary_contrast_10000_bootstrap.json).

### Frozen benchmark v2

Benchmark được tạo từ Shiu Supplementary Table 3:

- 106 source rows;
- 14 response-present và 92 response-absent theo published aggregate activation-rate field;
- 74 development và 32 held-out;
- checksum workbook: `6922E16825AA0C92A28E2A634B073DCAD7641E9C9283C4B9D8EE1E34E6D9B8D9`;
- protocol hash: `43b3704750572dade4774d514bcd986697f537b1b11de81ce918bac3310aad9f`;
- registry integrity: `READY`.

Quan trọng: response-present/absent là nhãn theo published field, không phải positive/negative biological effect, không phải significance test và không phải causal label.

## 7. Các gap hiện tại

### Gap A — chưa có comparative held-out result hoàn chỉnh

Đây là gap kỹ thuật–phương pháp quan trọng nhất. Evaluator chưa xuất được PASS vì chưa có score mapping thật cho degree-preserving rewire trên đúng 106 case.

Nguyên nhân:

- Table 3 dùng cell-type names;
- annotation release đã audit không có exact unique mapping cho `106/106` names;
- FlyWire snapshot 783 không được tự coi là FlyWire-630 của Shiu;
- prefix/name guessing sẽ tạo structural evidence giả.

Không được thay blocker này bằng published model score rồi gọi là Workbench reproduction.

### Gap B — benchmark là retrospective cùng upstream study

Shiu model và comparator experiment nằm trong cùng upstream paper. Benchmark v2 kiểm tra tính minh bạch và khả năng tái lập của procedure, nhưng chưa phải external independent validation.

### Gap C — thiếu domain-scientist review

Chưa có người ký cho:

- benchmark inclusion/exclusion;
- label semantics;
- MN9 interpretation;
- driver-line specificity;
- prospective wet-lab assay specification.

AI không thể đóng gate này.

### Gap D — chưa có second human reproduction

Hiện có automated/same-operator evidence. Chưa có một người khác chạy clean environment và kiểm tra cả success artifact lẫn failure artifact.

### Gap E — E2 confirmation và sensitivity chưa hoàn tất

E1 đã có 30-seed confirmation. E2-v2 mới có 10-seed screening; chưa có 30 fresh seeds và chưa chạy đầy đủ sensitivity panel synaptic/inhibitory strength.

### Gap F — cross-connectome chưa hoàn thành

BANC, FlyWire 783, MANC/MCNS/MAOL là hướng mở rộng, nhưng chưa có loader, mapping contract, provenance và kết quả so sánh trong repo. Không được xem khả năng upstream là bằng chứng local integration.

### Gap G — release hygiene

Cả hai worktree còn nhiều thay đổi/untracked files từ các phase trước. Chưa có commit/tag release sạch. Đây là gap audit/release, không phải bằng chứng code sai.

## 8. Trạng thái các release gate

| Gate | Trạng thái | Ý nghĩa |
|---|---|---|
| Software correctness | PASS | Code và regression tests đạt |
| Public registry integrity | READY | Checksum/split/row integrity đạt |
| E1 10-seed screening | PASS | Đã chạy đủ |
| E1 30-seed confirmation | PASS | Seed mới, đã chạy đủ |
| E2-v2 screening | PASS | 40/40, computational only |
| Benchmark protocol sign-off | BLOCKED | Chưa có reviewer khoa học |
| Benchmark mapping sign-off | BLOCKED | Chưa xác nhận mapping/assay semantics |
| Held-out comparison | BLOCKED | Thiếu real rewire score mapping |
| Independent reproduction | BLOCKED | Chưa có người thứ hai |
| MN9 biological review | BLOCKED | Chưa có expert review |
| Clean worktrees | BLOCKED | Còn thay đổi/untracked |
| Release tags | BLOCKED | Chưa tag HEAD sạch |

Artifact: [`release_gate_v2_with_seed_evidence_20260917.json`](../results/workbench/release_gate_v2_with_seed_evidence_20260917.json).

Public-data profile hiện là `READY_WITH_LIMITATIONS`, không phải Q1-ready release.

## 9. Hướng tiếp theo theo thứ tự ưu tiên

### P0 — Đóng comparative benchmark mà không gian dối

Chọn một trong hai đường:

1. Nhận mapping chính thức từ source/model snapshot 630 cho Table 3, có checksum và review; sau đó chạy Workbench, original model, random, effect-only, heuristic và rewire trên cùng held-out cases.
2. Nếu mapping Table 3 không thể đạt, chuyển benchmark chính sang tập có exact FlyWire IDs và ghi rõ v2 Table 3 là source-audit/coverage study, không trộn hai gate.

Output bắt buộc:

- score coverage từng system;
- common assessable denominator;
- precision@5 là primary endpoint;
- confusion matrix, precision, recall, AP, precision@10, false negatives;
- class balance;
- mọi unassessable case;
- rewire seeds, swap count và invariants.

### P1 — Hoàn thành evidence package

Tạo một bundle chứa:

- protocol và source checksum;
- mapping table;
- raw/public artifact manifest;
- benchmark comparison;
- E1/E2 campaign manifests;
- sensitivity output;
- failure injection tests;
- claim audit;
- software/environment lock.

### P2 — Independent reproduction

Nhờ một người thứ hai chạy một subset nhỏ từ clean environment. Cần cả:

- một success case;
- một failure/QC case;
- manifest/hash comparison;
- output tolerance;
- discrepancy log.

Nếu chỉ có một người và AI, ghi nhận là computational reproduction, không gọi là independent reproduction.

### P3 — Biological review

Gửi review package cho advisor/domain scientist để duyệt:

- MN9 identity và readout;
- input population;
- driver-line candidate;
- control và experimental unit;
- prospective assay;
- interpretation của null/negative result;
- cơ chế bị thiếu trong LIF substrate.

Reviewer ký vào protocol/spec, không ký thay kết quả chưa thực hiện.

### P4 — E2 confirmation và sensitivity

Chạy 30 fresh seeds cho E2 top contrast sau khi policy được duyệt, rồi chạy sensitivity panel `[0.7, 1.0, 1.3]` synaptic strength và `[0.5, 1.0, 1.5]` inhibitory strength. Không dùng benchmark held-out labels để tune.

### P5 — Cross-connectome robustness

Chỉ làm sau khi P0–P4 ổn định:

- loader cho BANC/FlyWire 783;
- explicit namespace mapping;
- version/checksum manifest;
- same assay và same readout contract;
- so sánh stability qua connectome.

Nếu kết luận không ổn định, đó là finding về connectome-dependence, không phải thất bại cần che giấu.

### P6 — Clean release

Chỉ sau khi review các thay đổi hiện tại:

1. phân loại giữ/bỏ file;
2. chạy full tests và clean-install test;
3. commit platform;
4. commit neural repo;
5. tag release tương ứng;
6. lưu manifest commit/tag/checksum.

Không commit hoặc tag toàn bộ worktree hiện tại một cách tự động vì đang có nhiều thay đổi tồn tại từ trước.

## 10. Claim ladder

| Mức | Claim được phép |
|---|---|
| Hiện tại | Reproducible computational prioritization/workbench pilot |
| Sau comparative benchmark | Procedure evaluated on a frozen retrospective public-data held-out set |
| Sau second human | Independently reproduced computational workflow |
| Sau biological review | Protocol/readout interpretation reviewed by a domain scientist |
| Sau cross-connectome | Scope-bounded robustness across declared connectome reconstructions |
| Sau wet-lab prospective | Chỉ khi có dữ liệu mới mới được nói về in-vivo biological effect |

Ngay cả sau cross-connectome vẫn không được nói “virtual fly equals X% real fly”, disease simulation đã được chứng minh, hoặc mọi negative result có thể loại bỏ.

## 11. Kết luận hiện tại

Dự án đã vượt qua giai đoạn prototype thuần phần mềm và hiện có một computational workbench có test, provenance, seed campaigns, benchmark registry và public-data audit.

Khoảng cách tới một bài Q1 không còn chủ yếu là thêm tính năng UI. Khoảng cách chính là:

1. benchmark mapping/evaluation trung thực;
2. external human reproduction;
3. domain-scientist review;
4. interpretation có giới hạn;
5. release archive sạch và có thể kiểm toán.

Nếu chưa có người thứ hai và chuyên gia sinh học, mục tiêu hợp lệ nhất là hoàn thiện methods/benchmark preprint với claim thấp, công khai toàn bộ blocker, và dùng kết quả negative/exploratory như bằng chứng về giới hạn của model chứ không biến chúng thành kết luận bệnh học.

