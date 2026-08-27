const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// P1-4 (REORG_DECISIONS.md) - 백엔드의 Gemini 호출 타임아웃(20초, gemini_provider.py)
// 보다 조금 더 길게 잡는다 - 정상적인 경우 백엔드가 먼저 502로 깔끔하게
// 응답하고, 이 타임아웃은 백엔드가 그마저도 못 하고 완전히 멈춰버린 경우의
// 최후 안전장치다. 이게 없으면 프론트는 fetch()가 끝없이 기다려서 "답변
// 작성 중..."이 정말로 무한정 떠 있을 수 있었다.
const REQUEST_TIMEOUT_MS = 25_000;

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(
  path: string,
  options: { method?: string; body?: unknown; token?: string | null } = {}
): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (options.token) headers["Authorization"] = `Bearer ${options.token}`;

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      method: options.method ?? "GET",
      headers,
      body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
      signal: controller.signal,
    });
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new ApiError(0, "요청 시간이 너무 오래 걸려요. 잠시 후 다시 시도해 주세요.");
    }
    throw err;
  } finally {
    clearTimeout(timeoutId);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  const data = await response.json().catch(() => null);
  if (!response.ok) {
    const message =
      typeof data?.detail === "string"
        ? data.detail
        : Array.isArray(data?.detail)
          ? data.detail.map((d: { msg: string }) => d.msg).join(", ")
          : "요청 처리 중 오류가 발생했습니다.";
    throw new ApiError(response.status, message);
  }
  return data as T;
}

export type UserRole = "BUSINESS_OWNER" | "CUSTOMER" | "ADMIN" | "PARTNER_MANAGER";

export interface AuthUser {
  id: string;
  email: string;
  name: string;
  role: UserRole;
  phone: string | null;
  locale: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user: AuthUser;
}

export type BusinessCategory = "RESTAURANT" | "CAFE" | "LODGING" | "EXPERIENCE" | "SHOPPING" | "LEISURE";
export type BusinessStatus = "DRAFT" | "ACTIVE" | "DISABLED";

export const CATEGORY_LABELS: Record<BusinessCategory, string> = {
  RESTAURANT: "음식점",
  CAFE: "카페",
  LODGING: "숙박",
  EXPERIENCE: "체험/관광",
  SHOPPING: "쇼핑",
  LEISURE: "레저",
};

export interface Business {
  id: string;
  owner_user_id: string | null;
  name_ko: string;
  name_en: string | null;
  name_zh: string | null;
  category: BusinessCategory;
  address: string;
  phone: string | null;
  status: BusinessStatus;
  data_source: string | null;
  created_at: string;
  updated_at: string;
}

export interface BusinessProfile {
  id: string;
  business_id: string;
  description: string | null;
  brand_tone: string | null;
  opening_hours: Record<string, unknown> | null;
  holiday: string | null;
  parking: string | null;
  pet_policy: string | null;
  reservation_policy: string | null;
  takeout_policy: string | null;
  payment_methods: Record<string, unknown> | null;
  faq: Record<string, unknown> | null;
  naver_place_url: string | null;
  naver_map_url: string | null;
}

// AUDIT P0 - monthly_visitor_estimate is owner/admin-only now; the public
// GET .../profile endpoint never returns it (backend strips it at the schema
// level, not just in the UI). Only GET/PATCH .../profile/owner carries it.
export interface BusinessOwnerProfile extends BusinessProfile {
  monthly_visitor_estimate: number | null;
}

export interface ProfileDraft {
  description: string;
  brand_tone: string;
}

export interface NaverLookupCandidate {
  title: string;
  road_address: string;
  category: string;
  map_url: string;
  naver_url: string;
  verified: boolean;
}

export interface Menu {
  id: string;
  business_id: string;
  name: string;
  description: string | null;
  price: string;
  image_url: string | null;
  is_signature: boolean;
  allergy_info: string | null;
  origin_info: string | null;
  options: Record<string, unknown> | null;
}

export interface MenuBulkDraftItem {
  name: string;
  price: string | null;
}

export type CouponDiscountType = "PERCENTAGE" | "FIXED_AMOUNT";
export type CouponStatus = "DRAFT" | "ACTIVE" | "EXPIRED" | "DISABLED";
export type CouponIssueStatus = "ISSUED" | "REDEEMED";

export interface Coupon {
  id: string;
  business_id: string;
  title: string;
  description: string | null;
  discount_type: CouponDiscountType;
  discount_value: string;
  start_at: string | null;
  end_at: string | null;
  conditions: string | null;
  usage_limit: number | null;
  status: CouponStatus;
  issued_count: number;
  redeemed_count: number;
}

export interface CouponIssue {
  id: string;
  coupon_id: string;
  code: string;
  status: CouponIssueStatus;
  issued_at: string;
  redeemed_at: string | null;
}

export interface UnrecordedCouponIssue extends CouponIssue {
  coupon_title: string;
}

export type ReservationStatus = "REQUESTED" | "CONFIRMED" | "CANCELLED" | "COMPLETED" | "NO_SHOW";

export interface Reservation {
  id: string;
  business_id: string;
  customer_name: string;
  customer_phone: string;
  reservation_time: string;
  party_size: number;
  notes: string | null;
  status: ReservationStatus;
  created_at: string;
}

export const api = {
  register: (body: { email: string; password: string; name: string; role: UserRole }) =>
    request<TokenResponse>("/api/v1/auth/register", { method: "POST", body }),

  login: (body: { email: string; password: string }) =>
    request<TokenResponse>("/api/v1/auth/login", { method: "POST", body }),

  me: (token: string) => request<AuthUser>("/api/v1/auth/me", { token }),

  myBusinesses: (token: string) => request<Business[]>("/api/v1/businesses/me", { token }),

  createBusiness: (
    token: string,
    body: {
      name_ko: string;
      name_en?: string;
      name_zh?: string;
      category: BusinessCategory;
      address: string;
      phone?: string;
    }
  ) => request<Business>("/api/v1/businesses", { method: "POST", body, token }),

  // AUDIT P1 - non-ACTIVE businesses now 404 unless the caller is the owner
  // or an admin, so an optional token lets the owner's own "AI 미리보기" page
  // keep working for a business that isn't ACTIVE yet.
  getBusiness: (id: string, token?: string | null) =>
    request<Business>(`/api/v1/businesses/${id}`, { token }),

  updateBusiness: (token: string, id: string, body: Partial<Business>) =>
    request<Business>(`/api/v1/businesses/${id}`, { method: "PATCH", body, token }),

  listUnclaimedBusinesses: (query: string) =>
    request<Business[]>(`/api/v1/businesses/unclaimed?query=${encodeURIComponent(query)}`),

  claimBusiness: (token: string, id: string) =>
    request<Business>(`/api/v1/businesses/${id}/claim`, { method: "POST", token }),

  getProfile: (id: string, token?: string | null) =>
    request<BusinessProfile>(`/api/v1/businesses/${id}/profile`, { token }),

  // AUDIT P0 - owner-only view (monthly_visitor_estimate included); backend
  // 401s with no token, 403s for a non-owner, never falls back to the public
  // shape.
  getOwnerProfile: (token: string, id: string) =>
    request<BusinessOwnerProfile>(`/api/v1/businesses/${id}/profile/owner`, { token }),

  updateProfile: (token: string, id: string, body: Partial<BusinessOwnerProfile>) =>
    request<BusinessOwnerProfile>(`/api/v1/businesses/${id}/profile`, { method: "PATCH", body, token }),

  naverLookup: (token: string, id: string) =>
    request<NaverLookupCandidate>(`/api/v1/businesses/${id}/naver-lookup`, { token }),

  draftProfile: (token: string, id: string) =>
    request<ProfileDraft>(`/api/v1/businesses/${id}/profile/draft`, { method: "POST", token }),

  listMenus: (id: string) => request<Menu[]>(`/api/v1/businesses/${id}/menus`),

  draftMenuDescription: (
    token: string,
    businessId: string,
    name: string,
    isSignature: boolean,
    originInfo?: string
  ) =>
    request<{ description: string }>(`/api/v1/businesses/${businessId}/menus/draft-description`, {
      method: "POST",
      body: { name, is_signature: isSignature, origin_info: originInfo || undefined },
      token,
    }),

  draftMenusFromText: (token: string, businessId: string, rawText: string) =>
    request<{ items: MenuBulkDraftItem[] }>(`/api/v1/businesses/${businessId}/menus/bulk-draft`, {
      method: "POST",
      body: { raw_text: rawText },
      token,
    }),

  createMenu: (
    token: string,
    businessId: string,
    body: {
      name: string;
      description?: string;
      price: string;
      image_url?: string;
      is_signature?: boolean;
      allergy_info?: string;
      origin_info?: string;
    }
  ) => request<Menu>(`/api/v1/businesses/${businessId}/menus`, { method: "POST", body, token }),

  deleteMenu: (token: string, businessId: string, menuId: string) =>
    request<void>(`/api/v1/businesses/${businessId}/menus/${menuId}`, { method: "DELETE", token }),

  updateMenu: (
    token: string,
    businessId: string,
    menuId: string,
    body: { is_signature: boolean }
  ) =>
    request<Menu>(`/api/v1/businesses/${businessId}/menus/${menuId}`, {
      method: "PATCH",
      body,
      token,
    }),

  chat: (businessId: string, message: string, history: ChatHistoryItem[] = []) =>
    request<ChatResponse>("/api/v1/ai/chat", {
      method: "POST",
      body: { business_id: businessId, message, history },
    }),

  // P1-5 (REORG_DECISIONS.md) - 공개(비로그인) 엔드포인트, recordRecommendationClick과
  // 같은 이유(채팅 자체가 비로그인이니 피드백도 같은 조건에서 남길 수 있어야 함).
  submitChatFeedback: (interactionId: string, feedback: AiInteractionFeedback) =>
    request<AiInteractionFeedbackResult>(`/api/v1/ai/interactions/${interactionId}/feedback`, {
      method: "POST",
      body: { feedback },
    }),

  recommend: (query: string) =>
    request<RecommendationResponse>("/api/v1/recommendations", { method: "POST", body: { query } }),

  // PILOT AUDIT TASK 3 - 추천→클릭 연결 기반. interaction_id는 recommend()
  // 응답의 interaction_id를 그대로 넘긴다.
  recordRecommendationClick: (interactionId: string, entityId: string, entityType: "business" | "tourist_place") =>
    request<RecommendationClickResponse>(`/api/v1/recommendations/${interactionId}/click`, {
      method: "POST",
      body: { entity_id: entityId, entity_type: entityType },
    }),

  listCoupons: (businessId: string, token?: string | null) =>
    request<Coupon[]>(`/api/v1/businesses/${businessId}/coupons`, { token }),

  listUnrecordedCouponIssues: (token: string, businessId: string) =>
    request<UnrecordedCouponIssue[]>(`/api/v1/businesses/${businessId}/coupons/issues`, { token }),

  createCoupon: (
    token: string,
    businessId: string,
    body: {
      title: string;
      description?: string;
      discount_type: CouponDiscountType;
      discount_value: string;
      conditions?: string;
      usage_limit?: number;
    }
  ) => request<Coupon>(`/api/v1/businesses/${businessId}/coupons`, { method: "POST", body, token }),

  updateCoupon: (token: string, businessId: string, couponId: string, body: Partial<Coupon>) =>
    request<Coupon>(`/api/v1/businesses/${businessId}/coupons/${couponId}`, {
      method: "PATCH",
      body,
      token,
    }),

  issueCoupon: (businessId: string, couponId: string) =>
    request<CouponIssue>(`/api/v1/businesses/${businessId}/coupons/${couponId}/issue`, { method: "POST" }),

  redeemCoupon: (token: string, businessId: string, code: string) =>
    request<CouponIssue>(`/api/v1/businesses/${businessId}/coupons/redeem`, {
      method: "POST",
      body: { code },
      token,
    }),

  createReservation: (
    businessId: string,
    body: {
      customer_name: string;
      customer_phone: string;
      reservation_time: string;
      party_size: number;
      notes?: string;
    }
  ) => request<Reservation>(`/api/v1/businesses/${businessId}/reservations`, { method: "POST", body }),

  listReservations: (token: string, businessId: string) =>
    request<Reservation[]>(`/api/v1/businesses/${businessId}/reservations`, { token }),

  updateReservationStatus: (token: string, businessId: string, reservationId: string, status: ReservationStatus) =>
    request<Reservation>(`/api/v1/businesses/${businessId}/reservations/${reservationId}`, {
      method: "PATCH",
      body: { status },
      token,
    }),

  getPerformance: (token: string, businessId: string) =>
    request<Performance>(`/api/v1/businesses/${businessId}/performance`, { token }),

  listTransactions: (token: string, businessId: string) =>
    request<Transaction[]>(`/api/v1/businesses/${businessId}/transactions`, { token }),

  createTransaction: (
    token: string,
    businessId: string,
    body: { amount: string; memo?: string; coupon_issue_id?: string; reservation_id?: string }
  ) => request<Transaction>(`/api/v1/businesses/${businessId}/transactions`, { method: "POST", body, token }),

  analyzeExpansion: (token: string, businessId: string) =>
    request<PartnerSuggestion[]>(`/api/v1/businesses/${businessId}/expansion/analyze`, {
      method: "POST",
      token,
    }),

  listExpansion: (token: string, businessId: string) =>
    request<PartnerSuggestion[]>(`/api/v1/businesses/${businessId}/expansion`, { token }),

  inviteExpansionPartner: (token: string, businessId: string, partnerBusinessId: string) =>
    request<PartnerSuggestion>(`/api/v1/businesses/${businessId}/expansion/${partnerBusinessId}/invite`, {
      method: "POST",
      token,
    }),

  generateExpansionMessage: (token: string, businessId: string, partnerBusinessId: string) =>
    request<PartnerSuggestion>(`/api/v1/businesses/${businessId}/expansion/${partnerBusinessId}/message`, {
      method: "POST",
      token,
    }),

  listIncomingExpansionInvites: (token: string, businessId: string) =>
    request<IncomingPartnerInvite[]>(`/api/v1/businesses/${businessId}/expansion/incoming`, { token }),

  acceptExpansionInvite: (token: string, businessId: string, senderBusinessId: string) =>
    request<IncomingPartnerInvite>(`/api/v1/businesses/${businessId}/expansion/${senderBusinessId}/accept`, {
      method: "POST",
      token,
    }),

  rejectExpansionInvite: (token: string, businessId: string, senderBusinessId: string) =>
    request<IncomingPartnerInvite>(`/api/v1/businesses/${businessId}/expansion/${senderBusinessId}/reject`, {
      method: "POST",
      token,
    }),

  getReferralJoinInfo: (referralToken: string) =>
    request<ReferralJoinInfo>(`/api/v1/referral/${referralToken}`),

  getMyHistory: (token: string) => request<MyHistory>("/api/v1/me/history", { token }),

  managerChat: (token: string, businessId: string, message: string) =>
    request<ChatResponse>(`/api/v1/businesses/${businessId}/manager/chat`, {
      method: "POST",
      body: { message },
      token,
    }),

  adminKpi: (token: string) => request<AdminKpi>("/api/v1/admin/kpi", { token }),

  adminStats: (token: string) => request<AdminStats>("/api/v1/admin/stats", { token }),

  adminListBusinesses: (token: string) =>
    request<AdminBusiness[]>("/api/v1/admin/businesses", { token }),

  adminUpdateBusinessStatus: (token: string, businessId: string, status: BusinessStatus) =>
    request<AdminBusiness>(`/api/v1/admin/businesses/${businessId}/status`, {
      method: "PATCH",
      body: { status },
      token,
    }),

  adminListUsers: (token: string) => request<AdminUser[]>("/api/v1/admin/users", { token }),

  adminBusinessGraph: (token: string) =>
    request<BusinessGraphEdge[]>("/api/v1/admin/business-graph", { token }),

  adminAiInteractionSummary: (token: string) =>
    request<AdminAiInteractionSummary[]>("/api/v1/admin/ai-interactions/summary", { token }),

  adminRecentAiInteractions: (token: string) =>
    request<AdminAiMessageDetail[]>("/api/v1/admin/ai-interactions/recent", { token }),

  adminListTouristPlaces: (token: string) =>
    request<TouristPlace[]>("/api/v1/admin/tourist-places", { token }),

  adminCreateTouristPlace: (
    token: string,
    body: { name: string; category: string; source_name?: string; source_url?: string; status?: TouristPlaceStatus }
  ) => request<TouristPlace>("/api/v1/admin/tourist-places", { method: "POST", body, token }),

  adminUpdateTouristPlace: (token: string, id: string, body: Partial<TouristPlace>) =>
    request<TouristPlace>(`/api/v1/admin/tourist-places/${id}`, { method: "PATCH", body, token }),

  // PILOT OPERATIONS DASHBOARD
  getBusinessPilotDashboard: (token: string, businessId: string, period: PilotPeriod) =>
    request<BusinessPilotDashboard>(`/api/v1/businesses/${businessId}/pilot/dashboard?period=${period}`, { token }),

  getAdminPilotOverview: (token: string, period: PilotPeriod) =>
    request<AdminPilotOverview>(`/api/v1/admin/pilot/overview?period=${period}`, { token }),

  updatePilotStatus: (token: string, businessId: string, pilotStatus: PilotStatus | null) =>
    request<AdminBusiness>(`/api/v1/admin/businesses/${businessId}/pilot-status`, {
      method: "PATCH",
      body: { pilot_status: pilotStatus },
      token,
    }),

  // CSV는 JSON이 아니라서 request<T>를 안 쓰고 직접 fetch해서 blob으로
  // 내려받는다 - 다운로드는 브라우저가 직접 트리거하도록 임시 링크를 쓴다.
  downloadPilotCsv: async (token: string, period: PilotPeriod): Promise<void> => {
    const response = await fetch(`${API_URL}/api/v1/admin/pilot/export.csv?period=${period}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!response.ok) {
      const data = await response.json().catch(() => null);
      throw new ApiError(response.status, typeof data?.detail === "string" ? data.detail : "다운로드에 실패했습니다.");
    }
    const blob = await response.blob();
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `pilot-${period}.csv`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
  },
};

export type PilotPeriod = "today" | "yesterday" | "7d" | "30d" | "all";
export const PILOT_PERIOD_LABELS: Record<PilotPeriod, string> = {
  today: "오늘",
  yesterday: "어제",
  "7d": "최근 7일",
  "30d": "최근 30일",
  all: "전체",
};

export type PilotStatus = "PILOT_ACTIVE" | "PILOT_PAUSED" | "PILOT_COMPLETED";
export const PILOT_STATUS_LABELS: Record<PilotStatus, string> = {
  PILOT_ACTIVE: "파일럿 진행 중",
  PILOT_PAUSED: "파일럿 일시중지",
  PILOT_COMPLETED: "파일럿 종료",
};

export interface FunnelStep {
  key: string;
  label: string;
  count: number;
  conversion_rate_from_previous: number | null;
}

export interface RevenueBreakdown {
  total_revenue: string;
  ai_connected_revenue: string;
  direct_revenue: string;
  assisted_revenue: string;
  unknown_revenue: string;
  ai_connected_transaction_count: number;
}

export interface AgentBreakdownRow {
  agent_type: string;
  interactions: number | null;
  recommendation_clicks: number | null;
  note: string | null;
}

export interface BusinessPilotDashboard {
  business_id: string;
  business_name: string;
  period: string;
  ai_interactions_total: number;
  ai_interactions_by_agent: Record<string, number>;
  coupons_issued: number;
  coupons_redeemed: number;
  reservations_created: number;
  reservations_completed: number;
  visits_confirmed: number;
  recommendation_clicks: number;
  funnel: FunnelStep[];
  revenue: RevenueBreakdown;
  agents: AgentBreakdownRow[];
}

export interface BusinessComparisonRow {
  business_id: string;
  business_name: string;
  pilot_status: PilotStatus | null;
  ai_interactions: number;
  recommendation_clicks: number;
  coupons_issued: number;
  reservations_created: number;
  visits_confirmed: number;
  transactions: number;
  direct_revenue: string;
  assisted_revenue: string;
  unknown_revenue: string;
  ai_connected_revenue: string;
}

export interface AdminPilotOverview {
  period: string;
  pilot_business_count: number;
  active_business_count: number;
  daily_active_businesses: number;
  weekly_active_businesses: number;
  businesses_using_ai: number;
  customer_ai_questions: number;
  chef_ai_questions: number;
  info_ai_questions: number;
  recommendation_impressions: number;
  recommendation_clicks: number;
  coupons_issued: number;
  coupons_redeemed: number;
  reservations_created: number;
  reservations_completed: number;
  visits_confirmed: number;
  transactions_created: number;
  revenue: RevenueBreakdown;
  revenue_by_business: Record<string, string>;
  expansion_runs: number;
  partner_candidates: number;
  partner_invites: number;
  referral_clicks: number;
  new_businesses_via_referral: number;
  funnel: FunnelStep[];
  businesses: BusinessComparisonRow[];
}

export interface AdminKpi {
  signed_up_businesses: number;
  active_owner_ai_last_30d: number;
  ai_response_count_last_30d: number;
  ai_recommendation_count_last_30d: number;
  coupon_conversion_rate: number | null;
  reservation_conversion_rate: number | null;
  actual_visits: number;
  ai_connected_revenue: string;
}

export interface AdminStats {
  businesses_by_status: Record<string, number>;
  users_by_role: Record<string, number>;
  reservations_by_status: Record<string, number>;
  coupons_issued: number;
  coupons_redeemed: number;
  partner_relationships_by_status: Record<string, number>;
  ai_interactions_last_30d: number;
  ai_interactions_by_agent_type: Record<string, number>;
  transactions_count: number;
  transactions_total_amount: string;
  transactions_amount_by_attribution: Record<string, string>;
  transactions_ai_connected_amount: string;
}

export interface AdminBusiness {
  id: string;
  name_ko: string;
  category: BusinessCategory;
  status: BusinessStatus;
  pilot_status: PilotStatus | null;
  owner_email: string | null;
  created_at: string;
}

export interface AdminUser {
  id: string;
  email: string;
  name: string;
  role: UserRole;
  created_at: string;
}

export interface AdminAiInteractionSummary {
  business_id: string | null;
  business_name: string | null;
  agent_type: string;
  count: number;
}

export interface BusinessGraphEdge {
  business_a_id: string;
  business_a_name: string;
  business_b_id: string;
  business_b_name: string;
  relationship_type: "PARTNER_TRACK" | "NEAR";
  status: PartnerRelationshipStatus | null;
  score: number | null;
  distance_m: number | null;
  created_at: string | null;
}

export type TouristPlaceStatus = "VERIFIED" | "UNVERIFIED" | "EXPIRED" | "DISABLED";

export interface TouristPlace {
  id: string;
  name: string;
  category: string;
  description: string | null;
  address: string | null;
  lon: number | null;
  lat: number | null;
  source_name: string | null;
  source_url: string | null;
  verified_at: string | null;
  expires_at: string | null;
  status: TouristPlaceStatus;
  created_at: string;
  updated_at: string;
}

export interface AdminAiMessageDetail {
  id: string;
  business_id: string | null;
  business_name: string | null;
  agent_type: string;
  user_message: string | null;
  reply: string | null;
  prompt_tokens: number | null;
  completion_tokens: number | null;
  estimated_cost_usd: string | null;
  prompt_version: string | null;
  created_at: string;
}

export interface MenuImageItem {
  id: string;
  name: string;
  image_url: string;
}

export interface ChatHistoryItem {
  role: "user" | "ai";
  text: string;
}

export interface ReservationDraft {
  customer_name: string | null;
  customer_phone: string | null;
  date: string | null;
  time: string | null;
  party_size: number | null;
  notes: string | null;
}

export interface ChatResponse {
  agent_type: string;
  reply: string;
  menu_images: MenuImageItem[];
  reservation_draft: ReservationDraft | null;
  interaction_id: string | null;
}

export type AiInteractionFeedback = "UP" | "DOWN";

export interface AiInteractionFeedbackResult {
  id: string;
  feedback: AiInteractionFeedback | null;
}

export interface RecommendationItem {
  id: string;
  name: string;
  category: string;
  source: "business" | "tourist_place";
  reason: string;
}

export interface RecommendationResponse {
  agent_type: string;
  reply: string;
  interaction_id: string | null;
  recommendations: RecommendationItem[];
}

export interface RecommendationClickResponse {
  id: string;
  ai_interaction_id: string;
  entity_id: string;
  entity_type: "business" | "tourist_place";
}

export interface Performance {
  period: string;
  ai_response_count: number;
  ai_response_count_by_agent_type: Record<string, number>;
  coupons_issued: number;
  coupons_redeemed: number;
  reservations_this_month: number;
  recommendation_clicks: number;
  recommendation_clicks_note: string;
  visits_confirmed: number;
  visits_confirmed_note: string;
  successful_referrals: number;
  successful_referrals_note: string;
  partner_invites_sent: number;
  partner_accepted: number;
  partner_performance_note: string;
  estimated_time_saved_minutes: number;
  estimated_time_saved_note: string;
  revenue_total: string;
  revenue_direct: string;
  revenue_assisted: string;
  revenue_unknown: string;
  revenue_ai_connected: string;
  revenue_ai_connected_note: string;
}

export type TransactionAttribution = "DIRECT" | "ASSISTED" | "UNKNOWN";

export interface Transaction {
  id: string;
  business_id: string;
  coupon_issue_id: string | null;
  reservation_id: string | null;
  amount: string;
  attribution: TransactionAttribution;
  memo: string | null;
  occurred_at: string;
  created_at: string;
}

export type PartnerRelationshipStatus = "SUGGESTED" | "INVITED" | "ACCEPTED" | "REJECTED";

export interface PartnershipEffectEstimate {
  candidate_monthly_visitors: number;
  estimated_interested_customers: number;
  estimated_converted_visits: number;
  estimated_additional_revenue: string;
  note: string;
}

export interface PartnerSuggestion {
  business_b_id: string;
  name_ko: string;
  category: BusinessCategory;
  is_claimed: boolean;
  score: number;
  reason: string;
  status: PartnerRelationshipStatus;
  invite_message: string | null;
  referral_token: string | null;
  effect_estimate: PartnershipEffectEstimate | null;
}

export interface ReferralJoinInfo {
  business_id: string;
  name_ko: string;
  category: BusinessCategory;
  address: string;
  is_claimed: boolean;
  sender_name: string;
}

export interface IncomingPartnerInvite {
  business_a_id: string;
  name_ko: string;
  category: BusinessCategory;
  score: number;
  reason: string;
  status: PartnerRelationshipStatus;
  invite_message: string | null;
  effect_estimate: PartnershipEffectEstimate | null;
}

export interface MyCouponHistoryItem {
  id: string;
  business_id: string;
  business_name: string;
  coupon_title: string;
  code: string;
  status: CouponIssueStatus;
  issued_at: string;
  redeemed_at: string | null;
}

export interface MyReservationHistoryItem {
  id: string;
  business_id: string;
  business_name: string;
  reservation_time: string;
  party_size: number;
  status: ReservationStatus;
  created_at: string;
}

export interface MyHistory {
  coupons: MyCouponHistoryItem[];
  reservations: MyReservationHistoryItem[];
}
