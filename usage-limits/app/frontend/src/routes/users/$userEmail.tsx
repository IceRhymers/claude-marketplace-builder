import { createFileRoute, Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";
import { ArrowLeft } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { getUserUsage, getUserSnapshot, getUserBudget } from "@/lib/api";

export const Route = createFileRoute("/users/$userEmail")({
  component: UserDetailPage,
});

function fmt(n: number | null | undefined): string {
  if (n == null) return "-";
  return n.toLocaleString();
}

function fmtDollars(n: number | null | undefined): string {
  if (n == null) return "-";
  return `$${n.toFixed(2)}`;
}

function UserDetailPage() {
  const { userEmail } = Route.useParams();
  const usage = useQuery({ queryKey: ["user-usage", userEmail], queryFn: () => getUserUsage(userEmail) });
  const snapshot = useQuery({ queryKey: ["user-snapshot", userEmail], queryFn: () => getUserSnapshot(userEmail) });
  const budget = useQuery({ queryKey: ["user-budget", userEmail], queryFn: () => getUserBudget(userEmail) });

  const isDefaultBudget = budget.data?.entity_type === "default";

  const budgetRows = [
    { period: "Daily", usage: snapshot.data?.dollar_cost_1d, limit: budget.data?.daily_dollar_limit ?? null },
    { period: "Weekly", usage: snapshot.data?.dollar_cost_7d, limit: budget.data?.weekly_dollar_limit ?? null },
    { period: "Monthly", usage: snapshot.data?.dollar_cost_30d, limit: budget.data?.monthly_dollar_limit ?? null },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="icon" asChild>
          <Link to="/users">
            <ArrowLeft className="h-4 w-4" />
          </Link>
        </Button>
        <h1 className="text-2xl font-bold">{userEmail}</h1>
        {budget.data && budget.data.daily_dollar_limit == null && budget.data.weekly_dollar_limit == null && budget.data.monthly_dollar_limit == null && <Badge>Unlimited</Badge>}
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-sm font-medium">Cost (30d)</CardTitle></CardHeader>
          <CardContent>{snapshot.isLoading ? <Skeleton className="h-8 w-24" /> : <div className="text-2xl font-bold">{fmtDollars(snapshot.data?.dollar_cost_30d)}</div>}</CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-sm font-medium">Tokens (30d)</CardTitle></CardHeader>
          <CardContent>{snapshot.isLoading ? <Skeleton className="h-8 w-24" /> : <div className="text-2xl font-bold">{fmt(snapshot.data?.total_tokens_30d)}</div>}</CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-sm font-medium">Requests (30d)</CardTitle></CardHeader>
          <CardContent>{snapshot.isLoading ? <Skeleton className="h-8 w-24" /> : <div className="text-2xl font-bold">{fmt(snapshot.data?.request_count_30d)}</div>}</CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <CardTitle>Budget Tracking</CardTitle>
            {isDefaultBudget && <Badge variant="outline">Default</Badge>}
            {!budget.data && !budget.isLoading && (
              <Badge variant="secondary">No Budget Configured</Badge>
            )}
          </div>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Period</TableHead>
                <TableHead>Usage</TableHead>
                <TableHead>Limit</TableHead>
                <TableHead>% Used</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {budgetRows.map((row) => {
                const pct = row.limit != null && row.usage != null
                  ? (row.limit === 0 ? Infinity : (row.usage / row.limit) * 100)
                  : null;
                return (
                  <TableRow key={row.period}>
                    <TableCell className="font-medium">{row.period}</TableCell>
                    <TableCell>{fmtDollars(row.usage)}</TableCell>
                    <TableCell>{fmtDollars(row.limit)}</TableCell>
                    <TableCell>{pct != null && isFinite(pct) ? `${pct.toFixed(1)}%` : pct === Infinity ? "∞" : "-"}</TableCell>
                    <TableCell>
                      {row.limit == null ? (
                        <Badge variant="secondary">No Limit</Badge>
                      ) : pct != null && pct >= 100 ? (
                        <Badge variant="destructive">Over Budget</Badge>
                      ) : pct != null && pct >= 75 ? (
                        <Badge className="bg-yellow-500 hover:bg-yellow-600 text-white">Warning</Badge>
                      ) : (
                        <Badge className="bg-green-600 hover:bg-green-700 text-white">On Track</Badge>
                      )}
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Daily Token Usage (30 days)</CardTitle>
        </CardHeader>
        <CardContent>
          {usage.isLoading ? (
            <Skeleton className="h-[300px] w-full" />
          ) : (
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={[...(usage.data?.days ?? [])].reverse()}>
                <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
                <XAxis dataKey="usage_date" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip formatter={(v: number) => v.toLocaleString()} />
                <Line type="monotone" dataKey="input_tokens" stroke="var(--chart-1)" strokeWidth={2} dot={false} name="Input" />
                <Line type="monotone" dataKey="output_tokens" stroke="var(--chart-2)" strokeWidth={2} dot={false} name="Output" />
              </LineChart>
            </ResponsiveContainer>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
