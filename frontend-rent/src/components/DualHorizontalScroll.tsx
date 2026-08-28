import { useLayoutEffect, useRef, type ReactNode, type UIEvent } from "react";

/** 넓은 표의 가로 스크롤을 위·아래에 두고 같이 움직이게 한다. */
export default function DualHorizontalScroll({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  const topRef = useRef<HTMLDivElement>(null);
  const bodyRef = useRef<HTMLDivElement>(null);
  const contentRef = useRef<HTMLDivElement>(null);
  const spacerRef = useRef<HTMLDivElement>(null);
  const lock = useRef(false);

  useLayoutEffect(() => {
    const content = contentRef.current;
    const spacer = spacerRef.current;
    if (!content || !spacer) return;
    const syncWidth = () => {
      spacer.style.width = `${content.scrollWidth}px`;
    };
    syncWidth();
    const ro = new ResizeObserver(syncWidth);
    ro.observe(content);
    const child = content.firstElementChild;
    if (child) ro.observe(child);
    return () => ro.disconnect();
  }, [children]);

  function mirror(from: HTMLDivElement | null, to: HTMLDivElement | null) {
    if (!from || !to || lock.current) return;
    if (from.scrollLeft === to.scrollLeft) return;
    lock.current = true;
    to.scrollLeft = from.scrollLeft;
    lock.current = false;
  }

  return (
    <div className={className}>
      <div
        ref={topRef}
        className="dual-h-scroll-top overflow-x-scroll overflow-y-hidden"
        onScroll={(e: UIEvent<HTMLDivElement>) => mirror(e.currentTarget, bodyRef.current)}
        aria-hidden
      >
        <div ref={spacerRef} className="h-px" />
      </div>
      <div
        ref={bodyRef}
        className="overflow-x-auto"
        onScroll={(e: UIEvent<HTMLDivElement>) => mirror(e.currentTarget, topRef.current)}
      >
        <div ref={contentRef}>{children}</div>
      </div>
    </div>
  );
}
