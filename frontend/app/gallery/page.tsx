import { redirect } from 'next/navigation';

// Gallery lives under a workspace section:
// /facebook/gallery or /youtube/gallery.
export default function GalleryRedirectPage() {
  redirect('/select');
}
