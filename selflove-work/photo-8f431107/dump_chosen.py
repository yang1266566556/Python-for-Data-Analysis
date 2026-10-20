import json
from pathlib import Path

WORK = Path(r"D:\Python for Data Analysis\selflove-work\photo-8f431107")
items = {i['query_id'] + '#' + str(i['rank']): i
         for i in list(json.loads((WORK / 'review_set.json').read_text(encoding='utf-8')))
         + [{**t, 'rank': 0} for t in json.loads((WORK / 'targeted_set.json').read_text(encoding='utf-8'))]}

CHOSEN = {
    'sky-blue-01': [('390-S16', None)],
    'sky-blue-02': [('203-S19', None)],
    'stone-wall-02': [('200-S21', None)],
    'stone-wall-04': [('079-S28', None)],
    'paving-03': [('073-S30', None)],
    'man-hair-01': [('195-S14', None)],
    'man-skin-02': [('305-S28', None)],
    'woman-skin-01': [('305-S19', None)],
    'man-hand-01': [('071-S02', None)],
    'woman-jacket-01': [('079-S14', None)],
    'man-lens-01': [('310-S26', None)],
    'man-black-02': [('089-S31', None)],
}
out = []
for qid, picks in CHOSEN.items():
    want = picks[0][0]
    found = None
    for key, it in items.items():
        if it['query_id'] == qid and it['swatch_id'] == want:
            found = it
            break
    if not found:
        out.append(f"{qid}: {want} NOT IN REVIEWED SET")
        continue
    out.append(json.dumps({
        'query': qid, 'region': found.get('region', ''), 'material': found['material'],
        'source': {'hex': found['anchor_hex'], 'lab': [round(v, 3) for v in found['anchor_lab']],
                   'tone': found['anchor_tone']},
        'target': {'scene': found['scene'], 'swatch_id': found['swatch_id'], 'hex': found['candidate_hex'],
                   'lab': [round(v, 3) for v in found['candidate_lab']], 'xy': found.get('swatch_source_xy'),
                   'atlas_tile': found['tile'], 'sample_in_tile': found['sample_in_tile'],
                   'frame_dimensions': found['frame_dimensions'], 'vertical_position': found['vertical_position'],
                   'scene_type': found['scene_type'], 'scene_lighting': found['scene_lighting'],
                   'scene_materials': found['scene_materials']},
        'delta_e_2000': found['delta_e_2000']}, ensure_ascii=False))
(WORK / 'chosen.json').write_text('\n'.join(out), encoding='utf-8')
print('\n'.join(out))
