'use client';

import { useState, useEffect, useRef } from 'react';
import { Textarea } from '@/components/ui/textarea';

interface SegmentTextEditorProps {
  segmentId: string;
  initialContent: string;
  isLocked: boolean;
  onSave: (id: string, data: { text_content: string }) => Promise<void>;
}

export function SegmentTextEditor({
  segmentId, initialContent, isLocked, onSave,
}: SegmentTextEditorProps) {
  const [text, setText] = useState(initialContent);
  const [isSaving, setIsSaving] = useState(false);
  const timerRef = useRef<NodeJS.Timeout | null>(null);
  const lastSavedRef = useRef(initialContent);

  // Sync if initialContent changes externally (e.g., optimistic rollback)
  useEffect(() => {
    setText(initialContent);
    lastSavedRef.current = initialContent;
  }, [initialContent]);

  // Debounced auto-save
  useEffect(() => {
    if (text === lastSavedRef.current) return; // No change

    timerRef.current = setTimeout(async () => {
      setIsSaving(true);
      try {
        await onSave(segmentId, { text_content: text });
        lastSavedRef.current = text;
      } finally {
        setIsSaving(false);
      }
    }, 500);

    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [text, segmentId, onSave]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, []);

  return (
    <div className="space-y-1">
      <Textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        disabled={isLocked}
        rows={4}
        className="resize-y"
        placeholder="Segment text content..."
      />
      {isSaving && (
        <p className="text-xs text-muted-foreground">Saving...</p>
      )}
    </div>
  );
}
