import { Orb } from "../ui/Orb";

const CHIPS = [
  "Text chat · now",
  "Voice · soon",
  "Local AI · soon",
  "Automation · soon",
];

/** Shown in the conversation area when the active chat has no messages. */
export function WelcomeMessage() {
  return (
    <div className="flex h-full flex-col items-center justify-center px-8 text-center">
      <Orb size={72} />
      <h1 className="mt-5 text-2xl font-bold text-ink">Welcome to TIA</h1>
      <p className="mt-3 max-w-md text-sm leading-relaxed text-muted">
        Your local-first desktop assistant. I'm being built to understand
        English and Roman Urdu — text chat works today, and voice, a local AI
        brain and automation arrive phase by phase.
      </p>
      <div className="mt-5 flex flex-wrap justify-center gap-2">
        {CHIPS.map((chip) => (
          <span
            key={chip}
            className="rounded-full border border-hairline bg-raised/60 px-3 py-1 text-xs text-muted"
          >
            {chip}
          </span>
        ))}
      </div>
      <p className="mt-6 text-xs text-faint">
        Everything runs on your computer. No cloud. No telemetry.
      </p>
    </div>
  );
}
