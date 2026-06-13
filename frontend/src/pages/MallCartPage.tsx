import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { Trash2 } from 'lucide-react';
import { useState } from 'react';
import { getMallCart, updateMallCartItem, deleteMallCartItem } from '../api/mall';
import { AppShell } from '../components/AppShell';
import { CartSummary } from '../components/mall/CartSummary';

function CartItemImage({ item }: { item: { image_url: string | null; image_emoji: string | null; name: string } }) {
  const [imageFailed, setImageFailed] = useState(false);

  if (item.image_url && !imageFailed) {
    return (
      <img
        className="cart-item-photo"
        src={item.image_url}
        alt=""
        onError={() => setImageFailed(true)}
      />
    );
  }

  return item.image_emoji ?? '📦';
}

export function MallCartPage() {
  const queryClient = useQueryClient();

  const cartQuery = useQuery({ queryKey: ['mall', 'cart'], queryFn: getMallCart });

  const updateMutation = useMutation({
    mutationFn: ({ productId, quantity }: { productId: string; quantity: number }) =>
      updateMallCartItem(productId, quantity),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['mall', 'cart'] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (productId: string) => deleteMallCartItem(productId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['mall', 'cart'] });
    },
  });

  const handleCheckout = () => {
    alert('当前版本已生成购买清单，请联系门店确认配送');
  };

  if (cartQuery.isLoading) {
    return (
      <AppShell title="购物车" activeId="mall">
        <div className="empty-state">正在加载购物车...</div>
      </AppShell>
    );
  }

  if (cartQuery.isError) {
    return (
      <AppShell title="购物车" activeId="mall">
        <div className="error-box">购物车加载失败</div>
      </AppShell>
    );
  }

  const cart = cartQuery.data!;

  if (cart.items.length === 0) {
    return (
      <AppShell title="购物车" activeId="mall">
        <div className="cart-empty">
          <div className="cart-empty-icon">🛒</div>
          <div className="cart-empty-text">购物车还是空的</div>
          <Link to="/mall" className="btn-primary">
            去商城看看
          </Link>
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell title="购物车" activeId="mall">
      <div className="cart-page">
        <div className="cart-items">
          {cart.items.map((item) => (
            <div key={item.product_id} className="cart-item">
              <Link to={`/mall/products/${item.product_id}`} className="cart-item-image">
                <CartItemImage item={item} />
              </Link>
              <div className="cart-item-info">
                <Link to={`/mall/products/${item.product_id}`} className="cart-item-name">
                  {item.name}
                </Link>
                {item.spec && <div className="cart-item-spec">{item.spec}</div>}
                <div className="cart-item-price">{item.price_text}</div>
              </div>
              <div className="cart-item-quantity">
                <button
                  type="button"
                  onClick={() =>
                    updateMutation.mutate({
                      productId: item.product_id,
                      quantity: Math.max(1, item.quantity - 1),
                    })
                  }
                  disabled={item.quantity <= 1 || updateMutation.isPending}
                >
                  -
                </button>
                <span>{item.quantity}</span>
                <button
                  type="button"
                  onClick={() =>
                    updateMutation.mutate({
                      productId: item.product_id,
                      quantity: item.quantity + 1,
                    })
                  }
                  disabled={updateMutation.isPending}
                >
                  +
                </button>
              </div>
              <div className="cart-item-subtotal">{item.subtotal_text}</div>
              <button
                className="cart-item-delete"
                onClick={() => deleteMutation.mutate(item.product_id)}
                disabled={deleteMutation.isPending}
              >
                <Trash2 size={16} />
              </button>
            </div>
          ))}
        </div>
        <CartSummary
          totalQuantity={cart.total_quantity}
          totalText={cart.total_text}
          onCheckout={handleCheckout}
        />
      </div>
    </AppShell>
  );
}
