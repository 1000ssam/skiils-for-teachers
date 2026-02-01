# skiils-for-teachers

한국 학교 교사를 위한 **Claude Code 스킬** 모음입니다.

공문서 정리, 인수인계서 작성 등 학교 행정 업무를 자동화합니다.

## 포함된 스킬

| 스킬 | 설명 |
|------|------|
| **document-organizer** | 공문서 파일을 공문번호별로 자동 분류하여 폴더로 정리 |
| **handover-generator** | 공문서 파일명을 분석하여 업무 인수인계서를 자동 생성 |

## 설치 방법

### 1. 이 리포지토리 클론

```bash
git clone https://github.com/slowly007-beep/skiils-for-teachers.git
```

### 2. 원하는 스킬을 `~/.claude/skills/`에 복사

```bash
# document-organizer 설치
cp -r skiils-for-teachers/skills/document-organizer ~/.claude/skills/

# handover-generator 설치
cp -r skiils-for-teachers/skills/handover-generator ~/.claude/skills/
```

Windows에서는:

```powershell
# document-organizer 설치
Copy-Item -Recurse skiils-for-teachers\skills\document-organizer $env:USERPROFILE\.claude\skills\

# handover-generator 설치
Copy-Item -Recurse skiils-for-teachers\skills\handover-generator $env:USERPROFILE\.claude\skills\
```

### 3. 설정 (document-organizer만 해당)

```bash
cd ~/.claude/skills/document-organizer
cp config.example.json config.json
```

`config.json`을 열어서 공문서가 저장된 경로를 입력합니다:

```json
{
  "profiles": {
    "work": {
      "path": "C:\\Users\\{본인 사용자명}\\Desktop\\공문 모음"
    }
  }
}
```

## 사용법

### document-organizer

Claude Code에서 다음과 같이 말하면 됩니다:

- `"공문서 정리"` — 기본 프로필 경로의 공문서를 자동 분류
- `"공문 분류"` — 동일
- `"personal 프로필로 공문 정리"` — 특정 프로필 사용

**필요 사항:** Node.js 설치 필요

**작동 원리:** 공문 파일명의 패턴 `(기관명-공문번호 (본문/첨부))`을 인식하여, 같은 공문번호의 본문+첨부를 하나의 폴더에 모아줍니다.

### handover-generator

- `"인수인계서 작성"` — 공문 폴더를 분석하여 마크다운 인수인계서 생성
- `"공문 분석해줘"` — 공문 분류 결과만 확인
- `"인수인계서 검증"` — 기존 인수인계서와 공문 목록 교차 검증

**작동 원리:** 공문 파일명에서 기관명, 공문번호, 제목을 추출하고, 업무 카테고리별로 자동 분류한 뒤 구조화된 인수인계서를 작성합니다. 파일 내용은 열지 않으며, 파일명만으로 동작합니다.

**출력 형식:** 노션 Import 호환 마크다운 (.md)

## 대상 파일명 패턴

이 스킬들은 한국 공공기관 전자문서시스템에서 내보낸 공문서 파일명을 기준으로 동작합니다:

```
(기관명-공문번호 (본문)) 문서 제목.pdf
(기관명-공문번호 (첨부)) [붙임1] 첨부 제목.hwpx
```

예시:
```
(인창고등학교-22206 (본문)) [제출] AI 중점학교 운영 신청.pdf
(인창고등학교-22206 (첨부)) [붙임1] 신청서.hwpx
```

## 라이선스

MIT License
