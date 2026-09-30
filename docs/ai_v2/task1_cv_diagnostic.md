# Task 1 fixed-CV diagnosis — post-result audit

The original Task 1 five-fold manifest is unchanged (`6b054c6ff0a6669cb6038b0cd365a6787f5fa5f2d0e5018094badd6cce256dab`). Counts below use only the 74 development labels from the development evaluator artifact. They were examined **after** Task 1 results and cannot be presented as pre-Task-1 planning.

| Original fold | Cases | Positive | Negative | Positive prevalence |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 15 | 1 | 14 | 6.7% |
| 1 | 15 | 2 | 13 | 13.3% |
| 2 | 15 | 5 | 10 | 33.3% |
| 3 | 15 | 1 | 14 | 6.7% |
| 4 | 14 | 1 | 13 | 7.1% |

Average Precision and AUPRC depend on both ranking and the fold's positive prevalence: a single positive ranked first can yield AP 1.0 in a one-positive fold, while a fold with five positives asks a different ranking question. Precision@5 advances in steps of 0.2 per positive in the top five. When a fold contains one or two positives, its maximum possible P@5 is only 0.2 or 0.4; fold 2 can reach 1.0. Recall@5 has coarse increments of 1.0, 0.5 or 0.2 for folds with one, two or five positives respectively. These denominators make the Task 1 fold variance unsurprising; they do not prove class balance is the only cause.

A separate stratified diagnostic manifest now distributes the ten positives as two per fold. It was created after Task 1 results and **does not replace** the original fixed CV. Its SHA-256 membership hash is `bddbe5a7a51a0610c4d6b82aaf27ac7e6fd10cf892eb0c824ec2dcd3f95fccfd` with seed `20260930`. Four folds have 15 cases (2 positive, 13 negative); one has 14 (2 positive, 12 negative). The assignment is deterministic, label-stratified and not hand-adjusted based on Task 1 performance.

Repeated stratified 5-fold CV could probe partition sensitivity, but ten repeats would create correlated estimates from the same ten positive cases, not 50 independent experiments. We leave it as a future candidate rather than create or execute a repeated protocol in this audit. One stratified repeat is the registered Task 1C diagnostic.
