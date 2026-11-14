import { useEffect } from "react";
import { X } from "lucide-react";

interface SettingsModalProps {
  onClose: () => void;
}

/** Static, honest settings summary — real settings arrive in later phases. */
const ROWS: Array<{ label: string; value: string }> = [
  { label: "Appearance", value: "Dark — the only theme for now" },
  { label: "AI backend", value: "Not connected — arrives in a later phase" },
  { label: "Microphone", value: "Coming soon" },
  { label: "Data", value: "Conversations are stored only in this window" },
];

export function SettingsModal({ onClose }: SettingsModalProps) {
  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        onClose();
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
      onClick={onClose}
      role="presentation"
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Settings"
        className="w-[420px] max-w-[calc(100vw-2rem)] rounded-2xl border border-hairline bg-surface p-5 shadow-2xl"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-center justify-between">
          <h2 className="text-base font-bold text-ink">Settings</h2>
          <button
            onClick={onClose}
            aria-label="Close settings"
            className="rounded-lg p-1.5 text-muted transition-colors hover:bg-raised hover:text-ink"
          >
            <X size={16} />
          </button>
        </div>
        <dl className="mt-4 space-y-3">
          {ROWS.map((row) => (
            <div
              key={row.label}
              className="flex items-center justify-between gap-4 rounded-lg bg-abyss/60 px-3 py-2.5"
            >
              <dt className="text-xs font-semibold text-muted">{row.label}</dt>
              <dd className="text-right text-xs text-faint">{row.value}</dd>
            </div>
          ))}
        </dl>
        <p className="mt-4 text-[11px] text-faint">
          More settings arrive with each phase of development.
        </p>
      </div>
    </div>
  );
}
