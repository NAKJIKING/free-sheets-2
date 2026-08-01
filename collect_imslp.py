"""IMSLP 선별 수확 — 확실한 퍼블릭 도메인 독주 악보 (스캔 PDF).

설계 (전용오선지·PDMX 라인과 같은 검증 철학):
 - 작품 목록: MediaWiki API(list=categorymembers)로 악기 카테고리
   ('For piano' 등)를 걷는다.
 - 저작권 이중 필터: ① 작품 제목의 작곡가가 화이트리스트(사후 70년+
   확실)에 있어야 하고 ② 파일 블록의 Copyright 필드가 Public Domain
   이어야 한다 (현대 판본 배제).
 - 예절: 파일 다운로드 2초 간격, API 호출 1초 간격, 파일당 8MB 상한.
 - 저장: PDF·썸네일은 깃 저장소가 아니라 **릴리스 자산**으로 올린다
   (_imslp_out/ 에 모아 두면 워크플로가 gh release upload).
   catalog2.json 항목의 base 가 릴리스 다운로드 URL을 가리키므로
   앱은 수정 없이 그대로 내려받는다. 미디는 없다(스캔 악보).
 - 중복 제거: 1·2권 카탈로그의 (정규화 제목, 작곡가 성) 키와 대조.

전제: poppler-utils(pdftoppm), webp(cwebp) 설치.
"""
import gzip
import json
import os
import re
import subprocess
import time
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, '_imslp_out')  # 릴리스 자산 업로드용 (깃 미포함)
# 릴리스 하나에 자산 1,000개 상한이 있다. 교본 수집 때 이 상한에
# 걸려 3천여 곡 중 1,000개만 올라갔고, 앱에서 대부분 미리보기·
# 다운로드가 안 돼 수리에만 하루가 걸렸다. 같은 실수를 반복하지
# 않도록 곡을 450개씩(자산 900개) 릴리스에 나눠 담는다.
SHARD = 450
CATALOG = os.path.join(ROOT, 'catalog2.json')
TAG_PREFIX = os.environ.get('IMSLP_TAG', 'imslp')
REL = 'https://github.com/NAKJIKING/free-sheets-2/releases/download'


def shard_of(n):
    """n번째 곡이 갈 (릴리스 태그, 자산 디렉터리)."""
    tag = f'{TAG_PREFIX}-{1 + n // SHARD}'
    return tag, os.path.join(OUT, tag)
VOL1 = ('https://raw.githubusercontent.com/NAKJIKING/'
        'free-sheets/main/catalog.json')
API = 'https://imslp.org/api.php'
UA = {'User-Agent': 'MySheetMusic-FreeLibrary/2.0 (public-domain collector; '
                    'contact hhs.79.dsn@gmail.com)'}
# IMSLP은 파일을 주기 전에 면책 동의 페이지를 한 번 거치게 한다.
# 동의 쿠키가 없으면 PDF 대신 그 HTML이 온다 — 후보를 995곡 찾고도
# 한 곡도 못 받은 원인이 이것으로 짐작된다.
DL_HEADERS = {**UA,
              'Accept-Encoding': 'identity',
              'Referer': 'https://imslp.org/',
              'Cookie': 'imslpdisclaimeraccepted=yes; imslp_wikiLanguageSelectorLanguage=en'}

TOTAL_LIMIT = int(os.environ.get('IMSLP_LIMIT', '5000'))
PER_COMPOSER = int(os.environ.get('IMSLP_PER_COMPOSER', '60'))
MAX_FILE = 8 * 1024 * 1024

# (카테고리, 악기 분류, 카테고리별 상한)
CATEGORIES = [
    ('For piano', 'Piano', 1200),
    ('For piano 4 hands', 'Piano', 200),
    ('For guitar', 'Guitar', 400),
    ('For violin, piano', 'Violin', 400),
    ('For violin', 'Violin', 200),
    ('For flute, piano', 'Flute', 300),
    ('For flute', 'Flute', 150),
    ('For cello, piano', 'Cello', 300),
    ('For clarinet, piano', 'Clarinet', 200),
    ('For trumpet, piano', 'Trumpet', 150),
    ('For organ', 'Organ', 300),
    ('For harpsichord', 'Harpsichord', 150),
    ('For viola, piano', 'Viola', 120),
    ('For oboe, piano', 'Oboe', 100),
    ('For bassoon, piano', 'Bassoon', 80),
    ('For horn, piano', 'Horn', 80),
    ('For saxophone, piano', 'Saxophone', 80),
    ('For harp', 'Harp', 120),
    ('For voice, piano', 'Voice', 400),
    ('For 2 violins, viola, cello', 'String quartet', 200),
]

# PD 판정은 pd_match.py 로 통일한다 — 수집기마다 명단이 따로
# 놀면 한쪽만 고쳤을 때 조용히 어긋난다.
from pd_match import is_pd_composer  # noqa: E402


def api_get(params, retries=3):
    qs = urllib.parse.urlencode({**params, 'format': 'json'})
    req = urllib.request.Request(f'{API}?{qs}', headers=UA)
    for i in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read().decode('utf-8'))
        except Exception as e:
            print(f'  ! api 재시도({i+1}): {e}', flush=True)
            time.sleep(3 * (i + 1))
    return None


def fetch_bytes(url, retries=2):
    # IMSLP는 Accept-Encoding 없이도 gzip으로 응답한다 — 평문을 요청하되
    # 그래도 gzip 매직이 오면 직접 푼다 (action=raw가 이 경우였다).
    req = urllib.request.Request(url, headers=DL_HEADERS)
    for i in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                data = r.read()
            if data[:2] == b'\x1f\x8b':
                data = gzip.decompress(data)
            return data
        except Exception as e:
            print(f'  ! 받기 재시도({i+1}): {e}', flush=True)
            time.sleep(3)
    return None


def norm(s):
    return re.sub(r'[^a-z0-9]+', ' ', (s or '').lower()).strip()


def existing_keys():
    """1·2권 카탈로그의 (제목, 작곡가 성) 정규화 키."""
    keys = set()
    for src in (VOL1, None):
        try:
            if src:
                data = json.loads(fetch_bytes(src).decode('utf-8'))
            else:
                if not os.path.exists(CATALOG):
                    continue
                data = json.load(open(CATALOG, encoding='utf-8'))
            for e in data:
                surname = (e.get('composer') or '').split(',')[0]
                keys.add((norm(e.get('title')), norm(surname)))
        except Exception as ex:
            print(f'기존 카탈로그 확인 실패: {ex}', flush=True)
    return keys


def walk_category(cat):
    """카테고리의 작품 페이지 제목들 (파일·하위분류 제외)."""
    cont = None
    while True:
        params = {
            'action': 'query', 'list': 'categorymembers',
            'cmtitle': f'Category:{cat}', 'cmlimit': '500',
            'cmnamespace': '0', 'cmtype': 'page',
        }
        if cont:
            params['cmcontinue'] = cont
        data = api_get(params)
        if not data:
            return
        for m in data.get('query', {}).get('categorymembers', []):
            yield m['title']
        cont = data.get('continue', {}).get('cmcontinue')
        if not cont:
            return
        time.sleep(1.0)


_debug_dumps = [3]  # 디버그 때 처음 몇 페이지의 구조를 로그로 남긴다


def page_wikitext(title):
    """작품 페이지 위키텍스트 — index.php는 봇 차단(캡차)이 걸리므로
    api.php(prop=revisions)로 받는다 (api.php는 차단되지 않음)."""
    data = api_get({
        'action': 'query', 'prop': 'revisions', 'rvprop': 'content',
        'rvslots': 'main', 'titles': title,
    })
    if not data:
        return ''
    for p in (data.get('query', {}).get('pages', {}) or {}).values():
        revs = p.get('revisions') or []
        if revs:
            slot = (revs[0].get('slots') or {}).get('main') or {}
            return slot.get('*') or revs[0].get('*') or ''
    return ''


def pick_pdf(work_title):
    """작품 페이지에서 Public Domain 표기가 있는 첫 PDF 파일명을 고른다."""
    text = page_wikitext(work_title)
    if not text:
        return None
    if os.environ.get('IMSLP_DEBUG') and _debug_dumps[0] > 0:
        _debug_dumps[0] -= 1
        blocks = text.lower().count('#fte:imslpfile')
        cps = re.findall(r'\|\s*Copyright[^=\n]*=\s*([^\n|}]+)', text)[:5]
        fns = re.findall(r'\|\s*File\s*Name[^=\n]*=\s*([^\n|}]+)', text)[:5]
        print(f'  [덤프] {work_title!r} 길이 {len(text)} '
              f'imslpfile블록 {blocks} Copyright {cps} File {fns}',
              flush=True)
        if blocks == 0:
            print('  [덤프 원문 앞부분] ' + text[:700].replace('\n', ' ⏎ '),
                  flush=True)
    for block in re.split(r'#fte:\s*imslpfile', text, flags=re.I)[1:]:
        cp = re.search(r'\|\s*Copyright[^=\n]*=\s*([^\n|}]+)', block)
        if not cp or 'public domain' not in cp.group(1).strip().lower():
            continue
        for m in re.finditer(r'\|\s*File\s*Name[^=\n]*=\s*([^\n|}]+)', block):
            name = m.group(1).strip()
            if name.lower().endswith('.pdf'):
                return name
    return None


def file_url(name):
    data = api_get({
        'action': 'query', 'titles': f'File:{name}',
        'prop': 'imageinfo', 'iiprop': 'url|size',
    })
    if not data:
        return (None, 0)
    pages = data.get('query', {}).get('pages', {})
    for p in pages.values():
        for ii in p.get('imageinfo', []) or []:
            u = ii.get('url', '')
            if u.startswith('//'):
                u = 'https:' + u
            return (u, int(ii.get('size') or 0))
    return (None, 0)


def make_thumb(pdf_path, out_path):
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


def main():
    os.makedirs(OUT, exist_ok=True)
    catalog = []
    if os.path.exists(CATALOG):
        catalog = json.load(open(CATALOG, encoding='utf-8'))
    done_urls = {e['source_url'] for e in catalog}
    seen = existing_keys()
    print(f'기존 곡 키 {len(seen)}개 (중복 제외 기준)', flush=True)

    debug = bool(os.environ.get('IMSLP_DEBUG'))
    cats = CATEGORIES[:2] if debug else CATEGORIES  # 디버그는 2개만
    # 이미 담긴 imslp 곡 수 — 샤드 번호를 여기서 이어 붙인다.
    imslp_before = sum(1 for e in catalog if e.get('source') == 'imslp')
    added = 0
    per_composer = {}
    for cat, inst, cap in cats:
        got = 0
        stats = {'seen': 0, 'paren': 0, 'wl': 0, 'fresh': 0, 'pdf': 0}
        samples = []
        print(f'== {cat} (상한 {cap})', flush=True)
        for title in walk_category(cat):
            stats['seen'] += 1
            if len(samples) < 5:
                samples.append(title)
            if debug and stats['seen'] >= 1200:
                break
            if added >= TOTAL_LIMIT:
                break
            if got >= cap:
                break
            m = re.search(r'\(([^()]+)\)\s*$', title)
            if not m:
                continue
            stats['paren'] += 1
            composer = m.group(1).strip()  # 'Chopin, Frédéric'
            # 'Chopin, Frédéric' 은 쉼표 앞이 성 — surname_of 가 그렇게 읽는다
            if not is_pd_composer(composer, ''):
                continue
            stats['wl'] += 1
            surname = composer.split(',')[0].strip()
            if per_composer.get(surname, 0) >= PER_COMPOSER:
                continue
            work = title[:m.start()].strip().rstrip(',')
            key = (norm(work), norm(surname))
            if key in seen:
                continue
            src = 'https://imslp.org/wiki/' + urllib.parse.quote(
                title.replace(' ', '_'))
            if src in done_urls:
                continue
            stats['fresh'] += 1
            time.sleep(1.0)
            name = pick_pdf(title)
            if not name:
                continue
            stats['pdf'] += 1
            time.sleep(1.0)
            url, size = file_url(name)
            if not url or size <= 0 or size > MAX_FILE:
                continue
            time.sleep(2.0)  # 다운로드 예절
            data = fetch_bytes(url)
            if debug:
                head = (data[:16] if data else b'(None)')
                print(f'  [파일 덤프] {name!r} url={url[:80]} '
                      f'크기 {len(data) if data else 0} 머리 {head!r}',
                      flush=True)
            if not data or not data.startswith(b'%PDF'):
                # 조용히 넘기면 '후보 995곡, 수집 0곡'의 이유를 못 본다.
                stats['nopdf'] = stats.get('nopdf', 0) + 1
                if stats['nopdf'] <= 3:
                    head = (data[:120] if data else b'(None)')
                    print(f'  ! PDF 아님: {name!r}\n    url={url}\n'
                          f'    크기 {len(data) if data else 0} 머리 {head!r}',
                          flush=True)
                continue
            asset = re.sub(r'[^A-Za-z0-9._-]', '_', name)[:100]
            # 이미 담긴 imslp 곡 수를 이어받아 샤드를 매긴다 —
            # 재실행해도 앞 릴리스를 다시 채우지 않는다.
            tag, shard_dir = shard_of(imslp_before + added)
            os.makedirs(shard_dir, exist_ok=True)
            with open(os.path.join(shard_dir, asset), 'wb') as f:
                f.write(data)
            thumb_asset = 'T_' + os.path.splitext(asset)[0] + '.webp'
            has_thumb = make_thumb(os.path.join(shard_dir, asset),
                                   os.path.join(shard_dir, thumb_asset))
            entry = {
                'source': 'imslp',
                'base': f'{REL}/{tag}',
                'source_url': src,
                'file': asset,
                'title': work,
                'composer': composer,
                'instrument': inst,
                'license': 'Public Domain',
            }
            if has_thumb:
                entry['thumb'] = thumb_asset
            catalog.append(entry)
            done_urls.add(src)
            seen.add(key)
            per_composer[surname] = per_composer.get(surname, 0) + 1
            added += 1
            got += 1
            if added % 25 == 0:
                print(f'  … 총 {added}곡', flush=True)
                json.dump(catalog, open(CATALOG, 'w', encoding='utf-8'),
                          ensure_ascii=False, indent=1)
        print(f'  {cat} 통계 {stats} / 예시 {samples[:3]}', flush=True)
        if added >= TOTAL_LIMIT:
            break

    json.dump(catalog, open(CATALOG, 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    n = sum(1 for e in catalog if e.get('source') == 'imslp')
    shards = sorted(os.listdir(OUT)) if os.path.isdir(OUT) else []
    files = sum(len(os.listdir(os.path.join(OUT, d))) for d in shards)
    print(f'IMSLP 신규 {added}곡 (2권 내 imslp 총 {n}곡), '
          f'자산 {files}개 · 릴리스 {len(shards)}개 {shards}', flush=True)


if __name__ == '__main__':
    main()
