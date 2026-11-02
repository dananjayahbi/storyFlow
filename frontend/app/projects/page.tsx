import { redirect } from 'next/navigation';

// Projects live under a workspace section: /facebook/projects or /youtube/projects.
export default function ProjectsRedirectPage() {
  redirect('/select');
}
