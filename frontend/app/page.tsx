"use client";

import { useCallback, useEffect, useState } from "react";
import styles from "./page.module.css";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type Status = "checking" | "connected" | "disconnected";

const STATUS_LABEL: Record<Status, string> = {
  checking: "Đang kiểm tra kết nối...",
  connected: "Đã kết nối backend",
  disconnected: "Không kết nối được backend",
};

export default function Home() {
  const [status, setStatus] = useState<Status>("checking");

  const fetchStatus = useCallback(() => {
    fetch(`${API_URL}/health`, { cache: "no-store" })
      .then(async (response) => {
        const data = (await response.json()) as { status?: string };
        setStatus(response.ok && data.status === "ok" ? "connected" : "disconnected");
      })
      .catch(() => {
        setStatus("disconnected");
      });
  }, []);

  useEffect(() => {
    fetchStatus();
  }, [fetchStatus]);

  const handleRetry = () => {
    setStatus("checking");
    fetchStatus();
  };

  return (
    <main className={styles.page}>
      <section className={styles.card}>
        <p className={styles.eyebrow}>Đồ án tốt nghiệp</p>
        <h1 className={styles.title}>Chatbot RAG luyện thi AWS SAA-C03</h1>
        <p className={styles.subtitle}>
          Hỗ trợ tự học và ôn luyện chứng chỉ AWS Certified Solutions Architect – Associate
          (SAA-C03) bằng hỏi đáp dựa trên tài liệu.
        </p>

        <div className={`${styles.status} ${styles[status]}`} role="status" aria-live="polite">
          <span className={styles.dot} aria-hidden="true" />
          <span>{STATUS_LABEL[status]}</span>
        </div>
        <p className={styles.hint}>Địa chỉ kiểm tra: {API_URL}/health</p>

        <button
          className={styles.button}
          type="button"
          onClick={handleRetry}
          disabled={status === "checking"}
        >
          Kiểm tra lại
        </button>

        <p className={styles.note}>
          Giai đoạn 0: khung ứng dụng đã sẵn sàng. Chức năng hỏi đáp RAG sẽ được bổ sung ở các
          giai đoạn tiếp theo.
        </p>
      </section>
    </main>
  );
}
