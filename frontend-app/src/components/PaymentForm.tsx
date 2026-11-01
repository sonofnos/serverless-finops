import { useState } from "react";
import { v4 as uuidv4 } from "uuid";
import { useCreatePayment } from "../hooks/usePayments";
import type { Payment } from "../api/client";

interface Props {
  sourceAccountId: string;
  onCreated?: (p: Payment) => void;
}

export function PaymentForm({ sourceAccountId, onCreated }: Props) {
  const [destId, setDestId] = useState("");
  const [amount, setAmount] = useState("");
  const [currency, setCurrency] = useState("USD");
  const [lastResult, setLastResult] = useState<string | null>(null);

  const { mutateAsync, isPending } = useCreatePayment();

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setLastResult(null);
    try {
      const payment = await mutateAsync({
        idempotency_key: uuidv4(),
        source_account_id: sourceAccountId,
        dest_account_id: destId,
        amount,
        currency,
      });
      setLastResult(`Payment ${payment.id} created — ${payment.status}`);
      setAmount("");
      onCreated?.(payment);
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { error?: string } } })?.response?.data?.error ?? "Request failed";
      setLastResult(`Error: ${msg}`);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-3">
      <div>
        <label className="block text-sm font-medium mb-1">Destination account ID</label>
        <input
          className="input w-full"
          placeholder="UUID"
          value={destId}
          onChange={(e) => setDestId(e.target.value)}
          required
        />
      </div>
      <div className="flex gap-3">
        <div className="flex-1">
          <label className="block text-sm font-medium mb-1">Amount</label>
          <input
            className="input w-full"
            type="number"
            min="0.01"
            step="0.01"
            placeholder="0.00"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            required
          />
        </div>
        <div className="w-24">
          <label className="block text-sm font-medium mb-1">Currency</label>
          <select
            className="input w-full"
            value={currency}
            onChange={(e) => setCurrency(e.target.value)}
          >
            <option>USD</option>
            <option>NGN</option>
            <option>GBP</option>
            <option>EUR</option>
          </select>
        </div>
      </div>
      <button type="submit" disabled={isPending} className="btn btn-primary w-full">
        {isPending ? "Sending…" : "Send Payment"}
      </button>
      {lastResult && (
        <p className={`text-sm ${lastResult.startsWith("Error") ? "text-red-500" : "text-green-600"}`}>
          {lastResult}
        </p>
      )}
    </form>
  );
}
