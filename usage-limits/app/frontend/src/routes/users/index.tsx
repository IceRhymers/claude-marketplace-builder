import { useState } from "react";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Command, CommandInput, CommandList, CommandEmpty, CommandGroup, CommandItem } from "@/components/ui/command";
import { ChevronsUpDown } from "lucide-react";
import { listUsers } from "@/lib/api";

export const Route = createFileRoute("/users/")({
  component: UsersIndexPage,
});

function UsersIndexPage() {
  const navigate = useNavigate();
  const users = useQuery({ queryKey: ["users"], queryFn: listUsers });
  const [open, setOpen] = useState(false);

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
            <Popover open={open} onOpenChange={setOpen}>
              <PopoverTrigger asChild>
                <Button variant="outline" role="combobox" aria-expanded={open} className="max-w-sm w-full justify-between">
                  Search users...
                  <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
                </Button>
              </PopoverTrigger>
              <PopoverContent>
                <Command>
                  <CommandInput placeholder="Type to filter..." />
                  <CommandList>
                    <CommandEmpty>No users found.</CommandEmpty>
                    <CommandGroup>
                      {users.data?.map((email) => (
                        <CommandItem
                          key={email}
                          value={email}
                          onSelect={() => {
                            setOpen(false);
                            navigate({ to: "/users/$userEmail", params: { userEmail: email } });
                          }}
                        >
                          {email}
                        </CommandItem>
                      ))}
                    </CommandGroup>
                  </CommandList>
                </Command>
              </PopoverContent>
            </Popover>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
