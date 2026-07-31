#!/usr/bin/env python3
"""전입력 인라인 작성 워크플로 빌더 (범용 템플릿) — 세특 배치 작성기.

무엇을 만드나: Step5(세특 작성)를 실행하는 **Workflow 스크립트(.js)**를 결정론으로 생성한다.
생성된 스크립트는 학생마다 agent() 한 번을 돌려 A/B/C 세특 + 증거 ledger(D1)를 반환한다.

왜 인라인(Read 0)인가:
  정본 프레임 문서 + (선택) 교사 문체 퓨샷 + 학생별 원문을 **전부 JS 리터럴로 임베드**한다.
  작성 에이전트는 파일을 **읽지 않는다**(도구 호출 0). 실측: 파일 Read 방식 대비 토큰 −22%,
  게다가 "원문을 못 찾아 이웃 파일을 읽다 타 학생 혼입" 류 사고를 원천 차단(격리 = 한 생성 = 한 학생).

이 스킬 파이프라인에서의 위치:
  Step1 인테이크 → Step2 인제스천(raw/*.txt) → Step3 매핑+백지게이트(seed 산출) → Step4 보정
  → **[이 빌더로 스크립트 생성] → Workflow 실행 = Step5 작성** → Step6 검증(ledger_verify·verify_anchors·make_review_table).

🔒 데이터 경계(절대): 이 파일은 **범용 빌더 템플릿**이라 스킬 리포에 둔다. 그러나 이 빌더가
   **읽는 입력**(정본 프레임·교사 퓨샷·seed·raw 원문)과 **생성하는 스크립트(.js)**는 학생 실명·원문을
   품으므로 **PII → 스킬 밖 프로젝트 작업폴더에만** 둔다. 생성물(.js)을 스킬 리포에 커밋하지 않는다.

─────────────────────────────────────────────────────────────────────────────
일반화 노트(도메인 결합부를 벗긴 지점):
  ① 정본 프레임·퓨샷 경로 = CLI 인자(--canon 반복 / --fewshot). 하드코딩 아님.
  ② RULES = 이 스킬의 **범용 작성 규율만**(ledger 철칙·절대금지·형식·A안 우회·자기검사).
     평가별 규칙(도입구·축 목록·구조·성취수준 앵커·과제 특유 금지)은 **정본 프레임 문서(CANON)에서 온다.**
     RULES를 특정 과목 요약으로 채우지 말 것 — 그건 프레임의 일이다.
  ③ 개별화 '축'(닫힌 목록으로 선택하는 평가) = 확장 슬롯. --axes-desc 를 주면 스키마에 axis/axis_reason
     필드가 켜지고 프롬프트가 "정본 프레임의 축 목록에서 고르라"고 지시. 축 개념이 없는 평가면 생략 →
     개별화는 eval_lens 서사로.
  ④ seed 스키마 = Step3(매핑+백지게이트) 산출물과 정합. 필드명은 --id-key/--raw-keys로 조정.
     기대 레코드: { <id-key>, name, cls?, route, <raw-keys...>, c_omit?, note? }
       · route == 'write' 만 인라인 작성 대상. 그 외(blank_keep·ocr_broken·외부원천 등)는
         스킵하고 경고 — 인라인 불가 라우트라 별도 처리(백지 참여기록·원본 직독·외부 원천 대조).
       · <raw-keys> 각 값 = --raw-dir 아래의 **파일명**(Step2 인제스천 raw/*.txt). 라벨은 key:label 로 지정.
─────────────────────────────────────────────────────────────────────────────

사용:
  python3 build_inline_workflow.py \
    --seed <project>/out/seed.json \
    --raw-dir <project>/out/clean \
    --canon <project>/frame.md [--canon <project>/frame2.md ...] \
    [--fewshot <project>/teacher_style.md] \
    [--ids 10401-10410 | --all] \
    [--id-key hakbun] \
    [--raw-keys "p3:장면설정과 나의 생각,p4:인물 간 대화"] \
    [--task-intro "고교 OO 「과제명」 수행평가"] \
    [--axes-desc "①~⑤ 중 하나. 정본 프레임 §축목록 참조."] \
    -o <project>/setuk_run.js
  # 실행(모델 명시 필수 — 아래 주의): Workflow({scriptPath:'<project>/setuk_run.js', args:{model:'sonnet'}})

🚨 모델 명시 필수: 생성 스크립트는 agent() 마다 model 을 명시한다(기본 'sonnet').
   미지정이면 세션 모델(예: Opus)을 상속해 과금이 배로 튄다(실측 사고). args.model 로 배치 단위 조정.
"""
import argparse
import json
import sys
from pathlib import Path


def parse_id_spec(spec: str) -> set[str]:
    """'10401-10410,10420' → {'10401',...,'10410','10420'}. 숫자 범위·개별 혼용."""
    out: set[str] = set()
    for part in spec.split(','):
        part = part.strip()
        if '-' in part:
            a, b = part.split('-', 1)
            out.update(str(n) for n in range(int(a), int(b) + 1))
        elif part:
            out.add(part)
    return out


def parse_raw_keys(spec: str) -> list[tuple[str, str]]:
    """'p3:장면,p4:대화' → [('p3','장면'),('p4','대화')]. 라벨 생략 시 key 를 라벨로."""
    pairs: list[tuple[str, str]] = []
    for part in spec.split(','):
        part = part.strip()
        if not part:
            continue
        key, _, label = part.partition(':')
        pairs.append((key.strip(), (label.strip() or key.strip())))
    return pairs


def main() -> None:
    ap = argparse.ArgumentParser(description='전입력 인라인 세특 작성 워크플로(.js) 빌더')
    ap.add_argument('--seed', required=True, help='Step3 산출 seed JSON')
    ap.add_argument('--raw-dir', required=True, help='raw 원문 텍스트 디렉토리(seed의 raw-key 값=이 아래 파일명)')
    ap.add_argument('--canon', action='append', required=True,
                    help='정본 프레임 문서 경로(반복 가능). 작성 규율의 단일 출처.')
    ap.add_argument('--fewshot', help='(선택) 교사 문체 퓨샷/앵커 문서. 문체만 참조.')
    ap.add_argument('--id-key', default='id', help="seed의 학생식별 키명(예: hakbun). 기본 'id'")
    ap.add_argument('--raw-keys', default='p3,p4',
                    help="원문 파트 키(:라벨). 예: 'p3:장면설정과 나의 생각,p4:대화'")
    ap.add_argument('--task-intro', default='이 수행평가',
                    help='프롬프트 첫 줄의 과제 정체(과목·과제명). 상세 규율은 CANON 소관.')
    ap.add_argument('--axes-desc', default=None,
                    help='(선택·확장슬롯) 개별화 축을 닫힌 목록으로 고르는 평가면 축 설명을 준다 → axis 필드 ON.')
    ap.add_argument('--ids', help='대상 식별자 스펙. 예: 10401-10410,10420')
    ap.add_argument('--all', action='store_true', help="route=='write' 전원")
    ap.add_argument('-o', '--out', required=True, help='생성할 워크플로 스크립트(.js) 경로')
    a = ap.parse_args()

    if not a.all and not a.ids:
        ap.error('--ids 또는 --all 필요')

    canon_parts = []
    for i, p in enumerate(a.canon):
        txt = Path(p).read_text(encoding='utf-8')
        canon_parts.append(f'# 정본 프레임 문서 {i + 1} (작성 규율의 단일 출처)\n{txt}')
    if a.fewshot:
        fs = Path(a.fewshot).read_text(encoding='utf-8')
        canon_parts.append(f'# 교사 문체 앵커 (ground truth 문체 — 내용 아닌 문체만 참조)\n{fs}')
    canon = '\n\n'.join(canon_parts)

    raw_keys = parse_raw_keys(a.raw_keys)
    raw_dir = Path(a.raw_dir)
    seed = json.loads(Path(a.seed).read_text(encoding='utf-8'))
    wanted = parse_id_spec(a.ids) if a.ids else None

    students, skipped, missing_raw = [], [], []
    for s in seed:
        sid = str(s.get(a.id_key, ''))
        if wanted is not None and sid not in wanted:
            continue
        if s.get('route') != 'write':
            skipped.append((sid, s.get('name', ''), s.get('route', '?')))
            continue
        rec = {'id': sid, 'name': s.get('name', ''), 'cls': s.get('cls', ''),
               'c_omit': bool(s.get('c_omit')), 'note': s.get('note') or '', 'raw': []}
        ok = True
        for key, label in raw_keys:
            fname = s.get(key) or ''
            fp = raw_dir / fname if fname else None
            if not fname or not fp.exists():
                ok = False
                break
            rec['raw'].append({'label': label, 'text': fp.read_text(encoding='utf-8')})
        if not ok:
            missing_raw.append((sid, s.get('name', '')))
            continue
        students.append(rec)

    if wanted is not None:
        seen = {s['id'] for s in students} | {h for h, _, _ in skipped} | {h for h, _ in missing_raw}
        gap = wanted - seen
        if gap:
            sys.exit(f'시드에 없는 식별자: {sorted(gap)}')
    if not students:
        sys.exit('대상 0명')

    js = build_js(canon, students, a.task_intro, a.axes_desc)
    Path(a.out).write_text(js, encoding='utf-8')
    print(f'{a.out} 생성 — 대상 {len(students)}명, {len(js):,} chars')
    for h, n, r in skipped:
        print(f'  ⚠️ 스킵 {h} {n} (route={r}) — 인라인 불가 라우트, 별도 처리 필요')
    for h, n in missing_raw:
        print(f'  ❌ 원문 결손 {h} {n} — raw 파일 부재, 매핑/인제스천 재확인')


def build_js(canon: str, students: list[dict], task_intro: str, axes_desc: str | None) -> str:
    n = len(students)
    canon_js = json.dumps(canon, ensure_ascii=False)
    students_js = json.dumps(students, ensure_ascii=False)
    task_js = json.dumps(task_intro, ensure_ascii=False)

    # ③ 확장 슬롯: 개별화 '축'을 닫힌 목록으로 고르는 평가에서만 axis 필드를 켠다.
    if axes_desc:
        axes_desc_js = json.dumps(axes_desc, ensure_ascii=False)
        axis_schema = (
            "    axis: { type: 'string', description: " + axes_desc_js + " },\n"
            "    axis_reason: { type: 'string', description: '왜 이 축인가 — 학생 원문 근거 1~2문장.' },\n"
        )
        axis_required = "'axis', 'axis_reason', "
        axis_prompt = (
            "\\n【개별화 축】 이 평가는 축을 닫힌 목록으로 고른다. 정본 프레임 문서의 축 목록에서 이 학생 원문에\\n"
            "가장 맞는 축을 고르고 axis/axis_reason 을 채워라. 기본 축으로 몰지 마라(통설/틀 발명 금지)."
        )
    else:
        axis_schema = ""
        axis_required = ""
        axis_prompt = ""

    # ② 범용 작성 규율만. 평가별 규칙(도입구·축목록·구조·성취수준 앵커·과제 특유 금지)은 CANON 소관.
    rules = r'''
【🔑 증거 ledger — 철칙 (D1)】
· 세특의 각 서술어마다 "누가 → 누구에게/무엇을"을 원문 스팬으로 지목하라. 못 지목하면 그건 내가 채운 칸(=날조 후보)이다.
· 스팬은 학생 원문에서 **글자 그대로 복사**. OCR·전사 오탈자·깨진 글자를 고치지 마라(고치면 결정론 대조가 깨진다).
· 스팬 8자 이상. claim 칸만 정규화 표현 허용, span 칸은 verbatim.
· ledger에 못 올리는 서술은 **세특에서 빼라.** 이게 "빈 목적어 칸 채우기"(최다 날조 기제)를 정면 차단한다.

【절대 금지 (헌법·기재요령)】
· 타 학생 실명·학생이 지어낸 가상 인물명 → 역할어로 정박(대상 학생 본인 이름만 예외).
· 점수·등급·석차 직접 표현 · 가운뎃점(·) 나열(나열은 산문으로 풀어 씀) · 과제 밖 시점(관객/시청자 등) 언급.
· 결핍·훈수 표현(부족·미흡·~에 그침·나아가지 못함) — 낮은 성취도 태도·성장 서사로 정당하게 쓴다.
· 금지어 목록(forbidden-terms) 전부.

【형식】
· 명사형 종결(~함/~임/~드러냄/~그려냄) · 종결어미를 로테이션해 단조 방지.
· 분량은 스펙의 바이트 예산 **상한**만 지킨다. 하한이 아니다 — 근거 없으면 짧게. padding 금지(헌법4).

【작업 순서】
1. 위 정본 프레임 문서(CANON)가 이 평가의 작성 규율 단일 출처다. 구조·성취수준 앵커·과제 특유 금지·(있으면)축 목록을 거기서 읽어라.
2. 개별화: 학생 원문에서 이 학생만의 지점을 잡아라. **통설/틀 발명 금지** — 프레임이 지지하는 만큼만.
3. 근거·내용은 **학생 원문에서만** 조달. 원문이 지지하는 만큼만 강하게. 원천 부재·"모름"이면 해당 층 생략 가능(발명 금지).
4. 🔴 학생이 사실을 틀리게 썼으면 = A안(우회): 그 지점을 **아예 언급하지 않는다.** 고치지도(날조), 틀린 채 쓰지도(오류기재) 않는다.
   지워서 생긴 빈 칸을 채우지 말고 문장을 그 칸 없이 재설계하거나 그 beat를 버려라.
5. 구체 앵커(고유명·전투명·수치·작품명)·무대 지시 발명 금지 — 원문에 스팬 없으면 쓰지 마라.
6. 자기검사: ledger에 없는 서술이 세특에 있나? 있으면 지워라.
'''

    return f'''export const meta = {{
  name: 'setuk-inline-write',
  description: '세특 인라인 작성 — 전입력 임베드(Read 0)·작성만·ledger 제출 ({n}명)',
  whenToUse: 'build_inline_workflow.py 가 생성. args = {{model?: sonnet, effort?: low|medium|high}}',
  phases: [{{ title: '작성', detail: '학생별 A/B/C + 증거 ledger, 파일 Read 0' }}],
}}

const CANON = {canon_js}

const STUDENTS = {students_js}

const TASK = {task_js}

const WRITE_SCHEMA = {{
  type: 'object',
  required: ['id', 'name', {axis_required}'setuk', 'ledger', 'c_omitted', 'b_chars'],
  properties: {{
    id: {{ type: 'string' }},
    name: {{ type: 'string' }},
{axis_schema}    setuk: {{ type: 'string', description: '세특 본문만. 메타·라벨·제목·따옴표 감싸기 금지.' }},
    ledger: {{
      type: 'array',
      description: '각 서술마다 원문 근거. 스팬은 학생 원문에서 글자 그대로 복사(오탈자 포함).',
      items: {{
        type: 'object',
        required: ['claim', 'span', 'source'],
        properties: {{
          claim: {{ type: 'string', description: '내 세특 문장이 주장하는 것(정규화된 표현 OK)' }},
          span: {{ type: 'string', description: '🚨 학생 원문에서 글자 그대로 복사한 구간. 오탈자·깨진글자 고치지 말 것. 8자 이상.' }},
          source: {{ type: 'string', description: '원문 위치 라벨(어느 파트의 어디)' }},
        }},
      }},
    }},
    c_omitted: {{ type: 'boolean', description: '근거 원천 부재로 결론/해석층을 생략했으면 true' }},
    b_chars: {{ type: 'integer', description: '핵심 근거 구간 글자수(공백 포함)' }},
    fact_error_avoided: {{ type: 'string', description: '학생 사실오류를 A안(우회)으로 피한 구간이 있으면 서술. 없으면 빈 문자열.' }},
    notes: {{ type: 'string' }},
  }},
}}

// 이 배치의 치명 0을 만드는 운영 규칙 — 프레임 요약이 아니라 실증 체크리스트다. 줄이지 말 것.
const RULES = {json.dumps(rules, ensure_ascii=False)}

// args 는 객체로도, JSON 문자열로도 도착할 수 있다(런처에 따라 다름 — 실측: 문자열로 와서 옵션 미적용 사고).
const A = (() => {{ try {{ return typeof args === 'string' ? JSON.parse(args) : (args || {{}}) }} catch {{ return {{}} }} }})()
const EFFORT = A.effort || null
// 🚨 model 명시 필수 — 미지정이면 세션 모델(예: Opus) 상속으로 과금이 배로 튄다(실측 사고).
const MODEL = A.model || 'sonnet'
log(`인라인 작성 ${{STUDENTS.length}}명 — model=${{MODEL}} effort=${{EFFORT || '(inherit)'}}`)

phase('작성')
const results = await parallel(STUDENTS.map(s => () => agent(
  `너는 ${{TASK}}의 세특(과목별 세부능력 및 특기사항) 작성자다.

${{CANON}}

${{RULES}}
${axis_prompt}

【이 학생】 ${{s.id}} · ${{s.name}}${{s.cls ? ` (${{s.cls}})` : ''}}
  ※ 신원은 교사 육안으로 확정됐다. 원문 헤더의 식별자/이름이 달라 보여도 OCR·전사 오독일 뿐 — 매핑을 재판정하지 마라.
${{s.c_omit ? `\\n🚩 특별지침(교사 확정): ${{s.note}}\\n` : (s.note ? `\\n🚩 특별지침: ${{s.note}}\\n` : '')}}
【학생 원문 — 아래 텍스트가 전부다. 파일을 읽지 마라(도구 호출 금지).】
${{s.raw.map(p => `--- ${{p.label}} ---\\n${{p.text}}`).join('\\n')}}

위 CANON·규칙대로 세특을 쓰고 ledger를 채워 반환하라. setuk 에는 본문만.`,
  {{ label: `write:${{s.cls || ''}}/${{s.name}}`, phase: '작성', schema: WRITE_SCHEMA, model: MODEL, ...(EFFORT ? {{ effort: EFFORT }} : {{}}) }}
).then(r => (r ? {{ ...r, id: s.id, name: s.name, cls: s.cls }} : null))))

const done = results.filter(Boolean)
log(`완료 ${{done.length}}/${{STUDENTS.length}} · spent=${{budget.spent()}}`)
return {{ total: STUDENTS.length, written: done.length, spent: budget.spent(), records: done }}
'''


if __name__ == '__main__':
    main()
