import { Badge } from "@/components/ui/badge";
import type { Verdict } from "@/lib/types";

const STYLES: Record<Verdict, string> = {
  verified: "bg-green-100 text-green-800 border border-green-300",
  exists_only: "bg-sky-100 text-sky-800 border border-sky-300",
  altered: "bg-yellow-100 text-yellow-800 border border-yellow-300",
  not_supported: "bg-orange-100 text-orange-800 border border-orange-300",
  unverifiable: "bg-gray-100 text-gray-700 border border-gray-300",
  fabricated: "bg-red-100 text-red-800 border border-red-300",
};

const LABELS: Record<Verdict, string> = {
  verified: "Verified",
  exists_only: "Exists only",
  altered: "Altered",
  not_supported: "Not supported",
  unverifiable: "Unverifiable",
  fabricated: "Fabricated",
};

export function VerdictBadge({ verdict }: { verdict: Verdict }) {
  return <Badge className={STYLES[verdict]}>{LABELS[verdict]}</Badge>;
}
