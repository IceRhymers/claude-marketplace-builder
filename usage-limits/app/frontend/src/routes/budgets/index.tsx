import { createFileRoute } from "@tanstack/react-router";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, useEffect } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  listBudgets, saveBudget, deleteBudget,
  getDefaultBudget, saveDefaultBudget,
  listActiveWarnings, resolveWarning,
  listAuditLog,
  type BudgetConfig,
} from "@/lib/api";

export const Route = createFileRoute("/budgets/")({
  component: BudgetsPage,
});

function fmtDollars(n: number | null | undefined): string {
  return n != null ? `$${n.toFixed(2)}` : "-";
}

function BudgetForm({ onSaved, editing, onCancelEdit }: { onSaved: () => void; editing: BudgetConfig | null; onCancelEdit: () => void }) {
  const [entityId, setEntityId] = useState("");
  const [daily, setDaily] = useState("");
  const [weekly, setWeekly] = useState("");
  const [monthly, setMonthly] = useState("");

  useEffect(() => {
    if (editing) {
      setEntityId(editing.entity_id);
      setDaily(editing.daily_dollar_limit != null ? String(editing.daily_dollar_limit) : "");
      setWeekly(editing.weekly_dollar_limit != null ? String(editing.weekly_dollar_limit) : "");
      setMonthly(editing.monthly_dollar_limit != null ? String(editing.monthly_dollar_limit) : "");
    }
  }, [editing]);

  const clearForm = () => {
    setEntityId(""); setDaily(""); setWeekly(""); setMonthly("");
    onCancelEdit();
  };

  const mutation = useMutation({
    mutationFn: saveBudget,
    onSuccess: () => {
      clearForm();
      onSaved();
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    mutation.mutate({
      entity_id: entityId,
      daily_dollar_limit: daily ? Number(daily) : null,
      weekly_dollar_limit: weekly ? Number(weekly) : null,
      monthly_dollar_limit: monthly ? Number(monthly) : null,
    });
  };

  return (
    <form onSubmit={handleSubmit} className="grid gap-3 md:grid-cols-5 items-end">
      <div>
        <label className="text-xs font-medium">User Email</label>
        <Input value={entityId} onChange={(e) => setEntityId(e.target.value)} required placeholder="user@example.com" disabled={!!editing} />
      </div>
      <div>
        <label className="text-xs font-medium">Daily ($)</label>
        <Input type="number" step="0.01" value={daily} onChange={(e) => setDaily(e.target.value)} placeholder="—" />
      </div>
      <div>
        <label className="text-xs font-medium">Weekly ($)</label>
        <Input type="number" step="0.01" value={weekly} onChange={(e) => setWeekly(e.target.value)} placeholder="—" />
      </div>
      <div>
        <label className="text-xs font-medium">Monthly ($)</label>
        <Input type="number" step="0.01" value={monthly} onChange={(e) => setMonthly(e.target.value)} placeholder="—" />
      </div>
      <div className="flex gap-2">
        <Button type="submit" disabled={mutation.isPending}>{editing ? "Update" : "Save"}</Button>
        {editing && <Button type="button" variant="outline" onClick={clearForm}>Cancel</Button>}
      </div>
    </form>
  );
}

function DefaultBudgetForm() {
  const qc = useQueryClient();
  const defaults = useQuery({ queryKey: ["default-budget"], queryFn: getDefaultBudget });
  const [daily, setDaily] = useState("");
  const [weekly, setWeekly] = useState("");
  const [monthly, setMonthly] = useState("");

  const mutation = useMutation({
    mutationFn: saveDefaultBudget,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["default-budget"] });
      qc.invalidateQueries({ queryKey: ["user-budget"] });
      qc.invalidateQueries({ queryKey: ["budgets"] });
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    mutation.mutate({
      daily_dollar_limit: daily ? Number(daily) : null,
      weekly_dollar_limit: weekly ? Number(weekly) : null,
      monthly_dollar_limit: monthly ? Number(monthly) : null,
    });
  };

  return (
    <div className="space-y-4">
      {defaults.data && (
        <div className="text-sm text-muted-foreground">
          Current: Daily {fmtDollars(defaults.data.daily_dollar_limit)} / Weekly {fmtDollars(defaults.data.weekly_dollar_limit)} / Monthly {fmtDollars(defaults.data.monthly_dollar_limit)}
        </div>
      )}
      <form onSubmit={handleSubmit} className="grid gap-3 md:grid-cols-4 items-end">
        <div>
          <label className="text-xs font-medium">Daily ($)</label>
          <Input type="number" step="0.01" value={daily} onChange={(e) => setDaily(e.target.value)} placeholder="—" />
        </div>
        <div>
          <label className="text-xs font-medium">Weekly ($)</label>
          <Input type="number" step="0.01" value={weekly} onChange={(e) => setWeekly(e.target.value)} placeholder="—" />
        </div>
        <div>
          <label className="text-xs font-medium">Monthly ($)</label>
          <Input type="number" step="0.01" value={monthly} onChange={(e) => setMonthly(e.target.value)} placeholder="—" />
        </div>
        <Button type="submit" disabled={mutation.isPending}>Update Default</Button>
      </form>
    </div>
  );
}

function BudgetsPage() {
  const qc = useQueryClient();
  const budgets = useQuery({ queryKey: ["budgets"], queryFn: listBudgets });
  const warnings = useQuery({ queryKey: ["warnings"], queryFn: listActiveWarnings });
  const audit = useQuery({ queryKey: ["audit"], queryFn: () => listAuditLog(100) });
  const [editing, setEditing] = useState<BudgetConfig | null>(null);

  const deleteMut = useMutation({
    mutationFn: deleteBudget,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["budgets"] }),
  });

  const resolveMut = useMutation({
    mutationFn: resolveWarning,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["warnings"] }),
  });

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Budgets & Limits</h1>
      <Tabs defaultValue="budgets">
        <TabsList>
          <TabsTrigger value="budgets">Budgets</TabsTrigger>
          <TabsTrigger value="defaults">Defaults</TabsTrigger>
          <TabsTrigger value="warnings">Warnings {warnings.data?.length ? `(${warnings.data.length})` : ""}</TabsTrigger>
          <TabsTrigger value="audit">Audit Log</TabsTrigger>
        </TabsList>

        <TabsContent value="budgets" className="space-y-4">
          <Card>
            <CardHeader><CardTitle>{editing ? `Edit Budget: ${editing.entity_id}` : "Set Budget"}</CardTitle></CardHeader>
            <CardContent>
              <BudgetForm onSaved={() => { setEditing(null); qc.invalidateQueries({ queryKey: ["budgets"] }); }} editing={editing} onCancelEdit={() => setEditing(null)} />
            </CardContent>
          </Card>
          <Card>
            <CardHeader><CardTitle>All Budgets</CardTitle></CardHeader>
            <CardContent>
              {budgets.isLoading ? <Skeleton className="h-32 w-full" /> : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>User</TableHead>
                      <TableHead>Daily</TableHead>
                      <TableHead>Weekly</TableHead>
                      <TableHead>Monthly</TableHead>
                      <TableHead>Type</TableHead>
                      <TableHead />
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {budgets.data?.map((b: BudgetConfig) => {
                      const isUnlimited = b.daily_dollar_limit == null && b.weekly_dollar_limit == null && b.monthly_dollar_limit == null;
                      return (
                        <TableRow key={b.id} className="cursor-pointer" onClick={() => setEditing(b)}>
                          <TableCell className="font-medium">{b.entity_id}</TableCell>
                          <TableCell>{fmtDollars(b.daily_dollar_limit)}</TableCell>
                          <TableCell>{fmtDollars(b.weekly_dollar_limit)}</TableCell>
                          <TableCell>{fmtDollars(b.monthly_dollar_limit)}</TableCell>
                          <TableCell>
                            {isUnlimited ? <Badge>Unlimited</Badge> : b.is_custom ? <Badge variant="secondary">Custom</Badge> : <Badge variant="outline">Default</Badge>}
                          </TableCell>
                          <TableCell>
                            <Button variant="destructive" size="sm" onClick={(e) => { e.stopPropagation(); deleteMut.mutate(b.id); }} disabled={deleteMut.isPending}>
                              Delete
                            </Button>
                          </TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="defaults">
          <Card>
            <CardHeader><CardTitle>Default Budget</CardTitle></CardHeader>
            <CardContent><DefaultBudgetForm /></CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="warnings">
          <Card>
            <CardHeader><CardTitle>Active Warnings</CardTitle></CardHeader>
            <CardContent>
              {warnings.isLoading ? <Skeleton className="h-32 w-full" /> : !warnings.data?.length ? (
                <p className="text-sm text-muted-foreground">No active warnings.</p>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>User</TableHead>
                      <TableHead>Reason</TableHead>
                      <TableHead>Usage</TableHead>
                      <TableHead>Limit</TableHead>
                      <TableHead>Enforced</TableHead>
                      <TableHead />
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {warnings.data.map((w) => (
                      <TableRow key={w.id}>
                        <TableCell className="font-medium">{w.user_id}</TableCell>
                        <TableCell>{w.reason}</TableCell>
                        <TableCell>{fmtDollars(w.dollar_usage)}</TableCell>
                        <TableCell>{fmtDollars(w.dollar_limit)}</TableCell>
                        <TableCell>{w.enforced_at ? new Date(w.enforced_at).toLocaleString() : "-"}</TableCell>
                        <TableCell>
                          <Button size="sm" variant="outline" onClick={() => resolveMut.mutate(w.id)} disabled={resolveMut.isPending}>
                            Resolve
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="audit">
          <Card>
            <CardHeader><CardTitle>Audit Log (last 100)</CardTitle></CardHeader>
            <CardContent>
              {audit.isLoading ? <Skeleton className="h-32 w-full" /> : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Time</TableHead>
                      <TableHead>Action</TableHead>
                      <TableHead>User</TableHead>
                      <TableHead>Details</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {audit.data?.map((entry) => (
                      <TableRow key={entry.id}>
                        <TableCell className="text-xs">{entry.created_at ? new Date(entry.created_at).toLocaleString() : "-"}</TableCell>
                        <TableCell><Badge variant="outline">{entry.action}</Badge></TableCell>
                        <TableCell>{entry.user_id ?? "-"}</TableCell>
                        <TableCell className="max-w-xs truncate text-xs">{entry.details ? JSON.stringify(entry.details) : "-"}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
