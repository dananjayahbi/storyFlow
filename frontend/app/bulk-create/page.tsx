import { redirect } from 'next/navigation';

// Bulk Create lives under a workspace section:
// /facebook/bulk-create or /youtube/bulk-create.
export default function BulkCreateRedirectPage() {
  redirect('/select');
}
