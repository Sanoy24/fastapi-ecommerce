import os
import glob

for file_path in glob.glob("app/models/*.py"):
    if os.path.basename(file_path) == "__init__.py":
        continue
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    if "from __future__ import annotations" not in content:
        content = "from __future__ import annotations\n" + content
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Added __future__ to {file_path}")
