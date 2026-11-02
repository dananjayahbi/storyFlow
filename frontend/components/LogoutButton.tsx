'use client';

import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';

export function LogoutButton() {
  const router = useRouter();
  const handleLogout = () => {
    try {
      localStorage.removeItem('storyflow_authenticated');
      localStorage.removeItem('storyflow_user');
    } catch {
      // ignore
    }
    try {
      fetch('http://localhost:8000/api/auth/logout/', { method: 'POST' });
    } catch {
      // ignore
    }
    router.replace('/login');
  };
  return (
    <Button variant="outline" size="sm" onClick={handleLogout}>
      Logout
    </Button>
  );
}
