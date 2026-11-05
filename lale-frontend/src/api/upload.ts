// src/api/upload.ts
import api from './axios';

export const uploadFileApi = async (file: File) => {
  const formData = new FormData();
  formData.append('file', file);

  // 注意：这里的 Content-Type 虽然是 multipart/form-data，但 axios 会自动为你加上 boundary
  return api.post('/api/documents/upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
    timeout: 120000, // 解析可能很久，给 120 秒超时
  });
};