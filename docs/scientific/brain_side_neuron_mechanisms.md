# Brain-Side Neuron Mechanisms & Biological Grounding (Gap 1 Specification)

## 1. Executive Summary

This document formalizes the biological mechanism, computational LIF neuron mapping, and peer-reviewed literature grounding for the 7 brain-driven Parkinson's disease (PD) models in this research pipeline.

By bridging experimental neurogenetics literature with Leaky Integrate-and-Fire (LIF) network simulations, each condition in `data/bridge_scales/` corresponds to an explicit pathophysiological hypothesis.

---

## 2. Mathematical Formalism (Brain-to-Body Bridge)

The brain simulation (`fly-brain`) models the central complex and Descending Neurons (DNs). The membrane potential $V_i(t)$ of each neuron $i$ evolves according to:

$$\tau_m \frac{dV_i(t)}{dt} = -(V_i(t) - V_{rest}) + R_m \sum_{j} W_{ij} S_j(t) + R_m I_{bias, i}$$

When $V_i(t) \ge V_{th}$, a spike is emitted ($S_i(t) = 1$) and $V_i(t) \leftarrow V_{reset}$.

The bridge scales transmitted to the body-side simulation (`drosophila-pd-flygym`) represent normalized Descending Neuron population firing rates:

$$\text{motor\_scale} = \frac{\langle r_{\text{fwd\_DN}}(\text{PD}) \rangle}{\langle r_{\text{fwd\_DN}}(\text{Control}) \rangle}, \quad \text{coupling\_scale} = \frac{\langle r_{\text{turn\_DN}}(\text{PD}) \rangle}{\langle r_{\text{turn\_DN}}(\text{Control}) \rangle}$$

---

## 3. Systematic Model Mapping & Biological Grounding

| Model ID | Genotype / Intervention | Biological Pathology & Mechanism | LIF Mathematical Intervention | Primary Literature Reference | `motor_scale` | `coupling_scale` |
|---|---|---|---|---|---|---|
| `pink1` | *PINK1* loss-of-function (Young adult) | Early mitochondrial stress leading to compensatory hyperexcitability prior to extensive cell loss. | Elevated intrinsic bias current $I_{bias} \times 1.15$ in descending motor pathways. | Clark et al., 2006 (*Nature*, DOI: `10.1038/nature04659`); Park et al., 2006 (*Nature*, DOI: `10.1038/nature04623`) | **1.1485** | **1.0476** |
| `parkin` | *parkin* null mutant (*park25*) | Defective ubiquitination, accumulation of substrate proteins in PPL1/PPM3 DA clusters, severe loss of gait coordination. | Selective attenuation of coordination interneuron synaptic weights $W_{\text{coord}} \times 0.48$. | Greene et al., 2003 (*PNAS*, DOI: `10.1073/pnas.0737556100`); Cha et al., 2005 (*JBC*) | **0.9851** | **0.4762** |
| `lrrk2` | *LRRK2* G2019S pathogenic gain-of-function | Elevated kinase activity, altered dopamine transporter (DAT) recycling, early hyper-reactivity with lateral instability. | Elevated baseline input $I_{bias}$ with asymmetric lateral synaptic decoupling. | Liu et al., 2008 (*J. Neurosci*, DOI: `10.1523/JNEUROSCI.3528-08.2008`); Imai et al., 2008 (*EMBO J*) | **1.1436** | **0.9048** |
| `dj1` | *DJ-1β* knockout | Increased susceptibility to oxidative stress (ROS), loss of tonic dopaminergic firing, general motor depression. | Generalized reduction in tonic bias drive $I_{bias}$ ($-4\%$) and moderate inter-leg coordination decoupling ($-28.6\%$). | Meulener et al., 2005 (*PNAS*, DOI: `10.1073/pnas.0505599102`); Menzies et al., 2005 (*Brain*) | **0.9604** | **0.7143** |
| `complexI` | Mitochondrial Complex I inhibition (Rotenone/MPTP mimic) | Electron transport chain failure, ATP depletion, aberrant burst firing followed by progressive failure. | Perturbed membrane integration thresholds and phase disruption across descending motor channels. | Coulom & Birman, 2004 (*J. Neurosci*, DOI: `10.1523/JNEUROSCI.3348-04.2004`); Poddighe et al., 2013 (*PLOS ONE*) | **1.1089** | **0.8571** |
| `pink1_age25` | *PINK1* null (25-day-old aged flies) | Age-dependent progressive degeneration of DA neurons (~40% loss in PPL1 cluster), classic Parkinsonian bradykinesia. | Structural ablation/silencing of 40% of dopaminergic projection neurons into the forward DN pathway. | Park et al., 2006 (*Nature*, DOI: `10.1038/nature04623`); Clark et al., 2006 (*Nature*) | **0.7826** | **0.5000** |
| `pink1_parkin_OE_age25` | Genetic Rescue (*pink1[B9]; UAS-parkin*, 25d) | Transgenic overexpression of Parkin downstream of PINK1 clears damaged mitochondria, suppresses DA apoptosis, and rescues locomotion. | Restoration of 85-90% of dopaminergic synaptic inputs in the descending motor pathway. | Yang et al., 2006 (*PNAS*, DOI: `10.1073/pnas.0602493103`); Park et al., 2006 (*Nature*) | **0.9565** | **0.8889** |

---

## 4. Verification & Reproducibility

Each model's bridge configuration is located at `data/bridge_scales/<model>_bridge_scales.json`.
Running the paired locomotion experiment evaluates the biomechanical outcome against the healthy unperturbed baseline:

```bash
python scripts/run_brain_driven_all.py \
  --baseline-config configs/experiments/healthy_baseline.yaml \
  --bridge-dir data/bridge_scales \
  --output-dir results/brain_driven
```
