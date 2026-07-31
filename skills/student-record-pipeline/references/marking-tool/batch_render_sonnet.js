export const meta = {
  name: 'sonnet-render-compare',
  description: '교사 마킹 + 레벨로 세특 렌더(격리 배치, 소넷 병렬)',
  phases: [{ title: 'Sonnet렌더', detail: '학생별 병렬 렌더(sonnet)', model: 'sonnet' }],
}

/* args 는 tool/render_args.py 가 만든다 — 손으로 만들지 않는다.
     {contract: "<이 라인의 render_contract.md 절대경로>", drafts_dir: "<초안이 저장될 폴더>",
      surface: {byte_max, forbidden, repeat_whitelist}, students: [...]}
   계약서 경로를 이 스크립트에 박지 않는 이유: 라인(실작업/레벨실험)마다 계약서 내용이 달라서,
   하드코딩하면 다른 라인의 규칙으로 렌더되는 조용한 사고가 난다(HANDOFF 2026-07-28 §2).
   그래서 경로가 없으면 추측하지 않고 즉시 멈춘다. */
const SCHEMA = {
  type: 'object', additionalProperties: false,
  properties: {
    setuk: { type: 'string' },
    ledger: { type: 'array', items: { type: 'object', additionalProperties: false,
      properties: { claim: { type: 'string' }, span: { type: 'string' } }, required: ['claim', 'span'] } },
    bytes_est: { type: 'integer' },
    notes: { type: 'string' },
    /* 교사 기타 요구사항을 못 지켰을 때의 사유 — 교사에게 **직접 보이는** 칸이다(교사 요청 2026-07-31).
       notes 는 표면 처리 메모라 화면에 안 뜬다. 요구사항을 물리는 건 교사가 알아야 할
       판단이므로 별도 칸으로 뽑아 화면 상단 배너로 띄운다. 지킨 경우엔 빈 문자열. */
    unmet: { type: 'string' },
  },
  required: ['setuk', 'ledger', 'bytes_est', 'notes', 'unmet'],
}

phase('Sonnet렌더')
const input = typeof args === 'string' ? JSON.parse(args) : args
const CONTRACT = input?.contract
const DRAFTS = input?.drafts_dir
const SURFACE = input?.surface || {}
const students = input?.students || []
if (!CONTRACT) throw new Error('args.contract 가 없다 — python3 tool/render_args.py 로 args를 만들 것(계약서 경로 누수 방지)')
if (!DRAFTS) throw new Error('args.drafts_dir 가 없다 — 초안을 어디에 쓸지 모르면 교사 화면에 아무것도 안 뜬다')
if (!students.length) throw new Error('args.students 가 비었다')

/* 교사가 [다시]를 누른 이력. 같은 실수를 반복하지 않게 프롬프트에 싣는다.
   사유가 비어 있으면 직전 초안 자체를 붙여 "이건 물렸다, 다르게 써라"로 처리한다. */
function rejectBlock(s) {
  const rs = s.rejects || []
  if (!rs.length) return ''
  /* 회차별 스냅샷이 있으면 각 회차 밑에 그 본문을 붙인다 — "이 버전들이 전부 물렸다"를
     보여야 같은 문장을 다시 내지 않는다. 스냅샷 도입 전 마킹은 setuk 이 비어 있어
     예전처럼 prev_setuk(디스크에서 읽은 직전 초안) 하나로 대신한다. */
  const hasSnap = rs.some(r => r.setuk)
  const reasons = rs.map((r, i) => {
    const why = r.reason || (r.setuk ? '(사유 없음 — 아래 본문 자체를 물린 것이다)'
                                     : '(사유 없음 — 아래 직전 초안이 물린 문장이다)')
    return `  ${i + 1}. ${why}` + (r.setuk ? `\n     ↳ 물린 본문: "${r.setuk}"` : '')
  }).join('\n')
  const prev = (!hasSnap && s.prev_setuk)
    ? `\n직전 초안(교사가 물린 문장 — 이 문장을 그대로 다시 쓰지 마라):\n"${s.prev_setuk}"` : ''
  const thin = rs.length >= 3
    ? '\n※ 3회 이상 물렸다. 표현을 더 꾸미지 마라 — 재료가 얇을 가능성이 높으니 더 짧고 정확하게 써라.'
    : ''
  return `\n**교사 반려 이력(${rs.length}회) — 다음 규칙보다 우선한다:**\n${reasons}${prev}${thin}\n`
}

/* 기타 요구사항 — 분량·톤·강조점, 또는 교사가 수업에서 관찰한 사실(계약서 §0-3).
   표면 규칙은 못 뚫고, 계약서 문체 기본값은 이긴다. 교사가 준 사실을 쓰면 ledger 에
   `기타 요구사항:` 접두사를 강제한다 — 안 붙으면 화면에서 원문 근거처럼 보여 날조와 구분이 안 된다. */
function extraBlock(s) {
  const x = (s.extra || '').trim()
  if (!x) return ''
  return `\n**교사 기타 요구사항(계약서 §0-3) — 표면 규칙(§2) 다음으로 우선한다:**\n  "${x}"\n`
    + `  · 분량 지시가 있으면 재료 두께 추정보다 이게 우선이다(교사는 그 학생을 봤고 너는 안 봤다).\n`
    + `  · 여기서 받은 **사실**을 쓰면 ledger 의 span 을 \`기타 요구사항: <교사가 쓴 말 그대로>\` 로 적어라. 불려 쓰지 마라.\n`
    + `  · §0(하드바인딩)·§1-2(레벨)와 정면충돌하면 따르지 마라. 대신 **\`unmet\` 칸에 왜 못 지켰는지 한 줄로 적어라.**\n`
    + `    이 칸은 교사가 화면에서 바로 읽는다. 쉬운 말로, 교사에게 하듯이 써라 —\n`
    + `    §0·§1-2 같은 조항 번호나 바이트 수치를 늘어놓지 말고 "무엇을 요청했는데 왜 못 했는지"만.\n`
    + `    예: "최대 분량으로 채우려면 선생님이 표시하지 않은 내용을 지어내야 해서 재료만큼만 썼습니다."\n`
}

/* 재료 블록 — 하이라이트가 **0개일 때만** 원문을 싣는다(위임).
   부분 마킹은 하드바인딩이다. 개수로만 가른다 — "부실해 보이면 원문도" 류의 판단을 넣으면
   '칠한 것 + 원문'이 섞여 하드바인딩이 조용히 샌다(계약서 §0-2). */
function materialBlock(s) {
  if (s.highlights.length) {
    const hl = s.highlights.map((h, i) => `  [${i + 1}](${h.section}) "${h.text}"  — 왜: ${h.why || '(없음)'}`).join('\n')
    return {
      rule: `**절대 규칙(하드바인딩)**: 아래 하이라이트 span + 그 '왜' + 역량 + 활동맥락, 이게 사실 원천의 전부다. 여기 없는 사실(다른 전투·인물·사건)을 절대 끌어오지 마라.
🚨 **재료 두께를 하이라이트 개수로 재지 마라(교사 결정).** 단 한 문장에도 깊이 있는 이해가 드러난다. 두께는 **교사가 붙인 '왜' + 역량 + 레벨**이 정한다 — 1개 + 두툼한 '왜' = 두꺼운 재료이고, 3개 + 빈 '왜' = 얇은 재료다. "개수가 적으니 한 문장"으로 잘라내지 마라.
단, 두께가 늘려주는 것은 **의미·도달의 층**이지 **사실의 개수**가 아니다. 사건·인물·용어는 끝까지 span 안에서만 나오고, '왜'가 말하지 않은 깊이를 발명해 늘리면 그게 부풀리기다.
🚨 **두께는 '도달'의 깊이로 가지 '장면' 서술의 길이로 가지 않는다(교사 결정).** 3박자 = 3문장이 기본이고 각 박자는 **한 문장으로 압축**한다. 대화를 주고받은 순서대로 옮기지 말고 "무엇을 설정했는지"로 요약해라 — 실측 사고: 같은 재료·같은 마킹에서 압축형이 전개형으로 부풀어 **1.35배**가 됐고(날조는 없었다, 늘어난 전부가 span 안이었다) 교사가 **압축형**을 골랐다. 길이는 재료에 담긴 **사건의 개수**로 늘어나지 한 장면을 자세히 풀어서 늘어나지 않는다.`,
      body: `하이라이트(교사가 원문에서 표시):\n${hl}`,
    }
  }
  const src = (s.sources || []).map(x => `[${x.label}]\n${x.text}`).join('\n\n')
  return {
    rule: `**위임(계약서 §0-2)**: 교사가 하이라이트를 하나도 남기지 않았다. 아래 **원문에서 의미 있는 대목을 네가 고른다.** 다만 원문에 없는 사실을 배경지식으로 끌어오면 그게 날조다 — 재료가 좁혀지지 않았다는 건 안전장치가 빠졌다는 뜻이지 자유가 늘었다는 뜻이 아니다. ledger의 span은 원문에서 글자 그대로 복사하고, 못 지목하는 서술은 빼라. notes 첫 줄에 \`위임\`이라고 적어라.`,
    body: src ? `원문(교사 미표시 — 네가 고른다):\n${src}` : `재료 없음 — 렌더하지 말고 notes에 '재료 0'이라고만 남겨라.`,
  }
}

/* 표면 규칙의 실값 — 계약서 §2 가 파일 이름으로 언급하는 것들을 **먹여 준다**.
   안 먹이면 서브에이전트가 그 이름을 단서로 프로젝트를 뒤진다(실측 사고, render_args.surface 주석). */
function surfaceBlock() {
  const w = SURFACE.repeat_whitelist || []
  const f = SURFACE.forbidden || []
  return `\n**표면 규칙 실값(이게 유일한 출처다 — 파일을 찾아 읽지 마라):**\n`
    + `  · 바이트 상한: ${SURFACE.byte_max ?? '(계약서 §2)'}B — **넘지 말아야 할 선이지 맞춰야 할 값이 아니다**\n`
    + `  · 금지어: ${f.length ? f.join(', ') : '없음'}\n`
    + `  · 동어반복 예외어(이 과목 주제어): ${w.length ? w.join(', ') : '(없음)'}\n`
}

const results = await parallel(students.map(s => async () => {
  const mat = materialBlock(s)
  const prompt = `너는 학생 1명의 교과세특(세부능력 및 특기사항) 한 단락을 렌더링한다.
먼저 이 계약서를 반드시 Read로 읽고 규칙·퓨샷·문체를 그대로 따른다:
${CONTRACT}

**🚨 재료 조달 경계(헌법 7조) — 위 계약서 1개 파일 말고는 아무것도 열지 마라.**
이 프롬프트에 실린 재료 + 계약서, 그게 전부다. 프로젝트를 뒤지지 마라:
  · \`find\`·\`ls\`·\`grep\` 으로 규칙 파일(draft-rules.json·repeat-whitelist.txt 등)을 찾지 마라 — 필요한 실값은 아래에 다 있다.
  · **초안 폴더(${DRAFTS})는 쓰기 전용이다.** 그 안의 다른 파일을 읽지 마라.
    거기 있는 건 승인된 적 없는 옛 초안이고, 읽는 순간 네 문장이 그 문장에 끌려간다.
    교사가 물린 초안이 있으면 이 프롬프트에 이미 실려 온다 — 안 실려 왔으면 없는 것이다.
  · 다른 학생의 마킹·초안·원문을 열지 마라. 너는 이 학생 1명만 본다.

${mat.rule}

학생: ${s.name} (${s.hakbun})
활동맥락(도입 고정): ${s.context}
역량(교사 지정 — 무엇에 도달했나): ${s.competency || '(미지정 — 근거로 세우고 notes에 `역량 자체 추정`을 남겨라)'}
도달 수준(교사 지정 — 얼마나): ${s.level || '(미지정)'}
${mat.body}
${extraBlock(s)}${rejectBlock(s)}
도달 수준 규칙(계약서 §1-2): 상=도달 문장을 쓰고 통설 전환까지 가능 / 중=도달 문장 한 겹만, 통설 전환 절 금지 / 하=도달 문장('이를 통해 …')을 쓰지 말고 한 일 서술로 끝 / 미지정=재료 두께로 추정. 레벨은 부풀리기 허가가 아니다 — 재료가 없으면 상이어도 짓지 말고 unmet에 쉬운 말로 남겨라.

표면 규칙: **위 계약서 §2를 그대로 따른다.** 명사형 종결(어휘 고정 목록 없음 — 그 문장에 맞는 말) / 직접 인용부호·타학생 실명·가상 인물명 금지(역할어 사용) / 동어반복 금지(같은 2자+ 낱말 조사만 바꿔 2회 이상 X, 단 아래 예외어·역량어는 제외) / OCR 오탈자는 표준 표기.
${surfaceBlock()}
**분량 튜닝 금지 — 바이트를 재면서 문장을 늘렸다 줄였다 하지 마라.**
재료가 말하는 만큼 쓰고, **마지막에 딱 한 번** 세서 \`bytes_est\` 에 적어라. 상한에 가까워지려고
절을 덧대는 순간 그게 패딩이다(계약서 §2 실측 사고: 초안이 정확히 상한값으로 나왔다).
계약서 §3 퓨샷의 **두꺼운 편과 얇은 편 사이** 어디에 놓일지는 **교사 '왜'의 두께**가 정한다 —
'왜'가 비었으면 한 문장에서 끝나는 게 정상이고 그건 실패가 아니다. 반대로 '왜'가 두툼하면
그 의미만큼은 쓴다(개수가 적다고 잘라내지 마라).
상한을 넘었을 때만 절을 덜어내고 다시 세라(늘리는 방향의 재작성은 하지 마라).

**저장(필수 — 이걸 빠뜨리면 교사는 네 초안을 못 본다):** StructuredOutput 으로 반환하기 전에,
같은 결과를 Write 도구로 \`${DRAFTS}/${s.hakbun}.json\` 에 저장하라. 이 파일이 교사 마킹 화면에
뜨는 실물이다. 파일 내용은 아래 JSON **하나뿐**이며 다른 텍스트·주석·코드펜스를 넣지 마라:
{"hakbun":"${s.hakbun}","setuk":"<세특 본문>","ledger":[{"claim":"...","span":"..."}],"bytes_est":<정수>,"notes":"<메모>","unmet":"<교사 요구사항을 못 지켰으면 그 이유 한 줄, 아니면 빈 문자열>"}
이름·역량·레벨은 넣지 마라 — 화면이 교사 마킹에서 직접 읽는다(네가 옮겨 적으면 어긋난다).

StructuredOutput 도구로 {setuk, ledger:[{claim,span}], bytes_est, notes, unmet}을 반환하라.`
  const r = await agent(prompt, { label: `sonnet:${s.name}`, phase: 'Sonnet렌더', model: 'sonnet', agentType: 'general-purpose', schema: SCHEMA })
  // level·delegated 는 입력에서 그대로 붙인다 — 모델 에코를 믿지 않는다.
  const meta = { hakbun: s.hakbun, name: s.name, level: s.level || null, delegated: !s.highlights.length }
  if (!r) return { ...meta, error: true }
  /* 본문(setuk·ledger)은 반환하지 않는다 — 실물은 디스크의 초안 파일이고 교사는 화면에서 본다.
     172명치 본문을 메인 에이전트 컨텍스트로 실어 나르면 그것만으로 수만 토큰이고, 그렇게
     옮긴 사본은 화면이 보는 파일과 어긋날 수 있다. 여기선 패딩·재료부족 신호만 올린다. */
  return { ...meta, bytes_est: r.bytes_est, notes: r.notes, unmet: r.unmet || '', ledger_n: (r.ledger || []).length }
}))

const reworks = students.filter(s => (s.rejects || []).length).length
const delegated = students.filter(s => !s.highlights.length).length
const extras = students.filter(s => (s.extra || '').trim()).length
log(`소넷 렌더 완료: ${results.filter(Boolean).length}/${students.length}`
  + `${delegated ? ` · 위임 ${delegated}명(검수 우선)` : ''}${reworks ? ` · 재렌더 ${reworks}명` : ''}`
  + `${extras ? ` · 기타 요구사항 ${extras}명` : ''}`)
/* 상한 근처는 거의 항상 패딩이다(계약서 §2 실측 사고). 본문을 안 싣는 대신 이 신호는 올린다. */
const padded = results.filter(r => r && !r.error && r.bytes_est >= 770).map(r => `${r.hakbun} ${r.name}(${r.bytes_est}B)`)
if (padded.length) log(`🚩 상한 근처 ${padded.length}명 — 패딩 의심, 화면에서 먼저 볼 것: ${padded.join(', ')}`)
/* 요구사항을 물린 학생은 교사가 반드시 봐야 한다 — 화면 배너로도 뜨지만 배치 로그에서도 세운다. */
const unmet = results.filter(r => r && !r.error && r.unmet)
if (unmet.length) log(`📝 기타 요구사항 미반영 ${unmet.length}명 — 사유가 화면 상단에 뜬다: ${unmet.map(r => `${r.hakbun} ${r.name}`).join(', ')}`)
return results.filter(Boolean)
