# Task 01.03.07 — Build ProjectCard Component

## Metadata

| Field                    | Value                                                                          |
| ------------------------ | ------------------------------------------------------------------------------ |
| **Sub-Phase**            | SubPhase 01.03 — Dashboard UI & Basic API                                      |
| **Phase**                | Phase 01 — The Skeleton                                                        |
| **Document Type**        | Layer 3 — Task Document                                                        |
| **Estimated Complexity** | Medium                                                                         |
| **Dependencies**         | [Task_01_03_04](Task_01_03_04_Define_TypeScript_Interfaces.md) — Types must exist |
| **Parent Document**      | [SubPhase_01_03_Overview.md](SubPhase_01_03_Overview.md) (Layer 2, §5.7)       |

---

## Objective

Create the `ProjectCard` component that displays a project's metadata (title, status badge, creation date, segment count) in a styled Shadcn/UI Card, wrapped in a navigation link.

---

## Instructions

### Step 1: Create `ProjectCard.tsx`

Create `frontend/components/ProjectCard.tsx`:

```tsx
import Link from 'next/link';
import { Card, CardHeader, CardTitle, CardContent, CardFooter } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Project } from '@/lib/types';

interface ProjectCardProps {
  project: Project;
}

const statusVariant: Record<Project['status'], 'default' | 'secondary' | 'destructive' | 'outline'> = {
  DRAFT: 'secondary',
  PROCESSING: 'outline',
  COMPLETED: 'default',
  FAILED: 'destructive',
};

export function ProjectCard({ project }: ProjectCardProps) {
  return (
    <Link href={`/projects/${project.id}`}>
      <Card className="hover:shadow-lg transition-shadow cursor-pointer">
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="text-lg">{project.title}</CardTitle>
            <Badge variant={statusVariant[project.status]}>
              {project.status}
            </Badge>
          </div>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            {project.segment_count} segment{project.segment_count !== 1 ? 's' : ''}
          </p>
        </CardContent>
        <CardFooter>
          <p className="text-xs text-muted-foreground">
            Created {new Date(project.created_at).toLocaleDateString('en-US', {
              year: 'numeric',
              month: 'short',
              day: 'numeric',
            })}
          </p>
        </CardFooter>
      </Card>
    </Link>
  );
}
```

---

## Expected Output

```
frontend/components/
├── ProjectCard.tsx         ← NEW
├── CreateProjectDialog.tsx ← Created in Task 01.03.08
└── ui/                     ← Existing (Shadcn/UI components)
```

---

## Validation

- [ ] `frontend/components/ProjectCard.tsx` exists.
- [ ] Component accepts `project: Project` prop.
- [ ] Card is wrapped in a Next.js `Link` to `/projects/{id}`.
- [ ] Project title is displayed in the card header.
- [ ] Status is shown as a `Badge` with variant mapped by status value.
- [ ] Badge variants: DRAFT → `secondary`, PROCESSING → `outline`, COMPLETED → `default`, FAILED → `destructive`.
- [ ] Segment count is displayed with proper singular/plural text.
- [ ] Creation date is formatted as human-readable (e.g., "Feb 16, 2026").
- [ ] Card has hover effect (`hover:shadow-lg transition-shadow`).

---

## Notes

- The `statusVariant` mapping uses Shadcn/UI `Badge` variant values. These may need adjustment based on the exact Shadcn/UI theme installed. The key principle is: DRAFT is neutral, PROCESSING is attention-getting, COMPLETED is positive, FAILED is negative.
- The component is a named export (`export function ProjectCard`) rather than a default export. This is consistent with Shadcn/UI component patterns and allows explicit imports.
- Date formatting uses `toLocaleDateString` with US English locale. This produces "Feb 16, 2026" format.

---

> **Parent:** [SubPhase_01_03_Overview.md](SubPhase_01_03_Overview.md) (Layer 2)
> **Previous Task:** [Task_01_03_06_Build_Dashboard_Page.md](Task_01_03_06_Build_Dashboard_Page.md)
> **Next Task:** [Task_01_03_08_Build_Create_Project_Dialog.md](Task_01_03_08_Build_Create_Project_Dialog.md)
