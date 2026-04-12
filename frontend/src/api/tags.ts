import { apiFetch, apiPost, apiPut, apiDelete } from "./client";
import type { Tag, TagListResponse } from "./types";

export async function listTags(search?: string): Promise<TagListResponse> {
  const qs = search ? `?search=${encodeURIComponent(search)}` : "";
  return apiFetch(`/api/tags${qs}`);
}

export async function createTag(name: string): Promise<Tag> {
  return apiPost("/api/tags", { name });
}

export async function renameTag(tagId: string, name: string): Promise<Tag> {
  return apiPut(`/api/tags/${tagId}`, { name });
}

export async function deleteTag(tagId: string): Promise<void> {
  return apiDelete(`/api/tags/${tagId}`);
}
