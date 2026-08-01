# free-sheets-2 — My Sheet Music 무료 악보 라이브러리 (2권)

**내 악보함(My Sheet Music)** 앱의 무료 악보 라이브러리 확장 저장소입니다.
본 카탈로그와 정책은 [free-sheets](https://github.com/NAKJIKING/free-sheets)
저장소가 관리하며, 이 저장소는 곡 파일(PDF·미디·썸네일)과 2권 카탈로그
(`catalog2.json`)를 담습니다.

수록 원칙: 저작권이 만료됐거나(퍼블릭 도메인) 재배포가 허용된 자유
라이선스로 공개된 악보만. **작곡가가 퍼블릭 도메인 명단(`pd_match.py`,
전원 사후 70년 경과 확인)에 있는 곡만** 남기며, 업로더가 적은
'Traditional' 표기는 증거로 인정하지 않습니다.

## Sources & Credits

- **PDMX** — *PDMX: A Large-Scale Public Domain MusicXML Dataset for
  Symbolic Music Processing* (Phillip Long, Zachary Novack, Taylor
  Berg-Kirkpatrick, Julian McAuley). Dataset **CC BY 4.0** via Zenodo
  (DOI [10.5281/zenodo.13763756](https://doi.org/10.5281/zenodo.13763756)).
  We use only the `no_license_conflict` subset, further restricted to
  composers whose works are unambiguously out of copyright. Per-song
  license strings come from the uploader's MuseScore declaration, which
  we do not independently verify. https://github.com/pnlong/PDMX
- **IMSLP** — public-domain scanned scores (per-file Copyright field
  checked; collector in `collect_imslp.py`, not yet in production).

수집 스크립트(`*.py`)는 MIT 라이선스입니다.

## 저작권 정책 / Takedown

권리자로서 이의가 있는 곡이 있다면 GitHub 이슈로 곡 제목과 근거를
알려주세요. 확인 즉시 카탈로그와 저장소에서 내리겠습니다.
If you are a rights holder and believe a score here infringes your
copyright, please open a GitHub issue — we will remove it promptly.
