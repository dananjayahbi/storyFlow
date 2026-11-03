'use client';

import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { ensureApiBaseUrl } from '@/lib/apiConfig';

export function LogoutButton() {
  const router = useRouter();
  const handleLogout = () => {
    try {
      localStorage.removeItem('storyflow_authenticated');
      localStorage.removeItem('storyflow_user');
    } catch {
      // ignore
    }
    ensureApiBaseUrl()
      .then((apiBase) => fetch(`${apiBase}/api/auth/logout/`, { method: 'POST' }))
      .catch(() => {
        // Backend optional during logout.
      });
    router.replace('/login');
  };
  return (
    <Button variant="outline" size="sm" onClick={handleLogout}>
      Logout
    </Button>
  );
}
