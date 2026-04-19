"use client";

import { API_BASE_URL_MISSING } from "@/lib/api";

export function ApiConfigBanner() {
  if (!API_BASE_URL_MISSING) return null;
  return (
    <div className="w-full border-b border-red bg-red/10 px-4 py-2 text-center font-mono text-xs text-red">
      Bifrost API is not configured. Set{" "}
      <span className="font-semibold">NEXT_PUBLIC_API_BASE_URL</span> in the
      deployment environment (e.g.{" "}
      <span className="font-semibold">
        https://api.bifrost.asgardaerospace.com/api/v1
      </span>
      ) and redeploy. Data calls will fail until this is set.
    </div>
  );
}
