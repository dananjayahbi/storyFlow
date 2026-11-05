'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Copy,
  FileText,
  ImagePlus,
  Images,
  Loader2,
  Sparkles,
  Trash2,
  Upload,
} from 'lucide-react';
import { toast } from 'sonner';

import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Textarea } from '@/components/ui/textarea';
import {
  deleteProjectThumbnailAsset,
  generateThumbnailPrompt,
  setActiveProjectThumbnail,
  updateProject,
  uploadProjectThumbnailAsset,
} from '@/lib/api';
import type {
  ProjectDetail,
  ProjectThumbnail,
  ThumbnailReadiness,
} from '@/lib/types';
import { cn } from '@/lib/utils';

interface MetadataManagementModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  project: ProjectDetail;
  onProjectRefreshed: () => void | Promise<void>;
}

interface PreviewFile {
  file: File;
  url: string;
}

const DEFAULT_SELECTION = 5;
const MIN_REFERENCES = 2;

const DOCUMENT_EXTENSIONS = ['.pdf', '.txt', '.md', '.csv', '.json'];

function computeReadiness(project: ProjectDetail): ThumbnailReadiness {
  if (project.thumbnail_readiness) return project.thumbnail_readiness;

  const segments = project.segments ?? [];
  const total = segments.length;
  const imageCount = segments.filter((segment) => segment.image_file).length;
  const textCount = segments.filter((segment) =>
    Boolean(segment.text_content?.trim()),
  ).length;
  const requiredImages = total > 0 ? Math.ceil(total / 2) : 0;
  const scriptReady = total > 0 && textCount > 0;
  const imagesReady = requiredImages > 0 && imageCount >= requiredImages;

  return {
    script_ready: scriptReady,
    images_ready: imagesReady,
    ready: scriptReady && imagesReady,
    segment_count: total,
    text_segment_count: textCount,
    image_count: imageCount,
    required_images: requiredImages,
    min_reference_images: MIN_REFERENCES,
  };
}

function errorMessage(error: unknown, fallback: string): string {
  const maybe = error as {
    response?: { data?: { error?: string; details?: string } };
    message?: string;
  };
  return (
    maybe?.response?.data?.error
    || maybe?.response?.data?.details
    || maybe?.message
    || fallback
  );
}

async function copyText(value: string): Promise<void> {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(value);
    return;
  }
  const helper = document.createElement('textarea');
  helper.value = value;
  helper.setAttribute('readonly', '');
  helper.style.position = 'fixed';
  helper.style.opacity = '0';
  document.body.appendChild(helper);
  helper.select();
  document.execCommand('copy');
  document.body.removeChild(helper);
}

export function MetadataManagementModal({
  open,
  onOpenChange,
  project,
  onProjectRefreshed,
}: MetadataManagementModalProps) {
  const [systemPrompt, setSystemPrompt] = useState('');
  const [systemOpen, setSystemOpen] = useState(false);
  const [savingSystem, setSavingSystem] = useState(false);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [message, setMessage] = useState('');
  const [externalImages, setExternalImages] = useState<PreviewFile[]>([]);
  const [documents, setDocuments] = useState<File[]>([]);
  const [prompt, setPrompt] = useState('');
  const [generating, setGenerating] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [busyThumbnailId, setBusyThumbnailId] = useState<string | null>(null);
  const [thumbnails, setThumbnails] = useState<ProjectThumbnail[]>([]);
  const [draggingExternal, setDraggingExternal] = useState(false);
  const [draggingThumbnail, setDraggingThumbnail] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const thumbnailInputRef = useRef<HTMLInputElement>(null);
  const externalInputRef = useRef<HTMLInputElement>(null);
  const documentInputRef = useRef<HTMLInputElement>(null);

  const readiness = useMemo(() => computeReadiness(project), [project]);
  const imageSegments = useMemo(
    () => (project.segments ?? []).filter((segment) => segment.image_file),
    [project.segments],
  );
  const externalImagesRef = useRef<PreviewFile[]>([]);
  externalImagesRef.current = externalImages;

  // Reset the working session whenever the dialog opens. The saved thumbnail
  // gallery is kept in sync separately so activation/refresh never wipes the
  // prompt the operator is editing.
  useEffect(() => {
    if (!open) return;
    setSystemPrompt(project.thumbnail_system_prompt ?? '');
    setSystemOpen(false);
    setSelectedIds(
      imageSegments
        .slice(0, DEFAULT_SELECTION)
        .map((segment) => segment.id),
    );
    setMessage('');
    setDocuments([]);
    setPrompt('');
    setError(null);
    setThumbnails(project.thumbnails ?? []);
    setExternalImages((previous) => {
      previous.forEach((item) => URL.revokeObjectURL(item.url));
      return [];
    });
    // Intentionally only on open/project id: re-running on every project
    // refresh would wipe in-progress edits.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, project.id]);

  useEffect(() => {
    if (!open) return;
    setThumbnails(project.thumbnails ?? []);
  }, [open, project.thumbnails]);

  useEffect(() => {
    if (open) return;
    setExternalImages((previous) => {
      previous.forEach((item) => URL.revokeObjectURL(item.url));
      return [];
    });
  }, [open]);

  useEffect(
    () => () => {
      externalImagesRef.current.forEach((item) =>
        URL.revokeObjectURL(item.url),
      );
    },
    [],
  );

  const toggleSegment = (segmentId: string) => {
    setSelectedIds((previous) =>
      previous.includes(segmentId)
        ? previous.filter((id) => id !== segmentId)
        : [...previous, segmentId],
    );
  };

  const addExternalImages = useCallback((files: FileList | File[]) => {
    const next = Array.from(files)
      .filter((file) => file.type.startsWith('image/'))
      .map((file) => ({ file, url: URL.createObjectURL(file) }));
    if (next.length === 0) {
      toast.error('Choose PNG, JPG or WebP reference images.');
      return;
    }
    setExternalImages((previous) => [...previous, ...next]);
  }, []);

  const removeExternalImage = (index: number) => {
    setExternalImages((previous) => {
      const target = previous[index];
      if (target) URL.revokeObjectURL(target.url);
      return previous.filter((_, position) => position !== index);
    });
  };

  const addDocuments = (files: FileList | File[]) => {
    const accepted = Array.from(files).filter((file) => {
      const lower = file.name.toLowerCase();
      return DOCUMENT_EXTENSIONS.some((extension) => lower.endsWith(extension));
    });
    if (accepted.length === 0) {
      toast.error('Reference files must be PDF, TXT, Markdown, CSV or JSON.');
      return;
    }
    setDocuments((previous) => [...previous, ...accepted]);
  };

  const saveSystemPrompt = async () => {
    setSavingSystem(true);
    try {
      await updateProject(project.id, {
        thumbnail_system_prompt: systemPrompt,
      });
      await onProjectRefreshed();
      toast.success('Thumbnail system prompt saved.');
    } catch (saveError) {
      toast.error(errorMessage(saveError, 'Could not save the system prompt.'));
    } finally {
      setSavingSystem(false);
    }
  };

  const handleGenerate = async () => {
    setError(null);
    if (!readiness.ready) {
      setError(
        readiness.script_ready
          ? `Add images to at least ${readiness.required_images} of ${readiness.segment_count} blocks first.`
          : 'Craft the script before generating a thumbnail prompt.',
      );
      return;
    }
    if (selectedIds.length < MIN_REFERENCES) {
      setError('Select at least two storyboard images as references.');
      return;
    }

    setGenerating(true);
    try {
      const result = await generateThumbnailPrompt(project.id, {
        systemPrompt,
        message,
        segmentIds: selectedIds,
        referenceImages: externalImages.map((item) => item.file),
        referenceDocs: documents,
      });
      setPrompt(result.prompt);
      toast.success('Thumbnail prompt generated.');
    } catch (generateError) {
      const detail = errorMessage(
        generateError,
        'The AI model could not draft a thumbnail prompt.',
      );
      setError(detail);
      toast.error(detail);
    } finally {
      setGenerating(false);
    }
  };

  const handleCopyPrompt = async () => {
    if (!prompt) return;
    try {
      await copyText(prompt);
      toast.success('Prompt copied to the clipboard.');
    } catch {
      toast.error('Could not copy the prompt.');
    }
  };

  const handleThumbnailFile = async (file: File) => {
    if (!file.type.startsWith('image/')) {
      toast.error('Choose a PNG, JPG or WebP thumbnail.');
      return;
    }
    setUploading(true);
    try {
      const created = await uploadProjectThumbnailAsset(
        project.id,
        file,
        prompt,
      );
      setThumbnails((previous) => {
        const others = previous
          .filter((item) => item.id !== created.id)
          .map((item) =>
            created.is_active ? { ...item, is_active: false } : item,
          );
        return [created, ...others];
      });
      await onProjectRefreshed();
      toast.success('Thumbnail saved.');
    } catch (uploadError) {
      toast.error(
        errorMessage(uploadError, 'Could not save that thumbnail image.'),
      );
    } finally {
      setUploading(false);
    }
  };

  const handleThumbnailPaste = (
    event: React.ClipboardEvent<HTMLDivElement>,
  ) => {
    const file = Array.from(event.clipboardData.files).find((item) =>
      item.type.startsWith('image/'),
    );
    if (!file) return;
    event.preventDefault();
    void handleThumbnailFile(file);
  };

  const handleActivateThumbnail = async (thumbnailId: string) => {
    setBusyThumbnailId(thumbnailId);
    try {
      const updated = await setActiveProjectThumbnail(
        project.id,
        thumbnailId,
      );
      setThumbnails((previous) =>
        previous.map((item) => ({
          ...item,
          is_active: item.id === updated.id,
        })),
      );
      await onProjectRefreshed();
      toast.success('Active thumbnail updated.');
    } catch (activateError) {
      toast.error(
        errorMessage(activateError, 'Could not activate that thumbnail.'),
      );
    } finally {
      setBusyThumbnailId(null);
    }
  };

  const handleDeleteThumbnail = async (thumbnailId: string) => {
    setBusyThumbnailId(thumbnailId);
    try {
      await deleteProjectThumbnailAsset(project.id, thumbnailId);
      setThumbnails((previous) =>
        previous.filter((item) => item.id !== thumbnailId),
      );
      await onProjectRefreshed();
      toast('Thumbnail deleted.');
    } catch (deleteError) {
      toast.error(
        errorMessage(deleteError, 'Could not delete that thumbnail.'),
      );
    } finally {
      setBusyThumbnailId(null);
    }
  };

  const readyToGenerate =
    readiness.ready && selectedIds.length >= MIN_REFERENCES && !generating;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="flex h-[100dvh] w-[100vw] max-w-none translate-x-[-50%] translate-y-[-50%] flex-col gap-0 overflow-hidden rounded-none border-0 p-0 sm:max-w-none"
        aria-describedby="metadata-management-description"
      >
        <DialogHeader className="shrink-0 border-b px-4 py-4 text-left sm:px-6">
          <DialogTitle className="flex items-center gap-2 text-lg">
            <Images className="size-5 text-primary" />
            Metadata management
          </DialogTitle>
          <DialogDescription id="metadata-management-description">
            Draft a YouTube thumbnail prompt from the script, storyboard images
            and extra references, then upload and choose the active thumbnail
            for “{project.title}”.
          </DialogDescription>
        </DialogHeader>

        <div className="flex-1 overflow-y-auto">
          <div className="mx-auto grid max-w-7xl gap-6 p-4 sm:p-6 lg:grid-cols-[minmax(0,1fr)_minmax(340px,440px)]">
            {/* ── Left: references and prompt controls ── */}
            <div className="min-w-0 space-y-5">
              <div
                className={cn(
                  'rounded-lg border p-3 text-sm',
                  readiness.ready
                    ? 'border-emerald-500/30 bg-emerald-500/5 text-emerald-700 dark:text-emerald-400'
                    : 'border-amber-500/30 bg-amber-500/5 text-amber-700 dark:text-amber-400',
                )}
              >
                {readiness.ready ? (
                  <p className="flex items-center gap-2">
                    <CheckCircle2 className="size-4 shrink-0" />
                    Thumbnail generation is ready — {readiness.image_count} of{' '}
                    {readiness.segment_count} blocks have images.
                  </p>
                ) : (
                  <p>
                    Thumbnail generation unlocks after the script is crafted
                    and at least half of the blocks have images.{' '}
                    {readiness.script_ready
                      ? `${readiness.image_count}/${readiness.segment_count} blocks have images (need ${readiness.required_images}).`
                      : 'This project has no script yet.'}
                  </p>
                )}
              </div>

              {/* System prompt */}
              <section className="rounded-lg border">
                <button
                  type="button"
                  className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left"
                  onClick={() => setSystemOpen((previous) => !previous)}
                  aria-expanded={systemOpen}
                  aria-controls="thumbnail-system-prompt"
                >
                  <span>
                    <span className="block text-sm font-medium">
                      System prompt
                    </span>
                    <span className="mt-0.5 block text-xs text-muted-foreground">
                      Collapsed by default. Leave empty to use the built-in
                      thumbnail art director.
                    </span>
                  </span>
                  {systemOpen ? (
                    <ChevronDown className="size-4 shrink-0" />
                  ) : (
                    <ChevronRight className="size-4 shrink-0" />
                  )}
                </button>
                {systemOpen && (
                  <div
                    id="thumbnail-system-prompt"
                    className="border-t px-4 py-3"
                  >
                    <Textarea
                      value={systemPrompt}
                      onChange={(event) => setSystemPrompt(event.target.value)}
                      placeholder="You are a senior YouTube thumbnail art director…"
                      className="min-h-40 font-mono text-xs"
                      aria-label="Thumbnail system prompt"
                    />
                    <div className="mt-2 flex justify-end">
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        onClick={() => void saveSystemPrompt()}
                        disabled={savingSystem}
                      >
                        {savingSystem ? (
                          <Loader2 className="mr-1.5 size-3.5 animate-spin" />
                        ) : null}
                        Save system prompt
                      </Button>
                    </div>
                  </div>
                )}
              </section>

              {/* Storyboard references */}
              <section className="space-y-2">
                <div className="flex items-center justify-between gap-3">
                  <h3 className="text-sm font-medium">
                    Storyboard reference images
                  </h3>
                  <span className="text-xs text-muted-foreground">
                    {selectedIds.length} selected
                  </span>
                </div>
                <p className="text-xs text-muted-foreground">
                  The first {DEFAULT_SELECTION} illustrated blocks are selected
                  by default. Add or remove any block.
                </p>
                {imageSegments.length === 0 ? (
                  <p className="rounded-lg border border-dashed p-4 text-sm text-muted-foreground">
                    Add images to the storyboard blocks to use them as
                    references.
                  </p>
                ) : (
                  <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 xl:grid-cols-4">
                    {imageSegments.map((segment) => {
                      const selected = selectedIds.includes(segment.id);
                      return (
                        <button
                          key={segment.id}
                          type="button"
                          onClick={() => toggleSegment(segment.id)}
                          aria-pressed={selected}
                          aria-label={`Use block ${segment.sequence_index + 1} as a reference`}
                          className={cn(
                            'group relative overflow-hidden rounded-lg border text-left transition',
                            selected
                              ? 'border-primary ring-2 ring-primary/30'
                              : 'border-border hover:border-primary/50',
                          )}
                        >
                          {/* eslint-disable-next-line @next/next/no-img-element */}
                          <img
                            src={segment.image_file ?? ''}
                            alt={`Block ${segment.sequence_index + 1}`}
                            className="h-20 w-full object-cover"
                          />
                          <span className="absolute left-1.5 top-1.5 rounded bg-black/70 px-1.5 py-0.5 text-[10px] font-medium text-white">
                            Block {segment.sequence_index + 1}
                          </span>
                          {selected && (
                            <span className="absolute right-1.5 top-1.5 rounded-full bg-primary p-0.5 text-primary-foreground">
                              <CheckCircle2 className="size-3.5" />
                            </span>
                          )}
                        </button>
                      );
                    })}
                  </div>
                )}
              </section>

              {/* External image references */}
              <section className="space-y-2">
                <div className="flex items-center justify-between gap-3">
                  <h3 className="text-sm font-medium">
                    Extra image references
                  </h3>
                  <Button
                    type="button"
                    size="sm"
                    variant="ghost"
                    className="h-7 text-xs"
                    onClick={() => externalInputRef.current?.click()}
                  >
                    <ImagePlus className="mr-1.5 size-3.5" />
                    Add images
                  </Button>
                </div>
                <div
                  role="button"
                  tabIndex={0}
                  onClick={() => externalInputRef.current?.click()}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter' || event.key === ' ') {
                      event.preventDefault();
                      externalInputRef.current?.click();
                    }
                  }}
                  onDragOver={(event) => {
                    event.preventDefault();
                    setDraggingExternal(true);
                  }}
                  onDragLeave={() => setDraggingExternal(false)}
                  onDrop={(event) => {
                    event.preventDefault();
                    setDraggingExternal(false);
                    addExternalImages(event.dataTransfer.files);
                  }}
                  className={cn(
                    'rounded-lg border border-dashed p-4 text-center text-xs text-muted-foreground transition',
                    draggingExternal && 'border-primary bg-primary/5',
                  )}
                >
                  Drop style references here, or click to choose images. These
                  are sent only with the prompt request.
                </div>
                <input
                  ref={externalInputRef}
                  type="file"
                  accept="image/*"
                  multiple
                  className="hidden"
                  aria-label="Upload extra reference images"
                  onChange={(event) => {
                    if (event.target.files) {
                      addExternalImages(event.target.files);
                    }
                    event.target.value = '';
                  }}
                />
                {externalImages.length > 0 && (
                  <ul className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                    {externalImages.map((item, index) => (
                      <li
                        key={`${item.file.name}-${index}`}
                        className="relative overflow-hidden rounded-lg border"
                      >
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img
                          src={item.url}
                          alt={item.file.name}
                          className="h-16 w-full object-cover"
                        />
                        <button
                          type="button"
                          onClick={() => removeExternalImage(index)}
                          className="absolute right-1 top-1 rounded-full bg-black/70 p-1 text-white"
                          aria-label={`Remove ${item.file.name}`}
                        >
                          <Trash2 className="size-3" />
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </section>

              {/* Documents */}
              <section className="space-y-2">
                <div className="flex items-center justify-between gap-3">
                  <h3 className="text-sm font-medium">
                    Extra reference files
                  </h3>
                  <Button
                    type="button"
                    size="sm"
                    variant="ghost"
                    className="h-7 text-xs"
                    onClick={() => documentInputRef.current?.click()}
                  >
                    <Upload className="mr-1.5 size-3.5" />
                    Add files
                  </Button>
                </div>
                <p className="text-xs text-muted-foreground">
                  PDF, TXT, Markdown, CSV or JSON notes. Their text is included
                  in the prompt request.
                </p>
                <input
                  ref={documentInputRef}
                  type="file"
                  accept=".pdf,.txt,.md,.csv,.json"
                  multiple
                  className="hidden"
                  aria-label="Upload extra reference files"
                  onChange={(event) => {
                    if (event.target.files) addDocuments(event.target.files);
                    event.target.value = '';
                  }}
                />
                {documents.length > 0 && (
                  <ul className="space-y-1">
                    {documents.map((document, index) => (
                      <li
                        key={`${document.name}-${index}`}
                        className="flex items-center gap-2 rounded-md border px-2 py-1.5 text-xs"
                      >
                        <FileText className="size-3.5 shrink-0 text-muted-foreground" />
                        <span className="min-w-0 flex-1 truncate">
                          {document.name}
                        </span>
                        <button
                          type="button"
                          onClick={() =>
                            setDocuments((previous) =>
                              previous.filter(
                                (_, position) => position !== index,
                              ),
                            )
                          }
                          className="text-muted-foreground hover:text-destructive"
                          aria-label={`Remove ${document.name}`}
                        >
                          <Trash2 className="size-3.5" />
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </section>

              {/* User message */}
              <section className="space-y-2">
                <h3 className="text-sm font-medium">Your instructions</h3>
                <Textarea
                  value={message}
                  onChange={(event) => setMessage(event.target.value)}
                  placeholder="For example: refer to the script and its images, then mimic the style of the reference thumbnails I uploaded."
                  className="min-h-24 text-sm"
                  aria-label="Your thumbnail instructions"
                />
              </section>

              {error && (
                <p className="rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2 text-xs text-destructive">
                  {error}
                </p>
              )}

              <Button
                type="button"
                onClick={() => void handleGenerate()}
                disabled={!readyToGenerate}
                className="w-full"
              >
                {generating ? (
                  <Loader2 className="mr-2 size-4 animate-spin" />
                ) : (
                  <Sparkles className="mr-2 size-4" />
                )}
                {generating ? 'Drafting prompt…' : 'Generate thumbnail prompt'}
              </Button>
            </div>

            {/* ── Right: prompt output and thumbnail gallery ── */}
            <div className="min-w-0 space-y-5">
              <section className="space-y-2">
                <div className="flex items-center justify-between gap-3">
                  <h3 className="text-sm font-medium">Generated prompt</h3>
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    className="h-7 text-xs"
                    onClick={() => void handleCopyPrompt()}
                    disabled={!prompt}
                  >
                    <Copy className="mr-1.5 size-3.5" />
                    Copy
                  </Button>
                </div>
                <Textarea
                  readOnly
                  value={prompt}
                  placeholder="Generate a prompt to see it here. You can generate as many times as you like."
                  className="min-h-56 font-mono text-xs"
                  aria-label="Generated thumbnail prompt"
                />
              </section>

              <section className="space-y-2">
                <div className="flex items-center justify-between gap-3">
                  <h3 className="text-sm font-medium">Project thumbnails</h3>
                  <span className="text-xs text-muted-foreground">
                    {thumbnails.length} saved
                  </span>
                </div>
                <div
                  role="button"
                  tabIndex={0}
                  onClick={() => thumbnailInputRef.current?.click()}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter' || event.key === ' ') {
                      event.preventDefault();
                      thumbnailInputRef.current?.click();
                    }
                  }}
                  onDragOver={(event) => {
                    event.preventDefault();
                    setDraggingThumbnail(true);
                  }}
                  onDragLeave={() => setDraggingThumbnail(false)}
                  onDrop={(event) => {
                    event.preventDefault();
                    setDraggingThumbnail(false);
                    const file = event.dataTransfer.files?.[0];
                    if (file) void handleThumbnailFile(file);
                  }}
                  onPaste={handleThumbnailPaste}
                  className={cn(
                    'flex min-h-32 flex-col items-center justify-center gap-2 rounded-lg border border-dashed p-4 text-center transition',
                    draggingThumbnail && 'border-primary bg-primary/5',
                  )}
                >
                  {uploading ? (
                    <Loader2 className="size-5 animate-spin text-primary" />
                  ) : (
                    <ImagePlus className="size-5 text-muted-foreground" />
                  )}
                  <p className="text-xs text-muted-foreground">
                    Paste, drop or click to upload the generated thumbnail. The
                    first upload becomes active automatically.
                  </p>
                </div>
                <input
                  ref={thumbnailInputRef}
                  type="file"
                  accept="image/*"
                  className="hidden"
                  aria-label="Upload thumbnail image"
                  onChange={(event) => {
                    const file = event.target.files?.[0];
                    event.target.value = '';
                    if (file) void handleThumbnailFile(file);
                  }}
                />

                {thumbnails.length === 0 ? (
                  <p className="rounded-lg border border-dashed p-4 text-sm text-muted-foreground">
                    No thumbnails uploaded yet.
                  </p>
                ) : (
                  <ul className="grid grid-cols-2 gap-3">
                    {thumbnails.map((thumbnail) => (
                      <li
                        key={thumbnail.id}
                        className={cn(
                          'overflow-hidden rounded-lg border',
                          thumbnail.is_active &&
                            'border-primary ring-2 ring-primary/30',
                        )}
                      >
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img
                          src={thumbnail.url ?? ''}
                          alt="Project thumbnail candidate"
                          className="aspect-video w-full object-cover"
                        />
                        <div className="flex items-center justify-between gap-2 p-2">
                          {thumbnail.is_active ? (
                            <Badge variant="secondary" className="text-[10px]">
                              Active
                            </Badge>
                          ) : (
                            <Button
                              type="button"
                              size="sm"
                              variant="ghost"
                              className="h-7 px-2 text-xs"
                              onClick={() =>
                                void handleActivateThumbnail(thumbnail.id)
                              }
                              disabled={busyThumbnailId === thumbnail.id}
                            >
                              {busyThumbnailId === thumbnail.id ? (
                                <Loader2 className="size-3.5 animate-spin" />
                              ) : (
                                'Make active'
                              )}
                            </Button>
                          )}
                          <Button
                            type="button"
                            size="icon"
                            variant="ghost"
                            className="size-7 text-destructive hover:text-destructive"
                            onClick={() =>
                              void handleDeleteThumbnail(thumbnail.id)
                            }
                            disabled={busyThumbnailId === thumbnail.id}
                            aria-label="Delete thumbnail"
                          >
                            <Trash2 className="size-3.5" />
                          </Button>
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </section>
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

export default MetadataManagementModal;
