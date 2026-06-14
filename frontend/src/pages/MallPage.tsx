import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { ShoppingCart } from 'lucide-react';
import { getMallHome } from '../api/mall';
import { AppShell } from '../components/AppShell';
import { MallBanner } from '../components/mall/MallBanner';
import { ZoneGrid } from '../components/mall/ZoneGrid';
import { ProductCard } from '../components/mall/ProductCard';
import { getMallCart } from '../api/mall';

const DAILY_PAGE_SIZE = 5;

function getMemberEmoji(relation: string): string {
  if (relation.includes('妈') || relation.includes('母')) return '👩';
  if (relation.includes('爸') || relation.includes('父')) return '👨';
  if (relation.includes('女') || relation.includes('女儿')) return '👧';
  if (relation.includes('儿') || relation.includes('儿子')) return '👦';
  if (relation.includes('奶') || relation.includes('外婆')) return '👵';
  if (relation.includes('爷') || relation.includes('外公')) return '👴';
  return '🏠';
}

export function MallPage() {
  const homeQuery = useQuery({ queryKey: ['mall', 'home'], queryFn: getMallHome });
  const cartQuery = useQuery({ queryKey: ['mall', 'cart'], queryFn: getMallCart });
  const [dailyPage, setDailyPage] = useState(0);

  const cartCount = cartQuery.data?.total_quantity ?? 0;

  if (homeQuery.isLoading) {
    return (
      <AppShell title="商城" activeId="mall">
        <div className="empty-state">正在加载商城...</div>
      </AppShell>
    );
  }

  if (homeQuery.isError) {
    return (
      <AppShell title="商城" activeId="mall">
        <div className="error-box">商城加载失败</div>
      </AppShell>
    );
  }

  const data = homeQuery.data!;
  const dailyTotalPages = Math.max(1, Math.ceil(data.daily_products.length / DAILY_PAGE_SIZE));
  const dailySlice = data.daily_products.slice(
    dailyPage * DAILY_PAGE_SIZE,
    (dailyPage + 1) * DAILY_PAGE_SIZE
  );

  const handleNextDaily = () => {
    // 触发重新拉取，拿到后端新一轮"家人聚合分 + 随机扰动"排序结果
    void homeQuery.refetch();
    setDailyPage(0);
  };

  return (
    <AppShell title="商城" activeId="mall">
      <MallBanner />

      {/* 家庭推荐 */}
      {data.family_recommendations.length > 0 && (
        <ZoneGrid title="🎯 为你家庭推荐">
          {data.family_recommendations.map((rec) => (
            <Link
              key={rec.member_id}
              to={`/mall/products?member_id=${rec.member_id}`}
              className="zone-card"
            >
              <div className="zone-icon">{getMemberEmoji(rec.relation)}</div>
              <div className="zone-name">{rec.zone_name}</div>
              <div className="zone-sub">{rec.summary}</div>
            </Link>
          ))}
          <Link to="/mall/products" className="zone-card zone-card-home">
            <div className="zone-icon">🏠</div>
            <div className="zone-name">{data.family_universal?.zone_name ?? '全家通用'}</div>
            <div className="zone-sub">{data.family_universal?.summary ?? '健康均衡'}</div>
          </Link>
        </ZoneGrid>
      )}

      {/* 健康专区 */}
      {data.health_zones.length > 0 && (
        <ZoneGrid title="🏥 健康专区" actions={<span style={{ color: '#9ca3af' }}>根据健康规则引擎筛选</span>}>
          {data.health_zones.map((zone) => (
            <Link
              key={zone.zone_code}
              to={`/mall/products?zone_code=${zone.zone_code}`}
              className={`zone-card zone-${zone.zone_code}`}
            >
              <div className="zone-icon">{zone.icon ?? '📦'}</div>
              <div className="zone-name">{zone.name}</div>
            </Link>
          ))}
        </ZoneGrid>
      )}

      {/* 今日推荐 */}
      {dailySlice.length > 0 && (
        <div className="card">
          <div className="card-title">
            🔥 今日猜你想买
            {dailyTotalPages > 1 && (
              <span className="card-title-actions" onClick={handleNextDaily} style={{ cursor: 'pointer' }}>
                换一批 🔄
              </span>
            )}
          </div>
          <div className="product-grid">
            {dailySlice.map((product) => (
              <ProductCard key={product.product_id} product={product} />
            ))}
          </div>
        </div>
      )}

      {/* 分类 */}
      {data.categories.length > 0 && (
        <ZoneGrid title="分类">
          {data.categories.map((cat) => (
            <Link
              key={cat.zone_code}
              to={`/mall/products?category_code=${cat.zone_code}`}
              className={`zone-card zone-cat-${cat.zone_code}`}
            >
              <div className="zone-icon">{cat.icon ?? '📦'}</div>
              <div className="zone-name">{cat.name}</div>
            </Link>
          ))}
        </ZoneGrid>
      )}

      {/* 购物车浮动按钮 */}
      <Link to="/mall/cart" className="mall-cart-fab">
        <ShoppingCart size={24} />
        {cartCount > 0 && <span className="mall-cart-badge">{cartCount}</span>}
      </Link>
    </AppShell>
  );
}
