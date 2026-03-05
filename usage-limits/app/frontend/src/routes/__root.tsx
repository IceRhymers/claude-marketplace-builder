import { createRootRouteWithContext, Link, Outlet } from "@tanstack/react-router";
import { QueryClient } from "@tanstack/react-query";
import { BarChart3, Users, Wallet, Activity } from "lucide-react";
import { ModeToggle } from "@/components/apx/mode-toggle";
import { Separator } from "@/components/ui/separator";

interface RouterContext {
  queryClient: QueryClient;
}

export const Route = createRootRouteWithContext<RouterContext>()({
  component: RootLayout,
});

const navItems = [
  { to: "/overview", label: "Overview", icon: BarChart3 },
  { to: "/users", label: "Users", icon: Users },
  { to: "/budgets", label: "Budgets", icon: Wallet },
  { to: "/otel", label: "OTEL", icon: Activity },
] as const;

function RootLayout() {
  return (
    <div className="flex h-screen">
      <aside className="flex w-56 flex-col border-r bg-sidebar text-sidebar-foreground">
        <div className="flex h-14 items-center gap-2 px-4 font-semibold">
          <Wallet className="h-5 w-5" />
          Usage Limits
        </div>
        <Separator />
        <nav className="flex flex-1 flex-col gap-1 p-2">
          {navItems.map(({ to, label, icon: Icon }) => (
            <Link
              key={to}
              to={to}
              className="flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors hover:bg-sidebar-accent [&.active]:bg-sidebar-accent [&.active]:text-sidebar-accent-foreground"
            >
              <Icon className="h-4 w-4" />
              {label}
            </Link>
          ))}
        </nav>
        <div className="border-t p-2">
          <ModeToggle />
        </div>
      </aside>
      <main className="flex-1 overflow-y-auto p-6">
        <Outlet />
      </main>
    </div>
  );
}
