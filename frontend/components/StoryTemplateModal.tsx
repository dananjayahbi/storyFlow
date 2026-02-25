'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { Separator } from '@/components/ui/separator';
import { Badge } from '@/components/ui/badge';
import { BookOpen, Copy, Check } from 'lucide-react';
import { toast } from 'sonner';

// ── Template & example data ──

const TEMPLATE_STRUCTURE = `{
  "title": "Your Story Title",
  "segments": [
    {
      "text_content": "Narration text for this segment...",
      "image_prompt": "Description of the image for this segment..."
    },
    {
      "text_content": "Next segment narration...",
      "image_prompt": "Next segment image description..."
    }
  ]
}`;

const EXAMPLE_STORY = `{
  "title": "The Lost City of Aurelia",
  "segments": [
    {
      "text_content": "Deep in the heart of the Amazon rainforest, where sunlight barely pierces the dense canopy above, a team of archaeologists discovered something extraordinary. Half-buried beneath centuries of jungle growth, the stone walls of an ancient city emerged from the earth like the bones of a sleeping giant.",
      "image_prompt": "An ancient stone city overgrown with jungle vines and moss, sunlight streaming through dense rainforest canopy, archaeological excavation site, cinematic wide shot, golden hour lighting"
    },
    {
      "text_content": "Dr. Elena Vasquez, the expedition leader, brushed the dirt from a carved stone tablet. The inscriptions were unlike anything she had seen before — a language that predated every known civilization in the Americas by at least a thousand years. Her hands trembled as she traced the symbols with her fingertips.",
      "image_prompt": "A female archaeologist carefully examining an ancient stone tablet with mysterious glowing inscriptions, headlamp illuminating carved symbols, close-up shot, dramatic lighting"
    },
    {
      "text_content": "As the team ventured deeper into the ruins, they found a grand plaza surrounded by towering pyramids. At the center stood a crystalline obelisk, perfectly preserved despite millennia of exposure. It caught the afternoon sun and scattered rainbow light across the weathered stone walls.",
      "image_prompt": "A magnificent ancient plaza with towering pyramids surrounding a glowing crystal obelisk, rainbow light refracting across stone walls, epic wide angle, fantasy archaeology setting"
    },
    {
      "text_content": "The most remarkable discovery came in the underground chambers beneath the largest pyramid. Walls lined with gold and precious stones reflected the glow of bioluminescent fungi that had colonized the ceiling, creating a living starscape above their heads.",
      "image_prompt": "Underground chamber with gold-lined walls and bioluminescent fungi on the ceiling creating a starry effect, treasure-filled ancient vault, ethereal blue-green glow, mysterious atmosphere"
    },
    {
      "text_content": "But it was the final chamber that changed everything. A perfectly circular room, its walls covered in astronomical charts of impossible accuracy. Star positions that modern telescopes had only recently confirmed. Calendar systems that predicted celestial events thousands of years into the future. Whoever built this city had knowledge that defied explanation.",
      "image_prompt": "A circular ancient observatory room with walls covered in precise astronomical charts and star maps, constellations glowing on dark stone walls, a lone archaeologist standing in awe at the center, dramatic overhead shot"
    }
  ]
}`;

// ── Copy button component ──

function CopyButton({ text, label }: { text: string; label: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      toast.success(`${label} copied to clipboard`);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      toast.error('Failed to copy to clipboard');
    }
  };

  return (
    <Button
      variant="outline"
      size="sm"
      className="h-7 text-xs gap-1.5"
      onClick={handleCopy}
    >
      {copied ? (
        <>
          <Check className="size-3" />
          Copied
        </>
      ) : (
        <>
          <Copy className="size-3" />
          Copy {label}
        </>
      )}
    </Button>
  );
}

// ── Main component ──

interface StoryTemplateModalProps {
  /** Custom trigger element. If not provided, renders a default button. */
  trigger?: React.ReactNode;
}

export function StoryTemplateModal({ trigger }: StoryTemplateModalProps) {
  return (
    <Dialog>
      <DialogTrigger asChild>
        {trigger ?? (
          <Button variant="outline" size="sm">
            <BookOpen className="size-4 mr-2" />
            Story Template
          </Button>
        )}
      </DialogTrigger>
      <DialogContent className="sm:max-w-2xl max-h-[85vh] flex flex-col">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <BookOpen className="size-5" />
            Story Template
          </DialogTitle>
        </DialogHeader>

        <div className="flex-1 overflow-y-auto space-y-6 pr-1">
          {/* Template Structure */}
          <section>
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <h3 className="text-sm font-semibold">Template Structure</h3>
                <Badge variant="secondary" className="text-[10px]">JSON</Badge>
              </div>
              <CopyButton text={TEMPLATE_STRUCTURE} label="Template" />
            </div>
            <p className="text-xs text-muted-foreground mb-2">
              Use this JSON structure to create a story. Each segment needs a{' '}
              <code className="text-[11px] bg-muted px-1 py-0.5 rounded">text_content</code> for narration
              and an <code className="text-[11px] bg-muted px-1 py-0.5 rounded">image_prompt</code> describing
              the visual for that segment.
            </p>
            <div className="relative">
              <pre className="bg-muted/50 border rounded-lg p-4 text-xs overflow-x-auto font-mono leading-relaxed">
                {TEMPLATE_STRUCTURE}
              </pre>
            </div>
          </section>

          <Separator />

          {/* Example Story */}
          <section>
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <h3 className="text-sm font-semibold">Example Story</h3>
                <Badge variant="outline" className="text-[10px]">5 segments</Badge>
              </div>
              <CopyButton text={EXAMPLE_STORY} label="Example" />
            </div>
            <p className="text-xs text-muted-foreground mb-2">
              A complete example story with narration texts and image prompts.
              You can copy this and import it into a project to see how it works.
            </p>
            <div className="relative">
              <pre className="bg-muted/50 border rounded-lg p-4 text-xs overflow-x-auto font-mono leading-relaxed max-h-80 overflow-y-auto">
                {EXAMPLE_STORY}
              </pre>
            </div>
          </section>

          {/* Tips */}
          <section className="bg-blue-500/5 border border-blue-500/20 rounded-lg p-3">
            <h4 className="text-xs font-semibold text-blue-600 dark:text-blue-400 mb-1.5">Tips</h4>
            <ul className="text-xs text-muted-foreground space-y-1 list-disc list-inside">
              <li>Each segment becomes one scene in your video</li>
              <li>Write <strong>text_content</strong> as natural narration — it will be converted to speech</li>
              <li>Write <strong>image_prompt</strong> as a detailed visual description for image generation</li>
              <li>You can add as many segments as needed</li>
              <li>Import your JSON via the <strong>Import Story</strong> button on the projects page</li>
            </ul>
          </section>
        </div>
      </DialogContent>
    </Dialog>
  );
}
