import { describe, it, expect } from "vitest";
import { getMe, getConversations, createConversation, deleteConversation, getMessages } from "./api";

describe("api.ts", () => {
  describe("getMe", () => {
    it("returns user object from GET /api/me", async () => {
      const result = await getMe();
      expect(result).toMatchObject({
        user_id: "test@example.com",
        display_name: "Test User",
      });
    });
  });

  describe("getConversations", () => {
    it("returns conversations array from GET /api/conversations", async () => {
      const result = await getConversations();
      expect(Array.isArray(result)).toBe(true);
      expect(result.length).toBeGreaterThan(0);
      expect(result[0]).toHaveProperty("conversation_id");
    });
  });

  describe("createConversation", () => {
    it("returns new conversation_id from POST /api/conversations", async () => {
      const result = await createConversation();
      expect(result).toHaveProperty("conversation_id");
      expect(result.conversation_id).toBe("new-conv-456");
    });
  });

  describe("deleteConversation", () => {
    it("sends DELETE request and returns 204", async () => {
      // Should not throw
      await expect(deleteConversation("test-conv-123")).resolves.toBeUndefined();
    });
  });

  describe("getMessages", () => {
    it("returns messages array for a conversation", async () => {
      const result = await getMessages("test-conv-123");
      expect(Array.isArray(result)).toBe(true);
      expect(result[0]).toHaveProperty("role");
      expect(result[0]).toHaveProperty("content");
    });
  });
});
