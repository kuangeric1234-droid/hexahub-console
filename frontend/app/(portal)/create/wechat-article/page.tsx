import { AgentForm } from "@/components/agent-form";

export default function WeChatArticlePage() {
  return (
    <AgentForm config={{
      title:       "微信公众号文章 (WeChat Article)",
      description: "生成适合微信公众号的长图文内容，结构清晰，适合品牌深度传播。",
      platform:    "WeChat Article",
      badge:       "中文",
      briefLabel:  "文章主题 / Brief",
      briefPlaceholder: "例如：深度解读AI如何改变跨境营销，目标读者：品牌主和营销人，约800-1200字，带小标题和总结…",
    }} />
  );
}
