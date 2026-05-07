import { tagsApi } from '@/api/tags';
import { api } from '@/api/client';

vi.mock('@/api/client', () => ({
  api: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn(), patch: vi.fn() },
  isAxiosError: vi.fn(),
}));

const m = api as any;
const res = (data: unknown) => Promise.resolve({ data });

beforeEach(() => { vi.clearAllMocks(); });

describe('tagsApi', () => {
  it('list: GETs /api/tags with params', async () => {
    m.get.mockReturnValue(res({ items: [], total: 0, limit: 100, offset: 0 }));

    await tagsApi.list({ limit: 100 });

    expect(m.get).toHaveBeenCalledWith('/api/tags', { params: { limit: 100 } });
  });

  it('list: works without params', async () => {
    m.get.mockReturnValue(res({ items: [] }));

    await tagsApi.list();

    expect(m.get).toHaveBeenCalledWith('/api/tags', { params: undefined });
  });

  it('get: GETs /api/tags/:id', async () => {
    const tag = { id: 't1', name: 'rust', user_id: 'u1', created_at: '' };
    m.get.mockReturnValue(res(tag));

    const result = await tagsApi.get('t1');

    expect(m.get).toHaveBeenCalledWith('/api/tags/t1');
    expect(result).toEqual(tag);
  });

  it('create: POSTs to /api/tags', async () => {
    m.post.mockReturnValue(res({ id: 't2', name: 'python' }));

    await tagsApi.create({ name: 'python' });

    expect(m.post).toHaveBeenCalledWith('/api/tags', { name: 'python' });
  });

  it('update: PUTs to /api/tags/:id', async () => {
    m.put.mockReturnValue(res({ id: 't1', name: 'typescript' }));

    await tagsApi.update('t1', { name: 'typescript' });

    expect(m.put).toHaveBeenCalledWith('/api/tags/t1', { name: 'typescript' });
  });

  it('delete: DELETEs /api/tags/:id', async () => {
    m.delete.mockReturnValue(res(null));

    await tagsApi.delete('t1');

    expect(m.delete).toHaveBeenCalledWith('/api/tags/t1');
  });
});
