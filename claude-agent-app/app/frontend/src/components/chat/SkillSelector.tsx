import { useQuery } from "@tanstack/react-query";
import { Zap } from "lucide-react";

interface Skill {
  name: string;
  description?: string;
}

async function getSkills(): Promise<Skill[]> {
  const resp = await fetch("/api/skills");
  if (!resp.ok) return [];
  return resp.json();
}

interface SkillSelectorProps {
  value: string | null;
  onChange: (skill: string | null) => void;
}

export function SkillSelector({ value, onChange }: SkillSelectorProps) {
  const { data: skills = [] } = useQuery<Skill[]>({
    queryKey: ["skills"],
    queryFn: getSkills,
    staleTime: 60_000,
  });

  if (skills.length === 0) return null;

  return (
    <div className="flex items-center gap-2 px-4 pb-2">
      <Zap className="h-3.5 w-3.5 text-muted-foreground flex-shrink-0" />
      <select
        aria-label="Select skill"
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value || null)}
        className="text-xs border rounded px-2 py-1 bg-background text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
      >
        <option value="">Default (no skill)</option>
        {skills.map((skill) => (
          <option key={skill.name} value={skill.name}>
            {skill.name}
          </option>
        ))}
      </select>
    </div>
  );
}
