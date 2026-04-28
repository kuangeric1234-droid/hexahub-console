import { AgentForm } from "@/components/agent-form";

export default function LinkedInPage() {
  return (
    <AgentForm config={{
      title:       "LinkedIn Post",
      description: "Generate professional long-form LinkedIn content optimised for engagement and reach.",
      platform:    "LinkedIn",
      badge:       "EN",
      briefLabel:  "Brief / Topic",
      briefPlaceholder: "e.g. Announce our new AI marketing platform, target cross-border e-commerce founders, conversational tone, include a question to drive comments…",
    }} />
  );
}
