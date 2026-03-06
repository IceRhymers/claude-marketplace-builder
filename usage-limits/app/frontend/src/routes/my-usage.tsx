import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { getMySnapshot, getMyHistory, getMyBudget } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export const Route = createFileRoute("/my-usage")({
  component: MyUsagePage,
});

function fmt(n: number | null | undefined): string {
  if (n == null) return "-";
  return n.toLocaleString();
}

function fmtDollars(n: number | null | undefined): string {
  if (n == null) return "-";
  return `$${n.toFixed(2)}`;
}

function MyUsagePage() {
  const { email } = useAuth();
  const snapshot = useQuery({ queryKey: ["my-snapshot"], queryFn: getMySnapshot, refetchInterval: 60_000 });
  const history = useQuery({ queryKey: ["my-history"], queryFn: () => getMyHistory(30), refetchInterval: 300_000 });
  const budget = useQuery({ queryKey: ["my-budget"], queryFn: getMyBudget, refetchInterval: 60_000 });

  const budgetRows = [
    { period: "Daily", usage: budget.data?.dollar_cost_1d, limit: budget.data?.daily_dollar_limit ?? null },
    { period: "Weekly", usage: budget.data?.dollar_cost_7d, limit: budget.data?.weekly_dollar_limit ?? null },
    { period: "Monthly", usage: budget.data?.dollar_cost_30d, limit: budget.data?.monthly_dollar_limit ?? null },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">My Usage</h1>
        {email && <p className="text-sm text-muted-foreground">{email}</p>}
      </div>

      {/* Usage Snapshot Cards */}
      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-sm font-medium">Cost (1d / 7d / 30d)</CardTitle></CardHeader>
          <CardContent>
            {snapshot.isLoading ? <Skeleton className="h-8 w-32" /> : (
              <div className="text-2xl font-bold">
                {fmtDollars(snapshot.data?.dollar_cost_1d)}
                <span className="text-base font-normal text-muted-foreground"> / {fmtDollars(snapshot.data?.dollar_cost_7d)} / {fmtDollars(snapshot.data?.dollar_cost_30d)}</span>
              </div>
            )}
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-sm font-medium">Tokens (1d / 7d / 30d)</CardTitle></CardHeader>
          <CardContent>
            {snapshot.isLoading ? <Skeleton className="h-8 w-32" /> : (
              <div className="text-2xl font-bold">
                {fmt(snapshot.data?.total_tokens_1d)}
                <span className="text-base font-normal text-muted-foreground"> / {fmt(snapshot.data?.total_tokens_7d)} / {fmt(snapshot.data?.total_tokens_30d)}</span>
              </div>
            )}
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-sm font-medium">Requests (1d / 7d / 30d)</CardTitle></CardHeader>
          <CardContent>
            {snapshot.isLoading ? <Skeleton className="h-8 w-32" /> : (
              <div className="text-2xl font-bold">
                {fmt(snapshot.data?.request_count_1d)}
                <span className="text-base font-normal text-muted-foreground"> / {fmt(snapshot.data?.request_count_7d)} / {fmt(snapshot.data?.request_count_30d)}</span>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Budget Status */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <CardTitle>Budget Status</CardTitle>
            {budget.data && budget.data.daily_dollar_limit == null && budget.data.weekly_dollar_limit == null && budget.data.monthly_dollar_limit == null && <Badge>Unlimited (no limits enforced)</Badge>}
          </div>
        </CardHeader>
        <CardContent>
          {budget.isLoading ? (
            <Skeleton className="h-24 w-full" />
          ) : !budget.data ? (
            <p className="text-sm text-muted-foreground">No budget assigned.</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Period</TableHead>
                  <TableHead>Usage</TableHead>
                  <TableHead>Limit</TableHead>
                  <TableHead className="w-48">Progress</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {budgetRows.map((row) => {
                  const pct = row.limit != null && row.usage != null
                    ? (row.limit === 0 ? 100 : Math.min((row.usage / row.limit) * 100, 100))
                    : null;
                  const rawPct = row.limit != null && row.usage != null
                    ? (row.limit === 0 ? Infinity : (row.usage / row.limit) * 100)
                    : null;
                  return (
                    <TableRow key={row.period}>
                      <TableCell className="font-medium">{row.period}</TableCell>
                      <TableCell>{fmtDollars(row.usage)}</TableCell>
                      <TableCell>{fmtDollars(row.limit)}</TableCell>
                      <TableCell>
                        {pct != null ? (
                          <div className="h-2 w-full rounded-full bg-muted">
                            <div
                              className={`h-full rounded-full transition-all ${
                                rawPct != null && rawPct >= 100
                                  ? "bg-destructive"
                                  : rawPct != null && rawPct >= 75
                                    ? "bg-yellow-500"
                                    : "bg-green-600"
                              }`}
                              style={{ width: `${pct}%` }}
                            />
                          </div>
                        ) : (
                          <span className="text-xs text-muted-foreground">-</span>
                        )}
                      </TableCell>
                      <TableCell>
                        {row.limit == null ? (
                          <Badge variant="secondary">No Limit</Badge>
                        ) : rawPct != null && rawPct >= 100 ? (
                          <Badge variant="destructive">Over Budget</Badge>
                        ) : rawPct != null && rawPct >= 75 ? (
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
          )}
        </CardContent>
      </Card>

      {/* Daily History Chart */}
      <Card>
        <CardHeader>
          <CardTitle>Daily Token Usage (30 days)</CardTitle>
        </CardHeader>
        <CardContent>
          {history.isLoading ? (
            <Skeleton className="h-[300px] w-full" />
          ) : (
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={[...(history.data?.days ?? [])].reverse()}>
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
