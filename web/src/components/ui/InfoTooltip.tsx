import { useState, useRef, useEffect, useCallback } from "react";
import { createPortal } from "react-dom";

interface InfoLine {
  text: string;
  color?: string;
  border?: string;
}

interface InfoTooltipProps {
  lines: (string | InfoLine)[];
}

export default function InfoTooltip({ lines }: InfoTooltipProps) {
  const [open, setOpen] = useState(false);
  const btnRef = useRef<HTMLButtonElement>(null);
  const tipRef = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState({ top: 0, left: 0 });

  const updatePos = useCallback(() => {
    if (!btnRef.current) return;
    const rect = btnRef.current.getBoundingClientRect();
    const tipWidth = 280;
    let left = rect.right + 6;
    if (left + tipWidth > window.innerWidth - 16) {
      left = rect.left - tipWidth - 6;
    }
    if (left < 8) left = 8;
    setPos({ top: rect.top, left });
  }, []);

  useEffect(() => {
    if (!open) return;
    updatePos();
    const handleClickOutside = (e: MouseEvent) => {
      if (
        btnRef.current?.contains(e.target as Node) ||
        tipRef.current?.contains(e.target as Node)
      )
        return;
      setOpen(false);
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [open, updatePos]);

  return (
    <span className="relative inline-block" style={{ textTransform: "none" }}>
      <button
        ref={btnRef}
        onClick={() => setOpen((o) => !o)}
        className="inline-flex items-center justify-center w-4 h-4 rounded-full border border-line text-faint text-[10px] font-bold hover:text-ink hover:border-accent transition-colors cursor-help"
        aria-label="Info"
      >
        ?
      </button>
      {open &&
        createPortal(
          <div
            ref={tipRef}
            className="fixed z-[100] w-[280px] bg-surface border border-line rounded-panel shadow-pop p-3 space-y-2"
            style={{ top: pos.top, left: pos.left, textTransform: "none", letterSpacing: "normal" }}
          >
            {lines.map((line, i) => {
              const item = typeof line === "string" ? { text: line } : line;
              return (
                <p key={i} className="text-xs text-muted font-normal flex items-start gap-1.5">
                  {item.color && (
                    <span
                      className="w-3 h-3 rounded-full shrink-0 mt-0.5"
                      style={{
                        background: item.color,
                        border: item.border ? `1.5px solid ${item.border}` : undefined,
                        boxSizing: "border-box",
                      }}
                    />
                  )}
                  <span>{item.text}</span>
                </p>
              );
            })}
          </div>,
          document.body,
        )}
    </span>
  );
}
