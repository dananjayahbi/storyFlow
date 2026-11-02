import { redirect } from 'next/navigation';

// Settings live under a workspace section:
// /facebook/settings or /youtube/settings.
export default function SettingsRedirectPage() {
  redirect('/select');
}
