import { useEffect, useRef, type TouchEvent as ReactTouchEvent } from 'react';

// Native HTML drag events are unreliable on touch screens. Share the same drop
// destinations as mouse dragging, while leaving ordinary swipes free to scroll.
export function useItineraryTouchDrag() {
  const active = useRef<AbortController | null>(null);
  useEffect(() => () => active.current?.abort(), []);

  return (event: ReactTouchEvent<HTMLElement>, drop: (day: string, before?: string) => void) => {
    active.current?.abort();
    const row: HTMLElement = event.currentTarget;
    const source = event.target;
    if (
      !row.draggable ||
      event.touches.length !== 1 ||
      !(source instanceof Element) ||
      source.closest('button, a, input, select, textarea')
    )
      return;

    const start = event.touches[0];
    const startedAt = performance.now();
    const grip = source.closest('.wp-grip');
    const planner = row.closest('.wp-planner');
    const controller = new AbortController();
    const { signal } = controller;
    active.current = controller;
    let moved = false;
    let frame = 0;
    let x = start.clientX;
    let y = start.clientY;
    let highlighted: HTMLElement | null = null;

    function targetAtPoint() {
      const target = document.elementFromPoint(x, y)?.closest<HTMLElement>('[data-drop-day]');
      return target && planner?.contains(target) ? target : null;
    }

    function preview() {
      frame = 0;
      if (!row.isConnected || !row.draggable) return controller.abort();
      const target = targetAtPoint();
      if (highlighted !== target) {
        highlighted?.removeAttribute('data-touch-over');
        target?.setAttribute('data-touch-over', '');
        highlighted = target;
      }
      // The destination can lie past the current viewport or in the scrolling day strip.
      const tabs = target?.closest<HTMLElement>('.wp-day-tabs');
      const previousLeft = tabs?.scrollLeft;
      const previousTop = window.scrollY;
      if (tabs) {
        const bounds = tabs.getBoundingClientRect();
        if (x < bounds.left + 24) tabs.scrollLeft -= 8;
        else if (x > bounds.right - 24) tabs.scrollLeft += 8;
      }
      if (y < 48) window.scrollBy(0, -8);
      else if (y > window.innerHeight - 48) window.scrollBy(0, 8);
      if (previousLeft !== tabs?.scrollLeft || previousTop !== window.scrollY) {
        frame = requestAnimationFrame(preview);
      }
    }

    signal.addEventListener('abort', () => {
      cancelAnimationFrame(frame);
      highlighted?.removeAttribute('data-touch-over');
      row.removeAttribute('data-touch-dragging');
      active.current = null;
    });
    window.addEventListener('blur', () => controller.abort(), { signal });
    row.addEventListener('contextmenu', (e) => e.preventDefault(), { signal });
    row.addEventListener('dragstart', (e) => e.preventDefault(), { signal });
    document.addEventListener('touchcancel', () => controller.abort(), { signal });
    document.addEventListener(
      'touchstart',
      (e) => {
        if (e.touches.length > 1) controller.abort();
      },
      { passive: true, signal },
    );
    row.addEventListener(
      'touchmove',
      (e) => {
        if (e.touches.length !== 1 || !e.cancelable) return controller.abort();
        const finger = e.touches[0];
        x = finger.clientX;
        y = finger.clientY;
        if (!moved) {
          if (Math.hypot(x - start.clientX, y - start.clientY) < 6) return;
          if (!grip && performance.now() - startedAt < 350) return controller.abort();
          moved = true;
          row.setAttribute('data-touch-dragging', '');
        }
        e.preventDefault();
        if (!frame) frame = requestAnimationFrame(preview);
      },
      { passive: false, signal },
    );
    document.addEventListener(
      'touchend',
      (e) => {
        const finger = e.changedTouches[0];
        x = finger.clientX;
        y = finger.clientY;
        const target = moved ? targetAtPoint() : null;
        if (moved && e.cancelable) e.preventDefault();
        controller.abort();
        if (row.isConnected && row.draggable && target?.dataset.dropDay) {
          drop(target.dataset.dropDay, target.dataset.beforeItem);
        }
      },
      { passive: false, signal },
    );
  };
}
