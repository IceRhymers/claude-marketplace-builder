import { createContext, useContext, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { getMe, type MeResponse } from "./api";

interface AuthContextValue {
  userId: string;
  displayName: string;
  isLoading: boolean;
}

const AuthContext = createContext<AuthContextValue>({
  userId: "",
  displayName: "",
  isLoading: true,
});

export function AuthProvider({ children }: { children: ReactNode }) {
  const { data, isLoading } = useQuery<MeResponse>({
    queryKey: ["me"],
    queryFn: getMe,
    retry: false,
    staleTime: 5 * 60 * 1000,
  });

  const value: AuthContextValue = {
    userId: data?.user_id ?? "",
    displayName: data?.display_name ?? "",
    isLoading,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  return useContext(AuthContext);
}
