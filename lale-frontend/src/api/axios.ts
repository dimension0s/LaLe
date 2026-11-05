import axios from 'axios';
import { message } from 'antd';
import { useUserStore } from '../store/useUserStore';

const api = axios.create({
  baseURL: 'http://localhost:8000',
  timeout: 120000, // 统一设置为 120 秒（应对 AI 整合接口）
});

// 请求拦截器：自动带上 Token
api.interceptors.request.use((config) => {
  const token = useUserStore.getState().token;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// 响应拦截器：统一处理错误
api.interceptors.response.use(
  (response) => {
    const res = response.data;
    if (res.code === 0) {
      return res.data; // 直接返回业务数据
    }
    message.error(res.msg || '请求失败');
    return Promise.reject(new Error(res.msg));
  },
  (error) => {
    if (error.response?.status === 401) {
      message.warning('登录已过期，请重新登录');
      useUserStore.getState().logout();
      window.location.href = '/login';
    } else {
      const msg = error.response?.data?.msg || error.message || '网络异常';
      message.error(msg);
    }
    return Promise.reject(error);
  }
);

export default api;