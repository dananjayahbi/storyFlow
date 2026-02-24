'use client';

import { useState, useRef } from 'react';
import { Upload, X } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface ImageUploaderProps {
  segmentId: string;
  currentImage: string | null;
  isLocked: boolean;
  onUpload: (segmentId: string, file: File) => Promise<void>;
  onRemove: (segmentId: string) => Promise<void>;
}

const ALLOWED_TYPES = ['image/jpeg', 'image/png', 'image/webp'];
const MAX_SIZE = 20 * 1024 * 1024; // 20MB

export function ImageUploader({
  segmentId, currentImage, isLocked, onUpload, onRemove,
}: ImageUploaderProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const dragCounterRef = useRef(0);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const imageUrl = currentImage
    ? (currentImage.startsWith('http') ? currentImage : `${process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000'}${currentImage}`)
    : null;

  const handleFile = async (file: File) => {
    if (!ALLOWED_TYPES.includes(file.type)) {
      setError('Only JPEG, PNG, and WebP images are allowed.');
      return;
    }
    if (file.size > MAX_SIZE) {
      setError('Image must be under 20MB.');
      return;
    }
    setError(null);
    setIsUploading(true);
    try {
      await onUpload(segmentId, file);
    } finally {
      setIsUploading(false);
    }
  };

  const onDragEnter = (e: React.DragEvent) => {
    e.preventDefault();
    if (isLocked) return;
    dragCounterRef.current++;
    setIsDragging(true);
  };

  const onDragOver = (e: React.DragEvent) => {
    e.preventDefault(); // REQUIRED — without this, onDrop won't fire
  };

  const onDragLeave = () => {
    dragCounterRef.current--;
    if (dragCounterRef.current === 0) setIsDragging(false);
  };

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    dragCounterRef.current = 0;
    setIsDragging(false);
    if (isLocked) return;
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  };

  const handleZoneClick = () => {
    if (isLocked) return;
    fileInputRef.current?.click();
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      handleZoneClick();
    }
  };

  const handleRemove = async () => {
    if (isLocked) return;
    await onRemove(segmentId);
  };

  // State B — Image uploaded: show preview with remove button
  if (imageUrl) {
    return (
      <div className="space-y-1">
        <div className="relative group">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={imageUrl}
            alt="Segment image"
            className="w-full h-auto rounded-md border"
          />
          {!isLocked && (
            <Button
              variant="destructive"
              size="icon"
              className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity h-8 w-8"
              onClick={handleRemove}
              aria-label="Remove image"
            >
              <X className="h-4 w-4" />
            </Button>
          )}
        </div>
        {error && (
          <p className="text-xs text-destructive">{error}</p>
        )}
      </div>
    );
  }

  // State A — No image: show drop zone
  return (
    <div className="space-y-1">
      <div
        role="button"
        tabIndex={isLocked ? -1 : 0}
        onClick={handleZoneClick}
        onKeyDown={handleKeyDown}
        onDragEnter={onDragEnter}
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        onDrop={onDrop}
        className={`flex flex-col items-center justify-center h-32 md:h-40 border-2 border-dashed rounded-md cursor-pointer transition-colors ${
          isLocked
            ? 'opacity-50 cursor-not-allowed border-muted'
            : isDragging
              ? 'border-primary bg-primary/5'
              : 'border-muted-foreground/25 hover:border-primary/50'
        }`}
      >
        {isUploading ? (
          <p className="text-sm text-muted-foreground">Uploading...</p>
        ) : (
          <>
            <Upload className="h-8 w-8 text-muted-foreground mb-2" />
            <p className="text-sm text-muted-foreground">
              Drop image here or click to browse
            </p>
          </>
        )}
      </div>

      <input
        ref={fileInputRef}
        type="file"
        accept="image/jpeg,image/png,image/webp"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) handleFile(file);
        }}
      />

      {error && (
        <p className="text-xs text-destructive">{error}</p>
      )}
    </div>
  );
}
