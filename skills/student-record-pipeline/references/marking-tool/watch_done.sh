#!/usr/bin/env bash
# 배치 트리거 감시자: 완료·미렌더 학생이 N명 모이거나, 첫 대기 후 T초 경과하면(먼저 오는 쪽)
# → 대기 목록 출력 후 종료. 순수 bash 폴링(LLM 0토큰).
# 튜닝: BATCH_N(기본 8), BATCH_TIMEOUT 초(기본 180=3분).
#   첫 배치는 문체 조기확인용으로 BATCH_N=3으로 띄우길 권장 → OK면 이후 8로.
# 예: BATCH_N=3 bash tool/watch_done.sh                     # 첫 배치(문체 확인)
#     BATCH_N=8 BATCH_TIMEOUT=180 bash tool/watch_done.sh   # 이후 벌크
cd "$(dirname "$0")/.."
BATCH_N=${BATCH_N:-8}
BATCH_TIMEOUT=${BATCH_TIMEOUT:-180}
first_seen=-1
for i in $(seq 1 4320); do            # 최대 ~6시간
  P=$(python3 tool/pending.py)
  count=$(printf '%s' "$P" | grep -c '[0-9]')
  if [ "$count" -eq 0 ]; then
    first_seen=-1                     # 대기열 비면 타이머 리셋
    sleep 5; continue
  fi
  if [ "$first_seen" -lt 0 ]; then first_seen=$SECONDS; fi   # 첫 대기 시각 기록
  elapsed=$(( SECONDS - first_seen ))
  # N명 모임 OR 첫 대기 후 T초 경과 → 발화(낙오자 흘려보냄)
  if [ "$count" -ge "$BATCH_N" ] || [ "$elapsed" -ge "$BATCH_TIMEOUT" ]; then
    echo "RENDER_BATCH (${count}명, ${elapsed}s 경과, N=${BATCH_N}/T=${BATCH_TIMEOUT})"
    echo "$P"
    exit 0
  fi
  sleep 5
done
echo "TIMEOUT"
