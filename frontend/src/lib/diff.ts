/**
 * Word-level diff between two strings.
 *
 * Returns an array of segments: each segment is "equal", "delete", or "insert".
 * Uses a simple LCS-based approach on word tokens (preserving whitespace).
 */

export interface DiffSegment {
  type: "equal" | "delete" | "insert";
  text: string;
}

// ---------------------------------------------------------------------------
// Tokenise — split into words + whitespace tokens so we preserve formatting
// ---------------------------------------------------------------------------

function tokenize(text: string): string[] {
  // Split into alternating whitespace / non-whitespace tokens
  return text.match(/\S+|\s+/g) ?? [];
}

// ---------------------------------------------------------------------------
// LCS table (classic DP)
// ---------------------------------------------------------------------------

function lcsTable(a: string[], b: string[]): number[][] {
  const m = a.length;
  const n = b.length;
  const dp: number[][] = Array.from({ length: m + 1 }, () =>
    new Array(n + 1).fill(0),
  );
  for (let i = 1; i <= m; i++) {
    for (let j = 1; j <= n; j++) {
      if (a[i - 1] === b[j - 1]) {
        dp[i][j] = dp[i - 1][j - 1] + 1;
      } else {
        dp[i][j] = Math.max(dp[i - 1][j], dp[i][j - 1]);
      }
    }
  }
  return dp;
}

// ---------------------------------------------------------------------------
// Backtrack through LCS to produce diff segments
// ---------------------------------------------------------------------------

export function wordDiff(oldText: string, newText: string): DiffSegment[] {
  const a = tokenize(oldText);
  const b = tokenize(newText);
  const dp = lcsTable(a, b);

  const result: DiffSegment[] = [];
  let i = a.length;
  let j = b.length;

  // Collect in reverse, then reverse
  const rev: DiffSegment[] = [];

  while (i > 0 || j > 0) {
    if (i > 0 && j > 0 && a[i - 1] === b[j - 1]) {
      rev.push({ type: "equal", text: a[i - 1] });
      i--;
      j--;
    } else if (j > 0 && (i === 0 || dp[i][j - 1] >= dp[i - 1][j])) {
      rev.push({ type: "insert", text: b[j - 1] });
      j--;
    } else {
      rev.push({ type: "delete", text: a[i - 1] });
      i--;
    }
  }

  rev.reverse();

  // Merge consecutive segments of the same type
  for (const seg of rev) {
    const last = result[result.length - 1];
    if (last && last.type === seg.type) {
      last.text += seg.text;
    } else {
      result.push({ ...seg });
    }
  }

  return result;
}

/**
 * Reconstruct text from diff segments, keeping only equal + insert parts.
 * Insert parts may have been edited by the user.
 */
export function applyDiff(segments: DiffSegment[], editedInserts: Map<number, string>): string {
  let text = "";
  let insertIdx = 0;
  for (const seg of segments) {
    if (seg.type === "equal") {
      text += seg.text;
    } else if (seg.type === "insert") {
      text += editedInserts.get(insertIdx) ?? seg.text;
      insertIdx++;
    }
    // skip "delete" segments
  }
  return text;
}
