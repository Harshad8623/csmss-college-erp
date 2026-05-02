// app/_layout.tsx — Root layout with auth gate + React Query + fonts
import { useEffect } from 'react';
import { Stack, router, useSegments } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { useAuthStore } from '../store/auth.store';
import '../global.css';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60 * 5,    // 5 minutes
      retry: 1,
    },
  },
});

function AuthGate() {
  const { isAuthenticated, isLoading, rehydrate, user } = useAuthStore();
  const segments = useSegments();

  useEffect(() => {
    rehydrate();
  }, []);

  useEffect(() => {
    if (isLoading) return;

    const inAuthGroup = segments[0] === '(auth)';

    if (!isAuthenticated && !inAuthGroup) {
      router.replace('/(auth)/login');
    } else if (isAuthenticated && inAuthGroup) {
      // If must change password, force that screen
      if (user?.must_change_password) {
        router.replace('/(auth)/change-password');
      } else {
        router.replace('/(tabs)/dashboard');
      }
    }
  }, [isAuthenticated, isLoading, segments, user]);

  return null;
}

export default function RootLayout() {
  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
      <SafeAreaProvider>
        <QueryClientProvider client={queryClient}>
          <StatusBar style="light" backgroundColor="#050d1a" />
          <AuthGate />
          <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: '#050d1a' } }}>
            <Stack.Screen name="(auth)"  options={{ headerShown: false }} />
            <Stack.Screen name="(tabs)"  options={{ headerShown: false }} />
          </Stack>
        </QueryClientProvider>
      </SafeAreaProvider>
    </GestureHandlerRootView>
  );
}
