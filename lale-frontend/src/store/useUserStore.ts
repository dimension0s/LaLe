import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface UserInfo {
  id: number;
  user_uuid: string;
  phone_number: string;
  nickname: string;
  avatar_url: string;
  email: string | null;
}

interface UserState {
  token: string | null;
  user: UserInfo | null;
  setAuth: (token: string, user: UserInfo) => void;
  logout: () => void;
}

export const useUserStore = create<UserState>()(
  persist(
    (set) => ({
      token: null,
      user: null,
      setAuth: (token, user) => set({ token, user }),
      logout: () => set({ token: null, user: null }),
    }),
    {
      name: 'lale-auth', // 存在 localStorage 的 key
    }
  )
);