import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  createAgentSession,
  deleteAgentSession,
  listAgentMessages,
  listAgentSessions,
  listQuickActions,
  sendAgentMessageStream
} from '../api/agent';
import type { AgentMessage, Attachment } from '../api/agent';
import { uploadPdf } from '../api/kb';
import { AppShell } from '../components/AppShell';
import { ChatInput } from '../components/chat/ChatInput';
import { MessageList } from '../components/chat/MessageList';
import { SessionList } from '../components/chat/SessionList';
import { UploadReportDialog } from '../components/UploadReportDialog';

function nowIso() {
  return new Date().toISOString();
}

export function ChatPage() {
  const queryClient = useQueryClient();
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [draft, setDraft] = useState('');
  const [localMessages, setLocalMessages] = useState<AgentMessage[]>([]);
  const [sendError, setSendError] = useState<string | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [attachments, setAttachments] = useState<Attachment[]>([]);
  const [uploadDialogOpen, setUploadDialogOpen] = useState(false);

  const sessionsQuery = useQuery({ queryKey: ['agent-sessions'], queryFn: listAgentSessions });
  const quickActionsQuery = useQuery({ queryKey: ['agent-quick-actions'], queryFn: listQuickActions });
  const messagesQuery = useQuery({
    queryKey: ['agent-messages', activeSessionId],
    queryFn: () => listAgentMessages(activeSessionId!),
    enabled: Boolean(activeSessionId)
  });

  const createSessionMutation = useMutation({
    mutationFn: () => createAgentSession('新对话'),
    onSuccess: async (session) => {
      setActiveSessionId(session.session_id);
      setLocalMessages([]);
      await queryClient.invalidateQueries({ queryKey: ['agent-sessions'] });
    }
  });

  const deleteSessionMutation = useMutation({
    mutationFn: deleteAgentSession,
    onSuccess: async () => {
      setActiveSessionId(null);
      setLocalMessages([]);
      await queryClient.invalidateQueries({ queryKey: ['agent-sessions'] });
    }
  });

  useEffect(() => {
    if (!activeSessionId && sessionsQuery.data && sessionsQuery.data.length > 0) {
      setActiveSessionId(sessionsQuery.data[0].session_id);
    }
  }, [activeSessionId, sessionsQuery.data]);

  const messages = useMemo(() => {
    return [...(messagesQuery.data ?? []), ...localMessages];
  }, [messagesQuery.data, localMessages]);

  const sendMutation = useMutation({
    mutationFn: async ({ content, messageAttachments = [] }: { content: string; messageAttachments?: Attachment[] }) => {
      let sessionId = activeSessionId;
      if (!sessionId) {
        const session = await createAgentSession('新对话');
        sessionId = session.session_id;
        setActiveSessionId(sessionId);
        await queryClient.invalidateQueries({ queryKey: ['agent-sessions'] });
      }

      await sendAgentMessageStream(sessionId, content, messageAttachments, {
        onUserMessage: (message) => {
          setLocalMessages((items) => {
            // 去重：handleSend 已经乐观渲染过一条 user 消息，临时 message_id 以 tmp_ 开头
            // 收到真实事件时按内容匹配并替换为真实 message_id
            const dupIndex = items.findIndex(
              (item) => item.role === 'user' && item.content === message.content && item.message_id.startsWith('tmp_')
            );
            if (dupIndex >= 0) {
              return items.map((item, i) =>
                i === dupIndex
                  ? ({
                      ...item,
                      message_id: message.message_id,
                      session_id: message.session_id,
                      attachments: message.attachments
                    } as AgentMessage)
                  : item
              );
            }
            return [
              ...items,
              {
                ...message,
                status: 'done',
                created_at: nowIso()
              } as AgentMessage
            ];
          });
        },
        onAssistantStart: (message) => {
          setLocalMessages((items) => {
            // 替换乐观占位：找到最后一条以 tmp_assistant_ 开头的 assistant 消息
            // 用真实 message_id 替换，不动 content（继续等第一条 delta）
            for (let i = items.length - 1; i >= 0; i--) {
              const item = items[i];
              if (item.role === 'assistant' && item.message_id.startsWith('tmp_assistant_')) {
                return items.map((it, idx) =>
                  idx === i
                    ? ({ ...it, message_id: message.message_id, session_id: sessionId } as AgentMessage)
                    : it
                );
              }
            }
            // 兜底：占位丢了（或刷新后重建），追加一条新的
            return [
              ...items,
              {
                message_id: message.message_id,
                session_id: sessionId,
                role: 'assistant',
                content: '',
                status: 'sending',
                created_at: nowIso()
              } as AgentMessage
            ];
          });
        },
        onDelta: (content) => {
          setLocalMessages((items) =>
            items.map((item, index) =>
              index === items.length - 1 && item.role === 'assistant'
                ? { ...item, content: item.content + content }
                : item
            )
          );
        },
        onProductRecommendations: (payload) => {
          setLocalMessages((items) =>
            items.map((item) =>
              item.message_id === payload.message_id && item.role === 'assistant'
                ? ({ ...item, product_recommendations: payload.items } as AgentMessage)
                : item
            )
          );
        },
        onAssistantDone: (message) => {
          // 注意：message 里可能没带 product_recommendations（如果后端没在 done 事件里回填），
          // 保留 onProductRecommendations 阶段已写入的本地字段；后端带了就以后端为准。
          setLocalMessages((items) =>
            items.map((item) =>
              item.message_id === message.message_id
                ? ({
                    ...item,
                    ...message,
                    product_recommendations:
                      message.product_recommendations ?? item.product_recommendations,
                    status: 'done',
                    created_at: item.created_at
                  } as AgentMessage)
                : item
            )
          );
        }
      });
    },
    onMutate: () => setSendError(null),
    onSuccess: async () => {
      setLocalMessages([]);
      await queryClient.invalidateQueries({ queryKey: ['agent-sessions'] });
      await queryClient.invalidateQueries({ queryKey: ['agent-messages'] });
    },
    onError: (error: Error) => {
      setSendError(error.message);
      setLocalMessages((items) =>
        items.map((item, index) => (index === items.length - 1 ? { ...item, status: 'failed' } : item))
      );
    }
  });

  const uploadMutation = useMutation({
    mutationFn: async ({ file, memberId }: { file: File; memberId: string }) => {
      const result = await uploadPdf({ file, memberId });
      return { file, result };
    },
    onMutate: () => {
      setUploadError(null);
      setSendError(null);
    },
    onError: (error: Error) => setUploadError(error.message)
  });

  function handleSend() {
    const content = draft.trim();
    if (!content && attachments.length === 0) return;
    if (sendMutation.isPending || uploadMutation.isPending) return;
    // 乐观渲染：用户消息立刻进聊天框，不等后端 SSE user_message 事件
    // （该事件被 _remember_user_message 阻塞数秒，会让用户以为消息没发出去）
    const optimisticId = `tmp_${crypto.randomUUID()}`;
    // 助手占位：assistant_start 事件要等记忆写入完成才到，先放一个 tmp_assistant_ 占位
    // 让"正在生成"提示立即出现，避免用户以为消息没发出去
    const assistantPlaceholderId = `tmp_assistant_${crypto.randomUUID()}`;
    setLocalMessages((items) => [
      ...items,
      {
        message_id: optimisticId,
        session_id: activeSessionId ?? '',
        role: 'user',
        content,
        status: 'done',
        created_at: nowIso(),
        attachments: attachments.length > 0 ? attachments : undefined
      } as AgentMessage,
      {
        message_id: assistantPlaceholderId,
        session_id: activeSessionId ?? '',
        role: 'assistant',
        content: '',
        status: 'sending',
        created_at: nowIso()
      } as AgentMessage
    ]);
    // 点击发送后立刻清空输入框和附件，不等流式回复结束
    setDraft('');
    setAttachments([]);
    setSendError(null);
    sendMutation.mutate({ content, messageAttachments: attachments });
  }

  function handleUpload(_file: File) {
    setUploadDialogOpen(true);
  }

  function handleRemoveAttachment(index: number) {
    setAttachments((prev) => prev.filter((_, i) => i !== index));
  }

  return (
    <AppShell title="与管家对话" activeId="chat">
      <div className="chat-layout">
        <SessionList
          sessions={sessionsQuery.data ?? []}
          activeSessionId={activeSessionId}
          onSelect={(sessionId) => {
            setActiveSessionId(sessionId);
            setLocalMessages([]);
            setSendError(null);
          }}
          onCreate={() => createSessionMutation.mutate()}
          onDelete={(sessionId) => deleteSessionMutation.mutate(sessionId)}
          deleting={deleteSessionMutation.isPending}
        />
        <section className="chat-main">
          <div className="chat-header">
            <div className="chat-agent-avatar">家</div>
            <div>
              <div className="chat-agent-name">Agent 管家</div>
              <div className="chat-agent-status">在线 · 已连接家庭健康档案、报告和商城推荐</div>
            </div>
          </div>
          {sessionsQuery.isError && <div className="chat-inline-error">会话列表加载失败</div>}
          {messagesQuery.isError && <div className="chat-inline-error">消息加载失败</div>}
          {uploadMutation.isPending && <div className="chat-inline-info">正在上传并解析报告...</div>}
          <MessageList messages={messages} loading={messagesQuery.isLoading} />
          <ChatInput
            value={draft}
            attachments={attachments}
            quickActions={quickActionsQuery.data ?? []}
            sending={sendMutation.isPending || createSessionMutation.isPending}
            uploading={uploadMutation.isPending}
            error={sendError || uploadError}
            onChange={setDraft}
            onSend={handleSend}
            onUpload={handleUpload}
            onRemoveAttachment={handleRemoveAttachment}
            onQuickAction={(action) => setDraft(action.label)}
          />
        </section>
      </div>
      <UploadReportDialog
        open={uploadDialogOpen}
        uploading={uploadMutation.isPending}
        error={uploadError}
        onClose={() => setUploadDialogOpen(false)}
        onUpload={(payload) => {
          uploadMutation.mutate(payload, {
            onSuccess: (data) => {
              const newAttachment: Attachment = {
                name: data.file.name,
                url: `已上传报告：${data.file.name}`,
                type: 'pdf'
              };
              setAttachments((prev) => [...prev, newAttachment]);
              setUploadDialogOpen(false);
            }
          });
        }}
      />
    </AppShell>
  );
}
