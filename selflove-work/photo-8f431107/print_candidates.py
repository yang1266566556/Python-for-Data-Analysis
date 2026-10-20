import json
from pathlib import Path

WORK = Path(r"D:\Python for Data Analysis\selflove-work\photo-8f431107")
items = json.loads((WORK / 'review_set.json').read_text(encoding='utf-8'))
lines = []
for it in items:
    obs = (it['scene_observation'] or '')[:24]
    lines.append(
        f"{it['query_id']:17s}#{it['rank']} {it['scene']:03d}-{it['swatch_id'][-3:]} "
        f"dE={it['delta_e_2000']:6.2f} L*={it['candidate_lab'][0]:5.1f} y={it['vertical_position']:.2f} "
        f"{it['scene_type']:9s} elig={'Y' if it['eligible'] else 'N'} | {obs}")
(WORK / 'candidate_table.txt').write_text('\n'.join(lines), encoding='utf-8')
print('\n'.join(lines))
