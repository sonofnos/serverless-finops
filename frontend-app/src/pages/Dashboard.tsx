import { useState } from "react";
import { useAccount } from "../hooks/usePayments";
import { PaymentForm } from "../components/PaymentForm";
import { TransactionList } from "../components/TransactionList";

// Demo account IDs — replace with real UUIDs after backend deploy
const DEMO_ACCOUNT_A = import.meta.env.VITE_ACCOUNT_A ?? "";
const DEMO_ACCOUNT_B = import.meta.env.VITE_ACCOUNT_B ?? "";

function AccountCard({ id }: { id: string }) {
  const { data: account, isLoading } = useAccount(id);
  if (!id) return null;
  if (isLoading) return <div className="card animate-pulse h-24" />;
  if (!account) return <div className="card text-sm text-gray-400">Account not found</div>;
  return (
    <div className="card">
      <p className="text-xs text-gray-400 uppercase tracking-wide">Account</p>
      <p className="text-lg font-semibold mt-1">{account.name}</p>
      <p className="text-3xl font-bold mt-1">
        {account.currency}{" "}
        {parseFloat(account.balance).toLocaleString("en-US", { minimumFractionDigits: 2 })}
      </p>
      <p className="text-xs text-gray-500 mt-1 font-mono">{account.id}</p>
    </div>
  );
}

export function Dashboard() {
  const [activeAccount, setActiveAccount] = useState(DEMO_ACCOUNT_A);
  const accounts = [DEMO_ACCOUNT_A, DEMO_ACCOUNT_B].filter(Boolean);

  return (
    <div className="max-w-4xl mx-auto px-4 py-8 space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Finops Dashboard</h1>
        <p className="text-sm text-gray-400 mt-1">
          Event-driven payment operations — Lambda · SQS · PostgreSQL · AppSync
        </p>
      </div>

      {/* Account cards */}
      {accounts.length > 0 ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {accounts.map((id) => (
            <button
              key={id}
              className={`text-left ${activeAccount === id ? "ring-2 ring-indigo-500" : ""}`}
              onClick={() => setActiveAccount(id)}
            >
              <AccountCard id={id} />
            </button>
          ))}
        </div>
      ) : (
        <div className="card">
          <p className="text-sm text-gray-400">
            Set <code>VITE_ACCOUNT_A</code> and <code>VITE_ACCOUNT_B</code> env vars to load
            live account data. Running against the local API at{" "}
            <code>{import.meta.env.VITE_API_URL ?? "http://localhost:3000"}</code>.
          </p>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Payment form */}
        <div className="card">
          <h2 className="text-base font-semibold mb-4">Send Payment</h2>
          {activeAccount ? (
            <PaymentForm sourceAccountId={activeAccount} />
          ) : (
            <p className="text-sm text-gray-400">Select an account above.</p>
          )}
        </div>

        {/* Transaction list */}
        <div className="card">
          <h2 className="text-base font-semibold mb-4">Transaction History</h2>
          {activeAccount ? (
            <TransactionList accountId={activeAccount} />
          ) : (
            <p className="text-sm text-gray-400">Select an account above.</p>
          )}
        </div>
      </div>
    </div>
  );
}
