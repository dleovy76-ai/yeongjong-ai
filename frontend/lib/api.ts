const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

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

  const response = await fetch(`${API_URL}${path}`, {
    method: options.method ?? "GET",
    headers,
    body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
  });

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
  options: Record<string, unknown> | null;
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
}

export interface CouponIssue {
  id: string;
  coupon_id: string;
  code: string;
  status: CouponIssueStatus;
  issued_at: string;
  redeemed_at: string | null;
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

  getBusiness: (id: string) => request<Business>(`/api/v1/businesses/${id}`),

  updateBusiness: (token: string, id: string, body: Partial<Business>) =>
    request<Business>(`/api/v1/businesses/${id}`, { method: "PATCH", body, token }),

  listUnclaimedBusinesses: (query: string) =>
    request<Business[]>(`/api/v1/businesses/unclaimed?query=${encodeURIComponent(query)}`),

  claimBusiness: (token: string, id: string) =>
    request<Business>(`/api/v1/businesses/${id}/claim`, { method: "POST", token }),

  getProfile: (id: string) => request<BusinessProfile>(`/api/v1/businesses/${id}/profile`),

  updateProfile: (token: string, id: string, body: Partial<BusinessProfile>) =>
    request<BusinessProfile>(`/api/v1/businesses/${id}/profile`, { method: "PATCH", body, token }),

  naverLookup: (token: string, id: string) =>
    request<NaverLookupCandidate>(`/api/v1/businesses/${id}/naver-lookup`, { token }),

  draftProfile: (token: string, id: string) =>
    request<ProfileDraft>(`/api/v1/businesses/${id}/profile/draft`, { method: "POST", token }),

  listMenus: (id: string) => request<Menu[]>(`/api/v1/businesses/${id}/menus`),

  createMenu: (
    token: string,
    businessId: string,
    body: { name: string; description?: string; price: string; is_signature?: boolean; allergy_info?: string }
  ) => request<Menu>(`/api/v1/businesses/${businessId}/menus`, { method: "POST", body, token }),

  deleteMenu: (token: string, businessId: string, menuId: string) =>
    request<void>(`/api/v1/businesses/${businessId}/menus/${menuId}`, { method: "DELETE", token }),

  chat: (businessId: string, message: string) =>
    request<ChatResponse>("/api/v1/ai/chat", { method: "POST", body: { business_id: businessId, message } }),

  chefChat: (businessId: string, message: string) =>
    request<ChatResponse>(`/api/v1/businesses/${businessId}/chef/chat`, { method: "POST", body: { message } }),

  recommend: (query: string) =>
    request<ChatResponse>("/api/v1/recommendations", { method: "POST", body: { query } }),

  listCoupons: (businessId: string, token?: string | null) =>
    request<Coupon[]>(`/api/v1/businesses/${businessId}/coupons`, { token }),

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

  managerChat: (token: string, businessId: string, message: string) =>
    request<ChatResponse>(`/api/v1/businesses/${businessId}/manager/chat`, {
      method: "POST",
      body: { message },
      token,
    }),

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
};

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

export interface ChatResponse {
  agent_type: string;
  reply: string;
}

export interface Performance {
  period: string;
  ai_response_count: number;
  coupons_issued: number;
  coupons_redeemed: number;
  estimated_time_saved_minutes: number;
  estimated_time_saved_note: string;
  revenue_total: string;
  revenue_direct: string;
  revenue_assisted: string;
  revenue_unknown: string;
  revenue_ai_connected: string;
  revenue_ai_connected_note: string;
}

export type TransactionAttribution = "DIRECT" | "NONE";

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

export interface PartnerSuggestion {
  business_b_id: string;
  name_ko: string;
  category: BusinessCategory;
  is_claimed: boolean;
  score: number;
  reason: string;
  status: PartnerRelationshipStatus;
  invite_message: string | null;
}

export interface IncomingPartnerInvite {
  business_a_id: string;
  name_ko: string;
  category: BusinessCategory;
  score: number;
  reason: string;
  status: PartnerRelationshipStatus;
  invite_message: string | null;
}
