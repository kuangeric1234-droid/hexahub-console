import { AgentForm } from "@/components/agent-form";

export default function AdCreativePage() {
  return (
    <AgentForm config={{
      title:       "Ad Creative",
      description: "Generate Meta ad concepts with visual direction, headline, primary text, CTA, and rationale.",
      platform:    "Ad Creative",
      badge:       "EN / 中文",
      briefLabel:  "Campaign Brief",
      briefPlaceholder: "e.g. Product: Hexa Hub AI platform. Objective: lead generation. Audience: e-commerce founders aged 28-45. Budget feel: premium but accessible. Need 3 ad concepts with different angles…",
    }} />
  );
}
