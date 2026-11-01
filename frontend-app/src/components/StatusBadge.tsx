import type { Payment } from "../api/client";

const colours: Record<Payment["status"], string> = {
  PENDING: "badge-warning",
  PROCESSING: "badge-info",
  COMPLETED: "badge-success",
  FAILED: "badge-error",
  REVERSED: "badge-ghost",
};

export function StatusBadge({ status }: { status: Payment["status"] }) {
  return (
    <span
      className={`inline-block rounded px-2 py-0.5 text-xs font-semibold uppercase tracking-wide ${colours[status]}`}
    >
      {status}
    </span>
  );
}
