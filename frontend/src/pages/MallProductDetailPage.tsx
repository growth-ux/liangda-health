import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, useParams, useNavigate } from 'react-router-dom';
import { getMallProduct, addMallCartItem } from '../api/mall';
import { RecommendationReason } from '../components/mall/RecommendationReason';
import { QuantityStepper } from '../components/mall/QuantityStepper';
import { ProductCard } from '../components/mall/ProductCard';

export function MallProductDetailPage() {
  const { productId } = useParams<{ productId: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [quantity, setQuantity] = useState(1);
  const [toast, setToast] = useState<string | null>(null);
  const [imageFailed, setImageFailed] = useState(false);

  const detailQuery = useQuery({
    queryKey: ['mall', 'product', productId],
    queryFn: () => getMallProduct(productId!),
    enabled: !!productId,
  });

  const addCartMutation = useMutation({
    mutationFn: () => addMallCartItem(productId!, quantity),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['mall', 'cart'] });
    },
  });

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 2000);
  };

  const handleAddToCart = () => {
    addCartMutation.mutate(undefined, {
      onSuccess: () => showToast('已加入购物车'),
      onError: () => showToast('加入购物车失败'),
    });
  };

  const handleBuyNow = () => {
    addCartMutation.mutate(undefined, {
      onSuccess: () => navigate('/mall/cart'),
      onError: () => showToast('加入购物车失败'),
    });
  };

  if (detailQuery.isLoading) {
    return (
      <div className="detail-page">
        <Link to="/mall" className="back-link">← 返回商城</Link>
        <div className="empty-state">正在加载商品...</div>
      </div>
    );
  }

  if (detailQuery.isError || !detailQuery.data) {
    return (
      <div className="detail-page">
        <Link to="/mall" className="back-link">← 返回商城</Link>
        <div className="error-box">商品加载失败</div>
      </div>
    );
  }

  const { product, recommend_reason, nutrition_rows, related_products, health_notice } = detailQuery.data;
  const hasDetailRows = nutrition_rows.length > 0 || !!product.ingredients || !!product.shelf_life;

  return (
    <div className="detail-page">
      <Link to="/mall" className="back-link">← 返回商城</Link>

      {toast && <div className="toast">{toast}</div>}

      <div className="card">
        <div className="product-detail">
          <div className="product-image-lg">
            {product.image_url && !imageFailed ? (
              <img
                className="product-detail-photo"
                src={product.image_url}
                alt=""
                onError={() => setImageFailed(true)}
              />
            ) : (
              product.image_emoji ?? '📦'
            )}
          </div>

          <div className="product-detail-info">
            <h1>{product.name}</h1>
            <div className="product-detail-meta">
              {product.brand && <span>品牌：{product.brand}</span>}
              {product.spec && <span>规格：{product.spec}</span>}
              {product.sales_text && <span>{product.sales_text}</span>}
            </div>

            <div className="product-detail-price">
              {product.price_text}
              {product.original_price_text && (
                <span className="product-detail-original-price">{product.original_price_text}</span>
              )}
            </div>

            {product.health_tags.length > 0 && (
              <div className="product-detail-tags">
                {product.health_tags.map((tag, i) => (
                  <span key={i} className={`tag ${i === 0 ? 'tag-success' : 'tag-info'}`}>
                    {tag}
                  </span>
                ))}
              </div>
            )}

            {recommend_reason && <RecommendationReason reason={recommend_reason} />}

            {hasDetailRows && (
              <table className="table" style={{ marginTop: '16px' }}>
                <tbody>
                  {nutrition_rows.map((row, i) => (
                    <tr key={i}>
                      <th style={{ width: '30%' }}>{row.label}</th>
                      <td>{row.value}</td>
                    </tr>
                  ))}
                  {product.ingredients && (
                    <tr>
                      <th>配料</th>
                      <td>{product.ingredients}</td>
                    </tr>
                  )}
                  {product.shelf_life && (
                    <tr>
                      <th>保质期</th>
                      <td>{product.shelf_life}</td>
                    </tr>
                  )}
                </tbody>
              </table>
            )}

            <div className="product-detail-actions">
              <QuantityStepper value={quantity} onChange={setQuantity} />
              <button
                className="btn-secondary"
                onClick={handleAddToCart}
                disabled={addCartMutation.isPending}
              >
                {addCartMutation.isPending ? '加入中...' : '加入购物车'}
              </button>
              <button
                className="btn-primary"
                onClick={handleBuyNow}
                disabled={addCartMutation.isPending}
              >
                立即购买
              </button>
            </div>

            <div className="product-detail-promises">
              <span>🚚 满 39 免运费</span>
              <span>📦 24h 发货</span>
              <span>↩ 7 天无理由</span>
            </div>
          </div>
        </div>
      </div>

      {/* 推荐搭配 */}
      {related_products.length > 0 && (
        <div className="card">
          <div className="card-title">🥗 推荐搭配</div>
          <div className="product-row">
            {related_products.map((p) => (
              <ProductCard key={p.product_id} product={p} size="small" />
            ))}
          </div>
        </div>
      )}

      {/* 健康提示 */}
      <div className="alert alert-info">
        <div className="alert-icon">ℹ</div>
        <div>
          <strong>温馨提示：</strong>{health_notice}
          {product.warning_tags.length > 0 && (
            <span> 过敏原提示：{product.warning_tags.join('、')}</span>
          )}
        </div>
      </div>
    </div>
  );
}
