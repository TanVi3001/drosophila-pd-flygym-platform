import json
import ast
import sys

nb = json.load(open("notebooks/colab/11_Bridge_Scales_Generation.ipynb", encoding="utf-8"))
ok = True
for i, cell in enumerate(nb["cells"]):
    if cell["cell_type"] != "code":
        continue
    src = "".join(cell["source"])
    # skip shell magics lines
    cleaned = "\n".join(
        (line.replace("!" + line.lstrip()[1:], "pass", 1)
         .replace("%" + line.lstrip()[1:], "pass", 1)
         if line.lstrip().startswith(("!", "%")) else line)
        for line in src.splitlines()
    )
    try:
        ast.parse(cleaned)
        print(f"cell {i}: syntax OK")
    except SyntaxError as exc:
        ok = False
        print(f"cell {i}: SYNTAX ERROR line {exc.lineno}: {exc.msg}")
        print("   ", (exc.text or "").rstrip())
sys.exit(0 if ok else 1)
