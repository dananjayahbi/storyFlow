import { redirect } from 'next/navigation';

// Project editors live under a workspace section:
// /facebook/projects/[id] or /youtube/projects/[id].
export default function ProjectRedirectPage() {
  redirect('/select');
}
