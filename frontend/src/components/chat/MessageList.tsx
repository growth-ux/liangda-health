import { useEffect, useRef } from 'react';
import type { AgentMessage } from '../../api/agent';
import { MessageBubble } from './MessageBubble';

type Props = {
  messages: AgentMessage[];
  loading: boolean;
};

const STICK_TO_BOTTOM_THRESHOLD = 64;

export function MessageList({ messages, loading }: Props) {
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
        <div className="message-row">
          <div className="msg-avatar agent">家</div>
          <div className="msg-wrap">
            <div className="msg-bubble">
              <div className="msg-text">
                你好，雨微，今天可以问我一日三餐怎么安排。
              </div>
            </div>
            <div className="msg-time">现在</div>
          </div>
        </div>
      )}
      {messages.map((message) => (
        <MessageBubble key={message.message_id} message={message} />
      ))}
    </div>
  );
}
