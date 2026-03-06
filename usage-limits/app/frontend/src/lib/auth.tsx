import { createContext, useContext, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { getMe, type MeResponse } from "./api";

interface AuthContextValue {
  email: string;
  displayName: string;
  isAdmin: boolean;
  isLoading: boolean;
}

const AuthContext = createContext<AuthContextValue>({
  email: "",
  displayName: "",
  isAdmin: false,
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
    email: data?.email ?? "",
    displayName: data?.display_name ?? "",
    isAdmin: data?.is_admin ?? false,
    isLoading,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  return useContext(AuthContext);
}
