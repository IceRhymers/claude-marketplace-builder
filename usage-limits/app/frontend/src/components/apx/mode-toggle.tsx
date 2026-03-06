import { Moon, Sun } from "lucide-react";
import { useTheme } from "@/components/apx/theme-provider";

export function ModeToggle() {
  const { theme, setTheme } = useTheme();
  return (
    <button
      onClick={() => setTheme(theme === "light" ? "dark" : "light")}
      className="w-8 h-8 p-2 rounded-sm transition-transform duration-200 hover:scale-110 hover:bg-accent"
    >
      {theme === "light" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
      <span className="sr-only">Toggle theme</span>
    </button>
  );
}
