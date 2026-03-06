import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";
import { DollarSign, Zap, Users } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { getOverviewMetrics, getTopUsers } from "@/lib/api";

export const Route = createFileRoute("/overview")({
  component: OverviewPage,
});

function MetricCard({ title, value, icon: Icon, loading }: { title: string; value: string; icon: React.ElementType; loading: boolean }) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="text-sm font-medium">{title}</CardTitle>
        <Icon className="h-4 w-4 text-muted-foreground" />
      </CardHeader>
      <CardContent>{loading ? <Skeleton className="h-8 w-24" /> : <div className="text-2xl font-bold">{value}</div>}</CardContent>
    </Card>
  );
}

function OverviewPage() {
  const metrics = useQuery({ queryKey: ["overview-metrics"], queryFn: getOverviewMetrics });
  const topUsers = useQuery({ queryKey: ["top-users"], queryFn: getTopUsers });

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Overview</h1>
      <div className="grid gap-4 md:grid-cols-3">
        <MetricCard title="Cost Today" value={`$${(metrics.data?.cost_today ?? 0).toFixed(2)}`} icon={DollarSign} loading={metrics.isLoading} />
        <MetricCard title="Requests Today" value={String(metrics.data?.requests_today ?? 0)} icon={Zap} loading={metrics.isLoading} />
        <MetricCard title="Active Users" value={String(metrics.data?.active_users ?? 0)} icon={Users} loading={metrics.isLoading} />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Top Users by Token Usage</CardTitle>
        </CardHeader>
        <CardContent>
          {topUsers.isLoading ? (
            <Skeleton className="h-[300px] w-full" />
          ) : (
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={topUsers.data?.slice(0, 10)} layout="vertical" margin={{ left: 120 }}>
                <XAxis type="number" />
                <YAxis type="category" dataKey="requester" width={110} tick={{ fontSize: 12 }} />
                <Tooltip formatter={(v: number) => v.toLocaleString()} />
                <Bar dataKey="total_tokens" fill="var(--chart-1)" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
