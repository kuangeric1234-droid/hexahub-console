import { AgentForm } from "@/components/agent-form";

export default function BlogPage() {
  return (
    <AgentForm config={{
      title:       "Blog Post",
      description: "Generate SEO-optimised long-form blog articles with structured headings and calls to action.",
      platform:    "Blog",
      badge:       "EN",
      briefLabel:  "Topic & Keywords",
      briefPlaceholder: "e.g. Topic: How AI is transforming cross-border marketing. Target keywords: AI marketing, cross-border e-commerce. Audience: marketing managers. Length: ~1200 words…",
    }} />
  );
}
