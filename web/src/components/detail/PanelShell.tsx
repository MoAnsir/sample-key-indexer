import { useEffect, useState, useCallback, useRef } from "react";
import type { ReactNode } from "react";

const ANIM_DURATION = 220;

interface PanelShellProps {
  open: boolean;
  onClose: () => void;
  children: ReactNode;
}

export default function PanelShell({ open, onClose, children }: PanelShellProps) {
  const [visible, setVisible] = useState(false);
  const [closing, setClosing] = useState(false);
  const closingRef = useRef(false);
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (open) {
      setVisible(true);
      setClosing(false);
      closingRef.current = false;
    }
  }, [open]);

  useEffect(() => {
    if (!visible) return;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = "";
    };
  }, [visible]);

  const handleClose = useCallback(() => {
    if (closingRef.current) return;
    closingRef.current = true;
    setClosing(true);
    setTimeout(() => {
      onClose();
      setVisible(false);
      setClosing(false);
      closingRef.current = false;
    }, ANIM_DURATION);
  }, [onClose]);

  useEffect(() => {
    if (!visible) return;
    panelRef.current?.focus();

    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        handleClose();
        return;
      }
      if (e.key === "Tab" && panelRef.current) {
        const focusable = panelRef.current.querySelectorAll<HTMLElement>(
          'button, a[href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
        );
        if (focusable.length === 0) return;
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (e.shiftKey) {
          if (document.activeElement === first) {
            e.preventDefault();
            last.focus();
          }
        } else {
          if (document.activeElement === last) {
            e.preventDefault();
            first.focus();
          }
        }
      }
    };

    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [visible, handleClose]);

  if (!visible) return null;

  return (
    <div className={`fixed inset-0 z-40 flex ${closing ? "animate-fade-out" : "animate-fade-in"}`}>
      <div
        className="absolute inset-0"
        style={{ background: "rgba(20,18,14,.32)" }}
        onClick={handleClose}
      />
      <div
        ref={panelRef}
        tabIndex={-1}
        className={`relative ml-auto w-full max-w-3xl bg-bg shadow-panel overflow-y-auto outline-none ${closing ? "animate-slide-out" : "animate-slide-in"}`}
      >
        {children}
      </div>
    </div>
  );
}
