import "./CancelOrderDialog.css";
import { useEffect, useRef } from "react";
import { createPortal } from "react-dom";

function CancelOrderDialog({
  isOpen,
  onKeepOrdering,
  onConfirmCancel,
  isCanceling = false,
}) {
  const dialogRef = useRef(null);
  const keepBtnRef = useRef(null);
  const triggerRef = useRef(null);

  useEffect(() => {
    if (!isOpen) return;

    // Save active element to restore focus when dialog closes
    triggerRef.current = document.activeElement;

    // Prevent background scrolling while modal is open
    const originalOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    // Focus the primary "Keep Ordering" button for keyboard accessibility
    const timer = setTimeout(() => {
      keepBtnRef.current?.focus();
    }, 50);

    const handleKeyDown = (e) => {
      if (e.key === "Escape") {
        e.preventDefault();
        if (!isCanceling) {
          onKeepOrdering();
        }
        return;
      }

      if (e.key === "Tab") {
        if (!dialogRef.current) return;
        const focusable = dialogRef.current.querySelectorAll(
          'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
        );
        if (!focusable || focusable.length === 0) return;

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

    window.addEventListener("keydown", handleKeyDown);

    return () => {
      clearTimeout(timer);
      window.removeEventListener("keydown", handleKeyDown);
      document.body.style.overflow = originalOverflow;

      // Restore focus to trigger element when dialog closes
      if (triggerRef.current && typeof triggerRef.current.focus === "function") {
        triggerRef.current.focus();
      }
    };
  }, [isOpen, isCanceling, onKeepOrdering]);

  if (!isOpen) return null;

  const handleOverlayClick = (e) => {
    // Only close if clicking directly on the backdrop overlay, not inside the modal
    if (e.target === e.currentTarget && !isCanceling) {
      onKeepOrdering();
    }
  };

  const dialogContent = (
    <div
      className="cancel-dialog-overlay"
      onClick={handleOverlayClick}
      role="dialog"
      aria-modal="true"
      aria-labelledby="cancel-dialog-title"
      aria-describedby="cancel-dialog-desc"
    >
      <div
        ref={dialogRef}
        className="cancel-dialog"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Functional accessible cross button */}
        <button
          type="button"
          className="cancel-dialog-icon-badge"
          aria-label="Close dialog"
          onClick={onKeepOrdering}
          disabled={isCanceling}
        >
          <span aria-hidden="true">✕</span>
        </button>

        <h1 id="cancel-dialog-title" className="cancel-dialog-title">
          Cancel this order?
        </h1>

        <p id="cancel-dialog-desc" className="cancel-dialog-message">
          Your current cart and meal selections will be cleared. You'll return to the welcome page.
        </p>

        <div className="cancel-dialog-actions">
          {/* Primary Action: Keep Ordering */}
          <button
            ref={keepBtnRef}
            type="button"
            className="cancel-dialog-btn-keep"
            onClick={onKeepOrdering}
            disabled={isCanceling}
          >
            Keep Ordering
          </button>

          {/* Secondary / Danger Action: Cancel Order */}
          <button
            type="button"
            className="cancel-dialog-btn-cancel"
            onClick={onConfirmCancel}
            disabled={isCanceling}
          >
            {isCanceling ? "Canceling..." : "Cancel Order"}
          </button>
        </div>
      </div>
    </div>
  );

  const mountNode =
    (typeof document !== "undefined" && document.getElementById("root")) ||
    (typeof document !== "undefined" && document.body) ||
    null;

  return mountNode ? createPortal(dialogContent, mountNode) : dialogContent;
}

export default CancelOrderDialog;

