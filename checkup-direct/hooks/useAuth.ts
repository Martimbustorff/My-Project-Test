import { createContext, useContext } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { apiPost } from '@/constants/Api';

export interface AuthContextType {
  isAuthenticated: boolean;
  token: string | null;
  login: (email: string, password: string) => Promise<void>;
  signup: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

export const AuthContext = createContext<AuthContextType>({
  isAuthenticated: false,
  token: null,
  login: async () => {},
  signup: async () => {},
  logout: async () => {},
});

export const useAuth = () => useContext(AuthContext);

export async function performLogin(email: string, password: string): Promise<string> {
  const data = await apiPost<{ access_token: string }>('/api/auth/login', { email, password });
  await AsyncStorage.setItem('auth_token', data.access_token);
  return data.access_token;
}

export async function performSignup(email: string, password: string): Promise<string> {
  const data = await apiPost<{ access_token: string }>('/api/auth/signup', { email, password });
  await AsyncStorage.setItem('auth_token', data.access_token);
  return data.access_token;
}

export async function performLogout(): Promise<void> {
  await AsyncStorage.removeItem('auth_token');
}
