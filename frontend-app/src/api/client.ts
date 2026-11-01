import axios from "axios";

const BASE = import.meta.env.VITE_API_URL ?? "http://localhost:3000";

export const api = axios.create({ baseURL: BASE });

export interface Account {
  id: string;
  owner_id: string;
  name: string;
  currency: string;
  balance: string;
  created_at: string;
}

export interface Payment {
  id: string;
  idempotency_key: string;
  source_account_id: string;
  dest_account_id: string;
  amount: string;
  currency: string;
  status: "PENDING" | "PROCESSING" | "COMPLETED" | "FAILED" | "REVERSED";
  failure_reason: string | null;
  created_at: string;
  updated_at: string;
}

export interface CreatePaymentInput {
  idempotency_key: string;
  source_account_id: string;
  dest_account_id: string;
  amount: string;
  currency: string;
}

export const fetchAccount = (id: string) =>
  api.get<Account>(`/accounts/${id}`).then((r) => r.data);

export const fetchPayments = (account_id: string) =>
  api
    .get<{ payments: Payment[] }>("/payments", { params: { account_id } })
    .then((r) => r.data.payments);

export const fetchPayment = (id: string) =>
  api.get<Payment>(`/payments/${id}`).then((r) => r.data);

export const createPayment = (input: CreatePaymentInput) =>
  api.post<Payment>("/payments", input).then((r) => r.data);

export const createAccount = (owner_id: string, name: string, currency = "USD") =>
  api
    .post<Account>("/accounts", { owner_id, name, currency })
    .then((r) => r.data);
