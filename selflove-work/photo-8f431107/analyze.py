"""Equivalent re-implementation of the self-love colour-matching maths.

The declared entry point (scripts/match_photo_palette.py) needs numpy/scipy/
scikit-image/Pillow.  This sandbox has no network, so those wheels cannot be
installed.  Everything below re-implements exactly the same published formulas
used by scripts/film_color.py:

  * sRGB -> CIELAB D65 2deg            (skimage.color.rgb2lab equivalent)
  * CIEDE2000 with kL=kC=kH=1          (skimage.color.deltaE_ciede2000 equivalent)
  * MEDIANCUT 32-cluster palette, each centroid snapped to a real member pixel
  * rank(): distance to EVERY swatch first, then the eligibility filters
            (active frame, gates, frame material, frame lighting, swatch tone,
             |dL*| <= max_lightness_delta)

The sRGB->Lab implementation is cross-validated against the 22336 Lab values
that the skill itself stored in data/film-library.json (computed by skimage on
the author's machine).  Nothing here writes into the skill directory.
"""
import json
import math
import struct
from pathlib import Path

ROOT = Path(r"C:\Users\yang\.codex\skills\self-love")
WORK = Path(r"D:\Python for Data Analysis\selflove-work\photo-8f431107")
TONE_NAMES = ['deep-shadow', 'shadow', 'midtone', 'light', 'highlight']

# ---------------------------------------------------------------- sRGB -> Lab
_XYZ_FROM_RGB = ((0.4124564, 0.3575761, 0.1804375),
                 (0.2126729, 0.7151522, 0.0721750),
                 (0.0193339, 0.1191920, 0.9503041))
_D65 = (0.95047, 1.0, 1.08883)
_EPS = (6.0 / 29.0) ** 3
_KAPPA = (29.0 / 6.0) ** 2 / 3.0
_OFFSET = 4.0 / 29.0


def _lin(v):
    v = v / 255.0
    return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4


def _f(t):
    return t ** (1.0 / 3.0) if t > _EPS else _KAPPA * t + _OFFSET


def srgb_to_lab(rgb):
    r, g, b = (_lin(c) for c in rgb)
    x = _XYZ_FROM_RGB[0][0] * r + _XYZ_FROM_RGB[0][1] * g + _XYZ_FROM_RGB[0][2] * b
    y = _XYZ_FROM_RGB[1][0] * r + _XYZ_FROM_RGB[1][1] * g + _XYZ_FROM_RGB[1][2] * b
    z = _XYZ_FROM_RGB[2][0] * r + _XYZ_FROM_RGB[2][1] * g + _XYZ_FROM_RGB[2][2] * b
    fx, fy, fz = _f(x / _D65[0]), _f(y / _D65[1]), _f(z / _D65[2])
    return [116.0 * fy - 16.0, 500.0 * (fx - fy), 200.0 * (fy - fz)]


# ---------------------------------------------------------------- CIEDE2000
def ciede2000(lab1, lab2, kL=1.0, kC=1.0, kH=1.0):
    L1, a1, b1 = lab1
    L2, a2, b2 = lab2
    C1 = math.hypot(a1, b1)
    C2 = math.hypot(a2, b2)
    Cbar = 0.5 * (C1 + C2)
    Cbar7 = Cbar ** 7
    G = 0.5 * (1.0 - math.sqrt(Cbar7 / (Cbar7 + 25.0 ** 7)))
    a1p, a2p = (1.0 + G) * a1, (1.0 + G) * a2
    C1p, C2p = math.hypot(a1p, b1), math.hypot(a2p, b2)
    h1p = math.degrees(math.atan2(b1, a1p)) % 360.0 if (a1p or b1) else 0.0
    h2p = math.degrees(math.atan2(b2, a2p)) % 360.0 if (a2p or b2) else 0.0
    dLp = L2 - L1
    dCp = C2p - C1p
    if C1p * C2p == 0.0:
        dhp = 0.0
    elif abs(h2p - h1p) <= 180.0:
        dhp = h2p - h1p
    elif h2p - h1p > 180.0:
        dhp = h2p - h1p - 360.0
    else:
        dhp = h2p - h1p + 360.0
    dHp = 2.0 * math.sqrt(C1p * C2p) * math.sin(math.radians(dhp / 2.0))
    Lbp = 0.5 * (L1 + L2)
    Cbp = 0.5 * (C1p + C2p)
    if C1p * C2p == 0.0:
        hbp = h1p + h2p
    elif abs(h1p - h2p) <= 180.0:
        hbp = 0.5 * (h1p + h2p)
    elif h1p + h2p < 360.0:
        hbp = 0.5 * (h1p + h2p + 360.0)
    else:
        hbp = 0.5 * (h1p + h2p - 360.0)
    T = (1.0 - 0.17 * math.cos(math.radians(hbp - 30.0))
         + 0.24 * math.cos(math.radians(2.0 * hbp))
         + 0.32 * math.cos(math.radians(3.0 * hbp + 6.0))
         - 0.20 * math.cos(math.radians(4.0 * hbp - 63.0)))
    dtheta = 30.0 * math.exp(-(((hbp - 275.0) / 25.0) ** 2))
    Cbp7 = Cbp ** 7
    Rc = 2.0 * math.sqrt(Cbp7 / (Cbp7 + 25.0 ** 7))
    Sl = 1.0 + (0.015 * (Lbp - 50.0) ** 2) / math.sqrt(20.0 + (Lbp - 50.0) ** 2)
    Sc = 1.0 + 0.045 * Cbp
    Sh = 1.0 + 0.015 * Cbp * T
    Rt = -math.sin(math.radians(2.0 * dtheta)) * Rc
    return math.sqrt((dLp / (kL * Sl)) ** 2 + (dCp / (kC * Sc)) ** 2
                     + (dHp / (kH * Sh)) ** 2
                     + Rt * (dCp / (kC * Sc)) * (dHp / (kH * Sh)))


# ---------------------------------------------------------------- 24bpp BMP
class Bmp:
    def __init__(self, path):
        data = Path(path).read_bytes()
        off = struct.unpack_from('<I', data, 10)[0]
        w, h = struct.unpack_from('<ii', data, 18)
        planes, bits = struct.unpack_from('<HH', data, 26)
        compression = struct.unpack_from('<I', data, 30)[0]
        if planes != 1 or bits != 24 or compression != 0:
            raise ValueError('Expected an uncompressed 24bpp BMP')
        self.w, self.h = w, abs(h)
        self.flip = h > 0
        self.stride = ((w * 3 + 3) // 4) * 4
        self.off = off
        self.data = data

    def get(self, x, y):
        row = (self.h - 1 - y) if self.flip else y
        i = self.off + row * self.stride + x * 3
        return (self.data[i + 2], self.data[i + 1], self.data[i])


def sample(bmp, rect, exclusions=(), step=2):
    l, t, r, b = rect
    x0, x1 = int(l * bmp.w), int(r * bmp.w)
    y0, y1 = int(t * bmp.h), int(b * bmp.h)
    px = []
    for y in range(y0, y1, step):
        for x in range(x0, x1, step):
            if any(ex[0] * bmp.w <= x < ex[2] * bmp.w and ex[1] * bmp.h <= y < ex[3] * bmp.h
                   for ex in exclusions):
                continue
            px.append(((x, y), bmp.get(x, y)))
    if len(px) < 16:
        raise ValueError('Insufficient sampled pixels')
    return px


# ------------------------------------------------- median cut (PIL-equivalent)
def median_cut(pixels, colors):
    """pixels: list of ((x,y),(r,g,b)).  Returns list of member index groups."""
    boxes = [list(range(len(pixels)))]
    while len(boxes) < colors:
        target, spread, channel = -1, -1, 0
        for i, box in enumerate(boxes):
            if len(box) < 2:
                continue
            for ch in range(3):
                vals = [pixels[j][1][ch] for j in box]
                rng = max(vals) - min(vals)
                if rng > spread:
                    target, spread, channel = i, rng, ch
        if target < 0 or spread <= 0:
            break
        box = boxes.pop(target)
        box.sort(key=lambda j: pixels[j][1][channel])
        mid = len(box) // 2
        boxes.append(box[:mid])
        boxes.append(box[mid:])
    return [b for b in boxes if b]


def palette(pixels, colors=32):
    groups = median_cut(pixels, colors)
    swatches = []
    for box in groups:
        labs = [srgb_to_lab(pixels[j][1]) for j in box]
        mean = [sum(c[k] for c in labs) / len(labs) for k in range(3)]
        chosen = min(range(len(box)),
                     key=lambda i: sum((labs[i][k] - mean[k]) ** 2 for k in range(3)))
        j = box[chosen]
        rgb = list(pixels[j][1])
        lab = labs[chosen]
        swatches.append({'rgb': rgb, 'hex': '#' + ''.join(f'{v:02X}' for v in rgb),
                         'lab': [round(v, 6) for v in lab],
                         'xy': list(pixels[j][0]), 'count': len(box),
                         'share': round(len(box) / len(pixels), 8),
                         'tone': TONE_NAMES[min(4, int(lab[0] / 20))],
                         'material_binding': 'unverified-pixel; frame tags are not pixel segmentation'})
    swatches.sort(key=lambda s: (-s['count'], s['hex'], tuple(s['xy'])))
    return swatches


# ---------------------------------------------------------------- film rank
def load_library():
    lib = json.loads((ROOT / 'data' / 'film-library.json').read_text(encoding='utf-8'))
    entries = []
    for frame in lib['frames']:
        for swatch in frame['palette']:
            entries.append((frame, swatch))
    return lib, entries


def rank(entries, rgb, material, lighting, tone, enabled_gates=(), max_dl=12.0, top=24):
    query = srgb_to_lab(rgb)
    out = []
    rejections = {}
    compatible = 0
    for frame, swatch in entries:
        d = ciede2000(swatch['lab'], query)
        reasons = []
        if not frame['active']:
            reasons.append('archive')
        missing = set(frame['review']['gates']) - set(enabled_gates)
        if missing:
            reasons.append('gate:' + ','.join(sorted(missing)))
        if material not in frame['review']['materials']:
            reasons.append('frame-material')
        if lighting != frame['review']['lighting']:
            reasons.append('illumination')
        if swatch['tone'] != tone:
            reasons.append('tone-role')
        if abs(swatch['lab'][0] - query[0]) > max_dl:
            reasons.append('lightness-delta')
        for r in reasons:
            rejections[r] = rejections.get(r, 0) + 1
        if not reasons:
            compatible += 1
        out.append({'scene': frame['scene'], 'swatch_id': swatch['id'], 'hex': swatch['hex'],
                    'lab': swatch['lab'], 'xy': swatch['xy'], 'delta_e_2000': d,
                    'rejected_for': reasons, 'original': frame['original']})
    out.sort(key=lambda c: (c['delta_e_2000'], c['scene'], c['swatch_id']))
    return {'source_rgb': list(rgb), 'source_lab': query,
            'library_frames_examined': len({f['scene'] for f, _ in entries}),
            'swatches_compared': len(entries), 'compatible_candidates': compatible,
            'rejection_counts': rejections, 'raw_nearest': out[:top],
            'compatible_nearest': [c for c in out if not c['rejected_for']][:top],
            'status': 'candidates-need-pixel-review' if compatible else 'no-compatible-candidate'}


# ---------------------------------------------------------------- validation
def validate(entries):
    checks = []
    for rgb, expected in [((255, 255, 255), [100.0, 0.0, 0.0]),
                          ((255, 0, 0), [53.2408, 80.0925, 67.2032]),
                          ((0, 255, 0), [87.7347, -86.1827, 83.1793]),
                          ((0, 0, 255), [32.2970, 79.1875, -107.8602]),
                          ((128, 128, 128), [53.5850, 0.0, 0.0])]:
        got = srgb_to_lab(rgb)
        checks.append({'kind': 'srgb-to-lab-known-value', 'input': list(rgb),
                       'expected': expected, 'got': [round(v, 4) for v in got],
                       'max_abs_error': round(max(abs(a - b) for a, b in zip(got, expected)), 4)})
    worst = 0.0
    worst_id = None
    for frame, swatch in entries:
        got = srgb_to_lab(swatch['rgb'])
        err = max(abs(a - b) for a, b in zip(got, swatch['lab']))
        if err > worst:
            worst, worst_id = err, swatch['id']
    checks.append({'kind': 'cross-validation-against-skill-stored-labs',
                   'samples': len(entries), 'worst_max_abs_component_error': round(worst, 6),
                   'worst_swatch': worst_id,
                   'note': 'skill Lab values were produced by skimage rgb2lab on the author machine'})
    for lab1, lab2, expected in [([50.0, 2.6772, -79.7751], [50.0, 0.0, -82.7485], 2.0425),
                                 ([50.0, 3.1571, -77.2803], [50.0, 0.0, -82.7485], 2.8615),
                                 ([50.0, 2.8361, -74.0200], [50.0, 0.0, -82.7485], 3.4412)]:
        got = ciede2000(lab1, lab2)
        checks.append({'kind': 'ciede2000-sharma-reference-pair', 'lab1': lab1, 'lab2': lab2,
                       'expected': expected, 'got': round(got, 4),
                       'abs_error': round(abs(got - expected), 4)})
    checks.append({'kind': 'ciede2000-identity', 'value': ciede2000([50, 10, -20], [50, 10, -20])})
    checks.append({'kind': 'ciede2000-symmetry',
                   'forward': ciede2000([50, 10, -20], [60, -5, 30]),
                   'backward': ciede2000([60, -5, 30], [50, 10, -20])})
    return checks


def main():
    plan = json.loads((WORK / 'plan.json').read_text(encoding='utf-8'))
    bmp = Bmp(WORK / 'source-24bpp.bmp')
    lib, entries = load_library()
    result = {'schema_version': 1,
              'engine': 'equivalent pure-python re-implementation of scripts/film_color.py',
              'declared_script_status': 'not runnable: scikit-image/Pillow unavailable, no network in sandbox',
              'source': plan['source'], 'source_sha256': plan['source_sha256'],
              'raster_used': str(WORK / 'source-24bpp.bmp'),
              'raster_note': '24bpp BMP decode of the same JPEG by GDI+; +/-1 LSB vs libjpeg possible',
              'catalog_sha256': __import__('hashlib').sha256(
                  (ROOT / 'data' / 'film-library.json').read_bytes()).hexdigest(),
              'validation': validate(entries),
              'library_frames': len({f['scene'] for f, _ in entries}),
              'library_swatches': len(entries)}

    # whole-image L* distribution for the pre-generation lightness gate
    px = sample(bmp, (0.0, 0.0, 1.0, 1.0), step=8)
    labs = sorted(srgb_to_lab(p[1])[0] for p in px)
    n = len(labs)
    result['whole_image_L_percentiles'] = {
        f'P{q}': round(labs[min(n - 1, int(q / 100.0 * n))], 3) for q in (1, 5, 25, 50, 75, 95, 99)}

    queries = []
    for region in plan['regions']:
        pixels = sample(bmp, region['rect'], region.get('exclusions', []), step=2)
        anchors = palette(pixels, region.get('colors', 3))
        for i, anchor in enumerate(anchors, 1):
            qid = f"{region['id']}-{i:02d}"
            comp = rank(entries, anchor['rgb'], region['material'], region['lighting'],
                        anchor['tone'], region.get('enabled_gates', []), top=8)
            queries.append({'query_id': qid, 'region': region, 'sampled_pixels': len(pixels),
                            'source_anchor': anchor, 'comparison': comp, 'status': comp['status']})
            print(f"{qid:22s} {anchor['hex']} L*={anchor['lab'][0]:6.2f} {anchor['tone']:12s} "
                  f"px={len(pixels):6d} compatible={comp['compatible_candidates']:5d} "
                  f"best={comp['compatible_nearest'][0]['scene'] if comp['compatible_nearest'] else '-'}")
    result['queries'] = queries
    result['status'] = 'pending-pixel-review'
    (WORK / 'analysis.json').write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding='utf-8')
    print('\nvalidation:', json.dumps(result['validation'], ensure_ascii=False))
    print('whole-image L*:', result['whole_image_L_percentiles'])
    print('wrote', WORK / 'analysis.json')


if __name__ == '__main__':
    main()
