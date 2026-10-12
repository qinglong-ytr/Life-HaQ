#!/usr/bin/env python3
"""Life-HaQ のアプリアイコンを作る（白い「Q」モノグラム＋赤のグラデーション）。
使い方: python3 scripts/make_icons.py [variant] [outdir]
"""
import sys, math, os
from PIL import Image, ImageDraw

TOP, BOT = (255, 92, 110), (222, 26, 58)   # 左上 → 右下

def gradient(S):
    g = Image.new('RGB', (S, S))
    px = g.load()
    for y in range(S):
        for x in range(S):
            t = (x + y) / (2 * (S - 1))
            px[x, y] = tuple(round(TOP[i] + (BOT[i] - TOP[i]) * t) for i in range(3))
    return g

def mark(d, S, variant, scale=1.0, color=(255, 255, 255)):
    cx, cy = S * 0.48, S * 0.47
    r = S * 0.215 * scale            # 輪の中心半径
    w = S * 0.085 * scale            # 線の太さ
    d.ellipse([cx - r - w/2, cy - r - w/2, cx + r + w/2, cy + r + w/2], fill=color)
    return cx, cy, r, w

def draw(S, variant, rounded, scale=1.0):
    base = gradient(S).convert('RGBA')
    lay = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    cx, cy, r, w = mark(d, S, variant, scale)
    # 輪の内側を抜く
    hole = Image.new('L', (S, S), 0)
    ImageDraw.Draw(hole).ellipse([cx - r + w/2, cy - r + w/2, cx + r - w/2, cy + r - w/2], fill=255)
    lay.putalpha(Image.eval(lay.getchannel('A'), lambda a: a) )
    a = lay.getchannel('A'); a.paste(0, mask=hole); lay.putalpha(a)
    d = ImageDraw.Draw(lay)
    ang = math.radians(45)
    if variant == 'tail':          # Q のしっぽ
        x0, y0 = cx + (r - w*0.2) * math.cos(ang), cy + (r - w*0.2) * math.sin(ang)
        L = S * 0.135 * scale
        x1, y1 = x0 + L * math.cos(ang), y0 + L * math.sin(ang)
        d.line([x0, y0, x1, y1], fill='white', width=round(w))
        for (x, y) in ((x0, y0), (x1, y1)):
            d.ellipse([x - w/2, y - w/2, x + w/2, y + w/2], fill='white')
    elif variant == 'dot':         # 輪＋右下のドット
        R = w * 0.78
        x, y = cx + (r + w * 1.55) * math.cos(ang), cy + (r + w * 1.55) * math.sin(ang)
        d.ellipse([x - R, y - R, x + R, y + R], fill='white')
    elif variant == 'arrow':       # 右上に伸びる矢印（成長）
        x0, y0 = cx, cy
        L = r + w * 1.9
        x1, y1 = cx + L * math.cos(-ang), cy + L * math.sin(-ang)
        d.line([x0, y0, x1, y1], fill='white', width=round(w))
        d.ellipse([x0 - w/2, y0 - w/2, x0 + w/2, y0 + w/2], fill='white')
        h = w * 1.9
        d.line([x1 - h, y1, x1, y1], fill='white', width=round(w)); d.line([x1, y1, x1, y1 + h], fill='white', width=round(w))
        for (x, y) in ((x1, y1), (x1 - h, y1), (x1, y1 + h)):
            d.ellipse([x - w/2, y - w/2, x + w/2, y + w/2], fill='white')
    out = Image.alpha_composite(base, lay)
    if rounded:
        m = Image.new('L', (S, S), 0)
        ImageDraw.Draw(m).rounded_rectangle([0, 0, S - 1, S - 1], radius=round(S * 0.225), fill=255)
        out.putalpha(m)
    return out

def render(size, variant, rounded, scale=1.0):
    big = draw(size * 4, variant, rounded, scale)
    return big.resize((size, size), Image.LANCZOS)

if __name__ == '__main__':
    variant = sys.argv[1] if len(sys.argv) > 1 else 'tail'
    out = sys.argv[2] if len(sys.argv) > 2 else 'icons'
    os.makedirs(out, exist_ok=True)
    render(180, variant, False).convert('RGB').save(f'{out}/app-180.png')          # iOS（角丸はiOSが付ける）
    render(192, variant, True).save(f'{out}/app-192.png')
    render(512, variant, True).save(f'{out}/app-512.png')
    render(512, variant, False, scale=0.82).convert('RGB').save(f'{out}/app-maskable-512.png')  # Android の切り抜き用に余白多め
    render(32, variant, True).save(f'{out}/app-32.png')
    print('ok', variant, out)
