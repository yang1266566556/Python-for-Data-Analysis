"""Targeted second pass: find eligible swatches whose 128x128 context is plausibly
open sky / distant haze (screened by low vertical position) and, separately, foliage
evidence regardless of the frame's own lighting label (auxiliary evidence only)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from analyze import srgb_to_lab, load_library, rank, ROOT, WORK  # noqa: E402

TARGETS = {
    'sky-blue-01': {'material': 'sky', 'lighting': 'neutral-day', 'max_y': 0.16},
    'sky-blue-02': {'material': 'sky', 'lighting': 'neutral-day', 'max_y': 0.16},
    'mountain-rock-01': {'material': 'stone', 'lighting': 'neutral-day', 'max_y': 0.28},
    'forest-01': {'material': 'foliage', 'lighting': None, 'max_y': 0.72},
    'forest-02': {'material': 'foliage', 'lighting': None, 'max_y': 0.72},
    'forest-03': {'material': 'foliage', 'lighting': None, 'max_y': 0.72},
}

analysis = json.loads((WORK / 'analysis.json').read_text(encoding='utf-8'))
by_id = {q['query_id']: q for q in analysis['queries']}
lib, entries = load_library()
crops = json.loads((ROOT / 'data' / 'palette-crops.json').read_text(encoding='utf-8'))
rows = {r['scene']: r for r in crops['frames']}

items = []
report = []
for qid, spec in TARGETS.items():
    anchor = by_id[qid]['source_anchor']
    res = rank(entries, anchor['rgb'], spec['material'],
               spec['lighting'] or 'neutral-day', anchor['tone'], (), top=400)
    pool = res['compatible_nearest'] if spec['lighting'] else res['raw_nearest']
    picked = []
    for c in pool:
        f = next(fr for fr in lib['frames'] if fr['scene'] == c['scene'])
        if spec['lighting'] is None and spec['material'] not in f['review']['materials']:
            continue
        y = c['xy'][1] / f['dimensions'][1]
        if y > spec['max_y']:
            continue
        picked.append((c, f, y))
        if len(picked) >= 6:
            break
    for c, f, y in picked:
        row = rows[c['scene']]
        patch = next(p for p in row['patches'] if p['swatch_id'] == c['swatch_id'])
        x, yy, w, h = patch['rect']
        tx, ty, tw, th = patch['tile']
        px, py = c['xy']
        items.append({
            'query_id': qid, 'role': 'targeted', 'rank': len([1 for i in items if i['query_id'] == qid]) + 1,
            'material': spec['material'], 'anchor_hex': anchor['hex'], 'anchor_lab': anchor['lab'],
            'anchor_tone': anchor['tone'], 'scene': c['scene'],
            'scene_lighting': f['review']['lighting'], 'scene_type': f['review']['scene_type'],
            'scene_materials': f['review']['materials'], 'scene_observation': f['review']['observation'],
            'swatch_id': c['swatch_id'], 'candidate_hex': c['hex'], 'candidate_lab': c['lab'],
            'delta_e_2000': round(c['delta_e_2000'], 4),
            'eligible': (not c['rejected_for']) and (f['review']['lighting'] == 'neutral-day'),
            'rejected_for': c['rejected_for'], 'frame_dimensions': f['dimensions'],
            'vertical_position': round(y, 3), 'atlas': str(ROOT / row['asset']), 'tile': patch['tile'],
            'sample_in_tile': [tx + px - x, ty + py - yy],
            'label': f"{qid} {c['swatch_id']} dE={c['delta_e_2000']:.1f} y={y:.2f} {f['review']['lighting']}"
        })
        report.append(f"{qid}: {c['scene']:03d}-{c['swatch_id'][-3:]} dE={c['delta_e_2000']:.2f} "
                      f"y={y:.2f} lighting={f['review']['lighting']} eligible={not c['rejected_for']}")

(WORK / 'targeted_set.json').write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding='utf-8')
print('\n'.join(report))
print('tiles:', len(items))
