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

export type BusinessCategory = "RESTAURANT" | "CAFE" | "LODGING" | "EXPERIENCE";
export type BusinessStatus = "DRAFT" | "ACTIVE" | "DISABLED";

export interface Business {
  id: string;
  owner_user_id: string;
  name_ko: string;
  name_en: string | null;
  name_zh: string | null;
  category: BusinessCategory;
  address: string;
  phone: string | null;
  status: BusinessStatus;
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
  payment_methods: Record<string, unknown> | null;
  faq: Record<string, unknown> | null;
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

  getProfile: (id: string) => request<BusinessProfile>(`/api/v1/businesses/${id}/profile`),

  updateProfile: (token: string, id: string, body: Partial<BusinessProfile>) =>
    request<BusinessProfile>(`/api/v1/businesses/${id}/profile`, { method: "PATCH", body, token }),

  listMenus: (id: string) => request<Menu[]>(`/api/v1/businesses/${id}/menus`),

  createMenu: (
    token: string,
    businessId: string,
    body: { name: string; description?: string; price: string; is_signature?: boolean; allergy_info?: string }
  ) => request<Menu>(`/api/v1/businesses/${businessId}/menus`, { method: "POST", body, token }),

  deleteMenu: (token: string, businessId: string, menuId: string) =>
    request<void>(`/api/v1/businesses/${businessId}/menus/${menuId}`, { method: "DELETE", token }),
};
