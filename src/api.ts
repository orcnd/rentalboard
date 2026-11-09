export interface Equipment {
  id: string;
  name: string;
  category: string;
  serial: string;
  day_rate: number;
  state: string;
}
export interface Customer {
  id: string;
  name: string;
  email: string;
  phone: string;
}
export interface Reservation {
  id: string;
  equipment_id: string;
  customer_id: string;
  starts_on: string;
  ends_on: string;
  day_rate: number;
  status: string;
  notes: string;
  equipment_name: string;
  category: string;
  customer_name: string;
}
export interface User {
  id: string;
  name: string;
  email: string;
  role: string;
  workspace_id: string;
  workspace_name: string;
  csrf: string;
}
export interface Session {
  user: User;
  today: string;
  demo_enabled: boolean;
  plan: { name: string; equipment_limit: number };
}
export interface Board {
  equipment: Equipment[];
  customers: Customer[];
  reservations: Reservation[];
}
let csrf = "";
export function setCsrf(value: string) {
  csrf = value;
}
export async function api<T>(
  path: string,
  method = "GET",
  body?: unknown,
): Promise<T> {
  const response = await fetch("/api" + path, {
    method,
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
      ...(csrf ? { "X-CSRF-Token": csrf } : {}),
    },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });
  const data = await response
    .json()
    .catch(() => ({
      detail: "Sunucuya ulaşılamadı. Biraz sonra tekrar dene.",
    }));
  if (!response.ok) {
    const message =
      typeof data.detail === "string"
        ? data.detail
        : Array.isArray(data.detail)
          ? "Alanları kontrol et. Adlar en az 2 karakter, parola en az 12 karakter olmalı."
          : "İşlem tamamlanamadı.";
    throw new Error(message);
  }
  return data as T;
}
export const money = (cents: number) =>
  new Intl.NumberFormat("tr-TR", {
    style: "currency",
    currency: "TRY",
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  }).format(cents / 100);
export function day(value: string) {
  return new Date(value + "T12:00:00Z");
}
export function iso(value: Date) {
  return value.toISOString().slice(0, 10);
}
export function add(value: string, days: number) {
  const date = day(value);
  date.setUTCDate(date.getUTCDate() + days);
  return iso(date);
}
export function nights(start: string, end: string) {
  return Math.round((day(end).getTime() - day(start).getTime()) / 86400000);
}
