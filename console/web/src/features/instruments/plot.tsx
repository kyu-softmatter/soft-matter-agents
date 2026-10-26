/** A small line plot of points, drawn from numbers the screen was given: no axis names are guessed. */

export interface Pt {
  x: number;
  y: number;
}

const W = 220;
const H = 120;

function scale(v: number, lo: number, hi: number, size: number): number {
  return hi === lo ? size / 2 : ((v - lo) / (hi - lo)) * size;
}

export function Plot({ label, points }: { label: string; points: Pt[] }) {
  const xs = points.map((p) => p.x);
  const ys = points.map((p) => p.y);
  const [x0, x1, y0, y1] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)];
  const at = (p: Pt) => `${scale(p.x, x0, x1, W - 10) + 5},${H - 5 - scale(p.y, y0, y1, H - 10)}`;
  return (
    <svg role="img" aria-label={label} viewBox={`0 0 ${W} ${H}`} className="inst-plot">
      <rect x="0" y="0" width={W} height={H} fill="none" stroke="currentColor" opacity="0.3" />
      {points.length > 1 && <polyline points={points.map(at).join(" ")} fill="none" stroke="currentColor" />}
      {points.map((p, i) => {
        const [cx, cy] = at(p).split(",");
        return <circle key={i} cx={cx} cy={cy} r="2" fill="currentColor" />;
      })}
    </svg>
  );
}
