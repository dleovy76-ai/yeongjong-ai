# YEONGJONG AI — Claude Code 통합 개발·사업 구현 마스터 프롬프트
### Version 1.0

> 이 문서는 프로젝트 오너가 작성한 원본 마스터 스펙을 그대로 보존한 것입니다.
> `CLAUDE.md`는 이 문서의 핵심 원칙을 요약한 실행 규칙이며, 세부 설계·근거는 항상 이 문서를 원본으로 참조합니다.

============================================================
0. PROJECT IDENTITY
============================================================

프로젝트명:
YEONGJONG AI

한국어 명칭:
영종 AI

서비스 정의:

"사장님에게는 AI 직원을,
방문객에게는 AI 여행 안내원을,
지역에는 AI 네트워크를 제공하여
AI가 실제 방문·예약·구매·매출을 만들어내는
지역 AI 경제 플랫폼"

핵심 시장:
인천광역시 중구 영종도 권역

최초 타깃:
1. 음식점
2. 카페
3. 숙박업소
4. 관광/체험업체

핵심 사용자:
A. 소상공인 사장님
B. 영종도 방문객
C. 플랫폼 관리자
D. 향후 지역기관/지자체

============================================================
1. ABSOLUTE PRODUCT PRINCIPLES
============================================================

이 프로젝트의 가장 중요한 원칙은 다음과 같다.

1. AI 자체를 판매하지 않는다.
2. 사장님의 시간과 비용을 절약한다.
3. AI가 고객을 실제 가게로 연결한다.
4. 모든 추천과 응대를 가능한 범위에서 측정한다.
5. 실제 방문/예약/구매와 연결되는 데이터를 수집한다.
6. AI가 만들어낸 성과를 사장님에게 보여준다.
7. 가입 업체가 다른 업체를 플랫폼으로 유입시키는 구조를 만든다.
8. 지역 업체 간 연결을 데이터화한다.
9. 개인정보 및 위치정보를 최소 수집 원칙으로 처리한다.
10. 초기에는 자동화보다 신뢰성과 검증을 우선한다.

절대로 다음과 같이 개발하지 않는다.

- 처음부터 전국 서비스 개발
- 처음부터 모든 AI Agent 구현
- 검증되지 않은 매출을 "AI 매출"로 표시
- 존재하지 않는 관광정보 생성
- 존재하지 않는 할인/제휴정보 생성
- AI가 사실처럼 추측한 영업시간/가격 표시
- 실제 결제가 없는데 매출로 집계
- 외부 플랫폼 API를 임의로 추정하여 구현

============================================================
2. CORE BUSINESS MODEL
============================================================

플랫폼의 핵심 순환 구조:

업체 가입
  ↓
사장님 AI 생성
  ↓
AI가 고객 응대
  ↓
관광객에게 지역 서비스 추천
  ↓
쿠폰/예약/방문
  ↓
실제 거래
  ↓
성과 측정
  ↓
사장님에게 ROI 제공
  ↓
AI가 연관 업체 탐색
  ↓
제휴/추천
  ↓
새 업체 가입
  ↓
지역 네트워크 확대

핵심 성장 공식:

Business Acquisition
+
AI Assistance
+
Customer Recommendation
+
Transaction
+
Measurement
+
Business Referral
=
Regional AI Network

============================================================
3. INITIAL MVP SCOPE
============================================================

MVP에서는 다음 4개의 AI Agent를 핵심으로 구현한다.

1. Manager AI
2. Customer AI
3. Chef AI
4. Info AI

그리고 플랫폼 성장 기능:

5. Expansion AI

데이터 분석 기능:

6. Performance Engine

기본 관리 기능:

7. Admin System

처음부터 아래 Agent를 완성형으로 만들 필요 없음.

- Marketing AI
- Review AI
- Sales AI
- Inventory AI
- Employee AI
- Tax AI

그러나 데이터 모델과 Agent Architecture는 향후 추가할 수 있도록 설계한다.

============================================================
4. SYSTEM ARCHITECTURE
============================================================

권장 구조:

Frontend:
Next.js + TypeScript

UI:
Tailwind CSS

Backend:
Python 3.11+

API:
FastAPI

Database:
PostgreSQL

Cache:
Redis

Vector DB:
초기에는 pgvector 권장

Object Storage:
S3 호환 스토리지

Authentication:
Google / Apple / Kakao 등 단계적 추가

AI:
LLM Provider abstraction 구조

예:

LLMProvider
 ├── OpenAIProvider
 ├── GeminiProvider
 └── ClaudeProvider

특정 LLM에 시스템 전체가 종속되지 않도록 한다.

Maps:
지도/장소 API Provider abstraction

Payment:
결제 Provider abstraction

Reservation:
예약 시스템 Provider abstraction

Analytics:
내부 Event Tracking Engine

============================================================
5. HIGH LEVEL ARCHITECTURE
============================================================

                    ┌─────────────────┐
                    │   Web / Mobile  │
                    └────────┬────────┘
                             │
                        REST API
                             │
                    ┌────────▼────────┐
                    │    FastAPI      │
                    └────────┬────────┘
                             │
        ┌────────────────────┼─────────────────────┐
        │                    │                     │
        ▼                    ▼                     ▼
 Business Service       AI Agent Engine       Analytics
        │                    │                     │
        ▼                    ▼                     ▼
 PostgreSQL             LLM Provider          Event Store
        │                    │
        ▼                    ▼
 Business Graph         Knowledge Retrieval
        │
        ▼
 Partner / Referral Engine

============================================================
6. USER ROLES
============================================================

ROLE 1:
BUSINESS_OWNER

ROLE 2:
CUSTOMER

ROLE 3:
ADMIN

ROLE 4:
PARTNER_MANAGER

향후:

ROLE 5:
LOCAL_GOVERNMENT

============================================================
7. BUSINESS OWNER ONBOARDING
============================================================

사장님 가입 과정은 최대한 단순해야 한다.

Step 1.
사업자 정보

- 업체명
- 업종
- 주소
- 전화번호
- 영업시간
- 휴무
- 대표 이미지

Step 2.
상품/메뉴

- 메뉴명
- 설명
- 가격
- 이미지
- 대표상품 여부
- 알레르기 정보
- 옵션

Step 3.
AI 정보

- 자주 묻는 질문
- 주차
- 반려동물
- 예약
- 포장
- 결제
- 특이사항

Step 4.
제휴 혜택

- 할인
- 쿠폰
- 이벤트
- 대상
- 기간
- 조건

Step 5.
AI 직원 생성

자동으로 Business AI Context를 생성한다.

============================================================
8. BUSINESS AI CONTEXT
============================================================

각 업체마다 독립적인 Context를 가진다.

예:

BusinessContext:

business_id
business_name
category
address
geo_location
phone
opening_hours
holiday
description
brand_tone
menus
services
parking
pet_policy
reservation_policy
payment_methods
promotion
coupon
faq
partner_businesses
approved_knowledge

AI는 승인된 BusinessContext를 우선 사용한다.

AI가 Context에 없는 사실을 임의로 생성하지 않는다.

============================================================
9. MANAGER AI
============================================================

Manager AI는 사용자가 직접 대화하는 대표 AI다.

책임:

- 다른 Agent 호출
- 사장님 요청 분류
- 업무 우선순위
- 성과 요약
- 추천
- 알림

예:

사용자:
"오늘 매출 어때?"

Manager AI
→ Sales Agent 호출

사용자:
"손님 좀 늘려봐."

Manager AI
→ Info Agent
→ Marketing Agent
→ Expansion/Partner data
를 조회한 후 제안한다.

Manager AI가 모든 업무를 직접 수행하지 않는다.

각 전문 Agent를 Tool Calling 방식으로 호출한다.

============================================================
10. CUSTOMER AI
============================================================

Customer AI는 고객 문의를 처리한다.

기능:

- 영업시간
- 메뉴
- 가격
- 주차
- 위치
- 예약
- 반려동물
- 포장
- 이벤트
- 쿠폰
- 추천

예:

고객:
"강아지 데리고 가도 돼요?"

Customer AI:
BusinessContext의 pet_policy를 조회하여 답변.

정보가 없으면:

"정확한 확인이 필요합니다."

라고 답한다.

추측하지 않는다.

============================================================
11. CHEF AI
============================================================

Chef AI는 메뉴 전문 Agent다.

기능:

1. 메뉴 소개
2. 메뉴 추천
3. 취향 기반 추천
4. 메뉴 조합
5. 대표 메뉴 추천
6. 신메뉴 소개
7. 알레르기 정보
8. 다국어 메뉴 설명

추천 결과에는 추천 근거를 기록한다.

예:

recommendation_id
business_id
customer_session_id
menu_id
reason
timestamp

가능하면 실제 주문과 연결한다.

============================================================
12. INFO AI
============================================================

Info AI는 영종도 지역정보 전문 Agent다.

범위:

- 관광지
- 해변
- 맛집
- 카페
- 숙박
- 체험
- 레저
- 쇼핑
- 교통
- 주차
- 축제
- 행사
- 지역 이벤트

Info AI는 반드시 Source-aware Architecture를 사용한다.

각 정보는:

source
source_type
verified_at
expires_at
confidence
status

를 가진다.

상태:

VERIFIED
UNVERIFIED
EXPIRED
DISABLED

만료된 정보는 추천하지 않는다.

============================================================
13. TOURIST AI
============================================================

방문객은 "영종도에서 무엇을 할까?"를 자연어로 질문할 수 있어야 한다.

예:

"공항 도착했는데 5시간 남았어."

"아이랑 갈 곳."

"비 오는 날."

"바다 보이는 카페."

"오늘 저녁 맛집."

"공항 가기 전에 들를 곳."

AI는 다음 Context를 고려한다.

- 현재 위치
- 시간
- 날짜
- 날씨
- 동행자
- 차량
- 예산
- 관심사
- 운영 여부

초기에는 위치 자동 수집을 강제하지 않는다.

사용자가 허용한 경우에만 사용한다.

============================================================
14. RECOMMENDATION ENGINE
============================================================

추천 알고리즘을 LLM 하나에 의존하지 않는다.

Recommendation Engine을 별도로 만든다.

입력:

user_context
business_context
time
distance
opening_status
promotion
category
rating
partner_status
availability

Score:

relevance_score
distance_score
open_score
promotion_score
partner_score
quality_score

최종:

recommendation_score

LLM은 설명과 자연어 생성에 사용한다.

추천 결정 자체는 구조화된 데이터 기반으로 한다.

============================================================
15. COUPON ENGINE
============================================================

Coupon:

id
business_id
title
description
discount_type
discount_value
start_at
end_at
conditions
usage_limit
status

상태:

DRAFT
ACTIVE
EXPIRED
DISABLED

쿠폰 발급 이벤트:

COUPON_ISSUED

사용:

COUPON_REDEEMED

실제 거래와 연결 가능하면:

TRANSACTION_CREATED

============================================================
16. RESERVATION ENGINE
============================================================

초기에는 내부 예약 또는 외부 예약 링크 방식으로 시작한다.

Reservation:

id
business_id
customer_id
source
reservation_time
party_size
status

상태:

REQUESTED
CONFIRMED
CANCELLED
COMPLETED
NO_SHOW

외부 예약 서비스는 Provider abstraction으로 처리한다.

============================================================
17. PERFORMANCE ENGINE
============================================================

이 프로젝트의 핵심 모듈.

모든 AI 활동을 Event로 기록한다.

Event 구조:

event_id
timestamp
user_id
business_id
session_id
agent_type
event_type
object_type
object_id
metadata
source

예:

AI_MESSAGE_SENT

MENU_VIEWED

MENU_RECOMMENDED

COUPON_ISSUED

COUPON_REDEEMED

RESERVATION_CREATED

RESERVATION_COMPLETED

BUSINESS_VISITED

TRANSACTION_CREATED

TRANSACTION_CONFIRMED

PARTNER_RECOMMENDED

PARTNER_INVITED

PARTNER_SIGNED_UP

============================================================
18. AI ATTRIBUTION
============================================================

절대로 단순히 AI가 대화했다고 매출로 계산하지 않는다.

매출 귀속 단계:

DIRECT
ASSISTED
INFLUENCED
UNKNOWN

예:

AI 추천
→ 쿠폰
→ 결제

= DIRECT

AI 추천
→ 사용자가 직접 방문
→ POS 연동

= ASSISTED / DIRECT 정책에 따라 정의

단순 노출:

= INFLUENCED 또는 UNKNOWN

대시보드에는 반드시 attribution 기준을 표시한다.

============================================================
19. BUSINESS PERFORMANCE DASHBOARD
============================================================

사장님에게:

이번 달

- AI 응대 건수
- 메뉴 추천
- 쿠폰 발급
- 쿠폰 사용
- 예약
- 예약 완료
- 방문
- 확인된 거래
- AI 연관 거래액
- 절감 예상 시간

을 보여준다.

예:

AI 응대:
2,481

예약:
387

쿠폰 사용:
216

확인 거래액:
₩15,190,000

예상 업무 절감:
27시간

============================================================
20. EXPANSION AI
============================================================

Expansion AI는 플랫폼의 자체 확장 Agent다.

목적:

"현재 가입 업체와 연관성이 높은 신규 사업자를 발견하고,
제휴 가능성을 분석하고,
사장님 승인 후 가입을 권유한다."

============================================================
21. PARTNER GRAPH
============================================================

업체 간 관계를 Graph 형태로 관리한다.

Business A
connected_to
Business B

Relationship:

relationship_id
business_a
business_b
relationship_type
score
created_at
status

예:

HOTEL
→ RESTAURANT

HOTEL
→ CAFE

RESTAURANT
→ CAFE

TOURIST_ATTRACTION
→ RESTAURANT

CAR_RENTAL
→ HOTEL

============================================================
22. EXPANSION AI PROCESS
============================================================

Step 1:
현재 업체 분석

Step 2:
주변 업체 탐색

Step 3:
업종 분석

Step 4:
고객층 분석

Step 5:
제휴 가능성 Score

Step 6:
예상 고객 교환량

Step 7:
추천 업체 생성

Step 8:
사장님 승인

Step 9:
제휴 제안 메시지 생성

Step 10:
초대 링크 생성

Step 11:
가입 여부 추적

Step 12:
성과 기록

============================================================
23. PARTNER RECOMMENDATION
============================================================

예:

"사장님과 연계 가능성이 높은 업체"

1. ○○호텔
score 92

2. △△체험
score 87

3. □□식당
score 82

표시 정보:

- 업체명
- 업종
- 거리
- 예상 연관성
- 추천 이유
- 현재 플랫폼 가입 여부
- 제휴 상태

============================================================
24. REFERRAL SYSTEM
============================================================

추천 가입 시스템.

A 업체가 B 업체를 초대.

B 가입.

Referral:

referrer_business_id
referred_business_id
status
created_at
reward_status

보상은 MVP에서는 포인트 또는 다음달 할인 구조를 고려한다.

============================================================
25. REFERRAL MESSAGE GENERATOR
============================================================

AI가 업체별 맞춤 메시지를 생성한다.

예:

"○○카페 사장님 안녕하세요.

현재 영종 AI에서 주변 관광객에게
○○카페를 추천하고 있습니다.

귀 업체와 제휴하면
호텔 투숙객에게 카페 혜택을 제공하고
카페 고객에게 숙박 혜택을 안내할 수 있습니다.

가입비 없이 무료로 시작할 수 있습니다.

[우리 가게 AI 만들기]"

초기에는 자동 발송하지 않는다.

사장님 승인 후 발송.

============================================================
26. ADMIN SYSTEM
============================================================

관리자 기능:

Business CRUD

User CRUD

Coupon CRUD

Promotion CRUD

Tourist Information CRUD

Knowledge Source CRUD

AI Conversation monitoring

Agent performance

Referral management

Partner management

Event monitoring

Transaction management

AI attribution review

Fraud detection

============================================================
27. DATA MODEL
============================================================

최소 테이블:

users
businesses
business_profiles
business_hours
menus
menu_options
business_faqs
promotions
coupons
coupon_issues
coupon_redemptions

tourist_places
tourist_place_sources
events
reservations
transactions

ai_sessions
ai_messages
ai_agents

recommendations
recommendation_events

business_relationships
partner_requests
referrals
referral_rewards

knowledge_documents
knowledge_chunks

admin_users
audit_logs

============================================================
28. KNOWLEDGE SYSTEM
============================================================

RAG 구조:

Source
→ Document
→ Chunk
→ Embedding
→ Retrieval
→ Agent

Knowledge Source priority:

1. 사업자 승인정보
2. 관리자 검증정보
3. 공식 기관정보
4. 신뢰할 수 있는 외부정보
5. 기타

정보에는 반드시:

source_url
source_name
verified_at
expires_at

를 기록한다.

============================================================
29. AI SAFETY
============================================================

AI가 다음을 임의 생성하면 안 된다.

- 가격
- 영업시간
- 할인율
- 예약 가능 여부
- 재고
- 숙박 가능 여부
- 관광지 운영 여부
- 교통 상황

확인되지 않은 경우:

"현재 확인되지 않은 정보입니다."

라고 표시한다.

============================================================
30. MULTILINGUAL
============================================================

영종도 특성상 다국어 구조를 처음부터 고려한다.

MVP:

한국어
영어
중국어

향후:

일본어

모든 Business Context는 locale을 지원한다.

예:

name_ko
name_en
name_zh

============================================================
31. MOBILE STRATEGY
============================================================

MVP:

Responsive Web

PWA 가능하도록 설계.

향후:

Flutter 또는 React Native 앱.

사장님 앱:

- AI 채팅
- 대시보드
- 쿠폰
- 예약
- 알림

방문객:

- AI 검색
- 지도
- 추천
- 쿠폰
- 예약

============================================================
32. MVP USER FLOW
============================================================

[사장님]

가입
↓
업체 등록
↓
메뉴 등록
↓
혜택 등록
↓
AI 생성
↓
AI 테스트
↓
공개
↓
고객 응대
↓
추천
↓
예약/쿠폰
↓
성과 확인

[관광객]

영종 AI 접속
↓
질문
↓
AI 추천
↓
업체 상세
↓
혜택
↓
쿠폰
↓
예약/방문
↓
후속 추천

[확장]

가입 업체
↓
Expansion AI
↓
연관 업체 분석
↓
사장님 승인
↓
초대
↓
신규 업체 가입
↓
네트워크 확대

============================================================
33. MVP SCREEN LIST
============================================================

PUBLIC

1. Landing
2. 영종 AI
3. AI Chat
4. Business Detail
5. Recommendation
6. Coupon
7. Reservation

BUSINESS

8. Business onboarding
9. AI employee dashboard
10. AI chat
11. Business profile
12. Menu management
13. Coupon management
14. Reservation management
15. Performance dashboard
16. Partner recommendation
17. Referral

ADMIN

18. Admin dashboard
19. Businesses
20. Tourist information
21. Coupons
22. AI conversations
23. Events
24. Transactions
25. Partners
26. Referrals
27. Knowledge sources

============================================================
34. LANDING PAGE CORE MESSAGE
============================================================

Headline:

"사장님은 장사하세요.
영종 AI가 나머지를 도와드립니다."

Subheadline:

"AI 직원이 고객을 응대하고,
메뉴를 추천하고,
관광객을 연결하고,
가게의 성과까지 알려드립니다."

CTA:

"우리 가게 AI 무료로 만들기"

Tourist CTA:

"영종도에서 뭐 할까?"

============================================================
35. BUSINESS OWNER VALUE PROPOSITION
============================================================

사장님이 얻는 것:

1. 업무시간 절감
2. 고객응대 자동화
3. 메뉴 판매 지원
4. 관광객 유입
5. 제휴 고객
6. 마케팅 지원
7. 성과 측정
8. 신규 고객 연결

핵심 문장:

"AI를 고용하세요."

============================================================
36. TOURIST VALUE PROPOSITION
============================================================

방문객:

"영종도에서 어디 갈지 고민하지 마세요."

AI가:

- 지금 갈 곳
- 먹을 곳
- 쉴 곳
- 잘 곳
- 할인받을 곳
- 예약할 곳

을 추천한다.

============================================================
37. BUSINESS MODEL
============================================================

Phase 1:

무료 MVP

목적:
시장 검증

Phase 2:

SaaS

Basic
29,900원

Pro
59,900원

Premium
99,000원

가격은 실제 고객 인터뷰와 비용구조 검증 후 확정한다.

Phase 3:

Transaction fee

Phase 4:

Local platform / B2G

============================================================
38. DEVELOPMENT PHASES
============================================================

PHASE 0
Architecture

- repository
- CI/CD
- environment
- DB
- API structure
- authentication
- logging

PHASE 1
Business onboarding

PHASE 2
Business AI

- Manager
- Customer
- Chef

PHASE 3
Tourist AI

- Info
- recommendation

PHASE 4
Coupon / Reservation

PHASE 5
Analytics

PHASE 6
Expansion AI

PHASE 7
Pilot

============================================================
39. PILOT TARGET
============================================================

첫 파일럿:

영종도

목표:

20~30개 업체

권장 구성:

10 음식점
10 카페
5 숙박
5 체험/관광

목표 관광객:

초기에는 트래픽보다
AI → 추천 → 방문 전환 검증을 우선한다.

============================================================
40. PILOT SUCCESS CRITERIA
============================================================

다음 조건을 검증한다.

1. 사장님이 AI를 실제 사용한다.
2. 고객이 AI에게 실제 질문한다.
3. AI 추천이 실제 클릭으로 이어진다.
4. 쿠폰 사용이 발생한다.
5. 예약이 발생한다.
6. 실제 방문이 확인된다.
7. 실제 거래가 발생한다.
8. 사장님이 AI의 가치를 인정한다.
9. 가입 업체가 다른 업체를 추천한다.

가장 중요한 KPI:

AI-ATTRIBUTED VERIFIED TRANSACTION VALUE

============================================================
41. ANTI-FRAUD
============================================================

매출 데이터 조작을 방지한다.

가능한 검증:

- POS 연동
- 예약 완료
- 쿠폰 사용
- QR 체크인
- 사업자 확인
- 관리자 검증

동일 사용자의 반복 이벤트를 구분한다.

============================================================
42. OBSERVABILITY
============================================================

모든 AI 요청에:

request_id
user_id
business_id
agent
model
prompt_version
latency
token_usage
cost
success
error

기록.

AI 비용 분석이 가능해야 한다.

============================================================
43. COST CONTROL
============================================================

모든 질문을 고비용 LLM으로 처리하지 않는다.

1단계:
Rule / DB

2단계:
검색 / Retrieval

3단계:
저비용 LLM

4단계:
고성능 LLM

질문 난이도에 따라 라우팅한다.

============================================================
44. PROMPT VERSIONING
============================================================

각 Agent의 Prompt는 코드에 하드코딩하지 않는다.

Prompt:

prompt_id
agent_type
version
content
status
created_at

대화 로그와 prompt_version을 연결한다.

============================================================
45. API DESIGN
============================================================

예:

POST /api/v1/auth/register

POST /api/v1/businesses

GET /api/v1/businesses/{id}

POST /api/v1/businesses/{id}/menus

POST /api/v1/ai/chat

POST /api/v1/recommendations

POST /api/v1/coupons

POST /api/v1/coupons/{id}/issue

POST /api/v1/coupons/{id}/redeem

POST /api/v1/reservations

GET /api/v1/businesses/{id}/performance

GET /api/v1/businesses/{id}/partners

POST /api/v1/referrals

POST /api/v1/expansion/analyze

POST /api/v1/partner/invite

============================================================
46. TESTING
============================================================

필수 테스트:

Unit Test

Integration Test

API Test

AI Response Test

RAG Test

Attribution Test

Coupon Test

Reservation Test

Referral Test

Permission Test

Security Test

Prompt Regression Test

============================================================
47. AI EVALUATION
============================================================

각 Agent 평가 기준:

Accuracy
Groundedness
Completeness
Relevance
Safety
Latency
Cost

테스트 질문 세트를 별도로 만든다.

예:

"오늘 몇 시까지 해요?"

"강아지 데려가도 돼요?"

"대표 메뉴가 뭐예요?"

"아이와 갈 만한 곳?"

"공항까지 얼마나 걸려요?"

============================================================
48. SECURITY
============================================================

필수:

JWT/session security

RBAC

Input validation

Rate limiting

Audit logs

Secret management

PII 최소 수집

Encryption

삭제 요청 처리

개인정보 보관기간 정책

============================================================
49. GDPR / KOREA PRIVACY
============================================================

한국 개인정보보호법 등 적용 법령을 검토한다.

특히:

위치정보
개인정보
마케팅 동의
쿠키
행동로그
예약정보

를 분리 관리한다.

AI가 개인정보를 불필요하게 기억하지 않도록 한다.

============================================================
50. DEVELOPMENT RULE
============================================================

Claude Code는 기능을 구현하기 전에:

1. repository 분석
2. 현재 architecture 분석
3. dependency 확인
4. DB schema 확인
5. API 확인
6. 기존 코드 재사용
7. 테스트 확인

을 수행한다.

기존 기능을 무작정 삭제하지 않는다.

============================================================
51. IMPLEMENTATION ORDER
============================================================

반드시 다음 순서로 개발한다.

STEP 1
Repository structure

STEP 2
Database

STEP 3
Authentication

STEP 4
Business onboarding

STEP 5
Business Context

STEP 6
AI Agent framework

STEP 7
Manager AI

STEP 8
Customer AI

STEP 9
Chef AI

STEP 10
Info AI

STEP 11
Recommendation Engine

STEP 12
Coupon

STEP 13
Reservation

STEP 14
Event tracking

STEP 15
Performance dashboard

STEP 16
Partner Graph

STEP 17
Expansion AI

STEP 18
Referral

STEP 19
Admin

STEP 20
Pilot deployment

============================================================
52. AGENT ARCHITECTURE
============================================================

Agent interface:

BaseAgent

methods:

initialize()
understand()
retrieve()
decide()
execute()
respond()
log()

Agents:

ManagerAgent
CustomerAgent
ChefAgent
InfoAgent
ExpansionAgent

향후:

MarketingAgent
ReviewAgent
SalesAgent
InventoryAgent
EmployeeAgent
TaxAgent

============================================================
53. TOOL ARCHITECTURE
============================================================

Agent가 사용할 수 있는 Tool을 표준화한다.

BusinessSearchTool
MenuSearchTool
TouristSearchTool
CouponTool
ReservationTool
MapTool
PartnerSearchTool
AnalyticsTool
EventTool

AI가 직접 DB를 무제한 조회하지 않는다.

Tool을 통해 필요한 데이터만 접근한다.

============================================================
54. REGIONAL KNOWLEDGE GRAPH
============================================================

영종도의 지역 객체를 그래프로 구성한다.

Node:

Business
TouristAttraction
Hotel
Restaurant
Cafe
Experience
Event
Transport
Parking

Edge:

NEAR
RELATED
PARTNER
RECOMMENDS
DISCOUNT
ROUTE_TO

향후 Knowledge Graph DB 도입 가능하도록 abstraction.

초기에는 PostgreSQL 관계 테이블로 구현한다.

============================================================
55. IMPORTANT BUSINESS RULE
============================================================

AI가 업체를 추천할 때

돈을 더 많이 내는 업체를 무조건 추천하지 않는다.

추천 품질을 우선한다.

유료 프로모션이 있는 경우:

"프로모션"

또는

"제휴 혜택"

등으로 명확히 표시한다.

============================================================
56. ADMIN CONTROL
============================================================

관리자는 다음을 강제로 비활성화할 수 있어야 한다.

Business
Coupon
Promotion
Tourist place
Knowledge source
AI agent
Partner
Referral

============================================================
57. MVP DELIVERY DEFINITION
============================================================

MVP 완료 조건:

[ ] 사장님 가입 가능
[ ] 업체 등록 가능
[ ] 메뉴 등록 가능
[ ] AI 직원 생성
[ ] 고객 질문 응답
[ ] 메뉴 추천
[ ] 영종도 관광정보 검색
[ ] 지역업체 추천
[ ] 쿠폰 발급
[ ] 쿠폰 사용
[ ] 예약
[ ] 이벤트 추적
[ ] 성과 대시보드
[ ] 연관업체 추천
[ ] 업체 초대
[ ] 관리자 페이지
[ ] 테스트
[ ] 배포

============================================================
58. CLAUDE CODE WORKING METHOD
============================================================

각 작업마다 반드시 다음 형식으로 진행한다.

1. PLAN
2. FILES TO CHANGE
3. IMPLEMENT
4. TEST
5. VERIFY
6. REPORT

각 단계가 끝날 때:

- 구현한 기능
- 변경 파일
- DB 변경
- API 변경
- 테스트 결과
- 남은 문제
- 다음 단계

를 보고한다.

============================================================
59. DO NOT OVERENGINEER
============================================================

MVP 단계에서:

- Microservices 금지
- Kubernetes 금지
- 복잡한 Event Bus 금지
- 별도 Graph DB 금지
- 자체 LLM 학습 금지

초기에는:

Modular Monolith

구조로 구현한다.

향후 트래픽 증가 시 분리한다.

============================================================
60. FINAL PRODUCT VISION
============================================================

최종적으로 YEONGJONG AI는:

"AI가 지역경제를 연결하는 플랫폼"

이 된다.

사장님:
AI 직원

방문객:
AI 여행 안내

지역업체:
AI 파트너 네트워크

지역:
AI 경제 데이터

플랫폼:
AI 기반 거래 연결

최종 Loop:

사장님 가입
→ AI 직원 생성
→ 고객 응대
→ 관광객 추천
→ 쿠폰
→ 예약
→ 방문
→ 거래
→ 성과 측정
→ AI가 연관 업체 발견
→ 업체 초대
→ 신규 업체 가입
→ 네트워크 확대
→ 더 많은 관광객
→ 더 많은 거래
→ 더 많은 데이터
→ 더 정확한 AI

============================================================
61. FIRST TASK FOR CLAUDE CODE
============================================================

아직 코드를 작성하지 말고 먼저 다음을 수행한다.

1. 현재 repository 구조 분석
2. 기존 코드 분석
3. 실행환경 분석
4. package/dependency 분석
5. DB 존재 여부 확인
6. 기존 인증 구조 확인
7. 기존 AI 코드 확인
8. 기존 API 확인
9. 재사용 가능한 모듈 확인

그리고 다음을 먼저 출력한다.

A. 현재 시스템 구조
B. 재사용 가능한 코드
C. 새로 필요한 모듈
D. DB 설계
E. API 설계
F. AI Agent 설계
G. 개발 순서
H. 예상 위험
I. MVP 범위
J. 첫 번째 구현 Task

그 후 승인 없이 전체 프로젝트를 한 번에 구현하지 말고,
작업 단위별로 구현 → 테스트 → 검증하면서 진행한다.

============================================================
END OF MASTER PROMPT
============================================================

============================================================
ADDENDUM — EXPANSION AI 강조 (프로젝트 오너 코멘트)
============================================================

이 계획에서 가장 중요한 것은 확장AI다.

왜냐하면 일반적인 SaaS는:
회사 → 광고 → 고객 → 가입
이라는 구조인데,

우리는:
업체 → AI → 연관 업체 → 가입 → 또 다른 AI → 또 다른 업체
라는 구조를 만들 수 있기 때문이다.

최종적으로는 이렇게 된다.

영종도 음식점 A
→ 인포AI가 호텔 B를 발견
→ 확장AI가 제휴 제안
→ 호텔 B 가입
→ 호텔 B의 AI가 카페 C 발견
→ 카페 C 가입
→ 카페 C의 AI가 체험업체 D 발견
→ D 가입
→ D의 AI가 음식점 E 발견
→ E 가입

플랫폼이 지역의 비즈니스 네트워크를 스스로 넓혀가는 구조다.

그리고 개발할 때 가장 중요한 한 가지:

AI를 많이 만드는 것이 목표가 아니다.

첫 번째 MVP에서 반드시 증명해야 할 것은 이것이다.

관광객이 영종 AI에게 질문한다.
↓
AI가 실제 업체를 추천한다.
↓
관광객이 쿠폰/예약을 이용한다.
↓
실제 업체를 방문한다.
↓
실제 매출이 발생한다.
↓
사장님이 "이 AI를 계속 써야겠다"고 한다.
↓
그 사장님이 다른 사장님을 데려온다.

이 하나의 Loop가 돌아가면 사업이 된다.

반대로 AI가 아무리 똑똑해도 이 Loop가 안 돌아가면
플랫폼을 크게 만들 이유가 없다.

따라서 Claude Code에게도
"기능을 많이 만드는 것보다 이 Loop를 가장 빨리 검증하는 방향으로 개발하라"
는 원칙을 반드시 지키게 하는 것이 좋다.

============================================================
END OF DOCUMENT
============================================================
