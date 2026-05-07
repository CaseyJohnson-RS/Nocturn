import { api } from './client';
import type { SearchRequest, SearchResponse } from '@/types/api';

export const ragApi = {
  search: (data: SearchRequest) =>
    api.post<SearchResponse>('/api/rag/search', data).then((r) => r.data),
};
