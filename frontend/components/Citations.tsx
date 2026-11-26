"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { apiRequest, fetchDocumentBlob } from "@/lib/api";
import type { Citation, DocumentList, DocumentSummary } from "@/lib/types";

import { Badge, Button, Modal, Spinner } from "./ui";

export function CitationChips({ citations }: { citations: Citation[] }) {
  const [documents, setDocuments] = useState<DocumentSummary[]>([]);
  const [documentsError, setDocumentsError] = useState(false);
  const [active, setActive] = useState<Citation | null>(null);

  useEffect(() => {
    let cancelled = false;
    apiRequest<DocumentList>("/documents")
      .then((data) => {
        if (!cancelled) {
          setDocuments(data.items);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setDocumentsError(true);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const byKey = useMemo(() => {
    const map = new Map<string, DocumentSummary>();
    documents.forEach((item) => {
      if (item.source_key) {
        map.set(item.source_key, item);
      }
    });
    return map;
  }, [documents]);

  if (citations.length === 0) {
    return null;
  }

  const activeDocument = active?.document ? byKey.get(active.document) ?? null : null;

  return (
    <div>
      <p className="text-xs font-semibold uppercase tracking-wide text-muted">
        Nguồn trích dẫn
      </p>
      <ul className="mt-2 flex flex-wrap gap-2">
        {citations.map((citation, index) => {
          const title =
            citation.document_title ?? citation.document ?? citation.source ?? "Tài liệu";
          return (
            <li key={`${citation.document ?? citation.source}-${citation.page ?? 0}-${index}`}>
              <button
                type="button"
                onClick={() => setActive(citation)}
                className="group inline-flex max-w-full items-center gap-2 rounded-full border border-brand-200 bg-white py-1.5 pl-3 pr-2 text-left text-xs font-medium text-brand-800 transition-colors hover:border-brand-500 hover:bg-brand-50"
                title="Mở tài liệu gốc tại trang trích dẫn"
              >
                <svg
                  viewBox="0 0 20 20"
                  fill="none"
                  aria-hidden="true"
                  className="size-4 shrink-0 text-brand-500"
                >
                  <path
                    d="M6 2.75h5.5L16 7.25v10H6z"
                    stroke="currentColor"
                    strokeWidth="1.4"
                    strokeLinejoin="round"
                  />
                  <path d="M11.25 3v4.5H16" stroke="currentColor" strokeWidth="1.4" />
                </svg>
                <span className="max-w-[16rem] truncate">{title}</span>
                {citation.page ? (
                  <span className="shrink-0 rounded-full bg-accent-soft px-2 py-0.5 text-[11px] font-semibold text-[#8a5a0f]">
                    Trang {citation.page}
                  </span>
                ) : null}
              </button>
            </li>
          );
        })}
      </ul>
      {documentsError ? (
        <p className="mt-2 text-xs text-muted">
          Chưa tải được danh mục tài liệu; chip vẫn hiển thị nội dung trích dẫn.
        </p>
      ) : null}
      {active ? (
        <DocumentViewer
          key={viewerKey(active, activeDocument)}
          citation={active}
          document={activeDocument}
          onClose={() => setActive(null)}
        />
      ) : null}
    </div>
  );
}

type ViewerState = "loading" | "ready" | "error";

function viewerKey(citation: Citation, doc: DocumentSummary | null): string {
  return `${citation.document ?? citation.source}-${citation.page ?? 0}-${doc?.id ?? "missing"}`;
}

function DocumentViewer({
  citation,
  document: doc,
  onClose,
}: {
  citation: Citation;
  document: DocumentSummary | null;
  onClose: () => void;
}) {
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const [state, setState] = useState<ViewerState>(doc ? "loading" : "error");
  const [error, setError] = useState<string | null>(
    doc ? null : "Chưa xác định được tệp PDF gốc cho trích dẫn này.",
  );
  const urlRef = useRef<string | null>(null);
  const seqRef = useRef(0);
  const documentId = doc?.id ?? null;

  const loadDocument = useCallback((id: string) => {
    const seq = ++seqRef.current;
    if (urlRef.current) {
      URL.revokeObjectURL(urlRef.current);
      urlRef.current = null;
    }
    fetchDocumentBlob(id)
      .then((blob) => {
        if (seq !== seqRef.current) {
          return;
        }
        const nextUrl = URL.createObjectURL(blob);
        urlRef.current = nextUrl;
        setBlobUrl(nextUrl);
        setState("ready");
      })
      .catch((caught: unknown) => {
        if (seq !== seqRef.current) {
          return;
        }
        setState("error");
        setError(caught instanceof Error ? caught.message : "Không tải được tài liệu.");
      });
  }, []);

  useEffect(() => {
    if (documentId) {
      loadDocument(documentId);
    }
    return () => {
      seqRef.current += 1;
    };
  }, [documentId, loadDocument]);

  useEffect(
    () => () => {
      if (urlRef.current) {
        URL.revokeObjectURL(urlRef.current);
      }
    },
    [],
  );

  const retry = () => {
    if (!documentId) {
      return;
    }
    setState("loading");
    setError(null);
    setBlobUrl(null);
    loadDocument(documentId);
  };

  const page = citation.page ?? 1;
  const title = citation.document_title ?? doc?.title ?? citation.source ?? "Tài liệu gốc";

  return (
    <Modal open title={title} onClose={onClose} wide>
      <div className="flex flex-col gap-4">
          <div className="rounded-lg border border-brand-100 bg-brand-50/60 px-4 py-3">
            <div className="flex flex-wrap items-center gap-2">
              {citation.section ? <Badge tone="brand">{citation.section}</Badge> : null}
              {citation.page ? <Badge tone="accent">Trang {citation.page}</Badge> : null}
            </div>
            {citation.quote?.trim() ? (
              <blockquote className="mt-2 border-l-2 border-brand-300 pl-3 text-sm leading-relaxed text-brand-900">
                {citation.quote}
              </blockquote>
            ) : (
              <p className="mt-2 text-sm text-muted">
                Câu trả lời có nhắc tới nguồn này nhưng chưa kèm đoạn trích nguyên văn.
              </p>
            )}
          </div>

          {state === "loading" ? (
            <div className="flex justify-center py-8">
              <Spinner label="Đang tải tài liệu PDF..." />
            </div>
          ) : null}

          {state === "error" ? (
            <div className="flex flex-col items-start gap-3 rounded-lg border border-[#f0cccc] bg-danger-soft px-4 py-3 text-sm text-danger">
              <span>{error}</span>
              {documentId ? (
                <Button variant="secondary" size="sm" onClick={retry}>
                  Thử lại
                </Button>
              ) : null}
            </div>
          ) : null}

          {state === "ready" && blobUrl ? (
            <div className="flex flex-col gap-2">
              <iframe
                src={`${blobUrl}#page=${page}`}
                title={`Tài liệu ${title} – trang ${page}`}
                className="h-[62vh] w-full rounded-lg border border-line bg-surface"
              />
              <div className="flex flex-wrap items-center gap-3 text-sm">
                <a
                  className="font-medium text-brand-700 underline underline-offset-2"
                  href={blobUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  Mở tài liệu trong tab mới
                </a>
                <a
                  className="font-medium text-brand-700 underline underline-offset-2"
                  href={blobUrl}
                  download={`${title}.pdf`}
                >
                  Tải PDF
                </a>
                <span className="text-xs text-muted">
                  Nếu trình duyệt không hiển thị PDF, hãy mở trong tab mới.
                </span>
              </div>
            </div>
          ) : null}
      </div>
    </Modal>
  );
}
