# 인스타 창의력 문제 게시

`puzzles/puzzles.yaml`의 문제를 이미지로 만들어 인스타그램에 올립니다.
**자동 예약 게시는 꺼져 있고, 검토를 마친 문제만 번호를 지정해 올립니다.**

## 구성

| 경로 | 역할 |
|---|---|
| `puzzles/puzzles.yaml` | 문제 목록 (제목, 단서, 힌트, 정답, 캡션) |
| `config.yaml` | 계정 아이디, 포인트 색, 하단 문구 |
| `templates/reel.html.j2` | 릴스 화면 디자인 (1080×1920, 후킹 문구 + 문제) |
| `templates/card.html.j2` | 피드 이미지 디자인 (1080×1350) |
| `assets/music/tick_tock.m4a` | 직접 합성한 저작권 없는 배경음 (`scripts/make_music.py`로 다시 만들 수 있음) |
| `scripts/render.py` | 문제 → 릴스 MP4 또는 피드 JPEG + 캡션 |
| `scripts/post_queue.py` | 다음에 올릴 문제 고르기 |
| `scripts/publish.py` | 인스타 API로 게시 |
| `state/posted.json` | 게시 기록 (자동 갱신, 직접 수정하지 마세요) |
| `.github/workflows/post.yml` | 매일 자동 실행 설정 |

## 처음 한 번만 할 일

저장소의 **Settings → Secrets and variables → Actions → New repository secret**에 두 개를 등록합니다.

| 이름 | 값 |
|---|---|
| `IG_ACCESS_TOKEN` | Meta에서 받은 액세스 토큰 (EAA…로 시작) |
| `IG_USER_ID` | 비즈니스 설정 → Instagram 계정에 보이는 ID 숫자 |

## 새 문제 추가

`puzzles/puzzles.yaml` 맨 아래에 기존 문제와 같은 형식으로 추가하고 저장(커밋)합니다. 목록에 넣는다고 바로 올라가지는 않고, 위의 '게시하기'로 번호를 지정해야 올라갑니다.
형식은 `exam`(시험지, 릴스 전용), `lock`(자물쇠), `sequence`(수열), `rows`(식·문장 나열) 네 가지입니다. 각 항목 설명은 `puzzles.yaml` 안 주석에 있습니다.

## 게시하기

**Actions → 인스타 자동 게시 → Run workflow**

| 입력 | 설명 |
|---|---|
| `puzzle_id` | 올릴 문제 번호 |
| `format` | `reel`(릴스 영상, 기본) 또는 `feed`(피드 이미지) |
| `mode` | `preview` 파일만 만들기 → `upload-test` 인스타 업로드·처리까지만(게시 안 함) → `publish` 실제 게시 |

- 만든 파일은 실행 결과 화면 아래 **Artifacts**에서 내려받아 확인할 수 있습니다.
- `publish`에서 이미 올린 번호를 넣으면 중복 게시를 막기 위해 거부합니다.

## 릴스

- 문제 화면 한 장을 9초 동안 보여주고 배경음을 깝니다. 길이는 `config.yaml`의 `reel_seconds`, 문제별 `seconds`로 바꿉니다.
- `config.yaml`의 `reel_timer`를 `true`로 바꾸면 '생각할 시간' 카운트다운 막대가 나타납니다.
- 맨 위 큰 문구는 문제의 `hook` 항목입니다. 없으면 제목이 들어갑니다.
- API로는 인스타 음악 라이브러리 곡을 붙일 수 없어 배경음을 영상에 직접 넣습니다. 다른 무료 음원을 쓰려면 `assets/music/`에 넣고 `config.yaml`의 `reel_music`을 바꿉니다.
- 릴스 화면 위·아래와 오른쪽은 앱 버튼에 가려지므로, 내용이 아래쪽 안전 영역을 넘으면 만들기 단계에서 오류로 알려줍니다.

## 매일 자동 게시를 다시 켜려면

`.github/workflows/post.yml` 맨 위의 `schedule` 주석을 풀고, `puzzle_id`를 `required: false`로 바꿉니다.
`cron`은 UTC 기준이라 **한국 시간에서 9시간을 뺀 값**을 적습니다. 예: 매일 오후 8시 7분 → `"7 11 * * *"`

## 실패했을 때

실행이 실패하면 GitHub가 가입한 이메일로 알려줍니다. Actions 탭에서 실패한 단계를 열면 한글 오류 메시지가 보입니다.
