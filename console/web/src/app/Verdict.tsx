/**
 * Shared display of model output and of Z (PLAN 6, rule 3): a model gives a
 * verdict from a fixed vocabulary, never a Z; Z shown to people comes from the
 * encoder read-back only.
 */

export const VERDICTS = ["in_focus", "step_up", "step_down", "no_sample_here", "unsure"] as const;
export type Verdict = (typeof VERDICTS)[number];

export function isVerdict(v: unknown): v is Verdict {
  return typeof v === "string" && (VERDICTS as readonly string[]).includes(v);
}

const LABEL: Record<Verdict, string> = {
  in_focus: "In focus",
  step_up: "Step up",
  step_down: "Step down",
  no_sample_here: "No sample here",
  unsure: "Unsure",
};

/**
 * Where a verdict came from, in the grade vocabulary (measured / computed / model):
 * "computed" is a classical result from code (e.g. the 100x focus sweep), "model"
 * is a model's output (DINO head, Claude). The shell owns these words.
 */
export const VERDICT_SOURCES = ["computed", "model"] as const;
export type VerdictSource = (typeof VERDICT_SOURCES)[number];

/**
 * A verdict, tagged with its source. `source` is required so no screen can show a
 * model's verdict untagged. Anything outside the five words is shown as "Unsure"
 * (and marked invalid) rather than passed through.
 */
export function FocusVerdict({ verdict, source }: { verdict: unknown; source: VerdictSource }) {
  const ok = isVerdict(verdict);
  const v: Verdict = ok ? verdict : "unsure";
  // an unexpected source string (from untyped data) is shown as the weaker grade
  const src: VerdictSource = source === "computed" ? "computed" : "model";
  return (
    <span className={`verdict verdict-${v}`} data-verdict={v} data-source={src}
          data-invalid={ok ? undefined : "true"}
          title={ok ? undefined : `not a verdict word: ${String(verdict)}`}>
      {LABEL[v]} <span className="grade">{src}</span>
    </span>
  );
}

/** Z from the encoder read-back (ZDrive), in um. null when it could not be read. */
export function EncoderZ({ readbackUm, digits = 2 }: { readbackUm: number | null | undefined; digits?: number }) {
  const ok = typeof readbackUm === "number" && Number.isFinite(readbackUm);
  return (
    <span className="encoder-z" title="ZDrive encoder read-back">
      Z {ok ? `${readbackUm.toFixed(digits)} µm` : "—"}
    </span>
  );
}
