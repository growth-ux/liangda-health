import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// 全部后端 API 都挂在 /api 下，前端路由（/mall、/members 等）由 React Router 处理，
// 不会与 API 路径冲突，所以这里不再需要 Accept 头 bypass。
// /uploads 和 /mall-products 是后端的静态资源挂载点（与前端路由不冲突），仍需代理。
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true
      },
      '/uploads': {
        target: 'http://localhost:8000',
        changeOrigin: true
      },
      '/mall-products': {
        target: 'http://localhost:8000',
        changeOrigin: true
      }
    }
  }
});
