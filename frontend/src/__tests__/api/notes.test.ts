import { notesApi } from '@/api/notes';
import { api } from '@/api/client';

vi.mock('@/api/client', () => ({
  api: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn(), patch: vi.fn() },
  isAxiosError: vi.fn(),
}));

const m = api as any;
const res = (data: unknown) => Promise.resolve({ data });

beforeEach(() => { vi.clearAllMocks(); });

describe('notesApi', () => {
  it('list: GETs /api/notes with params', async () => {
    m.get.mockReturnValue(res({ items: [], total: 0, limit: 50, offset: 0 }));

    await notesApi.list({ limit: 50, offset: 0 });

    expect(m.get).toHaveBeenCalledWith('/api/notes', { params: { limit: 50, offset: 0 } });
  });

  it('list: passes deleted=true for trash', async () => {
    m.get.mockReturnValue(res({ items: [] }));

    await notesApi.list({ deleted: true });

    expect(m.get).toHaveBeenCalledWith('/api/notes', { params: { deleted: true } });
  });

  it('list: passes no params when called with none', async () => {
    m.get.mockReturnValue(res({ items: [] }));

    await notesApi.list();

    expect(m.get).toHaveBeenCalledWith('/api/notes', { params: undefined });
  });

  it('search: GETs /api/notes/search with keywords and default limit', async () => {
    m.get.mockReturnValue(res({ items: [], total: 0, limit: 50, keywords: ['rust'] }));

    await notesApi.search('rust');

    expect(m.get).toHaveBeenCalledWith('/api/notes/search', {
      params: { keywords: 'rust', limit: 50 },
    });
  });

  it('search: accepts a custom limit', async () => {
    m.get.mockReturnValue(res({ items: [] }));

    await notesApi.search('query', 10);

    expect(m.get).toHaveBeenCalledWith('/api/notes/search', {
      params: { keywords: 'query', limit: 10 },
    });
  });

  it('get: GETs /api/notes/:id', async () => {
    const note = { id: 'n1', title: 'Test', content: null, version: 1, tags: [] };
    m.get.mockReturnValue(res(note));

    const result = await notesApi.get('n1');

    expect(m.get).toHaveBeenCalledWith('/api/notes/n1');
    expect(result).toEqual(note);
  });

  it('create: POSTs to /api/notes', async () => {
    m.post.mockReturnValue(res({ id: 'n2', title: null, content: null }));

    await notesApi.create({ title: null, content: null });

    expect(m.post).toHaveBeenCalledWith('/api/notes', { title: null, content: null });
  });

  it('update: PUTs to /api/notes/:id with version', async () => {
    m.put.mockReturnValue(res({ id: 'n1', version: 2 }));

    await notesApi.update('n1', { title: 'New', content: 'body', version: 1 });

    expect(m.put).toHaveBeenCalledWith('/api/notes/n1', {
      title: 'New', content: 'body', version: 1,
    });
  });

  it('delete: DELETEs /api/notes/:id (soft by default)', async () => {
    m.delete.mockReturnValue(res(null));

    await notesApi.delete('n1');

    expect(m.delete).toHaveBeenCalledWith('/api/notes/n1', { params: { permanent: false } });
  });

  it('delete: passes permanent=true for hard delete', async () => {
    m.delete.mockReturnValue(res(null));

    await notesApi.delete('n1', true);

    expect(m.delete).toHaveBeenCalledWith('/api/notes/n1', { params: { permanent: true } });
  });

  it('restore: POSTs to /api/notes/:id/restore', async () => {
    m.post.mockReturnValue(res({ id: 'n1' }));

    await notesApi.restore('n1');

    expect(m.post).toHaveBeenCalledWith('/api/notes/n1/restore');
  });

  it('setTags: PUTs to /api/notes/:id/tags', async () => {
    m.put.mockReturnValue(res({ id: 'n1', tags: [] }));

    await notesApi.setTags('n1', { tag_ids: ['t1', 't2'] });

    expect(m.put).toHaveBeenCalledWith('/api/notes/n1/tags', { tag_ids: ['t1', 't2'] });
  });

  it('batch: POSTs to /api/notes/batch', async () => {
    m.post.mockReturnValue(res({ items: [] }));

    await notesApi.batch({ note_ids: ['n1', 'n2'] });

    expect(m.post).toHaveBeenCalledWith('/api/notes/batch', { note_ids: ['n1', 'n2'] });
  });
});
