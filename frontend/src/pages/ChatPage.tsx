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
          setLocalMessages((items) => [
            ...items,
            {
              ...message,
              status: 'done',
              created_at: nowIso()
            } as AgentMessage
          ]);
        },
        onAssistantStart: (message) => {
          setLocalMessages((items) => [
            ...items,
            {
              message_id: message.message_id,
              session_id: sessionId,
              role: 'assistant',
              content: '',
              status: 'sending',
              created_at: nowIso()
            } as AgentMessage
          ]);
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
        onAssistantDone: (message) => {
          setLocalMessages((items) =>
            items.map((item) =>
              item.message_id === message.message_id
                ? ({ ...item, ...message, status: 'done', created_at: item.created_at } as AgentMessage)
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
