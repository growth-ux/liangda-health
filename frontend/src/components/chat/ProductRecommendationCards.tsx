import { useState } from 'react';
import { Link } from 'react-router-dom';
import type { ProductRecommendationItem } from '../../api/agent';
import { addMallCartItem, submitProductFeedback, type ProductFeedbackType } from '../../api/mall';

type Props = {
  items: ProductRecommendationItem[];
  sessionId?: string;
  messageId?: string;
};

const FEEDBACK_BUTTONS: { type: ProductFeedbackType; icon: string; title: string }[] = [
  { type: 'like', icon: '👍', title: '喜欢' },
  { type: 'dislike', icon: '👎', title: '不喜欢' },
  { type: 'too_expensive', icon: '💸', title: '太贵' },
];

function truncateProductName(name: string) {
  const chars = Array.from(name);
  return chars.length > 10 ? `${chars.slice(0, 10).join('')}...` : name;
}

export function ProductRecommendationCards({ items, sessionId, messageId }: Props) {
  // 每张卡片独立记录反馈状态：{ product_id: feedback_type }
  const [feedbackMap, setFeedbackMap] = useState<Record<string, string>>({});
  // 加购状态：{ product_id: true }
  const [cartMap, setCartMap] = useState<Record<string, boolean>>({});
  // 提交后短暂显示的提示
  const [toast, setToast] = useState<string | null>(null);

  if (items.length === 0) return null;

  async function handleFeedback(productId: string, type: ProductFeedbackType, itemMemberId?: string | null) {
    if (feedbackMap[productId]) return; // 已反馈，不重复提交
    setFeedbackMap((prev) => ({ ...prev, [productId]: type }));
    try {
      const res = await submitProductFeedback(productId, type, {
        memberId: itemMemberId ?? undefined,
        sessionId,
        messageId,
      });
      setToast(res.replacement_hint ?? res.message);
      setTimeout(() => setToast(null), 3000);
    } catch {
      setFeedbackMap((prev) => {
        const next = { ...prev };
        delete next[productId];
        return next;
      });
      setToast('反馈提交失败，请重试');
      setTimeout(() => setToast(null), 3000);
    }
  }

  async function handleAddToCart(productId: string) {
    if (cartMap[productId]) return;
    try {
      await addMallCartItem(productId, 1);
      setCartMap((prev) => ({ ...prev, [productId]: true }));
      setToast('已加入购物车');
      setTimeout(() => setToast(null), 2500);
    } catch {
      setToast('加购失败，请重试');
      setTimeout(() => setToast(null), 2500);
    }
  }

  return (
    <section className="msg-product-section card-message">
      <div className="card-message-header info">🛒 可选商品</div>
      <div className="card-message-body">
        <div className="product-row">
          {items.map((item, index) => {
            const givenFeedback = feedbackMap[item.product_id];
            const inCart = cartMap[item.product_id];
            return (
              <div key={`${item.product_id}-${index}`} className="product-card-wrapper">
                <Link
                  to={`/mall/products/${item.product_id}`}
                  className={`product-card${index === 1 ? ' active' : ''}`}
                  title={item.reason}
                >
                  <div className="product-image">
                    {item.image_url ? (
                      <img
                        className="msg-product-photo"
                        src={item.image_url}
                        alt=""
                        loading="lazy"
                      />
                    ) : (
                      <span>{item.image_emoji ?? '🛒'}</span>
                    )}
                  </div>
                  <div className="product-info">
                    <div className="product-name" title={item.name}>
                      {truncateProductName(item.name)}
                    </div>
                    <div className="product-price">{item.price_text}</div>
                  </div>
                </Link>
                {/* 反馈 + 加购 按钮行 */}
                <div className="product-feedback-row">
                  {FEEDBACK_BUTTONS.map((btn) => {
                    const isActive = givenFeedback === btn.type;
                    const isDisabled = !!givenFeedback && !isActive;
                    return (
                      <button
                        key={btn.type}
                        className={`feedback-btn${isActive ? ' active' : ''}${isDisabled ? ' disabled' : ''}`}
                        title={btn.title}
                        disabled={!!givenFeedback}
                        onClick={() => handleFeedback(item.product_id, btn.type, item.member_id)}
                      >
                        <span className="feedback-icon">{btn.icon}</span>
                        <span className="feedback-label">{btn.title}</span>
                      </button>
                    );
                  })}
                  {/* 加购按钮 */}
                  <button
                    className={`feedback-btn cart-btn${inCart ? ' done' : ''}`}
                    title={inCart ? '已加购' : '加入购物车'}
                    disabled={inCart}
                    onClick={() => handleAddToCart(item.product_id)}
                  >
                    <span className="feedback-icon">{inCart ? '✅' : '🛒'}</span>
                    <span className="feedback-label">{inCart ? '已加购' : '加购'}</span>
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </div>
      {/* 反馈提交后的浮动提示 */}
      {toast && (
        <div className="product-feedback-toast">{toast}</div>
      )}
    </section>
  );
}
