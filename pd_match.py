"""퍼블릭 도메인 작곡가 판정 — 수집기와 정리 스크립트가 같은 기준을 쓴다.

free-sheets / free-sheets-2 두 저장소에 같은 파일을 둔다(둘이 서로를
import 할 수 없어서다). 고칠 때는 양쪽을 함께 고칠 것.
"""
import re

# 전통곡 표기(Traditional·Anonymous 등)만으로는 통과시키지 않는다.
# 2026-07 점검에서 이 경로로 들어온 곡에서 실제 침해가 확인됐다.
STRICT_PD = True

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


def is_pd_composer(composer, artist):
    """작곡가 이름이 PD 명단에 있는가 — 전통곡 표기는 인정하지 않는다."""
    for field in (composer, artist):
        # ① 성 자리에 정확히 오면 인정 (모호한 이름도 여기선 통과)
        for sur in surname_of(field):
            if _PD_RE.fullmatch(sur.strip(" .,'\"-")):
                return True
        # ② 모호하지 않은 이름은 표기가 지저분해도('S.Rachmaninoff',
        #    'Franz SchubertOriginal in A-minor') 문자열 안에서 찾는다.
        if field and _PD_LOOSE_RE.search(field):
            return True
    return False


def is_trad(composer, artist):
    """민요·작자 미상 표기인가."""
    blob = ' '.join(x for x in (composer, artist) if x)
    return bool(_TRAD_RE.search(blob))


def is_pd_safe(composer, artist):
    """수집 허용 여부 — PD 작곡가이거나 전통곡 표기.

    주의: 전통곡 표기는 업로더가 직접 적은 값이라 검증된 사실이 아니다.
    2026-07 점검에서 이 경로로 들어온 곡에서 실제 침해가 확인돼,
    카탈로그는 `is_pd_composer` 만 통과시킨다(STRICT_PD=1 이 기본).
    """
    if is_pd_composer(composer, artist):
        return True
    return not STRICT_PD and is_trad(composer, artist)

