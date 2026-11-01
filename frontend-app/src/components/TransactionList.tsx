import { usePayments } from "../hooks/usePayments";
import { StatusBadge } from "./StatusBadge";

interface Props {
  accountId: string;
}

export function TransactionList({ accountId }: Props) {
  const { data: payments, isLoading, isError } = usePayments(accountId);

  if (isLoading) return <p className="text-sm text-gray-400">Loading…</p>;
  if (isError) return <p className="text-sm text-red-400">Failed to load transactions.</p>;
  if (!payments?.length) return <p className="text-sm text-gray-400">No transactions yet.</p>;

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-700 text-gray-400">
            <th className="py-2 text-left font-medium">ID</th>
            <th className="py-2 text-left font-medium">Amount</th>
            <th className="py-2 text-left font-medium">Direction</th>
            <th className="py-2 text-left font-medium">Status</th>
            <th className="py-2 text-left font-medium">Time</th>
          </tr>
        </thead>
        <tbody>
          {payments.map((p) => (
            <tr key={p.id} className="border-b border-gray-800 hover:bg-gray-800/40">
              <td className="py-2 font-mono text-xs text-gray-400">{p.id.slice(0, 8)}…</td>
              <td className="py-2 font-medium">
                {p.currency} {p.amount}
              </td>
              <td className="py-2 text-xs">
                {p.source_account_id === accountId ? (
                  <span className="text-red-400">↑ sent</span>
                ) : (
                  <span className="text-green-400">↓ received</span>
                )}
              </td>
              <td className="py-2">
                <StatusBadge status={p.status} />
              </td>
              <td className="py-2 text-xs text-gray-400">
                {new Date(p.created_at).toLocaleString()}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
