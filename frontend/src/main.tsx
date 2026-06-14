import React from 'react';
import ReactDOM from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter, Route, Routes } from 'react-router-dom';
import { ReportsPage } from './pages/ReportsPage';
import { DocumentDetailPage } from './pages/DocumentDetailPage';
import { ChatPage } from './pages/ChatPage';
import { MembersPage } from './pages/MembersPage';
import { MemberFormPage } from './pages/MemberFormPage';
import { MemberDetailPage } from './pages/MemberDetailPage';
import { MallPage } from './pages/MallPage';
import { MallProductListPage } from './pages/MallProductListPage';
import { MallProductDetailPage } from './pages/MallProductDetailPage';
import { MallCartPage } from './pages/MallCartPage';
import { DevicePage } from './pages/DevicePage';
import './styles.css';

const queryClient = new QueryClient();

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<ChatPage />} />
          <Route path="/chat" element={<ChatPage />} />
          <Route path="/reports" element={<ReportsPage />} />
          <Route path="/reports/:documentId" element={<DocumentDetailPage />} />
          <Route path="/members" element={<MembersPage />} />
          <Route path="/members/new" element={<MemberFormPage />} />
          <Route path="/members/:memberId" element={<MemberDetailPage />} />
          <Route path="/members/:memberId/edit" element={<MemberFormPage />} />
          <Route path="/mall" element={<MallPage />} />
          <Route path="/mall/products" element={<MallProductListPage />} />
          <Route path="/mall/products/:productId" element={<MallProductDetailPage />} />
          <Route path="/mall/cart" element={<MallCartPage />} />
          <Route path="/devices" element={<DevicePage />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>
);
