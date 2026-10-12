"""_build_plos017_script.py — generates scripts/_write_plos017_review.py"""
import json, re
from pathlib import Path

URL  = "https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0177710"
SHA  = "0F5706612DBC9F4D5504A330791C40662DD36CAC7C78F5208A2FB49AB03005FD"
SNAP = "../protocol_evidence_eval_draft_20261011_v2/source_snapshots/PLOS017.html"
RA   = "2026-10-12T12:55:00+07:00"
RV   = "reviewer_01"

C_PUB = (
    "Flies were reared in a light-dark controlled incubator on a 12h:12h light:dark cycle, "
    "kept at 25\u00b0C and 70% humidity on a standard cornmeal/molasses/yeast/agar medium. "
    "Experiments were carried out on flies of w 1118 Berlin ( w B) genetic background from "
    "the Heberlein Lab at UCSF, except for the experiments with the D \u03b1 7 mutant. "
    "The D \u03b1 7 deletion line, P \u0394 EY6 (EY6), and its precise excision control "
    "line, P \u0394 EY5 (EY5), were a gift from Amir Fayyazuddin "
    "(Dart Neuroscience, San Diego, CA, USA), who characterized these lines [ 29 ]. "
    "These lines are of a mixed background onto which the wild-type yellow and white genes "
    "were reintroduced. "
    "Nicotine and ethanol sensitivity assays used 17\u201322 males aged 2\u20134 days after eclosion. "
    "Flies used on behavioral assays were subjected to brief (<5min) CO 2 anesthesia during "
    "collection two days before the behavioral assay."
)
C_DRAFT = (
    "Flies were reared in a light-dark controlled incubator on a 12h:12h light:dark cycle, "
    "kept at 25\u00b0C and 70% humidity on a standard cornmeal/molasses/yeast/agar medium. "
    "Experiments were carried out on flies of w^{1118}Berlin (wB) genetic background from "
    "the Heberlein Lab at UCSF, except for the experiments with the D\u03b17 mutant. "
    "The D\u03b17 deletion line, P\u0394EY6 (EY6), and its precise excision control line, "
    "P\u0394EY5 (EY5), were a gift from Amir Fayyazuddin "
    "(Dart Neuroscience, San Diego, CA, USA), who characterized these lines. "
    "These lines are of a mixed background onto which the wild-type yellow and white genes "
    "were reintroduced. "
    "Nicotine and ethanol sensitivity assays used 17\u201322 males aged 2\u20134 days after eclosion. "
    "Flies used on behavioral assays were subjected to brief (<5min) CO2 anesthesia during "
    "collection two days before the behavioral assay."
)
