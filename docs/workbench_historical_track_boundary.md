# Historical track boundary

The active manuscript scope is defined in
`configs/workbench/active_manuscript_scope.yaml`.

The neural-disease repository is retained for historical and separate
validation work. Older Chen/Pozo calibration and Parkin prospective artifacts
must not be silently promoted into the active Workbench claim. They may be used
to document limitations, failed directional validation, or future work only
under their own claim locks and provenance.

This boundary is intentional: a computational Workbench benchmark labels
published response-presence/agreement cases, whereas a gene-specific biological
claim requires independently reviewed genetic intervention, mapping, assay
compatibility, and biological validation.
