# skiils-for-teachers

한국 학교 교사를 위한 **Claude Code 스킬** 모음입니다.

공문서 정리, 인수인계서 작성 등 학교 행정 업무를 자동화합니다.

## 포함된 스킬

| 스킬 | 설명 |
|------|------|
| **document-organizer** | 공문서 파일을 공문번호별로 자동 분류하여 폴더로 정리 |
| **handover-generator** | 공문서 파일명을 분석하여 업무 인수인계서를 자동 생성 |

## 설치 방법

### 방법 A: ZIP 다운로드 (추천)

> 개발 환경에 익숙하지 않다면 이 방법을 사용하세요. 가장 간단합니다.

**1단계.** 이 페이지 상단의 초록색 **`<> Code`** 버튼 → **`Download ZIP`** 클릭

**2단계.** 다운로드된 ZIP 파일을 압축 해제합니다.

**3단계.** 압축 해제한 폴더 안의 `skills` 폴더를 엽니다. 그 안에 `document-organizer`, `handover-generator` 폴더가 있습니다.

**4단계.** 원하는 스킬 폴더를 아래 경로에 복사합니다:

```
C:\Users\{본인 사용자명}\.claude\skills\
```

> **`.claude` 폴더가 안 보인다면:** 파일 탐색기 상단 메뉴에서 **보기 → 숨긴 항목** 체크를 켜세요.
>
> **`.claude` 폴더 자체가 없다면:** Claude Code를 한 번이라도 실행하면 자동 생성됩니다.

**5단계.** Claude Code를 재시작하면 설치 완료!

---

### 방법 B: 터미널 사용 (Git을 배워보고 싶다면)

> **Git**은 코드(파일)의 변경 이력을 추적하고 공유하는 도구입니다. 터미널에서 명령어 몇 줄로 파일을 다운로드하고 복사할 수 있습니다.
>
> 이 가이드는 Git을 처음 접하는 분을 위해 작성되었습니다. 순서대로 따라오시면 됩니다.

#### 사전 준비: Git 설치 확인

**1단계.** 먼저 Git이 이미 설치되어 있는지 확인합니다. PowerShell을 열어주세요.

PowerShell 여는 방법:
- **Windows 10:** 화면 왼쪽 아래 검색창에 `PowerShell` 입력 → **Windows PowerShell** 클릭
- **Windows 11:** 키보드에서 `Win + X` → **터미널** 클릭
- **공통:** 키보드에서 `Win + R` → `powershell` 입력 → Enter

**2단계.** PowerShell 창(파란색 또는 검은색 창)이 열리면, 아래 명령어를 그대로 복사해서 붙여넣고 Enter를 누르세요:

```powershell
git --version
```

- `git version 2.xx.x` 같은 메시지가 나오면 → Git이 설치된 것입니다. **"스킬 다운로드"** 단계로 건너뛰세요.
- `'git' is not recognized...` 오류가 나오면 → Git이 없는 것입니다. 아래 설치 단계를 따라주세요.

#### (Git이 없을 때만) Git 설치

**1단계.** 브라우저에서 https://git-scm.com 에 접속합니다.

**2단계.** 화면에 보이는 **Download for Windows** 버튼을 클릭하여 설치 파일을 다운로드합니다.

**3단계.** 다운로드된 설치 파일을 실행합니다. 설치 중에 여러 옵션이 나오는데, **모두 기본값(Next)으로 진행**하면 됩니다. 바꿀 필요 없습니다.

**4단계.** 설치가 끝나면 **PowerShell을 닫았다가 다시 열고**, `git --version`을 다시 입력하여 설치를 확인합니다.

#### 스킬 다운로드

**1단계.** PowerShell에서 아래 명령어를 붙여넣고 Enter를 누릅니다. 이 명령어는 GitHub에 올라와 있는 스킬 파일들을 내 컴퓨터로 복사하는 것입니다:

```powershell
git clone https://github.com/slowly007-beep/skiils-for-teachers.git
```

> 실행하면 `Cloning into 'skiils-for-teachers'...` 메시지가 나오면서 다운로드가 진행됩니다. 완료되면 현재 폴더에 `skiils-for-teachers` 폴더가 생깁니다.

#### 스킬 설치 (복사)

**2단계.** 아래 명령어 중 원하는 것을 붙여넣고 Enter를 누릅니다.

둘 다 한번에 설치 (추천):

```powershell
# skills 폴더 안의 모든 스킬을 .claude\skills\ 폴더로 복사합니다
Copy-Item -Recurse skiils-for-teachers\skills\* $env:USERPROFILE\.claude\skills\
```

document-organizer만 설치:

```powershell
# document-organizer 스킬만 .claude\skills\ 폴더로 복사합니다
Copy-Item -Recurse skiils-for-teachers\skills\document-organizer $env:USERPROFILE\.claude\skills\
```

handover-generator만 설치:

```powershell
# handover-generator 스킬만 .claude\skills\ 폴더로 복사합니다
Copy-Item -Recurse skiils-for-teachers\skills\handover-generator $env:USERPROFILE\.claude\skills\
```

#### 설치 확인

**3단계.** 파일이 제대로 복사되었는지 확인합니다:

```powershell
# .claude\skills 폴더 안에 어떤 폴더가 있는지 확인합니다
ls $env:USERPROFILE\.claude\skills\
```

`document-organizer`, `handover-generator` 등의 폴더가 보이면 성공입니다.

> **오류가 났다면:**
> - `Copy-Item: Cannot find path...` → `git clone`이 제대로 되었는지 확인하세요. PowerShell에서 `ls skiils-for-teachers` 를 입력했을 때 파일 목록이 보여야 합니다.
> - `.claude\skills` 경로가 없다는 오류 → Claude Code를 한 번이라도 실행한 적이 있어야 합니다. Claude Code를 실행한 뒤 다시 시도하세요.

**4단계.** Claude Code를 재시작하면 설치 완료!

---

## 사용법

### document-organizer (공문서 자동 분류)

Claude Code에서 다음과 같이 말하면 됩니다:

- `"공문서 정리해줘"` — 공문서를 공문번호별 폴더로 자동 분류
- `"공문 경로 변경"` — 정리 대상 폴더를 변경

**처음 실행하면** AI가 공문서 폴더 경로를 물어봅니다. 한 번 알려주면 이후에는 자동으로 기억합니다.

**필요 사항:** [Node.js](https://nodejs.org/) 설치 필요

**정리 전:**
```
공문 모음\
├── (인창고등학교-22206 (본문)) [제출] AI 중점학교 운영 신청.pdf
├── (인창고등학교-22206 (첨부)) [붙임1] 신청서.hwpx
├── (인창고등학교-22206 (첨부)) [붙임2] 계획서.hwpx
├── (인창고등학교-568 (본문)) [제출] 디지털튜터.pdf
└── (인창고등학교-568 (첨부)) [붙임1] 명단.xlsx
```

**정리 후:**
```
공문 모음\
├── (인창고등학교-22206 (본문)) [제출] AI 중점학교 운영 신청\
│   ├── (인창고등학교-22206 (본문)) [제출] AI 중점학교 운영 신청.pdf
│   ├── (인창고등학교-22206 (첨부)) [붙임1] 신청서.hwpx
│   └── (인창고등학교-22206 (첨부)) [붙임2] 계획서.hwpx
└── (인창고등학교-568 (본문)) [제출] 디지털튜터\
    ├── (인창고등학교-568 (본문)) [제출] 디지털튜터.pdf
    └── (인창고등학교-568 (첨부)) [붙임1] 명단.xlsx
```

### handover-generator (인수인계서 자동 생성)

- `"인수인계서 작성해줘"` — 공문 폴더를 분석하여 마크다운 인수인계서 생성
- `"공문 분석해줘"` — 공문 분류 결과만 확인
- `"인수인계서 검증해줘"` — 기존 인수인계서와 공문 목록 교차 검증

파일 내용은 열지 않으며, **파일명만으로** 업무를 분류하고 인수인계서를 작성합니다.

출력은 **노션 Import 호환 마크다운** (.md) 형식입니다.

## 대상 파일명 패턴

이 스킬들은 한국 공공기관 전자문서시스템(업무관리시스템)에서 내보낸 공문서 파일명을 기준으로 동작합니다:

```
(기관명-공문번호 (본문)) 문서 제목.pdf
(기관명-공문번호 (첨부)) [붙임1] 첨부 제목.hwpx
```

## 라이선스

MIT License
