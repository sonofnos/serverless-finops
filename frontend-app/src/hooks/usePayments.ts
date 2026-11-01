import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  fetchPayments,
  fetchPayment,
  fetchAccount,
  createPayment,
} from "../api/client";
import type { CreatePaymentInput } from "../api/client";

export const useAccount = (id: string) =>
  useQuery({ queryKey: ["account", id], queryFn: () => fetchAccount(id), enabled: !!id });

export const usePayments = (account_id: string) =>
  useQuery({
    queryKey: ["payments", account_id],
    queryFn: () => fetchPayments(account_id),
    enabled: !!account_id,
    refetchInterval: 5000, // poll every 5s (simulates subscription until AppSync connected)
  });

export const usePayment = (id: string) =>
  useQuery({
    queryKey: ["payment", id],
    queryFn: () => fetchPayment(id),
    enabled: !!id,
    refetchInterval: (q) =>
      q.state.data?.status === "PENDING" || q.state.data?.status === "PROCESSING"
        ? 2000
        : false,
  });

export const useCreatePayment = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: CreatePaymentInput) => createPayment(input),
    onSuccess: (payment) => {
      qc.invalidateQueries({ queryKey: ["payments", payment.source_account_id] });
      qc.invalidateQueries({ queryKey: ["payments", payment.dest_account_id] });
    },
  });
};
