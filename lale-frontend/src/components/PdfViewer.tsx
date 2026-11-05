import { useState, useEffect, useRef } from 'react';
import * as pdfjsLib from '@okkkde/pdfjs-dist';
import pdfjsWorker from '@okkkde/pdfjs-dist/legacy/build/pdf.worker.js?url';

pdfjsLib.GlobalWorkerOptions.workerSrc = pdfjsWorker;

interface PdfViewerProps {
  fileUrl: string;
  onSelectText: (text: string) => void;
  containerWidth: number;
  enableBoxSelect?: boolean;
}

export default function PdfViewer({ fileUrl, onSelectText, containerWidth, enableBoxSelect }: PdfViewerProps) {
  const [pdfDoc, setPdfDoc] = useState<any>(null);
  const [numPages, setNumPages] = useState<number>(0);

  useEffect(() => {
    const loadPdf = async () => {
      try {
        const loadingTask = pdfjsLib.getDocument(fileUrl);
        const pdf = await loadingTask.promise;
        setPdfDoc(pdf);
        setNumPages(pdf.numPages);
      } catch (error) {
        console.error("PDF 加载失败:", error);
      }
    };
    loadPdf();
  }, [fileUrl]);

  return (
    <div className="flex flex-col items-center w-full h-full bg-[#f3f4f6] overflow-y-auto py-2" style={{ userSelect: enableBoxSelect ? 'none' : 'text' }}>
      {pdfDoc && Array.from({ length: numPages }, (_, index) => (
        <PdfPage
          key={`${fileUrl}-page-${index + 1}`}
          pdfDoc={pdfDoc}
          pageNumber={index + 1}
          containerWidth={containerWidth}
          onSelectText={onSelectText}
          enableBoxSelect={enableBoxSelect}
        />
      ))}
    </div>
  );
}

function PdfPage({ pdfDoc, pageNumber, containerWidth, onSelectText, enableBoxSelect }: any) {
  const pageRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const textLayerRef = useRef<HTMLDivElement>(null);

  const [isDragging, setIsDragging] = useState(false);
  const [startPos, setStartPos] = useState({ x: 0, y: 0 });
  const [currentPos, setCurrentPos] = useState({ x: 0, y: 0 });

  useEffect(() => {
    let isCancelled = false;
    let renderTask: any = null; // 👈 用于存储当前的渲染任务

    const renderPage = async () => {
      if (!containerWidth || isCancelled) return;

      const page = await pdfDoc.getPage(pageNumber);
      const rotate = page.rotate || 0;
      const originalViewport = page.getViewport({ scale: 1, rotation: rotate });

      // 👇 核心修改：直接使用外部传来的几乎满屏宽度
      const scale = containerWidth / originalViewport.width;
      const viewport = page.getViewport({ scale, rotation: rotate });

      // 1. 渲染 Canvas
      const canvas = canvasRef.current;
      if (canvas) {
        const context = canvas.getContext('2d');
        const outputScale = window.devicePixelRatio || 1;
        canvas.width = Math.floor(viewport.width * outputScale);
        canvas.height = Math.floor(viewport.height * outputScale);
        canvas.style.width = `${Math.floor(viewport.width)}px`;
        canvas.style.height = `${Math.floor(viewport.height)}px`;

        const transform = outputScale !== 1 ? [outputScale, 0, 0, outputScale, 0, 0] : null;

        // 👇 核心修复：存储渲染任务，以便随时取消
        renderTask = page.render({ canvasContext: context, viewport, transform });

        try {
          await renderTask.promise;
        } catch (error: any) {
          // 如果是因为取消而报错，直接忽略，不抛给控制台
          if (error.name === 'RenderingCancelledException') {
            return;
          }
          console.error("PDF 渲染异常:", error);
          return;
        }
      }

      // 2. 渲染文本层
      if (isCancelled) return;
      const textContent = await page.getTextContent();
      const textLayer = textLayerRef.current;

      if (textLayer) {
        textLayer.innerHTML = '';
        textLayer.style.width = `${Math.floor(viewport.width)}px`;
        textLayer.style.height = `${Math.floor(viewport.height)}px`;

        textContent.items.forEach((item: any) => {
          if (!item.str || item.str.trim() === '') return;
          const tx = pdfjsLib.Util.transform(viewport.transform, item.transform);

          const span = document.createElement('span');
          span.textContent = item.str;
          span.style.position = 'absolute';
          span.style.color = 'transparent';
          span.style.whiteSpace = 'pre';
          span.style.cursor = enableBoxSelect ? 'crosshair' : 'text';
          span.style.userSelect = 'text';
          span.style.pointerEvents = 'auto';

          span.style.left = `${tx[4]}px`;
          span.style.top = `${tx[5] - item.height}px`;
          span.style.fontSize = `${item.height}px`;
          span.style.fontFamily = item.fontName;
          span.style.transform = `scaleX(${tx[0] / item.height})`;
          span.style.transformOrigin = '0% 0%';

          textLayer.appendChild(span);
        });
      }
    };

    renderPage();
    return () => { isCancelled = true;
    if (renderTask) {
        renderTask.cancel();
      }
    };
  }, [pdfDoc, pageNumber, containerWidth, enableBoxSelect]);

  // --- 框选逻辑 ---
  const handleMouseDown = (e: React.MouseEvent) => {
    if (!enableBoxSelect) return;
    e.preventDefault();
    const rect = pageRef.current?.getBoundingClientRect();
    if (!rect) return;
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    setIsDragging(true);
    setStartPos({ x, y });
    setCurrentPos({ x, y });
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!isDragging || !enableBoxSelect) return;
    const rect = pageRef.current?.getBoundingClientRect();
    if (!rect) return;
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    const boundedX = Math.max(0, Math.min(x, rect.width));
    const boundedY = Math.max(0, Math.min(y, rect.height));
    setCurrentPos({ x: boundedX, y: boundedY });
  };

  const handleMouseUp = () => {
    if (!isDragging || !enableBoxSelect) return;
    setIsDragging(false);

    const boxLeft = Math.min(startPos.x, currentPos.x);
    const boxRight = Math.max(startPos.x, currentPos.x);
    const boxTop = Math.min(startPos.y, currentPos.y);
    const boxBottom = Math.max(startPos.y, currentPos.y);
    if (boxRight - boxLeft < 10 || boxBottom - boxTop < 10) return;

    const textLayer = textLayerRef.current;
    const rect = pageRef.current?.getBoundingClientRect();
    if (!textLayer || !rect) return;

    const spans = textLayer.querySelectorAll('span');
    const intersectNodes: { text: string, top: number, left: number }[] = [];

    spans.forEach((span: any) => {
      const spanRect = span.getBoundingClientRect();
      const sLeft = spanRect.left - rect.left;
      const sRight = spanRect.right - rect.left;
      const sTop = spanRect.top - rect.top;
      const sBottom = spanRect.bottom - rect.top;

      if (!(sLeft > boxRight || sRight < boxLeft || sTop > boxBottom || sBottom < boxTop)) {
        if (span.textContent) {
          intersectNodes.push({ text: span.textContent, top: sTop, left: sLeft });
        }
      }
    });

    if (intersectNodes.length > 0) {
      intersectNodes.sort((a, b) => {
        if (Math.abs(a.top - b.top) < 5) return a.left - b.left;
        return a.top - b.top;
      });

      let extractedText = '';
      for (let i = 0; i < intersectNodes.length; i++) {
        extractedText += intersectNodes[i].text;
        if (i < intersectNodes.length - 1) {
          const currentText = intersectNodes[i].text;
          const nextText = intersectNodes[i + 1].text;
          if (!/[.,!?;:'"”)\]]$/.test(currentText) && !/^[.,!?;:'"”(\[]/.test(nextText)) {
            extractedText += ' ';
          }
        }
      }
      // 能清洗：去除首尾的无用符号，合并多余空格
      let finalText = extractedText.replace(/\s+/g, ' ').trim();
      onSelectText(finalText);
    }
  };

  const boxStyle = {
    left: Math.min(startPos.x, currentPos.x),
    top: Math.min(startPos.y, currentPos.y),
    width: Math.abs(currentPos.x - startPos.x),
    height: Math.abs(currentPos.y - startPos.y),
  };

  return (
    <div
      ref={pageRef}
      className="relative w-full flex justify-center mb-2 select-none" // 👈 缩减了 mb-8 为 mb-2
      style={{ cursor: enableBoxSelect ? 'crosshair' : 'default' }}
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onMouseLeave={() => setIsDragging(false)}
    >
      <div className="relative bg-white shadow-lg overflow-hidden" style={{ display: 'inline-block' }}>
        <canvas ref={canvasRef} className="block" />
        <div
          ref={textLayerRef}
          className="pdf-text-layer-container"
          style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, zIndex: 20, overflow: 'hidden' }}
        />
        {isDragging && (
          <div
            className="absolute z-30 pointer-events-none"
            style={{
              ...boxStyle,
              border: '1px dashed rgba(59, 130, 246, 0.8)', // 蓝色虚线边框
              backgroundColor: 'rgba(59, 130, 246, 0.1)',   // 10% 透明度的浅蓝色
              borderRadius: '2px' // 轻微圆角更柔和
            }}
          />
        )}
      </div>
    </div>
  );
}