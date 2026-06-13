import { useQuery } from '@tanstack/react-query';
import { Link, useSearchParams } from 'react-router-dom';
import { listMallProducts } from '../api/mall';
import { AppShell } from '../components/AppShell';
import { ProductCard } from '../components/mall/ProductCard';

export function MallProductListPage() {
  const [searchParams] = useSearchParams();
  const zoneCode = searchParams.get('zone_code') ?? undefined;
  const categoryCode = searchParams.get('category_code') ?? undefined;
  const memberId = searchParams.get('member_id') ?? undefined;

  const productsQuery = useQuery({
    queryKey: ['mall', 'products', { zone_code: zoneCode, category_code: categoryCode, member_id: memberId }],
    queryFn: () => listMallProducts({ zone_code: zoneCode, category_code: categoryCode, member_id: memberId }),
  });

  const title = productsQuery.data?.zone?.name ?? '全部商品';

  if (productsQuery.isLoading) {
    return (
      <AppShell title={title} activeId="mall">
        <Link to="/mall" className="back-link">← 返回商城</Link>
        <div className="empty-state">正在加载商品...</div>
      </AppShell>
    );
  }

  if (productsQuery.isError) {
    return (
      <AppShell title={title} activeId="mall">
        <Link to="/mall" className="back-link">← 返回商城</Link>
        <div className="error-box">商品加载失败</div>
      </AppShell>
    );
  }

  const products = productsQuery.data!.products;

  return (
    <AppShell title={title} activeId="mall">
      <Link to="/mall" className="back-link">← 返回商城</Link>

      {products.length === 0 ? (
        <div className="empty-state">暂无相关商品</div>
      ) : (
        <div className="product-grid">
          {products.map((product) => (
            <ProductCard key={product.product_id} product={product} />
          ))}
        </div>
      )}
    </AppShell>
  );
}
