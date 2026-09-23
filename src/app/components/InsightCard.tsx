import type { AgentResult } from "@/lib/types";

type Props = { result: AgentResult };

export function InsightCard({ result }: Props) {
  return (
    <div className="insightResult">
      <span className={`priority ${result.priority}`}>
        {result.priority} priority · {result.mode} mode
      </span>
      <h3>{result.headline}</h3>
      {result.degraded && <p className="degraded">{result.degraded}</p>}
      <p>{result.finding}</p>
      <h4>Recommended next action</h4>
      <p>{result.recommendation}</p>
      <h4>Evidence</h4>
      <ul>
        {result.evidence.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
      <small>{result.disclaimer}</small>
    </div>
  );
}
