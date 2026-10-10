#!/usr/bin/env python3
"""Life-HaQ: articles.json（毎日追加される記事）の形式チェック。

使い方:
  python3 scripts/validate_articles.py            # チェックのみ（問題があれば終了コード1）
  python3 scripts/validate_articles.py --list     # 既存の記事タイトルをカテゴリ別に表示（重複を避けるため）
"""
import json, re, sys, datetime, collections

INDEX, ARTICLES = 'index.html', 'articles.json'
html = open(INDEX, encoding='utf-8').read()
CATS = re.findall(r"\{k:'([^']+)',i:'", html)
BUILTIN = re.findall(r"\{id:'([a-z0-9-]+)',c:'([^']+)',t:'([^']+)'", html)
ID_RE = re.compile(r'^[a-z0-9-]{3,60}$')
DATE_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')


def norm(t):
    return re.sub(r'[\s「」『』【】（）()・、。!！?？:：\-—]', '', t)


def load():
    with open(ARTICLES, encoding='utf-8') as f:
        return json.load(f)


def list_titles():
    data = load()
    by = collections.defaultdict(list)
    for _id, c, t in BUILTIN:
        by[c].append(t)
    for a in data.get('articles', []):
        by[a.get('c', '?')].append(f"{a.get('t')}（{a.get('d')}追加）")
    for c in CATS:
        print(f'■ {c}（{len(by[c])}本）')
        for t in by[c]:
            print('  -', t)
    print('カテゴリ一覧:', ' / '.join(CATS))


def check():
    errs = []
    try:
        data = load()
    except Exception as e:
        print('articles.json を JSON として読めません:', e)
        return 1
    arts = data.get('articles')
    if not isinstance(arts, list):
        print('"articles" が配列ではありません'); return 1
    ids = {i for i, _, _ in BUILTIN}
    titles = {norm(t) for _, _, t in BUILTIN}
    today = datetime.date.today()

    def s(v, lo, hi, where):
        if not isinstance(v, str) or not (lo <= len(v.strip()) <= hi):
            errs.append(f'{where}: {lo}〜{hi}文字の文字列にしてください（今: {v!r:.60}）')
        elif '<' in v or '>' in v:
            errs.append(f'{where}: < や > は使えません')

    for n, a in enumerate(arts):
        w = f"記事{n + 1}（{a.get('id', '?') if isinstance(a, dict) else '?'}）"
        if not isinstance(a, dict):
            errs.append(f'{w}: オブジェクトではありません'); continue
        if not ID_RE.match(a.get('id', '')):
            errs.append(f'{w}: id は英小文字・数字・ハイフンで3〜60文字')
        elif a['id'] in ids:
            errs.append(f'{w}: id が既存の記事と重複しています')
        ids.add(a.get('id'))
        if a.get('c') not in CATS:
            errs.append(f'{w}: c は次のいずれか: {" / ".join(CATS)}')
        d = a.get('d', '')
        if not DATE_RE.match(d):
            errs.append(f'{w}: d は YYYY-MM-DD')
        else:
            try:
                if datetime.date.fromisoformat(d) > today + datetime.timedelta(days=1):
                    errs.append(f'{w}: d が未来の日付です')
            except ValueError:
                errs.append(f'{w}: d が正しい日付ではありません')
        s(a.get('t'), 6, 40, f'{w} t（タイトル）')
        if isinstance(a.get('t'), str):
            k = norm(a['t'])
            if k in titles:
                errs.append(f'{w}: 同じタイトルの記事がすでにあります')
            titles.add(k)
        s(a.get('s'), 8, 60, f'{w} s（要約）')
        sm = a.get('sum')
        if not isinstance(sm, list) or not (2 <= len(sm) <= 4):
            errs.append(f'{w}: sum は2〜4個の配列')
        else:
            for i, x in enumerate(sm):
                s(x, 8, 80, f'{w} sum[{i}]')
        sec = a.get('sec')
        if not isinstance(sec, list) or not (2 <= len(sec) <= 5):
            errs.append(f'{w}: sec は2〜5個の [見出し, [箇条書き...]]')
        else:
            for i, q in enumerate(sec):
                if not (isinstance(q, list) and len(q) == 2 and isinstance(q[1], list) and 2 <= len(q[1]) <= 6):
                    errs.append(f'{w} sec[{i}]: [見出し, [2〜6個の箇条書き]] の形にしてください'); continue
                s(q[0], 2, 24, f'{w} sec[{i}] 見出し')
                for j, x in enumerate(q[1]):
                    s(x, 8, 140, f'{w} sec[{i}][{j}]')
        for f in ('tip', 'warn'):
            if a.get(f):
                s(a[f], 8, 140, f'{w} {f}')
        kw = a.get('kw')
        if not isinstance(kw, list) or not (3 <= len(kw) <= 15) or not all(isinstance(x, str) and 1 <= len(x) <= 20 for x in kw):
            errs.append(f'{w}: kw は3〜15個の短い文字列（ひらがな・略語・言い換えも入れる）')
        src = a.get('src')
        if not isinstance(src, list) or not (1 <= len(src) <= 4):
            errs.append(f'{w}: src は1〜4個の [出典名, https://...]')
        else:
            for i, q in enumerate(src):
                if not (isinstance(q, list) and len(q) == 2 and isinstance(q[0], str) and isinstance(q[1], str) and q[1].startswith('https://')):
                    errs.append(f'{w} src[{i}]: [出典名, https://...] の形にしてください')
        extra = set(a) - {'id', 'c', 'd', 't', 's', 'sum', 'sec', 'tip', 'warn', 'kw', 'src'}
        if extra:
            errs.append(f'{w}: 不明な項目 {sorted(extra)}')
    if errs:
        print(f'問題が {len(errs)} 件あります:')
        for e in errs:
            print(' -', e)
        return 1
    print(f'OK: 追加記事 {len(arts)} 本（既存 {len(BUILTIN)} 本）')
    return 0


if __name__ == '__main__':
    if '--list' in sys.argv:
        list_titles(); sys.exit(0)
    sys.exit(check())
