import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { getOtelStatus, getOtelUserSummary, getOtelMetrics } from "@/lib/api";

export const Route = createFileRoute("/otel")({
  component: OtelPage,
});

function OtelPage() {
  const [filter, setFilter] = useState("");
  const status = useQuery({ queryKey: ["otel-status"], queryFn: getOtelStatus });
  const summary = useQuery({ queryKey: ["otel-summary"], queryFn: () => getOtelUserSummary(7), enabled: status.data?.enabled === true });
  const metrics = useQuery({ queryKey: ["otel-metrics", filter], queryFn: () => getOtelMetrics(filter || undefined, 7), enabled: status.data?.enabled === true });

  if (status.isLoading) return <Skeleton className="h-32 w-full" />;

  if (!status.data?.enabled) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold">OpenTelemetry Metrics</h1>
        <Card>
          <CardContent className="pt-6">
            <p className="text-muted-foreground">OTEL metrics are not enabled. Set <code className="rounded bg-muted px-1 py-0.5 text-xs">OTEL_TABLE</code> in your config to enable.</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">OpenTelemetry Metrics</h1>
        <Badge variant="secondary">Table: {status.data.otel_table}</Badge>
      </div>

      <Card>
        <CardHeader><CardTitle>User Summary (7 days)</CardTitle></CardHeader>
        <CardContent>
          {summary.isLoading ? <Skeleton className="h-32 w-full" /> : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>User</TableHead>
                  <TableHead>Total Value</TableHead>
                  <TableHead>Metric Count</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {summary.data?.map((u, i) => (
                  <TableRow key={i}>
                    <TableCell className="font-medium">{u.user_id ?? "unknown"}</TableCell>
                    <TableCell>{u.total_value.toLocaleString()}</TableCell>
                    <TableCell>{u.metric_count.toLocaleString()}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>Raw Metrics</CardTitle>
            <Input className="max-w-xs" placeholder="Filter by metric name..." value={filter} onChange={(e) => setFilter(e.target.value)} />
          </div>
        </CardHeader>
        <CardContent>
          {metrics.isLoading ? <Skeleton className="h-32 w-full" /> : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Metric</TableHead>
                  <TableHead>User</TableHead>
                  <TableHead>Token Count</TableHead>
                  <TableHead>Time</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {metrics.data?.map((m, i) => (
                  <TableRow key={i}>
                    <TableCell className="font-medium">{m.metric_name ?? "-"}</TableCell>
                    <TableCell>{m.user_id ?? "-"}</TableCell>
                    <TableCell>{m.token_count?.toLocaleString() ?? "-"}</TableCell>
                    <TableCell className="text-xs">{m.event_time ? new Date(m.event_time).toLocaleString() : "-"}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
