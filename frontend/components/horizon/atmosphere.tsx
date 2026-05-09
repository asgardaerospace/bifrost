"use client";

/**
 * Environmental atmosphere — Sprint 7.
 *
 * Single low-cost component that polls /environment and applies a band
 * attribute to <body>. The band drives the radial-gradient atmosphere
 * layer defined in globals.css (.atmosphere-layer + body[data-band=...]).
 *
 * Calm, restrained motion only. Operators with prefers-reduced-motion
 * see a steady tone (handled in CSS).
 */

import { useQuery } from "@tanstack/react-query";
import { useEffect } from "react";
import { api } from "@/lib/api";
import type { EnvironmentBand } from "@/types/api";

const BAND_FALLBACK: EnvironmentBand = "calm";

export function Atmosphere() {
  const { data } = useQuery({
    queryKey: ["sprint7-environment"],
    queryFn: api.environment,
    refetchInterval: 20_000,
    refetchOnWindowFocus: false,
  });

  const band: EnvironmentBand = data?.pulse.band ?? BAND_FALLBACK;

  useEffect(() => {
    if (typeof document === "undefined") return;
    document.body.setAttribute("data-band", band);
    return () => {
      // Leave the most recent band on cleanup so navigation between pages
      // doesn't flash to a default. The next mount overwrites it.
    };
  }, [band]);

  return (
    <div
      aria-hidden
      className="atmosphere-layer"
      data-testid="atmosphere-layer"
    />
  );
}

export function bandLabel(band: string): string {
  switch (band) {
    case "calm":
      return "Calm";
    case "active":
      return "Active";
    case "elevated":
      return "Elevated";
    case "critical":
      return "Critical";
    case "nominal":
      return "Nominal";
    case "watch":
      return "Watch";
    case "strain":
      return "Strain";
    default:
      return band;
  }
}

export function bandToneClass(band: string): string {
  switch (band) {
    case "critical":
      return "text-bandcritical";
    case "strain":
    case "elevated":
      return "text-bandstrain";
    case "watch":
      return "text-bandwatch";
    case "nominal":
    case "calm":
      return "text-bandnominal";
    case "active":
      return "text-accent";
    default:
      return "text-muted";
  }
}

export function bandRingClass(band: string): string {
  switch (band) {
    case "critical":
      return "ring-bandcritical/40";
    case "strain":
    case "elevated":
      return "ring-bandstrain/40";
    case "watch":
      return "ring-bandwatch/40";
    case "nominal":
    case "calm":
      return "ring-bandnominal/30";
    case "active":
      return "ring-accent/30";
    default:
      return "ring-border";
  }
}

export function bandFillClass(band: string): string {
  switch (band) {
    case "critical":
      return "bg-bandcritical/15";
    case "strain":
    case "elevated":
      return "bg-bandstrain/15";
    case "watch":
      return "bg-bandwatch/15";
    case "nominal":
    case "calm":
      return "bg-bandnominal/10";
    case "active":
      return "bg-accent/10";
    default:
      return "bg-border/40";
  }
}
