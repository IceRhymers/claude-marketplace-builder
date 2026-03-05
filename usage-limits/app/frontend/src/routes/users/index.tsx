import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { listUsers } from "@/lib/api";

export const Route = createFileRoute("/users/")({
  component: UsersIndexPage,
});

function UsersIndexPage() {
  const navigate = useNavigate();
  const users = useQuery({ queryKey: ["users"], queryFn: listUsers });

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Users</h1>
      <Card>
        <CardHeader>
          <CardTitle>Select a User</CardTitle>
        </CardHeader>
        <CardContent>
          {users.isLoading ? (
            <Skeleton className="h-9 w-full max-w-sm" />
          ) : (
            <Select onValueChange={(email) => navigate({ to: "/users/$userEmail", params: { userEmail: email } })}>
              <SelectTrigger className="max-w-sm">
                <SelectValue placeholder="Choose a user..." />
              </SelectTrigger>
              <SelectContent>
                {users.data?.map((email) => (
                  <SelectItem key={email} value={email}>
                    {email}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
