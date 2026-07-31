"""PDMX 확장 수집기 v2 — free-sheets-2 (2권) 전용.

1권(free-sheets)의 collect_pdmx.py 대비 확장점:
 - 작곡가 화이트리스트 대폭 확장 (사후 70년+ 경과가 확실한 작곡가
   위주 — 대부분 1930년 이전 사망이라 미국 기준으로도 안전)
 - 피아노 독주·기타 독주 타깃 추가
 - is_best_unique_arrangement 요구 완화 → (제목, 작곡가, 악기)
   단위 자체 중복 제거(인기 점수 최고본만)
 - 1권 카탈로그의 기존 pdmx 곡과 MuseScore ID 중복 배제
 - PDF + 미디 스트리밍 추출, 썸네일(WebP)까지 이 저장소에 생성
 - catalog2.json 에 base 필드(이 저장소 raw URL) 포함 — 1권의
   병합 워크플로가 그대로 합친다 (앱 업데이트 불필요)

전제: poppler-utils(pdftoppm), webp(cwebp) 설치.
"""
import csv
import io
import json
import os
import re
import subprocess
import tarfile
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(ROOT, 'raw')
MIDS = os.path.join(ROOT, 'mids')
THUMBS = os.path.join(ROOT, 'thumbs')
CATALOG = os.path.join(ROOT, 'catalog2.json')
ZEN = 'https://zenodo.org/api/records/15571083/files'
BASE_URL = 'https://raw.githubusercontent.com/NAKJIKING/free-sheets-2/main'
VOL1_CATALOG = ('https://raw.githubusercontent.com/NAKJIKING/'
                'free-sheets/main/catalog.json')
UA = {'User-Agent': 'MySheetMusic-FreeLibrary/2.0 (public-domain collector)'}

# 악기별 상한 — 기존 분류만 유지(신규 악기 없음). 여유 상한을 주고
# 이번 실행 신규 총량은 NEW_ADD로 ~3,000곡에서 끊는다.
# 재실행하면 기존 곡은 건너뛰고 상한까지 이어서 채운다.
CAPS = {
    'Piano': 8200,
    'Guitar': 1200,
    'Flute': 1000,
    'Violin': 900,
    'Cello': 800,
    'Clarinet': 700,
    'Trumpet': 700,
    'Saxophone': 700,
}

# 이번 실행에서 추가할 신규 곡 상한 (기존 분류 안에서 ~3,000곡).
NEW_ADD = int(os.environ.get('NEW_ADD', '3000'))

# 1권 전수조사에서 차단된 MuseScore ID — 그대로 승계.
BLOCKED_IDS = {
    '5902556', '4159766', '5907396', '873391', '5935685', '5941614',
    '5838089',
}

TARGETS = {
    'Flute': {73},
    'Violin': {40},
    'Cello': {42},
    'Clarinet': {71},
    'Trumpet': {56},
    'Saxophone': {64, 65, 66, 67},
    'Guitar': {24, 25},
}
KEYBOARD = {0, 1, 2, 3, 4, 5, 6, 7}

# ── 저작권 안전 장치: 원곡이 확실한 퍼블릭 도메인인 작곡가만 ──
# 1권 목록 + 확장(대부분 1930년 이전 사망 — 전 작품이 1930년 이전
# 출판이라 미국 출판 기준으로도 안전). 짧거나 흔한 성(Lee, King,
# Monk, Smart 등)은 오탐 위험이 있어 넣지 않는다.
PD_COMPOSERS = [
    # ── 1권 목록 ──
    'Bach', 'Handel', 'Vivaldi', 'Telemann', 'Purcell', 'Scarlatti',
    'Corelli', 'Albinoni', 'Pachelbel', 'Rameau', 'Couperin', 'Buxtehude',
    'Monteverdi', 'Palestrina', 'Byrd', 'Tallis', 'Dowland', 'Frescobaldi',
    'Lully', 'Charpentier', 'Quantz', 'Stamitz', 'Danzi', 'Boccherini',
    'Haydn', 'Mozart', 'Beethoven', 'Clementi', 'Czerny', 'Diabelli',
    'Hummel', 'Gluck', 'Salieri', 'Kuhlau', 'Cimarosa',
    'Schubert', 'Schumann', 'Chopin', 'Liszt', 'Mendelssohn', 'Brahms',
    'Wagner', 'Verdi', 'Rossini', 'Donizetti', 'Bellini', 'Puccini',
    'Tchaikovsky', 'Rimsky-Korsakov', 'Mussorgsky', 'Borodin', 'Glinka',
    'Rachmaninoff', 'Rachmaninov', 'Scriabin', 'Grieg', 'Dvorak',
    'Dvořák', 'Smetana', 'Janacek', 'Mahler', 'Bruckner',
    'Strauss', 'Debussy', 'Ravel', 'Faure', 'Fauré', 'Saint-Saens',
    'Saint-Saëns', 'Franck', 'Bizet', 'Gounod', 'Massenet',
    'Offenbach', 'Satie', 'Elgar', 'Holst', 'Albeniz', 'Albéniz',
    'Granados', 'Paganini', 'Sarasate', 'Wieniawski', 'Weber', 'Spohr',
    'MacDowell', 'Burgmüller', 'Burgmuller', 'Sibelius',
    'Tarrega', 'Tárrega', 'Sor', 'Giuliani', 'Carcassi', 'Carulli',
    'Aguado', 'Mertz', 'Milan', 'Sanz',
    'Arban', 'Clarke', 'Klose', 'Klosé', 'Rose', 'Baermann',
    'Crusell', 'Boehm', 'Böhm', 'Andersen', 'Popp', 'Köhler',
    'Kohler', 'Drouet', 'Demersseman', 'Doppler', 'Briccialdi',
    'Joplin', 'Sousa', 'Foster', 'Gregorian', 'Hymn',
    # ── 확장: 바로크·고전 ──
    'Biber', 'Zelenka', 'Fasch', 'Graupner', 'Heinichen', 'Pergolesi',
    'Marcello', 'Galuppi', 'Sammartini', 'Tartini', 'Geminiani',
    'Locatelli', 'Veracini', 'Leclair', 'Boismortier', 'Hotteterre',
    'Blavet', 'Loeillet', 'Caldara', 'Dittersdorf', 'Vanhal', 'Pleyel',
    'Krommer', 'Rosetti', 'Reicha', 'Ries', 'Sweelinck', 'Praetorius',
    'Gibbons', 'Victoria', 'Lassus', 'Josquin', 'Ockeghem',
    # ── 확장: 피아노·살롱 ──
    'Field', 'Moscheles', 'Kalkbrenner', 'Thalberg', 'Alkan', 'Heller',
    'Gurlitt', 'Streabbog', 'Lemoine', 'Duvernoy', 'Bertini',
    'Loeschhorn', 'Löschhorn', 'Hanon', 'Cramer', 'Dussek',
    'Moszkowski', 'Godard', 'Chaminade', 'Paderewski', 'Leschetizky',
    'Balakirev', 'Lyadov', 'Liadov', 'Arensky', 'Glazunov', 'Taneyev',
    'Lyapunov', 'Kalinnikov', 'Gottschalk', 'Nazareth', 'Ponce',
    # ── 확장: 바이올린·첼로 ──
    'Vieuxtemps', 'Ernst', 'Hubay', 'Joachim', 'Ysaye', 'Ysaÿe',
    'Auer', 'Beriot', 'Bériot', 'Rode', 'Kreutzer', 'Viotti',
    'Dancla', 'Kayser', 'Mazas', 'Sitt', 'Sevcik', 'Ševčík',
    'Accolay', 'Seitz', 'Rieding', 'Monti', 'Drdla', 'Popper',
    'Goltermann', 'Romberg', 'Klengel', 'Duport', 'Dotzauer', 'Servais',
    # ── 확장: 플루트·관악 ──
    'Tulou', 'Fürstenau', 'Furstenau', 'Gariboldi', 'Génin',
    'Genin', 'Taffanel', 'Gaubert', 'Terschak', 'Kummer', 'Pryor',
    'Alford', 'Teike', 'Fucik', 'Fučík',
    # ── 확장: 오페라·관현악·왈츠 ──
    'Meyerbeer', 'Halevy', 'Halévy', 'Auber', 'Delibes', 'Lalo',
    'Chabrier', 'Chausson', 'Duparc', 'Leoncavallo', 'Mascagni',
    'Ponchielli', 'Boito', 'Catalani', 'Giordano', 'Suppé', 'Suppe',
    'Lehár', 'Lehar', 'Millöcker', 'Millocker', 'Zeller',
    'Waldteufel', 'Ivanovici', 'Rosas',
    # ── 확장: 북유럽·영미 ──
    'Nielsen', 'Svendsen', 'Sinding', 'Halvorsen', 'Stenhammar',
    'Berwald', 'Gade', 'Lumbye', 'Merikanto', 'Sullivan', 'Parry',
    'Stanford', 'Coleridge-Taylor', 'Bridge', 'Butterworth', 'Nevin',
    # ── 확장: 오르간·교회 ──
    'Widor', 'Vierne', 'Guilmant', 'Boëllmann', 'Boellmann',
    'Karg-Elert', 'Rheinberger', 'Merkel', 'Batiste', 'Stainer',
    'Barnby', 'Dykes', 'Bradbury', 'Sankey', 'Sherwin', 'Doane',
    'Converse', 'Kirkpatrick', 'Hastings', 'Bourgeois', 'Croft',
    'Wesley',
    # ── 교육 정전 보강 (초·중급 교재 저자 — 전원 사후 70년+ 확인) ──
    # 피아노 초급 표준 교재
    'Beyer',       # 페르디난트 바이어 Op.101 — 초급 피아노 표준(한국 필수)
    'Reinagle',    # Alexander Reinagle — 초급 소품
    'Reinecke',    # Carl Reinecke — 피아노·플루트
    'Türk', 'Turk',  # Daniel Gottlob Türk — 초급 소품
    'Oesten',      # Theodor Oesten — 소나티네·소품
    'Lichner',     # Heinrich Lichner — 소나티네
    'Spindler',    # Fritz Spindler — 교습용 소품
    'Rebikov',     # Vladimir Rebikov — 어린이 소품
    # 바이올린 에튀드·학생 협주곡
    'Wohlfahrt',   # Franz Wohlfahrt Op.45 — 초급 바이올린 에튀드 표준
    'Dont',        # Jakob Dont — 바이올린 에튀드
    'Küchler', 'Kuchler',  # Ferdinand Küchler — 학생 협주곡
    # 첼로 교재·소품
    'Bréval', 'Breval',    # Jean-Baptiste Bréval — 첼로 소나타(스즈키)
    'Fiocco',      # Joseph-Hector Fiocco — Allegro(학생 표준)
    'Eccles',      # Henry Eccles — 첼로 소나타
    'Goens',       # Daniel van Goens — 첼로 소품
    # 플루트 교재
    'Berbiguier',  # Tranquille Berbiguier — 플루트 에튀드
    'Altès', 'Altes',      # Henry Altès — 플루트 교본
    # 클라리넷·목관 교재
    'Lefèvre', 'Lefevre',  # Xavier Lefèvre — 클라리넷 교본
    'Ferling',     # Franz Wilhelm Ferling — 색소폰·오보에 에튀드
    'Concone',     # Giuseppe Concone — 성악·악기 연습곡
    # 관현악 소품
    'Gossec',      # François-Joseph Gossec — Gavotte(학생 표준)
    # ── 2026-07 점검에서 표기 변형 탓에 놓쳤던 이름 보강 ──
    'Goudimel',    # Claude Goudimel †1572 — 시편가 화성
    'Petzold',     # Christian Petzold †1733 — 안나 막달레나 미뉴에트
    'Liapounow',   # Lyapunov 독일식 표기 †1924
    'Drouët',      # Louis Drouet — 악센트 표기
    'Neander',     # Joachim Neander †1680 — 찬송가
]
# 다른 뜻으로도 쓰이는 성 — 흔한 영어 낱말이거나(Field, Dont, Rose)
# 현대 음악가의 '이름' 자리에 오는 것들(Lalo Schifrin, Ernst Toch).
# 이 이름들은 문자열 아무 데나 나왔다고 통과시키면 안 되고, 반드시
# 성 자리(마지막 토큰)에 있어야만 인정한다.
AMBIGUOUS = {
    'alford', 'andersen', 'auer', 'barnby', 'beyer', 'bourgeois', 'bridge',
    'butterworth', 'clarke', 'converse', 'cramer', 'croft', 'doane', 'dont',
    'dykes', 'eccles', 'ernst', 'field', 'gade', 'genin', 'gibbons', 'hanon',
    'hastings', 'heller', 'hymn', 'klengel', 'kummer', 'lalo', 'marcello',
    'milan', 'monti', 'parry', 'ponce', 'rode', 'rose', 'ries', 'seitz',
    'sitt', 'stainer', 'turk', 'victoria', 'vincent', 'wesley',
}
_PD_RE = re.compile(
    '|'.join(re.escape(n) for n in PD_COMPOSERS), re.I)
# 성 자리 밖(문자열 어디든)에서도 인정하는 이름 — 위 모호 목록 제외.
_PD_LOOSE_RE = re.compile(
    r'\b(' + '|'.join(re.escape(n) for n in PD_COMPOSERS
                      if n.lower() not in AMBIGUOUS) + r')\b', re.I)
# 민요·작자 미상 표기 — 소스가 다국어라 영어 말고도 받아 준다.
_TRAD_RE = re.compile(
    r'\b(traditio\w*|trad\.?|tradicional|traddodiadol|folk\w*|folke\w*|'
    r'anonym\w*|anon\.?|unattributed|unknown|ukjent|okänd|hymn|spiritual|'
    r'gregorian|volkslied|chanson populaire)\b', re.I)

# 이름 꼬리에 붙는 이니셜·서수·귀족 전치사 — 성을 찾을 때 떼어낸다.
_TAIL = re.compile(
    r"^(?:[a-z]\.?|jr\.?|sr\.?|i{1,3}|iv|von|van|de[nrl]?|d[aiu]|le|la)$",
    re.I)


def surname_of(field):
    """이름 문자열들에서 '성'으로 볼 토큰만 뽑아 낸다.

    작곡가 이름을 문자열 어디서나 찾으면(단순 부분일치) 엉뚱한 곡이
    퍼블릭 도메인으로 통과한다 — 실제로 'dont know'가 Jakob **Dont**로,
    'Lalo Schifrin'(1932~)이 Édouard **Lalo**로 잡혀 저작권 있는 곡이
    섞여 들어왔다. 성은 이름의 마지막 토큰(또는 'Bach, J.S.'처럼 쉼표
    앞)이므로 모호한 이름은 그 자리에서만 인정한다.
    """
    for part in re.split(r'[;/&]|\barr\.|\b(?:and|feat\.?|with)\b',
                         re.sub(r'\(.*?\)', ' ', field or ''), flags=re.I):
        part = part.strip()
        if not part:
            continue
        if ',' in part:                       # "Bach, Johann Sebastian"
            yield part.split(',', 1)[0].strip()
            continue
        toks = [t for t in part.split() if t]
        while len(toks) > 1 and _TAIL.match(toks[-1]):
            toks.pop()                        # "Strauss Jr." → Strauss
        if toks:
            yield toks[-1]


def is_pd_safe(composer, artist):
    for field in (composer, artist):
        # ① 성 자리에 정확히 오면 인정 (모호한 이름도 여기선 통과)
        for sur in surname_of(field):
            if _PD_RE.fullmatch(sur.strip(" .,'\"-")):
                return True
        # ② 모호하지 않은 이름은 표기가 지저분해도('S.Rachmaninoff',
        #    'Franz SchubertOriginal in A-minor') 문자열 안에서 찾는다.
        if field and _PD_LOOSE_RE.search(field):
            return True
    blob = ' '.join(x for x in (composer, artist) if x)
    return bool(_TRAD_RE.search(blob))


def open_url(name):
    req = urllib.request.Request(f'{ZEN}/{name}/content', headers=UA)
    return urllib.request.urlopen(req, timeout=600)


def fetch(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def parse_tracks(s):
    try:
        return [int(x) for x in s.split('-')] if s and s != 'NA' else []
    except ValueError:
        return None


def classify(progs):
    """MIDI 프로그램 목록 → (악기, 독주 여부) 또는 None."""
    if not progs or len(progs) > 2:
        return None
    for name, targets in TARGETS.items():
        hits = [p for p in progs if p in targets]
        rest = [p for p in progs if p not in targets]
        if hits and all(p in KEYBOARD for p in rest):
            return (name, not rest)
    # 전부 건반 → 피아노 독주(또는 두 손·두 대)
    if all(p in KEYBOARD for p in progs):
        return ('Piano', True)
    return None


def norm(s):
    return re.sub(r'[^a-z0-9]+', ' ', (s or '').lower()).strip()


def pick_candidates(vol1_ids):
    """CSV 한 번 훑어 (제목·작곡가·악기) 대표본을 고른다."""
    best = {}  # (title, composer, inst) -> cand
    with open_url('PDMX.csv') as r:
        text = io.TextIOWrapper(r, encoding='utf-8', errors='replace')
        for row in csv.DictReader(text):
            if row.get('subset:no_license_conflict') != 'True':
                continue
            pdf = row.get('pdf', 'NA')
            if not pdf or pdf == 'NA':
                continue
            progs = parse_tracks(row.get('tracks', 'NA'))
            cls = classify(progs) if progs is not None else None
            if cls is None:
                continue
            inst, solo = cls
            if not is_pd_safe(row.get('composer_name', ''),
                              row.get('artist_name', '')):
                continue
            meta = row.get('metadata', '')
            m = re.search(r'/(\d+)\.json$', meta)
            ms_id = m.group(1) if m else ''
            if ms_id in BLOCKED_IDS or ms_id in vol1_ids:
                continue
            try:
                rating = float(row.get('rating') or 0)
                n_ratings = int(row.get('n_ratings') or 0)
                views = int(row.get('n_views') or 0)
            except ValueError:
                rating, n_ratings, views = 0.0, 0, 0
            score = (rating if n_ratings > 0 else 0.0, views)

            def _clean(v):
                return '' if v in (None, '', 'NA') else v.strip()
            title = (_clean(row.get('song_name'))
                     or _clean(row.get('title')) or 'Untitled')
            composer = (_clean(row.get('composer_name'))
                        or _clean(row.get('artist_name')))
            key = (norm(title), norm(composer), inst)
            cur = best.get(key)
            if cur is not None and cur['score'] >= score:
                continue
            midp = row.get('mid', 'NA')
            best[key] = {
                'pdf': pdf.lstrip('./'),
                'mid': midp.lstrip('./') if midp and midp != 'NA' else '',
                'score': score,
                'title': title,
                'composer': composer,
                'license': row.get('license') or 'publicdomain',
                'inst': inst,
                'solo': solo,
                'ms_id': ms_id,
            }
    # 악기별 인기순 상한 적용
    by_inst = {k: [] for k in CAPS}
    for c in best.values():
        by_inst[c['inst']].append(c)
    wanted = {}
    for inst, lst in by_inst.items():
        lst.sort(key=lambda c: c['score'], reverse=True)
        take = lst[:int(CAPS[inst] * 1.3)]  # 아카이브 누락 대비 여유분
        print(f'  {inst}: 후보 {len(lst)} → 선별 {len(take)}', flush=True)
        for c in take:
            wanted[c['pdf']] = c
    return wanted


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


def main():
    # 1권 카탈로그의 pdmx MuseScore ID — 중복 배제용.
    vol1_ids = set()
    try:
        for e in json.loads(fetch(VOL1_CATALOG).decode('utf-8')):
            if e.get('source') == 'pdmx':
                m = re.search(r'/score/(\d+)', e.get('source_url', ''))
                if m:
                    vol1_ids.add(m.group(1))
    except Exception as ex:
        print(f'1권 카탈로그 확인 실패(계속 진행): {ex}', flush=True)
    print(f'1권 pdmx 기존 {len(vol1_ids)}곡 제외', flush=True)

    print('== PDMX v2: CSV 선별', flush=True)
    wanted = pick_candidates(vol1_ids)
    print(f'총 추출 대상 {len(wanted)}개, pdf.tar.gz 스트리밍', flush=True)

    catalog = []
    if os.path.exists(CATALOG):
        catalog = json.load(open(CATALOG, encoding='utf-8'))
    seen = {e['source_url'] for e in catalog}
    counts = {k: 0 for k in CAPS}
    for e in catalog:
        if e.get('instrument') in counts:
            counts[e['instrument']] += 1
    added = 0
    mid_want = {}  # mid 경로 -> catalog entry
    with open_url('pdf.tar.gz') as r:
        with tarfile.open(fileobj=r, mode='r|gz') as tf:
            remaining = len(wanted)
            for m in tf:
                if remaining <= 0 or added >= NEW_ADD:
                    break
                if not m.isfile():
                    continue
                key = m.name.lstrip('./')
                c = wanted.get(key)
                if c is None:
                    continue
                remaining -= 1
                inst = c['inst']
                if counts[inst] >= CAPS[inst]:
                    continue
                src = (f"https://musescore.com/score/{c['ms_id']}"
                       if c['ms_id'] else f"pdmx2:{key}")
                if src in seen:
                    continue
                data = tf.extractfile(m).read()
                if not data.startswith(b'%PDF'):
                    continue
                inst_dir = os.path.join(RAW, 'pdmx2', inst.lower())
                os.makedirs(inst_dir, exist_ok=True)
                safe = re.sub(r'[^A-Za-z0-9._-]', '_', c['title'])[:60]
                stem = f"{safe}-{os.path.basename(key)[:12]}"
                with open(os.path.join(inst_dir, stem + '.pdf'), 'wb') as f:
                    f.write(data)
                entry = {
                    'source': 'pdmx2',
                    'base': BASE_URL,
                    'source_url': src,
                    'file': os.path.relpath(
                        os.path.join(inst_dir, stem + '.pdf'), ROOT),
                    'title': c['title'],
                    'composer': c['composer'],
                    'instrument': inst,
                    'license': c['license'],
                }
                catalog.append(entry)
                seen.add(src)
                counts[inst] += 1
                added += 1
                if c['mid']:
                    mid_want[c['mid']] = entry
                if added % 200 == 0:
                    print(f'  ...{added}곡 추출', flush=True)
                    json.dump(catalog, open(CATALOG, 'w', encoding='utf-8'),
                              ensure_ascii=False, indent=1)
    print(f'PDF {added}곡. 미디 대상 {len(mid_want)}곡, mid.tar.gz 스트리밍',
          flush=True)

    got_mid = 0
    if mid_want:
        with open_url('mid.tar.gz') as r:
            with tarfile.open(fileobj=r, mode='r|gz') as tf:
                remaining = len(mid_want)
                for m in tf:
                    if remaining <= 0:
                        break
                    if not m.isfile():
                        continue
                    e = mid_want.get(m.name.lstrip('./'))
                    if e is None:
                        continue
                    remaining -= 1
                    data = tf.extractfile(m).read()
                    if data[:4] != b'MThd':
                        continue
                    rel = e['file']
                    if rel.startswith('raw/'):
                        rel = rel[4:]
                    mid_rel = 'mids/' + os.path.splitext(rel)[0] + '.mid'
                    out = os.path.join(ROOT, mid_rel)
                    os.makedirs(os.path.dirname(out), exist_ok=True)
                    with open(out, 'wb') as f:
                        f.write(data)
                    e['midi'] = mid_rel
                    got_mid += 1
    print(f'미디 {got_mid}곡. 썸네일 생성', flush=True)

    made = 0
    for e in catalog:
        if e.get('thumb'):
            continue
        pdf = os.path.join(ROOT, e['file'])
        if not os.path.exists(pdf):
            continue
        rel = e['file']
        if rel.startswith('raw/'):
            rel = rel[4:]
        thumb_rel = 'thumbs/' + os.path.splitext(rel)[0] + '.webp'
        if make_thumb(pdf, os.path.join(ROOT, thumb_rel)):
            e['thumb'] = thumb_rel
            made += 1
        if made % 300 == 0 and made:
            print(f'  썸네일 {made}…', flush=True)

    json.dump(catalog, open(CATALOG, 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    n_mid = sum(1 for e in catalog if e.get('midi'))
    n_thumb = sum(1 for e in catalog if e.get('thumb'))
    print(f'== 악기별: {counts}', flush=True)
    print(f'2권 합계 {len(catalog)}곡 (미디 {n_mid}, 썸네일 {n_thumb})',
          flush=True)


if __name__ == '__main__':
    main()
