import type { ReactNode } from "react";

export interface Choice<T extends string> {
  value: T;
  label: ReactNode;
  hint?: string;
}

/** One choice out of a few, shown side by side. */
export function Segmented<T extends string>({ value, options, onChange, label }: { value: T; options: Choice<T>[]; onChange: (v: T) => void; label: string }) {
  return (
    <div className="seg" role="radiogroup" aria-label={label}>
      {options.map((o) => (
        <button key={o.value} type="button" role="radio" aria-checked={o.value === value} className={o.value === value ? "on" : ""} onClick={() => onChange(o.value)} title={o.hint}>
          {o.label}
        </button>
      ))}
    </div>
  );
}
