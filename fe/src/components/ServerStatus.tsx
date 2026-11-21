import { type AgentHealthResponse, BE_URL, type ReadinessResponse, getFromBackend } from "@/lib/api";
import styles from "./status.module.css";

function Badge({ status }: { status: string }) {
  return <span className={status === "UP" ? styles.up : styles.down}>{status}</span>;
}

// Server Component: Next gọi thẳng BE (BE_URL) lúc render.
export default async function ServerStatus() {
  const [readiness, agent] = await Promise.all([
    getFromBackend<ReadinessResponse>("/api/health/readiness"),
    getFromBackend<AgentHealthResponse>("/api/agent/health"),
  ]);

  return (
    <section className={styles.card}>
      <h2>Trạng thái hệ thống</h2>
      <p className={styles.muted}>FE (server) gọi BE tại {BE_URL}</p>
      {readiness.ok ? (
        <ul>
          <li>
            Backend <Badge status={readiness.data.status} />
          </li>
          {Object.entries(readiness.data.components).map(([name, status]) => (
            <li key={name}>
              {name} <Badge status={status} />
            </li>
          ))}
        </ul>
      ) : (
        <p>
          Backend <Badge status="DOWN" /> {readiness.error}
        </p>
      )}
      {agent.ok ? (
        <p>
          Agent <Badge status={agent.data.status} />
          {agent.data.agent && (
            <span className={styles.muted}> v{agent.data.agent.version}, LLM: {agent.data.agent.llm_providers.join(", ") || "chưa cấu hình"}</span>
          )}
        </p>
      ) : (
        <p>
          Agent <Badge status="DOWN" />
        </p>
      )}
    </section>
  );
}
