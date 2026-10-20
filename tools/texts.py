#!/usr/bin/env python3
"""Print only the id and text of each memo, so a second annotator can label without seeing the first labels."""

import json
import sys

with open(sys.argv[1], encoding="utf-8") as f:
    for line in filter(str.strip, f):
        record = json.loads(line)
        print(json.dumps({"id": record["id"], "text": record["text"]}, ensure_ascii=False))
