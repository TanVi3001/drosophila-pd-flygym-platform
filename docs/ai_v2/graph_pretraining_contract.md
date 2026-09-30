# AI V2 graph pretraining — PROPOSED / DEVELOPMENT

`GraphPretrainingContract` records an unlabeled graph source and SHA-256, feature-mask policy, encoder type, seed, self-supervised task, embedding dimension and inductive graph scope. `GraphEmbeddingArtifact` additionally records encoder config hash, source commit and pretraining mode. The development contract accepts only `inductive` scope; any transductive experiment needs a separate protocol and leakage review.

The graph may contain public, unlabeled connectivity. Validation nodes, edges, features and labels are not part of this contract. The interface rejects source names advertising labels/outcomes. It is a declarative software guard, so dataset provenance and storage isolation must be verified separately. No GraphMAE, GAT or GraphGPS training is implemented.
