import { DarkTheme, ThemeProvider } from '@react-navigation/native';
import { useFonts } from 'expo-font';
import { Stack, router } from 'expo-router';
import * as SplashScreen from 'expo-splash-screen';
import { useEffect, useState, useCallback } from 'react';
import 'react-native-reanimated';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { AuthContext, performLogin, performSignup, performLogout } from '@/hooks/useAuth';

SplashScreen.preventAutoHideAsync();

export default function RootLayout() {
  const [loaded] = useFonts({ SpaceMono: require('../assets/fonts/SpaceMono-Regular.ttf') });
  const [token, setToken] = useState<string | null>(null);
  const [authChecked, setAuthChecked] = useState(false);

  useEffect(() => {
    AsyncStorage.getItem('auth_token').then(t => {
      setToken(t);
      setAuthChecked(true);
    });
  }, []);

  useEffect(() => {
    if (loaded && authChecked) {
      SplashScreen.hideAsync();
      if (!token) {
        router.replace('/login');
      }
    }
  }, [loaded, authChecked, token]);

  const login = useCallback(async (email: string, password: string) => {
    const t = await performLogin(email, password);
    setToken(t);
    router.replace('/(tabs)');
  }, []);

  const signup = useCallback(async (email: string, password: string) => {
    const t = await performSignup(email, password);
    setToken(t);
    router.replace('/(tabs)');
  }, []);

  const logout = useCallback(async () => {
    await performLogout();
    setToken(null);
    router.replace('/login');
  }, []);

  if (!loaded || !authChecked) return null;

  return (
    <AuthContext.Provider value={{ isAuthenticated: !!token, token, login, signup, logout }}>
      <ThemeProvider value={DarkTheme}>
        <Stack screenOptions={{ headerShown: false }}>
          <Stack.Screen name="login" options={{ headerShown: false }} />
          <Stack.Screen name="signup" options={{ headerShown: false }} />
          <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
          <Stack.Screen name="+not-found" />
        </Stack>
      </ThemeProvider>
    </AuthContext.Provider>
  );
}
