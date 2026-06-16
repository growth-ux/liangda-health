import { Link } from 'react-router-dom';
import type { ProductRecommendationItem } from '../../api/agent';

type Props = {
  items: ProductRecommendationItem[];
};

function truncateProductName(name: string) {
  const chars = Array.from(name);
  return chars.length > 10 ? `${chars.slice(0, 10).join('')}...` : name;
}

export function ProductRecommendationCards({ items }: Props) {
  if (items.length === 0) return null;

  return (
    <section className="msg-product-section card-message">
      <div className="card-message-header info">🛒 可选商品</div>
      <div className="card-message-body">
        <div className="product-row">
          {items.map((item, index) => (
            <Link
              to={`/mall/products/${item.product_id}`}
              className={`product-card${index === 1 ? ' active' : ''}`}
              key={`${item.product_id}-${index}`}
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
          ))}
        </div>
      </div>
    </section>
  );
}
