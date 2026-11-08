# 인스타 창의력 문제 자동 게시

매일 정해진 시간에 `puzzles/puzzles.yaml`의 문제를 위에서부터 하나씩 이미지로 만들어 인스타그램에 올립니다.

## 구성

| 경로 | 역할 |
|---|---|
| `puzzles/puzzles.yaml` | 문제 목록 (제목, 단서, 힌트, 정답, 캡션) |
| `config.yaml` | 계정 아이디, 포인트 색, 하단 문구 |
| `templates/card.html.j2` | 이미지 디자인 (1080×1350) |
| `scripts/render.py` | 문제 → JPEG 이미지 + 캡션 |
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

`puzzles/puzzles.yaml` 맨 아래에 기존 문제와 같은 형식으로 추가하고 저장(커밋)하면, 차례가 되었을 때 자동으로 게시됩니다.
형식은 `lock`(자물쇠), `sequence`(수열), `rows`(식·문장 나열) 세 가지입니다.

## 직접 실행하기

**Actions → 인스타 자동 게시 → Run workflow**
- `dry_run`을 체크하면 게시하지 않고 이미지만 만들어 결과물(Artifacts)로 받을 수 있습니다.
- `puzzle_id`에 번호를 넣으면 그 문제를 올립니다. 이미 올린 문제는 중복 게시를 막기 위해 거부합니다.

## 게시 시간 바꾸기

`.github/workflows/post.yml`의 `cron` 값을 바꿉니다. GitHub는 UTC 기준이라 **한국 시간에서 9시간을 뺀 값**을 적습니다.
예: 한국 시간 매일 오후 8시 7분 → `"7 11 * * *"`, 오전 9시 7분 → `"7 0 * * *"`
GitHub 서버 사정에 따라 실행이 몇 분 늦어질 수 있습니다.

## 실패했을 때

실행이 실패하면 GitHub가 가입한 이메일로 알려줍니다. Actions 탭에서 실패한 단계를 열면 한글 오류 메시지가 보입니다.
