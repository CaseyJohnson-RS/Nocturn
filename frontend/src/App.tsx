import { useEffect } from 'react';
import { useAuthStore } from '@/stores/auth';
import { authApi } from '@/api/auth';

export default function App() {
  const { setUser, setAccessToken, setInitialized, isInitialized } = useAuthStore();

  useEffect(() => {
    if (isInitialized) return;

    authApi
      .refresh()
      .then((tokenRes) => {
        setAccessToken(tokenRes.access_token);
        return authApi.me();
      })
      .then((user) => {
        setUser(user);
      })
      .catch(() => {
        // Not authenticated
      })
      .finally(() => {
        setInitialized();
      });
  }, [isInitialized, setUser, setAccessToken, setInitialized]);

  return null;
}
