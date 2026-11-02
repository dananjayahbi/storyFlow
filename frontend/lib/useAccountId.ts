'use client';

import { useEffect, useState } from 'react';
import { getCurrentAccountId } from './account';
import type { Section } from './section';

/**
 * Resolve the active account id after mount.
 *
 * Returns `null` on the server and during the first client render so hrefs
 * and other markup stay identical through hydration. The effect then reads
 * the URL/localStorage selection and triggers a normal post-hydration update.
 */
export function useAccountId(section: Section): string | null {
  const [accountId, setAccountId] = useState<string | null>(null);

  useEffect(() => {
    setAccountId(getCurrentAccountId(section));
  }, [section]);

  return accountId;
}
