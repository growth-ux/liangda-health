import { Link } from 'react-router-dom';
import { useState } from 'react';
import type { MallProduct } from '../../api/mall';

type Props = {
  product: MallProduct;
  size?: 'large' | 'small';
};

function ProductImage({ product, className }: { product: MallProduct; className: string }) {
  const [imageFailed, setImageFailed] = useState(false);

  if (product.image_url && !imageFailed) {
    return (
      <img
        className={className}
        src={product.image_url}
        alt=""
        loading="lazy"
        onError={() => setImageFailed(true)}
      />
    );
  }

  return <span className="product-emoji">{product.image_emoji ?? '📦'}</span>;
}

export function ProductCard({ product, size = 'large' }: Props) {
  if (size === 'small') {
    return (
      <Link to={`/mall/products/${product.product_id}`} className="product-card">
        <div className="product-image">
          <ProductImage product={product} className="product-photo product-photo-small" />
        </div>
        <div className="product-info">
          <div className="product-name">{product.name}</div>
          <div className="product-price">{product.price_text}</div>
        </div>
      </Link>
    );
  }

  return (
    <Link to={`/mall/products/${product.product_id}`} className="product-card-lg">
      <div className="product-image product-image-art">
        {product.health_tags.length > 0 && (
          <span className="product-tag">{product.health_tags[0]}</span>
        )}
        <ProductImage product={product} className="product-photo" />
      </div>
      <div className="product-info">
        <div className="product-name">{product.name}</div>
        {product.recommend_reason && (
          <div className="recommend-reason">💡 {product.recommend_reason}</div>
        )}
        <div className="product-price-row">
          <span className="product-price">{product.price_text}</span>
          {product.original_price_text && (
            <span className="product-original-price">{product.original_price_text}</span>
          )}
        </div>
      </div>
    </Link>
  );
}
