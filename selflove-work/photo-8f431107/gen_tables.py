import json
from pathlib import Path

WORK = Path(r"D:\Python for Data Analysis\selflove-work\photo-8f431107")
a = json.loads((WORK / 'analysis.json').read_text(encoding='utf-8'))
plan = json.loads((WORK / 'plan.json').read_text(encoding='utf-8'))
rects = {r['id']: r for r in plan['regions']}

lines = ['# 02 原照分区实测色卡（源证据）', '',
         f"- 原照：1702 × 1276 sRGB JPEG，`source_sha256 = {a['source_sha256']}`",
         f"- 采样：归一化矩形内步长 2（与 `match_photo_palette.py` 的 `sample(step=2)` 一致）",
         f"- 全图 L* 分位：{json.dumps(a['whole_image_L_percentiles'], ensure_ascii=False)}",
         f"- 色卡算法：32 簇 median-cut（此处每区 3–4 色），每个锚点取该簇内最接近簇 Lab 均值的**真实成员像素**",
         '',
         '| 区域 | 材料 | 矩形(w×h 面积占比) | 锚点 | HEX | L* | a* | b* | 原照 xy | 簇占比 | 明度角色 |',
         '| --- | --- | --- | --- | --- | ---: | ---: | ---: | --- | ---: | --- |']
for q in a['queries']:
    rid = q['region']['id']
    rect = rects[rid]['rect']
    share = (rect[2] - rect[0]) * (rect[3] - rect[1])
    s = q['source_anchor']
    lines.append(f"| {rid} | {q['region']['material']} | {rect[2]-rect[0]:.3f}×{rect[3]-rect[1]:.3f} = {share*100:.2f}% | "
                 f"{q['query_id']} | `{s['hex']}` | {s['lab'][0]:.2f} | {s['lab'][1]:.2f} | {s['lab'][2]:.2f} | "
                 f"{s['xy']} | {s['share']*100:.1f}% | {s['tone']} |")
lines += ['', '> 面积占比是**矩形采样面积**，不是语义面积；一个矩形内可混有相邻材质，已在 `plan.json` 的 `source_evidence` 中逐条记录。', '']
(WORK / '02-source-palette.md').write_text('\n'.join(lines), encoding='utf-8')

rej = {}
for q in a['queries']:
    for k, v in q['comparison']['rejection_counts'].items():
        rej[k] = rej.get(k, 0) + v
tot = sum(rej.values())
lines = ['# 03 全库 22,336 色 CIEDE2000 比较（数值证据）', '',
         f"- 比较对象：`data/film-library.json`，698 帧 × 32 色 = **22,336** 个实测色卡",
         f"- 查询锚点数：{len(a['queries'])}；每次比较都对全部 22,336 色计算 CIEDE2000，再按资格过滤",
         f"- 资格过滤：帧 active、门禁为空、帧级材料包含区域材料、帧照明 == 区域照明、色卡明度角色相同、|ΔL*| ≤ 12",
         f"- 目录哈希：`{a['catalog_sha256']}`",
         '', '## 实现与校验', '']
for c in a['validation']:
    if c['kind'] == 'srgb-to-lab-known-value':
        lines.append(f"- sRGB→Lab 已知值 {c['input']}：期望 {c['expected']}，实得 {c['got']}，最大误差 {c['max_abs_error']}")
    elif c['kind'] == 'cross-validation-against-skill-stored-labs':
        lines.append(f"- **与本 skill 自存 Lab 交叉校验**：{c['samples']} 个色卡，最大分量误差 "
                     f"{c['worst_max_abs_component_error']}（最差 {c['worst_swatch']}）")
    elif c['kind'] == 'ciede2000-sharma-reference-pair':
        lines.append(f"- CIEDE2000 标准参考对 {c['lab1']} vs {c['lab2']}：期望 {c['expected']}，实得 {c['got']}，误差 {c['abs_error']}")
    elif c['kind'] == 'ciede2000-identity':
        lines.append(f"- CIEDE2000 同色自比：{c['value']}")
    elif c['kind'] == 'ciede2000-symmetry':
        lines.append(f"- CIEDE2000 对称性：{c['forward']:.9f} vs {c['backward']:.9f}")
lines += ['', '## 过滤原因统计（全部查询累计）', '', '| 原因 | 次数 |', '| --- | ---: |']
for k, v in sorted(rej.items(), key=lambda kv: -kv[1]):
    lines.append(f"| `{k}` | {v} |")
lines += ['', '## 逐区域可兼容候选数', '', '| 区域 | 区域锚点数 | 各锚点可兼容候选数 |', '| --- | ---: | --- |']
by_region = {}
for q in a['queries']:
    by_region.setdefault(q['region']['id'], []).append(q['comparison']['compatible_candidates'])
for rid, vals in by_region.items():
    lines.append(f"| {rid} | {len(vals)} | {', '.join(str(v) for v in vals)} |")
lines += ['', '> 「可兼容」只表示帧级标签与明度护栏通过，**不代表该色块像素属于该材质**；材质判定见 `04-pixel-review.md`。', '']
(WORK / '03-library-match.md').write_text('\n'.join(lines), encoding='utf-8')
print('wrote 02-source-palette.md and 03-library-match.md')
