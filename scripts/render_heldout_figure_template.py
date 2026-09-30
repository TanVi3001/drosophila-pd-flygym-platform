#!/usr/bin/env python
"""Render a placeholder SVG without accepting or reading held-out outcomes."""

from __future__ import annotations

import argparse
from pathlib import Path


SVG = '''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="700" viewBox="0 0 1200 700">
<rect width="1200" height="700" fill="white"/>
<text x="600" y="70" text-anchor="middle" font-family="Arial" font-size="30" font-weight="bold">Held-out ranking evaluation</text>
<text x="600" y="120" text-anchor="middle" font-family="Arial" font-size="20" fill="#9b1c1c">PENDING ONE-TIME HELD-OUT EXECUTION</text>
<rect x="130" y="190" width="940" height="390" fill="#f7f8fa" stroke="#7b8794" stroke-width="2" stroke-dasharray="10 8"/>
<text x="600" y="350" text-anchor="middle" font-family="Arial" font-size="26" fill="#52606d">No held-out values loaded or displayed</text>
<text x="600" y="395" text-anchor="middle" font-family="Arial" font-size="18" fill="#52606d">Populate only from the approved, checksum-frozen execution record.</text>
<text x="600" y="645" text-anchor="middle" font-family="Arial" font-size="16" fill="#52606d">Protocol: shiu_v2_final_evaluation_v1 · k = 5 (locked)</text>
</svg>\n'''


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(SVG, encoding="utf-8")
    print(f"PENDING_TEMPLATE_ONLY: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
