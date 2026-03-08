import { defineStore } from "pinia";
import { ref, reactive, computed } from "vue";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  type: "text" | "tool_call" | "tool_result" | "error";
  toolName?: string;
  toolDesc?: string;
  toolInput?: Record<string, unknown>;
  timestamp: number;
  streaming?: boolean;
  thinking?: string;
}

export interface Skill {
  name: string;
  description: string;
}

export interface ConversationItem {
  id: string;
  title: string;
  source?: string;
  created_at: string | null;
  updated_at: string | null;
}

export interface MemoryNode {
  path: string;
  name: string;
  kind: "file" | "directory";
  children?: MemoryNode[];
  updated_at?: string | null;
}

export interface MemoryDocument {
  path: string;
  name: string;
  content: string;
  updated_at: string | null;
}

export const useChatStore = defineStore("chat", () => {
  // 默认使用相对路径，依赖 Nginx 的 proxy_pass 反向代理到 backend
  // 如果本地开发 npm run dev 配置了 VITE_WS_URL 则使用本地的直连代理
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  
  // WebSocket 地址：优先取环境变量，没有则组合当前域名 + /ws/chat
  const defaultWsUrl = `${protocol}//${window.location.host}/ws/chat`;
  const WS_URL = import.meta.env.VITE_WS_URL || defaultWsUrl;
  
  // REST API 地址：优先取环境变量，没有则使用空字符串（即相对路径，由浏览器自动加上当前域名发送给 Nginx）
  const backendUrl = import.meta.env.VITE_API_BASE_URL || "";

  const messages = reactive<ChatMessage[]>([]);
  const isConnected = ref(false);
  const isLoading = ref(false);
  const sessionId = ref<string | null>(null);
  const skills = ref<Skill[]>([]);
  const conversations = ref<ConversationItem[]>([]);
  const currentConversationId = ref<string | null>(null);
  const memoryTree = ref<MemoryNode[]>([]);
  const selectedMemoryPath = ref<string | null>(null);
  const memoryContent = ref<MemoryDocument | null>(null);
  const memoryError = ref<string | null>(null);
  const isMemoryTreeLoading = ref(false);
  const isMemoryContentLoading = ref(false);
  const isMemoryDeleting = ref(false);
  const isMemoryTreeLoaded = ref(false);
  const isMemoryLoading = computed(
    () =>
      isMemoryTreeLoading.value ||
      isMemoryContentLoading.value ||
      isMemoryDeleting.value
  );

  let ws: WebSocket | null = null;
  let messageIdCounter = 0;

  function genId(): string {
    return `msg-${Date.now()}-${messageIdCounter++}`;
  }

  function findFirstMemoryFile(nodes: MemoryNode[]): string | null {
    for (const node of nodes) {
      if (node.kind === "file") return node.path;
      if (node.children?.length) {
        const childPath = findFirstMemoryFile(node.children);
        if (childPath) return childPath;
      }
    }

    return null;
  }

  function treeContainsPath(nodes: MemoryNode[], targetPath: string): boolean {
    for (const node of nodes) {
      if (node.path === targetPath) return true;
      if (node.children?.length && treeContainsPath(node.children, targetPath)) {
        return true;
      }
    }

    return false;
  }

  function findRecentToolInput(
    toolName?: string,
  ): Record<string, unknown> | undefined {
    if (!toolName) return undefined;

    for (let index = messages.length - 1; index >= 0; index -= 1) {
      const message = messages[index];
      if (
        message?.type === "tool_call" &&
        message.toolName === toolName &&
        message.toolInput
      ) {
        return message.toolInput;
      }
    }

    return undefined;
  }

  function getToolPath(toolInput?: Record<string, unknown>): string | null {
    const value = toolInput?.file_path ?? toolInput?.path;
    return typeof value === "string" && value.trim() ? value.trim() : null;
  }

  function handleMemoryArtifact(toolInput?: Record<string, unknown>) {
    const path = getToolPath(toolInput);
    if (!path || !path.startsWith("/memories/")) return;

    if (isMemoryTreeLoaded.value) {
      void fetchMemoryTree(true);
      return;
    }

    isMemoryTreeLoaded.value = false;
  }

  // ─── WebSocket ──────────────────────────────

  function connect() {
    if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
        return;
    }
    
    ws = new WebSocket(WS_URL);

    ws.onopen = () => {
      isConnected.value = true;
      // 如果有当前会话，绑定到该会话
      ws?.send(
        JSON.stringify({
          type: "init",
          conversation_id: currentConversationId.value,
        })
      );
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);

      switch (data.type) {
        case "session":
          sessionId.value = data.session_id;
          if (data.conversation_id) {
            currentConversationId.value = data.conversation_id;
          }
          break;

        case "text":
          messages.push({
            id: genId(),
            role: "assistant",
            content: data.content,
            type: "text",
            timestamp: Date.now(),
          });
          break;

        case "text_delta":
          if (messages.length > 0) {
            const lastMsg = messages[messages.length - 1];
            // 如果最后一条消息是 assistant 的文本消息，直接追加文本
            if (lastMsg && lastMsg.role === "assistant" && lastMsg.type === "text") {
              lastMsg.content += data.content;
              break;
            }
          }
          // 如果没有，或者最后一条不是文本消息（可能是工具调用等），则新建一条
          messages.push({
            id: genId(),
            role: "assistant",
            content: data.content,
            type: "text",
            timestamp: Date.now(),
            streaming: true,
          });
          break;

        case "thinking_delta":
          // 思考内容追加到最后一条助手消息，或新建一条
          if (messages.length > 0) {
            const lastMsg = messages[messages.length - 1];
            if (lastMsg && lastMsg.role === "assistant") {
              lastMsg.thinking = (lastMsg.thinking || "") + data.content;
              break;
            }
          }
          messages.push({
            id: genId(),
            role: "assistant",
            content: "",
            type: "text",
            timestamp: Date.now(),
            streaming: true,
            thinking: data.content,
          });
          break;

        case "tool_call":
          messages.push({
            id: genId(),
            role: "system",
            content: data.tool_desc || `正在执行 Tool: **${data.tool_name}**`,
            type: "tool_call",
            toolName: data.tool_name,
            toolDesc: data.tool_desc,
            toolInput: data.tool_input,
            timestamp: Date.now(),
          });
          break;

        case "tool_result":
          const toolResultInput = data.tool_input || findRecentToolInput(data.tool_name);
          messages.push({
            id: genId(),
            role: "system",
            content: data.result,
            type: "tool_result",
            toolName: data.tool_name,
            toolInput: toolResultInput,
            timestamp: Date.now(),
          });
          handleMemoryArtifact(toolResultInput);
          break;

        case "done":
          isLoading.value = false;
          // 标记最后一条助手消息为非流式，触发完整 Markdown 渲染
          if (messages.length > 0) {
            const lastMsg = messages[messages.length - 1];
            if (lastMsg && lastMsg.role === "assistant" && lastMsg.streaming) {
              lastMsg.streaming = false;
            }
          }
          // 刷新会话列表（标题可能更新了）
          fetchConversations();
          break;

        case "error":
          messages.push({
            id: genId(),
            role: "system",
            content: data.content,
            type: "error",
            timestamp: Date.now(),
          });
          isLoading.value = false;
          break;

        case "cleared":
          messages.length = 0;
          break;

        case "title_update":
          // 更新会话列表中的标题
          const conv = conversations.value.find(
            (c) => c.id === data.conversation_id
          );
          if (conv) {
            conv.title = data.title;
          }
          break;
      }
    };

    ws.onclose = () => {
      isConnected.value = false;
      setTimeout(connect, 3000);
    };

    ws.onerror = () => {
      isConnected.value = false;
    };
  }

  function sendMessage(displayContent: string, sendContent?: string) {
    if (!ws || !displayContent.trim()) return;

    messages.push({
      id: genId(),
      role: "user",
      content: displayContent,
      type: "text",
      timestamp: Date.now(),
    });

    isLoading.value = true;
    ws.send(JSON.stringify({ type: "message", content: sendContent || displayContent }));
  }

  function clearChat() {
    if (!ws) return;
    ws.send(JSON.stringify({ type: "clear" }));
  }

  function abortAgent() {
    if (!ws || !isLoading.value) return;
    ws.send(JSON.stringify({ type: "abort" }));
  }

  // ─── REST API: 会话管理 ─────────────────────

  async function fetchConversations(query?: string) {
    try {
      const url = query?.trim()
        ? `${backendUrl}/api/conversations?q=${encodeURIComponent(query.trim())}`
        : `${backendUrl}/api/conversations`;
      const res = await fetch(url);
      conversations.value = await res.json();
    } catch (e) {
      console.warn("获取会话列表失败:", e);
    }
  }

  async function createConversation() {
    try {
      const res = await fetch(`${backendUrl}/api/conversations`, {
        method: "POST",
      });
      const conv: ConversationItem = await res.json();
      conversations.value.unshift(conv);
      await switchConversation(conv.id);
    } catch (e) {
      console.warn("创建会话失败:", e);
    }
  }

  async function switchConversation(convId: string) {
    currentConversationId.value = convId;
    messages.length = 0;

    // 加载历史消息
    try {
      const res = await fetch(
        `${backendUrl}/api/conversations/${convId}/messages`
      );
      const historyMsgs: Array<{
        id: string;
        role: string;
        content: string;
        type: string;
        tool_name: string | null;
        tool_input: Record<string, unknown> | null;
        thinking: string | null;
        created_at: string | null;
      }> = await res.json();

      for (const m of historyMsgs) {
        messages.push({
          id: m.id,
          role: m.role as "user" | "assistant" | "system",
          content: m.role === 'user' 
            ? m.content.replace(/<system_hint>[\s\S]*?<\/system_hint>/g, '').trim() 
            : m.content,
          type: m.type as "text" | "tool_call" | "tool_result" | "error",
          toolName: m.tool_name || undefined,
          toolInput:
            m.tool_input ||
            ((m.type === "tool_result" && m.tool_name)
              ? findRecentToolInput(m.tool_name)
              : undefined),
          thinking: m.thinking || undefined,
          timestamp: m.created_at ? new Date(m.created_at).getTime() : Date.now(),
        });
      }
    } catch (e) {
      console.warn("加载历史消息失败:", e);
    }

    // 重新绑定 WebSocket 到新会话
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(
        JSON.stringify({
          type: "init",
          conversation_id: convId,
        })
      );
    }
  }

  async function deleteConversation(convId: string) {
    try {
      await fetch(`${backendUrl}/api/conversations/${convId}`, {
        method: "DELETE",
      });
      conversations.value = conversations.value.filter((c) => c.id !== convId);

      // 如果删的是当前会话，切换到第一个或清空
      if (currentConversationId.value === convId) {
        if (conversations.value.length > 0 && conversations.value[0]) {
          await switchConversation(conversations.value[0].id);
        } else {
          currentConversationId.value = null;
          messages.length = 0;
        }
      }
    } catch (e) {
      console.warn("删除会话失败:", e);
    }
  }

  // ─── Skills ─────────────────────────────────

  async function fetchSkills() {
    try {
      const res = await fetch(`${backendUrl}/api/skills`);
      skills.value = await res.json();
    } catch (e) {
      console.warn("获取 Skills 列表失败:", e);
    }
  }

  async function fetchMemoryTree(force = false) {
    if (isMemoryTreeLoading.value) return;
    if (isMemoryTreeLoaded.value && !force) return;

    isMemoryTreeLoading.value = true;
    memoryError.value = null;

    try {
      const res = await fetch(`${backendUrl}/api/memories/tree`);
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }

      const tree: MemoryNode[] = await res.json();
      memoryTree.value = tree;
      isMemoryTreeLoaded.value = true;

      const nextPath =
        selectedMemoryPath.value && treeContainsPath(tree, selectedMemoryPath.value)
          ? selectedMemoryPath.value
          : findFirstMemoryFile(tree);

      if (!nextPath) {
        selectedMemoryPath.value = null;
        memoryContent.value = null;
        return;
      }

      if (force || memoryContent.value?.path !== nextPath) {
        await fetchMemoryContent(nextPath);
      }
    } catch (e) {
      memoryError.value = "加载记忆失败";
      console.warn("加载记忆树失败:", e);
      if (!memoryTree.value.length) {
        selectedMemoryPath.value = null;
        memoryContent.value = null;
      }
    } finally {
      isMemoryTreeLoading.value = false;
    }
  }

  async function fetchMemoryContent(path: string) {
    if (!path) return;

    selectedMemoryPath.value = path;
    isMemoryContentLoading.value = true;
    memoryError.value = null;

    try {
      const res = await fetch(
        `${backendUrl}/api/memories/content?path=${encodeURIComponent(path)}`
      );
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }

      memoryContent.value = await res.json();
    } catch (e) {
      memoryContent.value = null;
      memoryError.value = "读取记忆失败";
      console.warn("读取记忆文档失败:", e);
    } finally {
      isMemoryContentLoading.value = false;
    }
  }

  async function deleteMemoryFile(path: string) {
    if (!path || isMemoryDeleting.value) return;

    isMemoryDeleting.value = true;
    memoryError.value = null;

    try {
      const res = await fetch(
        `${backendUrl}/api/memories/content?path=${encodeURIComponent(path)}`,
        { method: "DELETE" }
      );
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }

      if (selectedMemoryPath.value === path) {
        memoryContent.value = null;
      }

      await fetchMemoryTree(true);
    } catch (e) {
      memoryError.value = "删除记忆失败";
      console.warn("删除记忆文件失败:", e);
    } finally {
      isMemoryDeleting.value = false;
    }
  }

  function disconnect() {
    ws?.close();
    ws = null;
  }

  // 组件卸载时不要清理全局连接，所以通常不再这里定义 onUnmounted
  // 但如果你有特殊需求，可以使用 application 级别的钩子

  return {
    messages,
    isConnected,
    isLoading,
    sessionId,
    skills,
    conversations,
    currentConversationId,
    memoryTree,
    selectedMemoryPath,
    memoryContent,
    memoryError,
    isMemoryLoading,
    connect,
    sendMessage,
    clearChat,
    abortAgent,
    fetchConversations,
    createConversation,
    switchConversation,
    deleteConversation,
    fetchSkills,
    fetchMemoryTree,
    fetchMemoryContent,
    deleteMemoryFile,
    disconnect
  };
});
