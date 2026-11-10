#!/usr/bin/env python3
"""Bundle the same reviewed public explanations for first-launch offline reading."""
import json
from pathlib import Path
root=Path(__file__).resolve().parent.parent
briefs=json.loads((root/'content/technologies.json').read_text())
seed=root/'ios/ResearchRadar/Resources/ReadingShelf.json'
raw=json.loads(seed.read_text());raw['technology_briefs']=briefs
seed.write_text(json.dumps(raw,ensure_ascii=False,indent=2)+'\n')
print('Bundled',len(briefs),'public technology explanations; personal data not read.')
