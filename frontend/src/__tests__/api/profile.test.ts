import { profileApi } from '@/api/profile';
import { api } from '@/api/client';

vi.mock('@/api/client', () => ({
  api: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn(), patch: vi.fn() },
  isAxiosError: vi.fn(),
}));

const m = api as any;
const res = (data: unknown) => Promise.resolve({ data });

beforeEach(() => { vi.clearAllMocks(); });

describe('profileApi', () => {
  it('updateNickname: PUTs to /api/profile/nickname', async () => {
    const updatedUser = { id: 'u1', nickname: 'newname' };
    m.put.mockReturnValue(res(updatedUser));

    const result = await profileApi.updateNickname({ nickname: 'newname' });

    expect(m.put).toHaveBeenCalledWith('/api/profile/nickname', { nickname: 'newname' });
    expect(result).toEqual(updatedUser);
  });

  it('changePassword: PUTs to /api/profile/password', async () => {
    m.put.mockReturnValue(res({ message: 'Password changed.' }));

    await profileApi.changePassword({ current_password: 'old', new_password: 'new123' });

    expect(m.put).toHaveBeenCalledWith('/api/profile/password', {
      current_password: 'old',
      new_password: 'new123',
    });
  });

  it('deleteAccount: POSTs to /api/profile/delete_account', async () => {
    m.post.mockReturnValue(res(null));

    await profileApi.deleteAccount({ password: 'mypassword' });

    expect(m.post).toHaveBeenCalledWith('/api/profile/delete_account', { password: 'mypassword' });
  });
});
