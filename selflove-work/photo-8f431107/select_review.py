"""Expand the pixel-review set: top-N eligible candidates for the key colour roles."""
import json
from pathlib import Path

WORK = Path(r"D:\Python for Data Analysis\selflove-work\photo-8f431107")
ROOT = Path(r"C:\Users\yang\.codex\skills\self-love")

ROLES = [
    ('sky-blue-01', 'sky highlight / cloud white'),
    ('sky-blue-02', 'sky mid blue'),
    ('mountain-rock-01', 'distant rock, cool midtone'),
    ('mountain-rock-03', 'distant rock/haze, light'),
    ('forest-01', 'foliage dark (no eligible match)'),
    ('stone-wall-02', 'stone masonry midtone'),
    ('stone-wall-04', 'stone masonry light'),
    ('wood-plank-01', 'wood plank light'),
    ('paving-03', 'sunlit paving, warm light'),
    ('man-hair-01', 'hair dark volume'),
    ('woman-hair-03', 'hair sunlit light'),
    ('man-skin-02', 'skin midtone (male)'),
    ('woman-skin-01', 'skin light (female)'),
    ('man-hand-01', 'skin highlight (hand)'),
    ('man-black-02', 'deepest dark anchor (black knit)'),
    ('man-jacket-02', 'steel-blue coated fabric'),
    ('woman-jacket-01', 'lavender-blue fabric midtone'),
    ('man-lens-01', 'dark mirrored lens'),
]

analysis = json.loads((WORK / 'analysis.json').read_text(encoding='utf-8'))
crops = json.loads((ROOT / 'data' / 'palette-crops.json').read_text(encoding='utf-8'))
rows = {r['scene']: r for r in crops['frames']}
library = json.loads((ROOT / 'data' / 'film-library.json').read_text(encoding='utf-8'))
frames = {f['scene']: f for f in library['frames']}
by_id = {q['query_id']: q for q in analysis['queries']}

items = []
report = []
for qid, role in ROLES:
    q = by_id[qid]
    anchor = q['source_anchor']
    pool = q['comparison']['compatible_nearest'] or q['comparison']['raw_nearest']
    take = pool[:5]
    for rank, c in enumerate(take, 1):
        row = rows[c['scene']]
        patch = next(p for p in row['patches'] if p['swatch_id'] == c['swatch_id'])
        x, y, w, h = patch['rect']
        tx, ty, tw, th = patch['tile']
        px, py = c['xy']
        f = frames[c['scene']]
        items.append({
            'query_id': qid, 'role': role, 'rank': rank, 'material': q['region']['material'],
            'anchor_hex': anchor['hex'], 'anchor_lab': anchor['lab'], 'anchor_tone': anchor['tone'],
            'scene': c['scene'], 'scene_lighting': f['review']['lighting'],
            'scene_type': f['review']['scene_type'], 'scene_materials': f['review']['materials'],
            'scene_observation': f['review']['observation'],
            'swatch_id': c['swatch_id'], 'candidate_hex': c['hex'], 'candidate_lab': c['lab'],
            'delta_e_2000': round(c['delta_e_2000'], 4), 'eligible': not c['rejected_for'],
            'rejected_for': c['rejected_for'],
            'frame_dimensions': f['dimensions'], 'swatch_source_xy': c['xy'],
            'vertical_position': round(c['xy'][1] / f['dimensions'][1], 3),
            'atlas': str(ROOT / row['asset']),
            'tile': patch['tile'], 'sample_in_tile': [tx + px - x, ty + py - y],
            'label': f"{qid}#{rank} {c['swatch_id']} dE={c['delta_e_2000']:.2f} |{anchor['hex']}>{c['hex']}"
        })
    report.append({'query_id': qid, 'role': role, 'anchor_hex': anchor['hex'],
                   'anchor_lab': [round(v, 2) for v in anchor['lab']], 'tone': anchor['tone'],
                   'eligible_pool': q['comparison']['compatible_candidates'],
                   'candidates': [{'rank': i + 1, 'swatch_id': c['swatch_id'], 'scene': c['scene'],
                                   'hex': c['hex'], 'delta_e_2000': round(c['delta_e_2000'], 4),
                                   'eligible': not c['rejected_for']} for i, c in enumerate(take)]})

(WORK / 'review_set.json').write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding='utf-8')
(WORK / 'review_plan.json').write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding='utf-8')
print('tiles:', len(items))
for r in report:
    print(f"{r['query_id']:18s} {r['anchor_hex']} L*={r['anchor_lab'][0]:6.1f} pool={r['eligible_pool']:4d} "
          + ' '.join(f"{c['scene']:03d}-{c['swatch_id'][-3:]}({c['delta_e_2000']:.1f}{'' if c['eligible'] else '!'})"
                     for c in r['candidates']))
