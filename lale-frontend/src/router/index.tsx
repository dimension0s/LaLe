import { createBrowserRouter, Navigate } from 'react-router-dom';
import { useUserStore } from '../store/useUserStore';
import Dashboard from '../pages/Dashboard';
import Documents from '../pages/Documents';
import Reader from '../pages/Reader';
import Notes from '../pages/Notes';
import NoteDetail from '../pages/NoteDetail';
import Vocabulary from '../pages/Vocabulary';
import Recycle from '../pages/Recycle';

// 路由守卫：保护内部数据页面
const ProtectedRoute = ({ children }: { children: React.ReactNode }) => {
  const token = useUserStore((state) => state.token);
  if (!token) {
    // 未登录一律打回首页
    return <Navigate to="/" replace />;
  }
  return <>{children}</>;
};

export const router = createBrowserRouter([
  {
    path: '/',
    element: <Dashboard />, // 👈 首页公开访问
  },
  // 👇 以下页面全部受保护，未登录跳回首页
  { path: '/documents', element: <ProtectedRoute><Documents /></ProtectedRoute> },
  { path: '/reader/:doc_uuid', element: <ProtectedRoute><Reader /></ProtectedRoute> },
  { path: '/notes', element: <ProtectedRoute><Notes /></ProtectedRoute> },
  { path: '/notes/:note_uuid', element: <ProtectedRoute><NoteDetail /></ProtectedRoute> },
  { path: '/vocabulary', element: <ProtectedRoute><Vocabulary /></ProtectedRoute> },
  { path: '/recycle', element: <ProtectedRoute><Recycle /></ProtectedRoute> },
]);