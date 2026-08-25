# P1-6 — Customer AI 대화형 예약 수집 설계

작성일: 2026-08-25. 구현 전 사전조사 결과를 파일로 남겨 재유실을 방지하기 위해 작성.

## 핵심 원칙

**대화형 예약은 새로운 예약 시스템이 아니다. 기존 예약 폼을 AI가 대화로 채워주는 것뿐이다.**

- `Reservation` DB/스키마/API는 그대로 사용한다. 새 테이블, draft 저장용 DB를 만들지 않는다.
- **AI는 절대 예약을 직접 생성하지 않는다.** 대화 중 아무리 정보가 다 모여도 AI는 "예약해드렸습니다"라고
  말하지 않는다. 항상 "예약 내용을 확인해주세요" → 사람이 `[예약 확정]`을 눌러야만 실제
  `Reservation` row가 생긴다 — 기존 `api.createReservation()`을 그대로 재사용한다.
- **예약 가능 여부를 판단하지 않는다.** 현재 `Reservation`에는 슬롯/정원 검증이 전혀 없다(과거 시간
  거부 말고는 아무 제약이 없음). 그래서 AI는 "오후 7시 예약 가능합니다" 같은 말을 절대 하지 않고,
  "예약 요청 내용을 접수했어요. 사장님이 확인 후 확정해드립니다"로 통일한다 — 이건 수동 폼의 접수
  완료 문구와 동일한 톤이다.

## 흐름

```
손님 ↔ Customer AI 대화
   ↓ (매 메시지)
프론트가 지금까지의 전체 대화(history)를 백엔드로 함께 전송
   ↓
백엔드: 대화 전체에 "예약" 키워드가 있으면 ReservationDraftAgent 호출
   ↓
전체 대화를 다시 통째로 분석해 {이름, 전화번호, 날짜, 시간, 인원, 요청사항} 재추출
   (손님이 말하지 않은 항목은 null. 이전 값에 patch하지 않고 매번 처음부터 재도출 —
    "3명" → "아 4명이요" 같은 정정이 상태 관리 없이 자연스럽게 반영됨)
   ↓
ChatResponse.reservation_draft로 프론트에 전달
   ↓
프론트: "예약 내용을 확인해주세요" 카드 렌더링, 빈 항목은 "확인 필요"로 표시
   ↓
필수 항목(이름/연락처/날짜/시간/인원) 전부 채워졌을 때만 [예약 확정] 버튼 활성화
   ↓
클릭 → 기존 api.createReservation() 호출 (수동 폼과 동일한 함수/엔드포인트)
   ↓
Reservation(status=REQUESTED) 생성
   ↓
기존 P1-1 흐름 그대로 (사장님이 CONFIRMED → 방문 후 COMPLETED → 매출 기록)
```

## 아키텍처 결정: 왜 2개의 LLM 호출인가

기존 `CustomerAgent`는 "자연어 답변 하나만 생성"하는 단일 책임 에이전트다(이 프로젝트의 다른 모든
에이전트도 마찬가지 — `ExpansionAgent`는 순수 JSON, `MenuDraftAgent`는 순수 텍스트, 하나의 LLM
호출이 하나의 출력 형태만 내도록 일관되게 설계돼 있음). 자연어 답변과 구조화된 JSON 추출을 한 호출에
섞으면 형식이 깨지기 쉽고 기존 컨벤션과도 어긋난다. 그래서:

1. **`CustomerAgent`** (기존, 프롬프트 규칙 변경 없음) — 자연어 답변 생성. 이번에 `conversation_history`를
   컨텍스트에 추가로 넣어(기존 프롬프트 룰은 그대로 두고 새 블록만 추가) 정정 발화에도 맥락 있게 답할 수
   있게 한다.
2. **`ReservationDraftAgent`** (신규, `services/agents/reservation_draft.py`) — 순수 JSON 추출 전용.
   `MenuDraftAgent`/`ProfileDraftAgent`와 같은 "초안 생성" 계열 패턴을 따른다.

라우터(`routers/ai.py`)가 두 호출을 순서대로 orchestrate한다. `ReservationDraftAgent`는 `business_id`
없이(= `context`에 넣지 않고) 호출한다 — `AiInteraction.business_id`가 채워지면 Performance의
`ai_response_count`(해당 업체 AI 상담 횟수)가 한 손님의 한 턴을 두 번으로 세게 되어 숫자가 부풀기
때문이다(Info AI가 이미 같은 이유로 `business_id=None`을 쓰는 것과 동일한 원칙).

## 키워드 게이트

매 요청마다 무조건 추출 LLM을 또 부르면 비용이 늘고, 일반 대화에 불필요한 draft가 뜰 위험도 커진다.
`history + message` 전체 텍스트에 `"예약"`이 한 번이라도 포함될 때만 `ReservationDraftAgent`를 호출한다.
정정 발화("아 4명이요")처럼 그 메시지 자체엔 "예약"이 없어도, 같은 대화의 앞부분에 이미 "예약"이 있었으면
전체 history를 보는 게이트라 정상적으로 다시 걸린다.

이중 방어: 키워드 게이트를 통과해도, `ReservationDraftAgent`의 프롬프트 자체가
`has_reservation_intent: false`를 반환할 수 있다(예: 과거에 예약했던 걸 언급만 하는 경우) — 이 경우
`reservation_draft`는 `null`로 응답한다. 키워드 게이트(비용/1차 방어) + LLM 판단(정확도/2차 방어) 두 겹.

## 스키마

```
ChatRequest:
  business_id, message (기존)
  + history: [{role: "user"|"ai", text: str}]  (신규, 기본값 [])

ChatResponse:
  agent_type, reply, menu_images (기존)
  + reservation_draft: {
      customer_name: str | null
      customer_phone: str | null
      date: str | null   # YYYY-MM-DD, "내일" 같은 표현을 현재 시각(KST) 기준으로 변환
      time: str | null   # HH:MM, 24시간제
      party_size: int | null
      notes: str | null
    } | null   (신규)
```

`date`/`time`을 분리해두는 이유: 부분 정보 상태에서도 카드에 "8월 26일 · 확인 필요"처럼 자연스럽게
보여줄 수 있고, 실제 `reservation_time`(ISO datetime)으로의 조합은 프론트가 `[예약 확정]` 클릭
시점(둘 다 채워졌을 때만 버튼이 활성화되므로 그 시점엔 항상 둘 다 존재)에 한다 — 수동 폼이 이미
`new Date(resvTime).toISOString()`으로 하는 것과 동일한 방식.

## 하지 않는 것 (범위 밖)

- 예약 슬롯/정원 시스템, 영업시간 교차검증, 중복·동시 예약 방지 — `Reservation` 자체의 기존 구조적
  공백이며 대화형 예약 여부와 무관하게 필요한, 별도 백로그.
- `Reservation` DB/스키마 변경.
- 기존 수동 "예약 요청하기" 폼 제거 — 그대로 유지, AI 확인 카드는 그 옆에 추가되는 것.
- AI가 예약 가능 여부를 판단하는 것.
- AI가 사람 확인 없이 예약을 생성하는 것.

## 참고: 왜 새 DB 테이블 없이 가능한가

`ChatWidget.tsx`가 이미 화면에 보여줄 전체 대화를 `messages` state로 들고 있다 — 이걸 그대로
`history`로 매 요청에 실어 보내면, 백엔드는 세션도 DB도 없이 매번 "지금까지의 전체 대화"를 받아
처음부터 다시 분석할 수 있다(성철이형 프로젝트 `fact_extraction.py`의 "매번 전체 재분석" 패턴과 동일).
draft는 확정 전까지 프론트 상태로만 존재하고, 확정 버튼을 누르는 순간에만 기존
`api.createReservation()`을 통해 실제 DB에 닿는다.
