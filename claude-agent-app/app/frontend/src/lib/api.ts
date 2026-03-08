/**
 * Typed API wrappers for the claude-agent-app backend.
 */

export interface MeResponse {
  user_id: string;
  display_name: string;
}

export interface Conversation {
  conversation_id: string;
  title: string | null;
  created_at: string;
  updated_at: string;
}

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;
}

export interface CreateConversationResponse {
  conversation_id: string;
  created_at: string;
}

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const resp = await fetch(path, options);
  if (!resp.ok) {
    throw new Error(`API error ${resp.status}: ${resp.statusText}`);
  }
  if (resp.status === 204) {
    return undefined as T;
  }
  return resp.json() as Promise<T>;
}

export async function getMe(): Promise<MeResponse> {
  return apiFetch<MeResponse>("/api/me");
}

export async function getConversations(): Promise<Conversation[]> {
  return apiFetch<Conversation[]>("/api/conversations");
}

export async function createConversation(): Promise<CreateConversationResponse> {
  return apiFetch<CreateConversationResponse>("/api/conversations", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
  });
}

export async function deleteConversation(conversationId: string): Promise<void> {
  return apiFetch<void>(`/api/conversations/${conversationId}`, {
    method: "DELETE",
  });
}

export async function getMessages(conversationId: string): Promise<Message[]> {
  return apiFetch<Message[]>(`/api/conversations/${conversationId}/messages`);
}
