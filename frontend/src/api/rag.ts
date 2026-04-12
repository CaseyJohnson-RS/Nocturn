import { apiPost } from "./client";
import type { SearchResponse } from "./types";

export async function search(query: string, limit: number = 5): Promise<SearchResponse> {
  return apiPost("/api/rag/search", { query, limit });
}
