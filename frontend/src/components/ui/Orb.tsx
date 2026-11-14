interface OrbProps {
  size: number;
  className?: string;
}

/** The TIA brand orb: navy gradient circle with a cyan ring and "T" mark. */
export function Orb({ size, className }: OrbProps) {
  return (
    <div
      className={`flex shrink-0 items-center justify-center rounded-full border border-accent/25 bg-linear-to-br from-raised to-abyss font-bold text-accent ${className ?? ""}`}
      style={{ width: size, height: size, fontSize: size * 0.32 }}
    >
      T
    </div>
  );
}
