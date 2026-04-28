import { AgentForm } from "@/components/agent-form";

export default function WeChatMomentsPage() {
  return (
    <AgentForm config={{
      title:       "朋友圈文案 (WeChat Moments)",
      description: "生成适合朋友圈的简短走心文案，自然不生硬，带互动感。",
      platform:    "WeChat Moments",
      badge:       "中文",
      briefLabel:  "内容方向 / Brief",
      briefPlaceholder: "例如：分享我们的产品上线，语气轻松接地气，不超过150字，结尾引导点赞或留言…",
    }} />
  );
}
