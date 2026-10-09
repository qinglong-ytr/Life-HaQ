#!/usr/bin/env python3
"""Life-HaQ: 毎朝のニュースを集めて news.json を更新する（GitHub Actions から実行）。

ニュースサイトの RSS から、お金・暮らしに関係する見出しとリンクを集めます。
本文は転載せず、見出し・配信元・リンクと、カテゴリごとの「家計との関わり」の一言だけを載せます。
"""
import json, re, sys, datetime, urllib.request, urllib.parse, email.utils, html
import xml.etree.ElementTree as ET

JST = datetime.timezone(datetime.timedelta(hours=9))
NEWS = 'news.json'
KEEP_DAYS = 7
MAX_ITEMS = 6
UA = 'Mozilla/5.0 (Life-HaQ news updater; +https://github.com/qinglong-ytr/Life-HaQ)'

# (カテゴリ, Google ニュースの検索語)
QUERIES = [
    ('金利',     '日銀 OR 政策金利 OR 長期金利 OR 為替'),
    ('NISA',    'NISA OR iDeCo OR 新NISA'),
    ('税金',     '税制改正 OR ふるさと納税 OR 確定申告 OR 年末調整 OR 所得税'),
    ('不動産',   '住宅ローン金利 OR 家賃 OR マンション価格 OR 不動産価格'),
    ('キャリア', '賃上げ OR 実質賃金 OR 転職 OR 最低賃金 OR 求人倍率'),
    ('暮らし',   'マイナンバーカード OR 年金 OR 社会保険料 OR 物価 OR 値上げ'),
]
# Google ニュースが取れなかったときの予備（NHK 経済）
FALLBACK_FEEDS = [('https://www3.nhk.or.jp/rss/news/cat5.xml', 'NHK')]
FALLBACK_RULES = [
    ('金利', r'日銀|金利|為替|円安|円高'), ('NISA', r'NISA|ＮＩＳＡ|iDeCo|投資信託'),
    ('税金', r'税|ふるさと納税|確定申告'), ('不動産', r'住宅|家賃|マンション|不動産'),
    ('キャリア', r'賃金|賃上げ|雇用|転職|求人'), ('暮らし', r'年金|物価|値上げ|マイナ|保険料'),
]
# カテゴリごとの「家計との関わり」（日替わりで切り替え）
HINTS = {
    '金利': ['住宅ローンの変動金利や預金の金利に関わるニュースです。変動金利で借りている人は、次の金利見直しの時期を確認しておきましょう。',
             '金利や為替は、ローンの返済額や外国資産の評価額に影響します。1日の動きより数か月の流れで見るのがおすすめです。'],
    'NISA': ['NISA・iDeCoの制度や使い方に関わるニュースです。自分の枠や掛金の設定に影響がないか確認しておきましょう。',
             '制度の変更は施行日と対象者が大事です。手続きが必要かどうかは金融機関の案内でも確認できます。'],
    '税金': ['税金や控除に関わるニュースです。年末調整や確定申告で手取りが変わることがあるので、対象になるか確認しておきましょう。',
             '税制の変更は、決まってから実際に始まるまで時間があります。いつから・誰が対象かをチェックしておきましょう。'],
    '不動産': ['住まいのお金に関わるニュースです。家賃の更新や住宅購入・借り換えを考えている人は、相場の流れを押さえておきましょう。',
               '住宅ローンや家賃は家計の中で一番大きな固定費です。金利タイプごとの返済額の違いも試算しておくと安心です。'],
    'キャリア': ['働き方や収入に関わるニュースです。自分の職種・業界の相場と比べて、年収を見直すきっかけにしましょう。',
                 '賃金や求人の動きは転職のタイミングにも関わります。今の市場価値を知る材料にしましょう。'],
    '暮らし': ['毎日の暮らしと手続きに関わるニュースです。自分に必要な手続きや、家計への影響がないか確認しておきましょう。',
               '物価や社会保険料の変化は手取りに直結します。固定費の見直しとあわせてチェックしておきましょう。'],
}

def fetch(url):
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()

def parse_rss(xml_bytes):
    """RSS 2.0 の item を (title, link, source, published) で返す"""
    out = []
    root = ET.fromstring(xml_bytes)
    for it in root.iter('item'):
        title = (it.findtext('title') or '').strip()
        link = (it.findtext('link') or '').strip()
        src_el = it.find('source')
        src = (src_el.text or '').strip() if src_el is not None and src_el.text else ''
        if src and title.endswith(' - ' + src):
            title = title[: -len(' - ' + src)].strip()
        elif not src and ' - ' in title:
            title, src = title.rsplit(' - ', 1)
        pub = None
        try:
            pub = email.utils.parsedate_to_datetime(it.findtext('pubDate') or '')
            if pub and pub.tzinfo is None:
                pub = pub.replace(tzinfo=datetime.timezone.utc)
        except Exception:
            pub = None
        title = html.unescape(re.sub(r'\s+', ' ', title))
        if title and link.startswith('http'):
            out.append({'title': title, 'url': link, 'src': html.unescape(src), 'pub': pub})
    return out

def norm(t):
    return re.sub(r'[\s「」『』【】（）()・、。!！?？:：\-—]', '', t)[:40]

def google_news(q):
    url = 'https://news.google.com/rss/search?' + urllib.parse.urlencode(
        {'q': q + ' when:2d', 'hl': 'ja', 'gl': 'JP', 'ceid': 'JP:ja'})
    return parse_rss(fetch(url))

def collect(now, seen):
    picked, used = [], set(seen)
    cutoff = now - datetime.timedelta(days=2)
    def ok(x):
        k = norm(x['title'])
        return k and k not in used and (x['pub'] is None or x['pub'] >= cutoff)
    pools = {}
    for cat, q in QUERIES:
        try:
            items = google_news(q)
        except Exception as e:
            print(f'[warn] {cat}: {e}', file=sys.stderr); items = []
        items.sort(key=lambda x: x['pub'] or cutoff, reverse=True)
        pools[cat] = [x for x in items if ok(x)]
    if not any(pools.values()):
        for url, name in FALLBACK_FEEDS:
            try:
                for x in parse_rss(fetch(url)):
                    x['src'] = x['src'] or name
                    for cat, pat in FALLBACK_RULES:
                        if re.search(pat, x['title']) and ok(x):
                            pools.setdefault(cat, []).append(x); break
            except Exception as e:
                print(f'[warn] fallback {url}: {e}', file=sys.stderr)
    # 1周目は各カテゴリから1件ずつ、足りなければ2周目
    for rnd in range(2):
        for cat, _ in QUERIES:
            if len(picked) >= MAX_ITEMS: break
            pool = pools.get(cat) or []
            while pool:
                x = pool.pop(0)
                k = norm(x['title'])
                if k in used: continue
                used.add(k)
                hint = HINTS[cat][(now.toordinal() + rnd) % len(HINTS[cat])]
                picked.append({'cat': cat, 'title': x['title'], 'body': hint, 'src': x['src'] or 'ニュース', 'url': x['url']})
                break
    return picked

def main():
    now = datetime.datetime.now(JST)
    today = now.date().isoformat()
    try:
        data = json.load(open(NEWS, encoding='utf-8'))
    except Exception:
        data = {'days': []}
    days = [d for d in data.get('days', []) if d.get('date') != today]
    seen = {norm(i.get('title', '')) for d in days for i in d.get('items', [])}
    items = collect(now, seen)
    if len(items) < 2:
        print(f'集められたニュースが {len(items)} 件だけなので、更新しません。', file=sys.stderr)
        return 0
    days.insert(0, {'date': today, 'items': items})
    days.sort(key=lambda d: d['date'], reverse=True)
    out = {'updated': today, 'days': days[:KEEP_DAYS]}
    with open(NEWS, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
        f.write('\n')
    print(f'{today}: {len(items)} 件')
    for i in items: print(f"- [{i['cat']}] {i['title']} ({i['src']})")
    return 0

if __name__ == '__main__':
    sys.exit(main())
