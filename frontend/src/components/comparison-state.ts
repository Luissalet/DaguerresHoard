import type { PhotoDetail } from "../types";

export interface ComparisonResult { id: string; detail?: PhotoDetail; error?: string }

// A changed side cancels only its old response, without touching the other side.
export function loadComparisonPhoto(id: string, load: (id: string) => Promise<PhotoDetail>, receive: (value: ComparisonResult) => void) {
  let active = true;
  load(id).then(detail => {
    if (active) receive({ id, detail });
  }).catch((error: unknown) => {
    if (active) receive({ id, error: error instanceof Error ? error.message : String(error) });
  });
  return () => { active = false; };
}
