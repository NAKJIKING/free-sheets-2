"""CPDL(Choral Public Domain Library) 수집기 — free-sheets-2 (2권).

CPDL은 재배포 조건이 문서에 명시된 소스다. 곡마다 위키 문서에
`{{Copy|...}}` 로 라이선스가 적혀 있고(CPDL 라이선스 / CC / 퍼블릭
도메인), 대부분 자원봉사자가 새로 조판해 판면권도 걸리지 않는다 —
신뢰 등급이 Mutopia 급이다.

다만 CPDL에는 생존 작곡가가 자기 곡을 CPDL 라이선스로 올린 것도
많다. 그 자체는 합법이지만 우리 기준("확실한 것만")에 맞추기 위해
**작곡가가 PD 명단(pd_match.py)에 있는 곡만** 받는다. 라이선스도
재배포가 명시된 것만 통과시킨다 — 두 조건을 모두 만족해야 한다.

동작
 1. MediaWiki API 로 본문 문서 목록을 훑는다(allpages, ns=0).
 2. 50개씩 묶어 위키텍스트를 받아 작곡가·라이선스·PDF 파일명을 뽑는다.
 3. 통과한 곡의 PDF를 내려받아 썸네일(WebP)을 만들고 catalog2.json 에
    source='cpdl' 로 붙인다. 병합 워크플로가 본 카탈로그로 합친다.

DISCOVER=1 로 돌리면 아무것도 내려받지 않고 API 응답과 위키텍스트
표본만 찍는다 — 파서를 실제 문서 구조에 맞출 때 쓴다.

전제: poppler-utils(pdftoppm), webp(cwebp).
"""
import json
import os
import re
import subprocess
import time
import urllib.parse
import urllib.request

from pd_match import is_pd_composer

ROOT = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(ROOT, 'raw', 'cpdl')
THUMBS = os.path.join(ROOT, 'thumbs', 'cpdl')
CATALOG = os.path.join(ROOT, 'catalog2.json')
API = 'https://www.cpdl.org/wiki/api.php'
SITE = 'https://www.cpdl.org'
BASE_URL = 'https://raw.githubusercontent.com/NAKJIKING/free-sheets-2/main'
UA = {'User-Agent': 'MySheetMusic-FreeLibrary/1.0 (public-domain collector)'}

DISCOVER = os.environ.get('DISCOVER', '') == '1'
NEW_ADD = int(os.environ.get('NEW_ADD', '4500'))
DEADLINE = time.time() + int(os.environ.get('MAX_MINUTES', '300')) * 60

# 재배포가 명시된 라이선스만. CPDL 라이선스는 GPL 계열 카피레프트라
# 고지를 보존하면 재배포할 수 있다.
OK_LICENSE = re.compile(
    r'(?i)(cpdl|creative\s*commons|public\s*domain|CC[\s-]?BY)')
# 반대로 이것들은 재배포 조건이 아니다 — 명시적으로 막는다.
NO_LICENSE = re.compile(
    r'(?i)(personal\s*use|non[\s-]?commercial\s*only|all\s*rights\s*reserved|'
    r'permission\s*required|copyright\s*holder)')


def api(**params):
    params.setdefault('format', 'json')
    params.setdefault('formatversion', '2')
    url = API + '?' + urllib.parse.urlencode(params)
    for i in range(4):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read().decode('utf-8', 'replace'))
        except Exception as e:
            print(f'  ! API 실패({i + 1}) {e}', flush=True)
            time.sleep(3 * (i + 1))
    return None


def fetch(url):
    for i in range(3):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=90) as r:
                return r.read()
        except Exception:
            time.sleep(3 * (i + 1))
    return None


def all_pages(limit=None):
    """본문 이름공간의 문서 제목을 모두 훑는다."""
    cont = {}
    out = []
    while True:
        d = api(action='query', list='allpages', apnamespace=0,
                aplimit='500', **cont)
        if not d:
            break
        out.extend(p['title'] for p in d.get('query', {}).get('allpages', []))
        if limit and len(out) >= limit:
            return out[:limit]
        if 'continue' not in d:
            break
        cont = d['continue']
        time.sleep(0.2)
    return out


def wikitext(titles):
    """제목 목록 → {제목: 위키텍스트} (50개씩 묶어 요청)."""
    out = {}
    for i in range(0, len(titles), 50):
        d = api(action='query', prop='revisions', rvprop='content',
                rvslots='main', titles='|'.join(titles[i:i + 50]))
        if not d:
            continue
        for p in d.get('query', {}).get('pages', []):
            revs = p.get('revisions') or []
            if revs:
                out[p['title']] = (revs[0].get('slots', {})
                                   .get('main', {}).get('content', '') or '')
        time.sleep(0.2)
    return out


def parse_page(title, text):
    """위키텍스트에서 (작곡가, 라이선스, PDF 파일명 목록)."""
    comp = ''
    m = re.search(r'\{\{\s*Composer\s*\|\s*([^}|]+)', text, re.I)
    if m:
        comp = m.group(1).strip()
    else:
        # 문서 제목이 "곡명 (작곡가)" 꼴인 경우가 많다
        m = re.search(r'\(([^)]+)\)\s*$', title)
        if m:
            comp = m.group(1).strip()

    lic = ''
    m = re.search(r'\{\{\s*Copy\s*\|\s*([^}|]+)', text, re.I)
    if m:
        lic = m.group(1).strip()

    pdfs = re.findall(r'\[\[\s*(?:Media|File|Image)\s*:\s*([^\]|]+?\.pdf)',
                      text, re.I)
    seen = set()
    uniq = []
    for p in pdfs:
        p = p.strip().replace('_', ' ')
        if p.lower() not in seen:
            seen.add(p.lower())
            uniq.append(p)
    return comp, lic, uniq


def file_urls(names):
    """파일 이름 목록 → {이름: 내려받기 URL}."""
    out = {}
    for i in range(0, len(names), 50):
        d = api(action='query', prop='imageinfo', iiprop='url',
                titles='|'.join('File:' + n for n in names[i:i + 50]))
        if not d:
            continue
        for p in d.get('query', {}).get('pages', []):
            ii = p.get('imageinfo') or []
            if ii and ii[0].get('url'):
                out[p['title'][5:]] = ii[0]['url']
        time.sleep(0.2)
    return out


def make_thumb(pdf_path, out_path):
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    tmp = out_path + '.tmp'
    try:
        subprocess.run(
            ['pdftoppm', '-f', '1', '-l', '1', '-scale-to', '480',
             '-singlefile', '-png', pdf_path, tmp],
            check=True, capture_output=True, timeout=60)
        subprocess.run(
            ['cwebp', '-quiet', '-q', '55', tmp + '.png', '-o', out_path],
            check=True, capture_output=True, timeout=60)
        return True
    except Exception:
        return False
    finally:
        if os.path.exists(tmp + '.png'):
            os.remove(tmp + '.png')


def discover():
    """파서를 실제 문서 구조에 맞추기 위한 표본 출력."""
    titles = all_pages(limit=60)
    print(f'문서 표본 {len(titles)}개', flush=True)
    print(titles[:20], flush=True)
    texts = wikitext(titles[:8])
    for t, x in texts.items():
        comp, lic, pdfs = parse_page(t, x)
        print('=' * 70, flush=True)
        print(f'제목: {t}', flush=True)
        print(f'파싱: 작곡가={comp!r} 라이선스={lic!r} PDF={pdfs}', flush=True)
        print('--- 위키텍스트 앞 1200자 ---', flush=True)
        print(x[:1200], flush=True)
    if texts:
        names = []
        for t, x in texts.items():
            names.extend(parse_page(t, x)[2])
        if names:
            print('파일 URL 조회 표본:', file_urls(names[:10]), flush=True)


def main():
    if DISCOVER:
        discover()
        return

    os.makedirs(RAW, exist_ok=True)
    catalog = []
    if os.path.exists(CATALOG):
        catalog = json.load(open(CATALOG, encoding='utf-8'))
    seen = {e.get('source_url') for e in catalog}

    print('== CPDL: 문서 목록', flush=True)
    titles = all_pages()
    print(f'본문 문서 {len(titles)}개', flush=True)

    added = 0
    stat = {'작곡가탈락': 0, '라이선스탈락': 0, 'PDF없음': 0, '내려받기실패': 0}
    for i in range(0, len(titles), 50):
        if added >= NEW_ADD or time.time() > DEADLINE:
            break
        batch = titles[i:i + 50]
        texts = wikitext(batch)
        # 통과 후보만 모아 파일 URL을 한 번에 조회한다
        cands = []
        for t in batch:
            x = texts.get(t)
            if not x:
                continue
            comp, lic, pdfs = parse_page(t, x)
            if not pdfs:
                stat['PDF없음'] += 1
                continue
            if not is_pd_composer(comp, ''):
                stat['작곡가탈락'] += 1
                continue
            if NO_LICENSE.search(lic) or not OK_LICENSE.search(lic):
                stat['라이선스탈락'] += 1
                continue
            src = f'{SITE}/wiki/index.php/{urllib.parse.quote(t.replace(" ", "_"))}'
            if src in seen:
                continue
            cands.append((t, comp, lic, pdfs[0], src))
        if not cands:
            continue
        urls = file_urls([c[3] for c in cands])
        for t, comp, lic, pdf, src in cands:
            if added >= NEW_ADD or time.time() > DEADLINE:
                break
            url = urls.get(pdf)
            if not url:
                stat['내려받기실패'] += 1
                continue
            data = fetch(url)
            if not data or not data.startswith(b'%PDF'):
                stat['내려받기실패'] += 1
                continue
            stem = re.sub(r'[^A-Za-z0-9._-]', '_', t)[:60]
            dest = os.path.join(RAW, stem + '.pdf')
            n = 1
            while os.path.exists(dest):
                dest = os.path.join(RAW, f'{stem}-{n}.pdf')
                n += 1
            with open(dest, 'wb') as f:
                f.write(data)
            rel = os.path.relpath(dest, ROOT)
            entry = {
                'source': 'cpdl',
                'base': BASE_URL,
                'source_url': src,
                'file': rel,
                'title': re.sub(r'\s*\([^)]*\)\s*$', '', t).strip() or t,
                'composer': comp,
                'instrument': 'Choir',
                'license': lic,
            }
            thumb_rel = ('thumbs/cpdl/'
                         + os.path.splitext(os.path.basename(dest))[0]
                         + '.webp')
            if make_thumb(dest, os.path.join(ROOT, thumb_rel)):
                entry['thumb'] = thumb_rel
            catalog.append(entry)
            seen.add(src)
            added += 1
            if added % 100 == 0:
                json.dump(catalog, open(CATALOG, 'w', encoding='utf-8'),
                          ensure_ascii=False, indent=1)
                print(f'  … {added}곡 (탈락 {stat})', flush=True)
            time.sleep(0.3)          # 서버 예의상 간격

    json.dump(catalog, open(CATALOG, 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print(f'CPDL 신규 {added}곡 · 탈락 {stat}', flush=True)
    print(f'2권 합계 {len(catalog)}곡', flush=True)


if __name__ == '__main__':
    main()
