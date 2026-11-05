import api from './axios';

export const updateAvatarApi = (avatar_url: string) => {
  return api.patch('/api/account/avatar', { avatar_url });
};

export const updateNicknameApi = (nickname: string) => {
  return api.patch('/api/account/nickname', { nickname });
};

// 上传头像文件
export const uploadAvatarApi = (file: File) => {
  const formData = new FormData();
  formData.append('file', file);
  return api.post('/api/account/avatar/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
};