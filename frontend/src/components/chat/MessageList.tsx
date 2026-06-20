import { useEffect, useRef } from 'react';
import type { AgentMessage } from '../../api/agent';
import type { HealthAnalysisOverview } from '../../api/healthAnalysis';
import { MessageBubble } from './MessageBubble';
import type { EvidenceModalState } from './evidence/EvidenceActions';

type Props = {
  messages: AgentMessage[];
  loading: boolean;
  overview?: HealthAnalysisOverview | null;
  overviewLoading?: boolean;
  overviewError?: boolean;
  modalState: EvidenceModalState;
  onModalChange: (next: EvidenceModalState) => void;
  mobileEvidenceMode?: boolean;
};

const STICK_TO_BOTTOM_THRESHOLD = 64;

function greetingText() {
  const hour = new Date().getHours();
  if (hour < 11) return '早上好';
  if (hour < 14) return '中午好';
  if (hour < 18) return '下午好';
  return '晚上好';
}

function WelcomeSummary({
  overview,
  loading,
  error
}: {
  overview?: HealthAnalysisOverview | null;
  loading?: boolean;
  error?: boolean;
}) {
  const familyName = overview?.family.name ?? '雨微';
  const items = overview?.summary.slice(0, 3) ?? [];

  return (
    <div className="message-row">
      <div className="msg-avatar agent">家</div>
      <div className="msg-wrap">
        <div className="msg-bubble welcome-summary-bubble">
          <div className="welcome-summary-title">
            {greetingText()}，{familyName}。☀️ 今天的家庭健康摘要：
          </div>
          {loading && <div className="welcome-summary-muted">正在整理今日家庭健康摘要...</div>}
          {!loading && error && (
            <div className="welcome-summary-muted">今天可以问我一日三餐怎么安排，也可以让我帮你看报告。</div>
          )}
          {!loading && !error && items.length === 0 && (
            <div className="welcome-summary-muted">暂无可用摘要。可以先添加家人或上传近期体检报告。</div>
          )}
          {!loading && !error && items.length > 0 && (
            <ul className="welcome-summary-list">
              {items.map((item) => (
                <li key={item.text} className={`welcome-summary-${item.level}`}>
                  {item.text}
                </li>
              ))}
            </ul>
          )}
        </div>
        <div className="msg-time">现在</div>
      </div>
    </div>
  );
}

export function MessageList({
  messages,
  loading,
  overview,
  overviewLoading,
  overviewError,
  modalState,
  onModalChange,
  mobileEvidenceMode = false,
}: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  // 记录是否“贴底”：用户主动上滑读历史时不再被流式输出拽回底部
  const stickToBottomRef = useRef(true);

  function handleScroll() {
    const node = containerRef.current;
    if (!node) return;
    const distanceFromBottom = node.scrollHeight - node.scrollTop - node.clientHeight;
    stickToBottomRef.current = distanceFromBottom <= STICK_TO_BOTTOM_THRESHOLD;
  }

  useEffect(() => {
    const node = containerRef.current;
    if (!node) return;
    // 切换会话 / 首屏加载：必须滚到底
    if (loading || stickToBottomRef.current) {
      node.scrollTop = node.scrollHeight;
      stickToBottomRef.current = true;
    }
  }, [messages, loading]);

  return (
    <div ref={containerRef} className="chat-messages" onScroll={handleScroll}>
      {loading && <div className="empty-state">正在加载消息...</div>}
      {!loading && messages.length === 0 && (
        <WelcomeSummary overview={overview} loading={overviewLoading} error={overviewError} />
      )}
      {messages.map((message) => (
        <MessageBubble
          key={message.message_id}
          message={message}
          modalState={modalState}
          onModalChange={onModalChange}
          mobileEvidenceMode={mobileEvidenceMode}
        />
      ))}
    </div>
  );
}
