/**
 * Shared agent/analysis types — migrated from packages/types.
 *
 * These are pure type definitions shared within the frontend.
 * No business logic, no prompts, no AI clients.
 */

// ── Agent Analysis Types ──────────────────────────────────────

export type ImageType = "landscape" | "portrait_with_people" | "pure_portrait";

export type DeficiencyCategory =
  | "color"
  | "clarity"
  | "composition"
  | "portrait_detail"
  | "lighting"
  | "other";

export type DeficiencySeverity = "low" | "medium" | "high";

export type ImageDeficiency = {
  category: DeficiencyCategory;
  description: string;
  severity: DeficiencySeverity;
};

export type AgentImageAnalysis = {
  imageType: ImageType;
  imageTypeReason: string;
  deficiencies: ImageDeficiency[];
  summary: string;
  editPrompt: string;
};

// ── Agent Mode ────────────────────────────────────────────────

export type AgentMode = "agent" | "editor";
