# violet-db-mirror

Violet 메타데이터와 모바일용 DB 스냅샷을 자동으로 갱신해서 GitHub Release에 보관하는 저장소다.

현재 `.github/workflows/sync-db.yml`은 6시간마다 다음 작업을 수행한다.

1. 이전 실행에서 저장한 전체 상태 DB(`violet-state.db.zst`)를 받는다.
2. `pingpingjinping/violet`의 `fast-hsync`를 빌드한다.
3. Hitomi + ExHentai 데이터를 동기화한다.
4. 변경분(delta)을 만든다.
5. 한국어 모바일 DB(`rawdata-korean.db`)를 만든다.
6. 무결성을 검사한다.
7. 갱신된 파일들을 `db-state` Release에 다시 업로드한다.

## ExHentai 쿠키

GitHub Actions 저장소 Secret에 `EH_COOKIE`를 만든다.

값은 전체 쿠키 문자열이다.

```text
ipb_member_id=...; ipb_pass_hash=...; igneous=...
```

워크플로에서는 쿠키 값을 로그에 출력하지 않는다.

---

# 언어 DB 추가 방법

나중에 영어/일본어/전체 DB 같은 새로운 모바일 DB를 추가할 때 참고할 절차다.

## 먼저 구조부터

이 저장소에는 성격이 다른 DB가 두 종류 있다.

### 1. 전체 상태 DB

```text
violet-state.db
violet-state.db.zst
```

이 파일은 `fast-hsync`가 계속 갱신하는 **원본/수집용 DB**다.

Hitomi + ExHentai의 전체 데이터가 들어 있고, 각 언어 DB는 이 파일에서 필요한 행만 뽑아서 만든다.

즉 영어 DB를 새로 만든다고 해서 영어 데이터를 인터넷에서 처음부터 따로 다시 긁는 구조가 아니다.

```text
Hitomi + ExHentai
       ↓
violet-state.db
       ↓
 ┌──────────────┬──────────────┬──────────────┬─────────────┐
 ↓              ↓              ↓              ↓
한국어 DB       영어 DB        일본어 DB      전체 DB
```

### 2. 앱이 실제로 받는 모바일 DB

현재/예정 파일 이름은 다음과 같다.

| 앱 DB 종류 | DB의 `Language` 값 | Release 파일 이름 |
| --- | --- | --- |
| 한국어 | `korean` | `rawdata-korean.db` |
| 영어 | `english` | `rawdata-english.db` |
| 일본어 | `japanese` | `rawdata-japanese.db` |
| 전체 | 언어 필터 없음 | `rawdata.db` |

Violet 앱은 현재 `ko / en / ja / global` 규칙으로 위 파일 이름을 계산한다.

따라서 **영어/일본어/전체 DB는 서버 쪽 파일만 만들어서 정확한 이름으로 제공하면 앱 코드를 다시 손대지 않아도 된다.**

---

# A. 기존 `violet-state.db`가 있는 경우

현재 운영 방식에서는 이 경우가 기본이다.

## 1. 언어 DB 생성 코드 만들기

현재 한국어 DB는 `scripts/export-korean.py`가 만든다.

새 언어를 추가할 때는 이 스크립트를 일반화하거나, 같은 방식의 exporter를 새로 만들면 된다.

언어별 조건은 다음과 같다.

### 한국어

```sql
WHERE lower(trim(Language)) = 'korean'
```

### 영어

```sql
WHERE lower(trim(Language)) = 'english'
```

### 일본어

```sql
WHERE lower(trim(Language)) = 'japanese'
```

### 전체 DB

전체 DB는 `Language` 조건을 넣지 않는다.

```sql
SELECT ...
FROM HitomiColumnModel
```

즉 전체 DB는 `violet-state.db`의 `HitomiColumnModel` 전체를 모바일용 파일로 복사하면 된다.

## 2. DB를 임시 파일에 먼저 만든다

완성되지 않은 DB가 Release에 올라가지 않게 반드시 임시 파일에 만든 뒤 검증한다.

예:

```text
rawdata-english.tmp.db
        ↓ 검증 성공
rawdata-english.db
```

한국어 exporter와 동일하게 다음 순서로 만드는 것이 안전하다.

1. 원본 `violet-state.db`를 읽기 전용으로 연다.
2. `HitomiColumnModel` 테이블 스키마를 복사한다.
3. 원하는 언어의 행만 복사한다.
4. `HitomiColumnModel`에 걸린 일반 인덱스를 복사한다.
5. 트랜잭션을 완료한다.
6. `PRAGMA quick_check`를 실행한다.
7. 행 개수가 0이면 실패 처리한다.
8. 검증에 성공한 경우에만 임시 파일을 최종 파일로 교체한다.

## 3. 생성 결과 검증

예를 들어 영어 DB라면 최소한 다음을 확인한다.

```sql
PRAGMA quick_check;

SELECT COUNT(*)
FROM HitomiColumnModel;

SELECT COUNT(*)
FROM HitomiColumnModel
WHERE lower(trim(coalesce(Language, ''))) <> 'english';
```

정상 조건:

```text
quick_check = ok
전체 행 수 > 0
영어가 아닌 행 수 = 0
```

일본어도 동일하게 `japanese`로 검사한다.

전체 DB는 언어 혼합이 정상이라 마지막 언어 검사는 하지 않는다.

---

# B. GitHub Actions에 언어 DB 생성 추가

`.github/workflows/sync-db.yml`의 현재 `Export Korean DB` 단계가 기준 예제다.

영어를 추가한다고 하면 대략 아래 작업이 필요하다.

## 1. exporter 실행

예:

```text
source : work/violet-state.db
output : work/rawdata-english.db
filter : english
```

일본어:

```text
output : work/rawdata-japanese.db
filter : japanese
```

전체:

```text
output : work/rawdata.db
filter : 없음
```

## 2. 워크플로 안에서 검증

각 파일에 대해 다음을 검사한다.

- `PRAGMA quick_check = ok`
- 행 개수 0이 아님
- 언어 DB라면 다른 언어 행이 들어가지 않았는지 확인
- 가능하면 원본 상태 DB의 해당 언어 행 수와 정확히 일치하는지 확인

## 3. Release 업로드 목록에 추가

현재 `Replace release assets` 단계의

```bash
gh release upload db-state ...
```

목록에 새 파일을 넣는다.

예:

```text
work/rawdata-korean.db
work/rawdata-english.db
work/rawdata-japanese.db
work/rawdata.db
```

`--clobber`를 사용하므로 같은 이름의 기존 Release asset은 새 파일로 교체된다.

## 4. 상태 보고서에도 넣는 것을 권장

`sync-status.json`과 Release notes에 각 DB의 다음 정보를 추가해두면 확인하기 쉽다.

- 행 개수
- 파일 크기
- SHA-256
- 마지막 생성 시각

필수는 아니지만 나중에 DB가 잘못 생성됐는지 확인할 때 유용하다.

---

# C. `syncversion.txt` 설정

여러 언어 DB를 지원할 때 특히 중요하다.

앱은 manifest에 적힌 URL 뒤에 DB 종류에 맞는 접미사를 **직접 붙인다.**

따라서 `syncversion.txt`에는 특정 언어 파일이 아니라 공통 **베이스 URL**을 넣어야 한다.

예:

```text
db 1789900000 https://github.com/pingpingjinping/violet-db-mirror/releases/download/db-state/rawdata
```

그러면 앱에서 자동으로 다음처럼 바뀐다.

```text
ko     -> rawdata-korean.db
en     -> rawdata-english.db
ja     -> rawdata-japanese.db
global -> rawdata.db
```

### 중요

다국어 DB를 실제로 열기 전에는 아래처럼 쓰면 안 된다.

```text
.../rawdata-korean.db
```

이 상태에서 앱이 영어 DB를 선택하면 뒤에 `-english.db`를 또 붙이게 되어 URL이 잘못된다.

---

# D. 완전히 새 언어를 추가하는 경우

한국어/영어/일본어/전체는 현재 앱 쪽 규칙이 이미 준비되어 있다.

따라서 이 네 종류는 mirror/Pi 서버에서 파일만 준비하면 된다.

그 외의 언어를 새로 추가하려면 앱도 수정해야 한다.

예를 들어 중국어 DB를 다시 추가한다면:

```text
앱 타입        zh
DB Language    chinese
파일 이름      rawdata-chinese.db
```

그리고 `violet-release`에서 다음을 확인/수정한다.

1. DB 선택 UI
2. `SyncManager.createRawdbPostfixiOS()`
3. `SyncManager.translateToLanguage()`
4. DB 기본값/폴백 처리
5. 필요하면 번역 문자열

---

# E. 원본 `violet-state.db` 자체가 없는 경우

이 부분은 **언어 DB 추가**와는 별개의 초기 구축 단계다.

현재 정기 `sync-db.yml`은 이미 존재하는

```text
db-state / violet-state.db.zst
```

를 내려받아 이어서 갱신하는 구조이므로, 이 파일이 완전히 사라진 상태에서는 정기 워크플로만으로 자동 복구되지 않는다.

## 가장 쉬운 복구 방법

정상 동작 중인 Violet 전체 DB가 다른 곳에 있다면 그 DB를 새 상태 DB의 시작점으로 사용하는 것이 가장 빠르다.

예를 들어 Pi의 정상 `data.db`를 복사해서:

```text
data.db
  ↓
violet-state.db
  ↓ zstd 압축
violet-state.db.zst
  ↓
db-state Release에 업로드
```

그 다음 `Sync Violet DB` 워크플로를 수동 실행하면 이후부터 다시 6시간 증분 동기화가 이어진다.

업로드 전에 반드시:

```sql
PRAGMA quick_check;
```

결과가 `ok`인지 확인한다.

## 인터넷에서 완전히 새로 수집해야 하는 경우

`fast-hsync`는 빈 DB 생성 자체는 가능하다.

작은 범위 예시는 `.github/workflows/test-collector.yml`에 있다.

```bash
./fast-hsync violet-state.db \
  --start-id=4192000 \
  --end-id=4192050
```

다만 전체 Hitomi DB를 1부터 최신 ID까지 한 번에 만드는 것은 범위가 매우 크므로, 정기 GitHub Actions의 60분 작업으로 처리하는 용도는 아니다.

완전 초기 구축이 필요하면 로컬/Pi 같은 장시간 실행 가능한 환경에서 ID 범위를 여러 구간으로 나눠 `fast-hsync`를 반복 실행해 상태 DB를 만든 뒤, 마지막에 `--with-exh` 동기화와 무결성 검사를 하고 `violet-state.db.zst`로 올리는 쪽이 안전하다.

즉 평소에는 **기존 상태 DB를 계속 이어 쓰는 것이 정상 운영 방식**이다.

---

# F. 최종 체크리스트

새 언어 DB를 실제로 켜기 전에 아래를 모두 확인한다.

- 원본 `violet-state.db`가 최신 상태다.
- 새 언어 exporter가 원하는 `Language`만 복사한다.
- `PRAGMA quick_check` 결과가 `ok`다.
- 행 개수가 0이 아니다.
- Release 파일 이름이 앱 규칙과 정확히 일치한다.
- `syncversion.txt`가 특정 언어 파일이 아닌 `rawdata` 베이스 URL을 가리킨다.
- `sync-db.yml`의 `gh release upload` 목록에 새 파일이 들어 있다.
- GitHub Release에서 실제 파일이 보인다.
- 앱에서 해당 DB를 선택했을 때 올바른 URL을 요청한다.
- 다운로드 후 검색/작품 상세가 정상 동작한다.

## 참고

- `rawdata.db` 전체 DB는 언어별 DB보다 훨씬 클 수 있다. 저장 공간과 다운로드 용량을 먼저 확인한다.
- `violet-state.db.zst`는 수집 상태 보존용이고, 앱이 직접 받는 DB가 아니다.
- 이 저장소의 GitHub mirror와 WalnutPi의 모바일 DB 서버는 서로 별도 배포 경로다. 여기서 영어 DB를 만든다고 Pi 서버에도 자동으로 생기는 것은 아니다.
- 현재 한국어 DB 생성 방식이 새 언어 DB를 만들 때의 기준 구현이다.
