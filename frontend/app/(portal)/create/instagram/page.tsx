import { AgentForm } from "@/components/agent-form";

export default function InstagramPage() {
  return (
    <AgentForm config={{
      title:            "Instagram Post",
      description:      "Generate captions with emoji, hashtag sets, and a bilingual option for Australian-Chinese audiences.",
      platform:         "Instagram",
      badge:            "EN",
      briefLabel:       "Caption Brief",
      briefPlaceholder: "e.g. Product launch post for our new AI dashboard. Energetic tone. Include 3 hashtag options. Visual theme: clean, tech-forward…",
      showCollaborator: true,
    }} />
  );
}
