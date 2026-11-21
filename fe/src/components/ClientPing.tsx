"use client";

import { useState } from "react";
import styles from "./status.module.css";

// Client Component: trình duyệt gọi /api/health cùng origin, Next chuyển tiếp sang BE (rewrites).
export default function ClientPing() {
  const [result, setResult] = useState<string>("chưa gọi");

  async function ping() {
    setResult("đang gọi...");
    try {
      const response = await fetch("/api/health", { cache: "no-store" });
      setResult(`HTTP ${response.status} ${JSON.stringify(await response.json())}`);
    } catch (error) {
      setResult(`lỗi: ${error instanceof Error ? error.message : String(error)}`);
    }
  }

  return (
    <section className={styles.card}>
      <h2>Gọi BE từ trình duyệt</h2>
      <p className={styles.muted}>GET /api/health qua proxy của Next</p>
      <button type="button" onClick={ping}>
        Gọi thử
      </button>
      <pre>{result}</pre>
    </section>
  );
}
