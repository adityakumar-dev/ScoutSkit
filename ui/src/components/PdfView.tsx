import { useEffect, useRef, useState } from "react";
import type { PDFDocumentLoadingTask, PDFDocumentProxy } from "pdfjs-dist";

const ZOOMS = [0.6, 0.8, 1, 1.25, 1.5, 2];
const PAGE_WIDTH = 860; // css pixels at 100%
const LOOKAHEAD = "800px"; // pages this close to the screen are drawn

/** One page, drawn only when it is about to be seen (a syllabus can have hundreds). */
function Page({ doc, number, width, ratio }: { doc: PDFDocumentProxy; number: number; width: number; ratio: number }) {
  const box = useRef<HTMLDivElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const [near, setNear] = useState(false);

  useEffect(() => {
    const el = box.current;
    if (!el) return;
    const watcher = new IntersectionObserver(([entry]) => setNear(entry.isIntersecting), { rootMargin: LOOKAHEAD });
    watcher.observe(el);
    return () => watcher.disconnect();
  }, []);

  useEffect(() => {
    if (!near || !canvas.current) return;
    let task: { cancel: () => void; promise: Promise<unknown> } | null = null;
    let stale = false;
    doc.getPage(number).then((page) => {
      if (stale || !canvas.current) return;
      const base = page.getViewport({ scale: 1 });
      const viewport = page.getViewport({ scale: (width / base.width) * Math.min(window.devicePixelRatio || 1, 2) });
      const target = canvas.current;
      target.width = Math.floor(viewport.width);
      target.height = Math.floor(viewport.height);
      task = page.render({ canvas: target, viewport });
      task.promise.catch(() => undefined); // a cancelled render (scrolled away, zoomed) is not an error
    });
    return () => {
      stale = true;
      task?.cancel();
    };
  }, [near, doc, number, width]);

  return (
    <div ref={box} className="pdf-page" style={{ width, height: Math.round(width * ratio) }}>
      <canvas ref={canvas} style={{ width: "100%", height: "100%" }} />
      <span className="pdf-page-no">{number}</span>
    </div>
  );
}

/** A PDF drawn in the page itself, so it looks the same in every browser. */
export function PdfView({ url }: { url: string }) {
  const [doc, setDoc] = useState<PDFDocumentProxy | null>(null);
  const [ratio, setRatio] = useState(1.414);
  const [error, setError] = useState("");
  const [zoom, setZoom] = useState(2);

  useEffect(() => {
    let loading: PDFDocumentLoadingTask | null = null;
    let cancelled = false;
    (async () => {
      try {
        const pdfjs = await import("pdfjs-dist");
        const worker = (await import("pdfjs-dist/build/pdf.worker.min.mjs?url")).default;
        pdfjs.GlobalWorkerOptions.workerSrc = worker;
        loading = pdfjs.getDocument({ url });
        const opened = await loading.promise;
        if (cancelled) return;
        const first = await opened.getPage(1);
        const view = first.getViewport({ scale: 1 });
        setRatio(view.height / view.width);
        setDoc(opened);
      } catch (failure) {
        if (!cancelled) setError(failure instanceof Error ? failure.message : String(failure));
      }
    })();
    return () => {
      cancelled = true;
      void loading?.destroy(); // stops the download and the worker
    };
  }, [url]);

  if (error) return <p className="error viewer-pad">Could not show this PDF here: {error}. Use ↗ to open it in a new tab, or download it.</p>;
  if (!doc) return <p className="hint viewer-pad">Opening PDF…</p>;
  const width = Math.round(PAGE_WIDTH * ZOOMS[zoom]);
  return (
    <div className="pdf-view">
      <div className="pdf-bar">
        <span className="mono">{doc.numPages} page{doc.numPages > 1 ? "s" : ""}</span>
        <div className="pdf-zoom">
          <button className="ghost" disabled={zoom === 0} onClick={() => setZoom(zoom - 1)} aria-label="Zoom out">−</button>
          <span className="mono">{Math.round(ZOOMS[zoom] * 100)}%</span>
          <button className="ghost" disabled={zoom === ZOOMS.length - 1} onClick={() => setZoom(zoom + 1)} aria-label="Zoom in">+</button>
        </div>
      </div>
      <div className="pdf-pages">
        {Array.from({ length: doc.numPages }, (_, i) => <Page key={`${i}-${width}`} doc={doc} number={i + 1} width={width} ratio={ratio} />)}
      </div>
    </div>
  );
}
