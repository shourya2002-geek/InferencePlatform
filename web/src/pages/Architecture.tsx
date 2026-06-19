import { useState } from "react";
import { AlertTriangle, ArrowUpRight, FileCode2, Gauge, ListChecks } from "lucide-react";
import { Panel, PanelHead, PageHeader, Badge } from "@/components/primitives";
import { FlowDiagram } from "@/components/viz/FlowDiagram";
import { ARCH_NODES } from "@/sim/content";

export default function Architecture() {
  const [sel, setSel] = useState("scheduler");
  const node = ARCH_NODES.find((n) => n.id === sel) ?? ARCH_NODES[0];

  return (
    <div>
      <PageHeader
        title="Architecture Explorer"
        desc="Click any component to inspect its responsibilities, live metrics, bottlenecks and scaling strategy. Request tokens animate through the real lifecycle; red tokens are errors being shed."
        source="docs/ARCHITECTURE.md"
      />
      <div className="space-y-4 p-6">
        <Panel>
          <PanelHead
            title="Request lifecycle"
            sub="select a node to inspect"
            right={
              <div className="flex items-center gap-3 text-2xs text-fg-faint">
                <span className="flex items-center gap-1"><span className="h-1.5 w-1.5 rounded-full bg-ok" /> healthy</span>
                <span className="flex items-center gap-1"><span className="h-1.5 w-1.5 rounded-full bg-warn" /> pressured</span>
                <span className="flex items-center gap-1"><span className="h-1.5 w-1.5 rounded-full bg-danger" /> degraded</span>
              </div>
            }
          />
          <div className="p-4">
            <FlowDiagram selectedId={sel} onSelect={setSel} />
          </div>
        </Panel>

        <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
          <Panel className="lg:col-span-2">
            <PanelHead
              title={
                <span className="flex items-center gap-2">
                  {node.label}
                  <Badge tone="default">{node.sub}</Badge>
                </span>
              }
              sub={node.id === "response" ? "terminal" : `stage ${ARCH_NODES.findIndex((n) => n.id === sel) + 1} of ${ARCH_NODES.length}`}
              right={
                <span className="flex items-center gap-1.5 text-2xs text-fg-faint">
                  <FileCode2 className="h-3.5 w-3.5" /> <span className="mono">{node.source}</span>
                </span>
              }
            />
            <div className="grid grid-cols-1 gap-4 p-4 md:grid-cols-2">
              <Section icon={<ListChecks className="h-3.5 w-3.5 text-info" />} title="Responsibilities">
                <ul className="space-y-1.5">
                  {node.responsibilities.map((r) => (
                    <li key={r} className="flex gap-2 text-[13px] leading-snug text-fg-muted">
                      <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-fg-faint" />
                      {r}
                    </li>
                  ))}
                </ul>
              </Section>
              <div className="space-y-4">
                <Section icon={<AlertTriangle className="h-3.5 w-3.5 text-warn" />} title="Bottlenecks">
                  <ul className="space-y-1.5">
                    {node.bottlenecks.map((b) => (
                      <li key={b} className="flex gap-2 text-[13px] leading-snug text-fg-muted">
                        <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-warn/70" />
                        {b}
                      </li>
                    ))}
                  </ul>
                </Section>
                <Section icon={<ArrowUpRight className="h-3.5 w-3.5 text-ok" />} title="Scaling strategy">
                  <p className="text-[13px] leading-snug text-fg-muted">{node.scaling}</p>
                </Section>
              </div>
            </div>
          </Panel>

          <Panel>
            <PanelHead title={<span className="flex items-center gap-2"><Gauge className="h-3.5 w-3.5 text-torch" /> Exposed metrics</span>} />
            <div className="space-y-2 p-4">
              {node.metrics.map((m) => (
                <div key={m} className="rounded-md border border-line bg-ink-900 px-2.5 py-2">
                  <code className="mono text-xs text-info">{m}</code>
                </div>
              ))}
              <div className="mt-3 rounded-md border border-line bg-ink-750 p-3 text-2xs leading-relaxed text-fg-faint">
                These are scraped by Prometheus and rendered on the Observability page. A single
                <span className="mono text-fg-muted"> trace_id</span> threads through every node so logs,
                metrics and traces correlate across the Redis hops.
              </div>
            </div>
          </Panel>
        </div>
      </div>
    </div>
  );
}

function Section({ icon, title, children }: { icon: React.ReactNode; title: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="mb-2 flex items-center gap-1.5 text-2xs font-semibold uppercase tracking-wider text-fg-faint">
        {icon} {title}
      </div>
      {children}
    </div>
  );
}
