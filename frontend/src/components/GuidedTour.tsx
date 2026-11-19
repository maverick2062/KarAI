import { useCallback, useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { TOUR_STEPS } from "../tour/tourSteps";

interface TargetRect {
  top: number;
  left: number;
  width: number;
  height: number;
}

interface TooltipPosition {
  top: number;
  left: number;
}

export function GuidedTour() {
  const location = useLocation();
  const navigate = useNavigate();
  const { user, registrationTutorialPending, consumeRegistrationTutorial } = useAuth();
  const [isOpen, setIsOpen] = useState(false);
  const [currentStepIndex, setCurrentStepIndex] = useState(0);
  const [targetRect, setTargetRect] = useState<TargetRect | null>(null);
  const [targetUnavailable, setTargetUnavailable] = useState(false);
  const [tooltipPosition, setTooltipPosition] = useState<TooltipPosition>({ top: 16, left: 16 });
  const tooltipRef = useRef<HTMLDivElement>(null);

  const step = TOUR_STEPS[currentStepIndex];

  const closeTour = useCallback(() => {
    setIsOpen(false);
  }, []);

  const startTour = useCallback(() => {
    setCurrentStepIndex(0);
    setIsOpen(true);
    if (location.pathname !== "/dashboard") {
      navigate("/dashboard");
    }
  }, [location.pathname, navigate]);

  useEffect(() => {
    if (!registrationTutorialPending || !user) return;
    if (location.pathname !== "/dashboard") {
      navigate("/dashboard");
      return;
    }
    consumeRegistrationTutorial();
    startTour();
  }, [
    consumeRegistrationTutorial,
    location.pathname,
    navigate,
    registrationTutorialPending,
    startTour,
    user,
  ]);

  useEffect(() => {
    window.addEventListener("start-karai-tour", startTour);
    return () => window.removeEventListener("start-karai-tour", startTour);
  }, [startTour]);

  useEffect(() => {
    if (location.pathname === "/login" || location.pathname === "/register") {
      setIsOpen(false);
    }
  }, [location.pathname]);

  const updatePosition = useCallback(() => {
    if (!isOpen || !step || location.pathname !== step.route) return;

    const target = document.querySelector<HTMLElement>(step.target);
    if (!target) {
      setTargetRect(null);
      setTargetUnavailable(true);
      return;
    }

    setTargetUnavailable(false);
    const rect = target.getBoundingClientRect();
    setTargetRect({
      top: rect.top - 6,
      left: rect.left - 6,
      width: rect.width + 12,
      height: rect.height + 12,
    });

    const tooltip = tooltipRef.current;
    const tooltipWidth = tooltip?.offsetWidth ?? 340;
    const tooltipHeight = tooltip?.offsetHeight ?? 220;
    const margin = 16;
    const centerLeft = rect.left + rect.width / 2 - tooltipWidth / 2;
    const left = Math.max(margin, Math.min(centerLeft, window.innerWidth - tooltipWidth - margin));
    const useTop = step.placement === "top"
      ? rect.top >= tooltipHeight + margin
      : rect.bottom + tooltipHeight + margin > window.innerHeight && rect.top >= tooltipHeight + margin;
    const top = useTop
      ? Math.max(margin, rect.top - tooltipHeight - margin)
      : Math.min(rect.bottom + margin, window.innerHeight - tooltipHeight - margin);

    setTooltipPosition({ top, left });
  }, [isOpen, location.pathname, step]);

  useEffect(() => {
    if (!isOpen || !step) return;
    if (location.pathname !== step.route) {
      navigate(step.route);
      return;
    }

    let attempts = 0;
    const interval = window.setInterval(() => {
      attempts += 1;
      const target = document.querySelector<HTMLElement>(step.target);
      if (target) {
        window.clearInterval(interval);
        target.scrollIntoView({ behavior: "smooth", block: "center" });
        window.requestAnimationFrame(updatePosition);
      } else if (attempts >= 30) {
        window.clearInterval(interval);
        updatePosition();
      }
    }, 100);

    return () => window.clearInterval(interval);
  }, [currentStepIndex, isOpen, location.pathname, navigate, step, updatePosition]);

  useEffect(() => {
    if (!isOpen) return;
    window.addEventListener("resize", updatePosition);
    window.addEventListener("scroll", updatePosition, true);
    return () => {
      window.removeEventListener("resize", updatePosition);
      window.removeEventListener("scroll", updatePosition, true);
    };
  }, [isOpen, updatePosition]);

  useEffect(() => {
    if (!isOpen) return;
    tooltipRef.current?.focus();

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        closeTour();
        return;
      }
      if (event.key !== "Tab" || !tooltipRef.current) return;

      const controls = tooltipRef.current.querySelectorAll<HTMLButtonElement>("button:not(:disabled)");
      const first = controls.item(0);
      const last = controls.item(controls.length - 1);
      if (!first || !last) return;
      if (event.shiftKey && (document.activeElement === first || document.activeElement === tooltipRef.current)) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [closeTour, currentStepIndex, isOpen]);

  function moveToStep(nextIndex: number) {
    setCurrentStepIndex(nextIndex);
    const nextStep = TOUR_STEPS[nextIndex];
    if (nextStep.route !== location.pathname) navigate(nextStep.route);
  }

  if (!isOpen || !step) return null;

  return (
    <div className="tour-portal">
      <div className="tour-backdrop" onClick={closeTour} />
      {targetRect && (
        <div
          className="tour-spotlight"
          style={{
            top: targetRect.top,
            left: targetRect.left,
            width: targetRect.width,
            height: targetRect.height,
          }}
        />
      )}
      <section
        ref={tooltipRef}
        className="tour-tooltip"
        style={{ top: tooltipPosition.top, left: tooltipPosition.left }}
        role="dialog"
        aria-modal="true"
        aria-labelledby="karai-tour-title"
        aria-describedby="karai-tour-content"
        tabIndex={-1}
      >
        <div className="tour-tooltip__header">
          <span className="tour-tooltip__badge">
            Step {currentStepIndex + 1} of {TOUR_STEPS.length}
          </span>
          <button type="button" className="tour-tooltip__close" onClick={closeTour} aria-label="Exit tutorial">
            ×
          </button>
        </div>
        <h2 id="karai-tour-title" className="tour-tooltip__title">{step.title}</h2>
        <p id="karai-tour-content" className="tour-tooltip__content">{step.content}</p>
        {targetUnavailable && (
          <p className="tour-tooltip__hint">
            This section is not currently visible. You can continue the tutorial.
          </p>
        )}
        <div className="tour-tooltip__footer">
          <button type="button" className="button button--ghost tour-tooltip__skip" onClick={closeTour}>
            Skip tutorial
          </button>
          <div className="tour-tooltip__nav-buttons">
            {currentStepIndex > 0 && (
              <button type="button" className="button button--secondary" onClick={() => moveToStep(currentStepIndex - 1)}>
                Back
              </button>
            )}
            {currentStepIndex < TOUR_STEPS.length - 1 ? (
              <button type="button" className="button button--primary" onClick={() => moveToStep(currentStepIndex + 1)}>
                Next
              </button>
            ) : (
              <button type="button" className="button button--primary" onClick={closeTour}>
                Finish
              </button>
            )}
          </div>
        </div>
      </section>
    </div>
  );
}
