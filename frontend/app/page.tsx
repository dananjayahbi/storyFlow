import { redirect } from 'next/navigation';

// `/select` is the application home page. After login the user picks a
// workspace (Facebook Reels or YouTube Videos) and every subsequent page
// lives under that section's URL prefix.
export default function HomePage() {
  redirect('/select');
}
