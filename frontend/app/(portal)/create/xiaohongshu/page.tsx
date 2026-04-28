import { AgentForm } from "@/components/agent-form";

export default function XiaohongshuPage() {
  return (
    <AgentForm config={{
      title:       "小红书帖子 (Xiaohongshu Post)",
      description: "为小红书生成种草内容，符合平台调性，带话题标签和表情符号。",
      platform:    "Xiaohongshu",
      badge:       "中文",
      briefLabel:  "内容方向 / Brief",
      briefPlaceholder: "例如：推广我们的AI营销工具，目标受众：25-35岁跨境电商创业者，风格：真实分享、干货满满，带3个热门话题标签…",
    }} />
  );
}
