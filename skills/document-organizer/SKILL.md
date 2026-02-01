---
name: document-organizer
description: "한국 공공기관 공문서 파일들을 공문 번호별로 자동 분류하여 폴더로 정리합니다. 같은 공문 번호를 가진 파일들(본문 + 첨부파일)을 하나의 폴더에 모아주며, 폴더명은 본문 파일명을 사용합니다. Use when: (1) 공문서 정리, (2) 공문 분류, (3) 공문 파일 정리가 필요할 때. 파일명 패턴은 references/pattern_examples.md 참조."
allowed-tools: Bash(node *), Read, Glob, Grep
---

# Document Organizer

## Overview
Windows 환경에서 한국 공공기관 공문서 파일을 공문 번호별로 자동 분류합니다.

**런타임:** Node.js (필수)

## Workflow

Claude는 아래 순서를 **반드시** 따른다.

### Step 1. Config 로드
```
Read → config.json  (이 스킬 디렉토리 내)
```
- 파일 없음 → 사용자에게 경로 요청 → config.json 생성
- 파일 있음 → `profiles.<default_profile>.path` 추출

### Step 2. 스크립트 실행
```bash
node "<이 스킬의 디렉토리>/scripts/organize.mjs"
```
- 스킬 디렉토리는 `~/.claude/skills/document-organizer` (설치 위치에 따라 다를 수 있음)
- 프로필 지정 시: `node organize.mjs <config_path> <profile_name>`
- 스크립트가 config.json을 직접 읽고, 대상 폴더를 스캔하고, 정리까지 한번에 수행

### Step 3. 결과 보고
스크립트 출력을 사용자에게 전달 (생성 폴더 수, 이동 파일 수)

**이것이 전부다.** Config 읽기 1턴 + 스크립트 실행 1턴 = **최대 2턴**으로 완료해야 한다.

## 파일명 패턴

```
(기관명-공문번호 (본문)) [제출] 제목.확장자
(기관명-공문번호 (첨부)) [붙임N] 제목.확장자
```

정규표현식:
```
/\(([^-]+)-(\d+)\s+\((본문|첨부)\)\)/
```

상세 예시 → `references/pattern_examples.md`

## Configuration

**위치:** 이 스킬 디렉토리 내 `config.json`

처음 사용 시 `config.example.json`을 `config.json`으로 복사한 뒤, 경로를 수정한다.

```json
{
  "version": "1.0",
  "default_profile": "work",
  "profiles": {
    "work": {
      "name": "업무용 공문 폴더",
      "path": "C:\\Users\\{사용자명}\\Desktop\\공문 모음",
      "last_used": null
    }
  }
}
```

**경로 규칙:**
- 반드시 Windows 절대경로 사용 (`C:\\...`)
- JSON 내 역슬래시는 이스케이프 (`\\`)
- `/c/Users/...` 같은 Git Bash 스타일 경로 사용 금지

상세 구조 → `references/config_structure.md`

## Commands

| 사용자 입력 | 동작 |
|---|---|
| `"공문서 정리"` / `"공문 정리"` / `"공문 분류"` | 기본 프로필로 정리 |
| `"personal 프로필로 공문 정리"` | 특정 프로필 사용 |
| `"공문 정리 설정 초기화"` | config.json 삭제 |

프로필 추가/변경은 config.json을 직접 Edit하면 된다.

## Output Example

```
공문 모음\
├── (인창고등학교-22206 (본문)) [제출] AI 중점학교 운영 신청\
│   ├── (인창고등학교-22206 (본문)) [제출] AI 중점학교.pdf
│   ├── (인창고등학교-22206 (첨부)) [붙임1] 신청서.hwpx
│   └── (인창고등학교-22206 (첨부)) [붙임2] 계획서.hwpx
└── (인창고등학교-568 (본문)) [제출] 디지털튜터\
    ├── (인창고등학교-568 (본문)) [제출] 디지털튜터.pdf
    └── (인창고등학교-568 (첨부)) [붙임1] 명단.xlsx
```

## Scripts

- `scripts/organize.mjs` — 메인 정리 스크립트 (Node.js)

## Notes
- 본문 파일이 없는 공문은 `공문_기관명-번호` 폴더명 사용
- 패턴 미매칭 파일은 이동하지 않고 원본 위치 유지
- 이미 폴더가 존재하면 기존 폴더에 파일 추가
