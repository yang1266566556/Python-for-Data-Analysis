"""Pick the nearest eligible candidate per query and emit tile-extraction jobs."""
import json
from pathlib import Path

WORK = Path(r"D:\Python for Data Analysis\selflove-work\photo-8f431107")
ROOT = Path(r"C:\Users\yang\.codex\skills\self-love")

analysis = json.loads((WORK / 'analysis.json').read_text(encoding='utf-8'))
crops = json.loads((ROOT / 'data' / 'palette-crops.json').read_text(encoding='utf-8'))
rows = {r['scene']: r for r in crops['frames']}
library = json.loads((ROOT / 'data' / 'film-library.json').read_text(encoding='utf-8'))
frames = {f['scene']: f for f in library['frames']}

items = []
summary = []
for q in analysis['queries']:
    anchor = q['source_anchor']
    cands = q['comparison']['compatible_nearest'] or q['comparison']['raw_nearest']
    if not cands:
        summary.append([q['query_id'], anchor['hex'], '-', 'NO-CANDIDATE'])
        continue
    c = cands[0]
    row = rows[c['scene']]
    patch = next(p for p in row['patches'] if p['swatch_id'] == c['swatch_id'])
    x, y, w, h = patch['rect']
    tx, ty, tw, th = patch['tile']
    px, py = c['xy']
    f = frames[c['scene']]
    items.append({
        'query_id': q['query_id'], 'region': q['region']['id'], 'material': q['region']['material'],
        'anchor_hex': anchor['hex'], 'anchor_lab': anchor['lab'], 'anchor_tone': anchor['tone'],
        'anchor_share': anchor['share'],
        'scene': c['scene'], 'scene_lighting': f['review']['lighting'],
        'scene_type': f['review']['scene_type'], 'scene_materials': f['review']['materials'],
        'scene_observation': f['review']['observation'],
        'swatch_id': c['swatch_id'], 'candidate_hex': c['hex'], 'candidate_lab': c['lab'],
        'delta_e_2000': round(c['delta_e_2000'], 4), 'eligible': not c['rejected_for'],
        'atlas': str(ROOT / row['asset']),
        'tile': patch['tile'], 'sample_in_tile': [tx + px - x, ty + py - y],
        'source_crop_rect': patch['rect'],
        'label': f"{q['query_id']} {c['swatch_id']} dE={c['delta_e_2000']:.2f} {anchor['hex']}->{c['hex']}"
    })
    summary.append([q['query_id'], anchor['hex'], f"{c['scene']:03d}-{c['swatch_id']}",
                    f"{c['delta_e_2000']:.3f}", c['hex'], q['comparison']['compatible_candidates'],
                    c['rejected_for']])

(WORK / 'tiles.json').write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding='utf-8')

print(f"{'query':22s} {'src':8s} {'target':16s} {'dE00':>7s} {'tgt hex':8s} {'ok#':>5s}")
for s in summary:
    print(f"{s[0]:22s} {s[1]:8s} {s[2]:16s} {s[3]:>7s} {str(s[4] if len(s)>4 else ''):8s} "
          f"{str(s[5] if len(s)>5 else ''):>5s} {'' if len(s)<7 else s[6]}")
print('\ndistinct scenes:', sorted({i['scene'] for i in items}))
print('tiles:', len(items), '-> wrote tiles.json')
