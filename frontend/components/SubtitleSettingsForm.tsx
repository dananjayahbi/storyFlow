'use client';

import { useState, useCallback, useRef, useEffect } from 'react';
import { useSettingsStore } from '@/lib/stores';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { VALIDATION } from '@/lib/constants';
import { SubtitlePreview } from '@/components/SubtitlePreview';
import { Type, Upload, Loader2 } from 'lucide-react';
import { toast } from 'sonner';

// ── Props ──────────────────────────────────────────────────────────
interface SubtitleSettingsFormProps {
  /** Current subtitle font path (may be empty for default). */
  font: string;
  /** Current subtitle color hex string. */
  color: string;
  /** Called with partial settings update to persist changes. */
  onChange: (data: { subtitle_font?: string; subtitle_color?: string }) => Promise<void>;
}

// ── Helpers ────────────────────────────────────────────────────────

/** Extract a display name from a font file path.
 *  e.g. "/fonts/custom.ttf" → "custom"
 *  Falls back to "Default (Roboto Bold)" when path is empty. */
function parseFontName(fontPath: string): string {
  if (!fontPath || fontPath.trim() === '') {
    return 'Default (Roboto Bold)';
  }
  // Get filename from path, strip extension
  const parts = fontPath.replace(/\\/g, '/').split('/');
  const filename = parts[parts.length - 1] || '';
  const dotIdx = filename.lastIndexOf('.');
  return dotIdx > 0 ? filename.substring(0, dotIdx) : filename || 'Default (Roboto Bold)';
}

/** Validate a font file on the client side. Returns an error string or null. */
function validateFontFile(file: File): string | null {
  const ext = file.name.substring(file.name.lastIndexOf('.')).toLowerCase();
  const allowed = VALIDATION.ALLOWED_FONT_EXTENSIONS as readonly string[];
  if (!allowed.includes(ext)) {
    return 'Only .ttf and .otf files are accepted';
  }
  if (file.size > VALIDATION.MAX_FONT_SIZE) {
    return 'Font file must be under 10 MB';
  }
  return null;
}

// ── Component ──────────────────────────────────────────────────────

export function SubtitleSettingsForm({
  font,
  color,
  onChange,
}: SubtitleSettingsFormProps) {
  const { uploadFont, isFontUploading } = useSettingsStore();

  // ── Font state ──
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [fontError, setFontError] = useState<string | null>(null);

  // ── Color state ──
  const [localColor, setLocalColor] = useState(color);
  const [colorError, setColorError] = useState<string | null>(null);
  const colorTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Sync local color when prop changes (e.g. after fetch)
  useEffect(() => {
    setLocalColor(color);
  }, [color]);

  // Cleanup debounce timer on unmount
  useEffect(() => {
    return () => {
      if (colorTimerRef.current) clearTimeout(colorTimerRef.current);
    };
  }, []);

  // ── Font Upload Handler ──
  const handleFontSelect = useCallback(
    async (e: React.ChangeEvent<HTMLInputElement>) => {
      setFontError(null);
      const file = e.target.files?.[0];
      if (!file) return;

      // Client-side validation
      const error = validateFontFile(file);
      if (error) {
        setFontError(error);
        // Reset input so the same file can be re-selected
        if (fileInputRef.current) fileInputRef.current.value = '';
        return;
      }

      try {
        await uploadFont(file);
        toast.success('Font uploaded successfully');
      } catch {
        toast.error('Failed to upload font');
      }

      // Reset input
      if (fileInputRef.current) fileInputRef.current.value = '';
    },
    [uploadFont]
  );

  // ── Color Change Handler (debounced) ──
  const handleColorInput = useCallback(
    (value: string) => {
      setLocalColor(value);

      // Validate hex color
      if (value && !VALIDATION.HEX_COLOR_REGEX.test(value)) {
        setColorError('Enter a valid hex color (e.g., #FFFFFF)');
        return;
      }
      setColorError(null);

      // Debounce the API call
      if (colorTimerRef.current) clearTimeout(colorTimerRef.current);
      colorTimerRef.current = setTimeout(() => {
        onChange({ subtitle_color: value });
      }, 300);
    },
    [onChange]
  );

  // ── Native color picker handler (no debounce needed — discrete events) ──
  const handleColorPicker = useCallback(
    (value: string) => {
      setLocalColor(value);
      setColorError(null);
      // Debounce picker changes too (fires rapidly on drag)
      if (colorTimerRef.current) clearTimeout(colorTimerRef.current);
      colorTimerRef.current = setTimeout(() => {
        onChange({ subtitle_color: value });
      }, 300);
    },
    [onChange]
  );

  return (
    <div className="space-y-4">
      {/* ── Section Header ── */}
      <div className="flex items-center gap-1.5">
        <Type className="h-4 w-4 text-muted-foreground" />
        <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Subtitles
        </h3>
      </div>

      {/* ── Font Section ── */}
      <div className="space-y-2">
        <label className="text-xs text-muted-foreground font-medium">
          Font
        </label>

        {/* Current font display */}
        <div className="flex items-center gap-2">
          <span className="text-sm truncate flex-1">
            {parseFontName(font)}
          </span>
        </div>

        {/* Upload button + hidden file input */}
        <div>
          <input
            ref={fileInputRef}
            type="file"
            accept=".ttf,.otf"
            onChange={handleFontSelect}
            className="hidden"
          />
          <Button
            size="sm"
            variant="outline"
            onClick={() => fileInputRef.current?.click()}
            disabled={isFontUploading}
            className="w-full"
          >
            {isFontUploading ? (
              <>
                <Loader2 className="h-4 w-4 mr-1.5 animate-spin" />
                Uploading…
              </>
            ) : (
              <>
                <Upload className="h-4 w-4 mr-1.5" />
                Upload Font
              </>
            )}
          </Button>

          {/* Font validation error */}
          {fontError && (
            <p className="text-xs text-destructive mt-1">{fontError}</p>
          )}
        </div>
      </div>

      {/* ── Color Section ── */}
      <div className="space-y-2">
        <label className="text-xs text-muted-foreground font-medium">
          Color
        </label>

        <div className="flex items-center gap-2">
          {/* Color swatch / native picker */}
          <input
            type="color"
            value={
              VALIDATION.HEX_COLOR_REGEX.test(localColor) ? localColor : '#FFFFFF'
            }
            onChange={(e) => handleColorPicker(e.target.value)}
            className="h-8 w-8 rounded border border-input cursor-pointer shrink-0"
          />

          {/* Hex text input */}
          <Input
            value={localColor}
            onChange={(e) => handleColorInput(e.target.value)}
            placeholder="#FFFFFF"
            className="h-8 text-sm font-mono flex-1"
            maxLength={7}
          />
        </div>

        {/* Color validation error */}
        {colorError && (
          <p className="text-xs text-destructive mt-1">{colorError}</p>
        )}
      </div>

      {/* ── Subtitle Preview (Task 05.03.04) ── */}
      <SubtitlePreview font={font} color={localColor} />
    </div>
  );
}
