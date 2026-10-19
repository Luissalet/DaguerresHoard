"""Explicit source build step for the cold owner catalogue, no engine or data."""
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from daguerre_hoard.studio import catalog
data=catalog()
(ROOT/'daguerre_hoard'/'studio-catalog.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print({group:len(tools) for group,tools in data.items()})
