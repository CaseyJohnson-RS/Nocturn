import { aiApi, sendMessage, confirmBulkStream } from '@/api/ai';
import { api } from '@/api/client';
import { useAuthStore } from '@/stores/auth';

// ── Mock the axios api instance for non-SSE methods ───────────────────────────

vi.mock('@/api/client', () => ({
  api: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn(), patch: vi.fn() },
  isAxiosError: vi.fn(),
}));

// Cast to any — vi.mocked() doesn't resolve mock helpers on overloaded axios types
const m = api as any;
const res = (data: unknown) => Promise.resolve({ data });

beforeEach(() => {
  vi.clearAllMocks();
  useAuthStore.setState({ accessToken: null, user: null, isInitialized: false });
});

// ── REST methods ──────────────────────────────────────────────────────────────

describe('aiApi REST methods', () => {
  it('listSessions: GETs /api/ai/sessions', async () => {
    m.get.mockReturnValue(res({ items: [], total: 0 }));

    await aiApi.listSessions({ limit: 50 });

    expect(m.get).toHaveBeenCalledWith('/api/ai/sessions', { params: { limit: 50 } });
  });

  it('createSession: POSTs to /api/ai/sessions', async () => {
    m.post.mockReturnValue(res({ id: 's1', title: null }));

    await aiApi.createSession({ dismiss_session_id: null });

    expect(m.post).toHaveBeenCalledWith('/api/ai/sessions', { dismiss_session_id: null });
  });

  it('createSession: uses empty body by default', async () => {
    m.post.mockReturnValue(res({ id: 's1' }));

    await aiApi.createSession();

    expect(m.post).toHaveBeenCalledWith('/api/ai/sessions', {});
  });

  it('updateSession: PUTs to /api/ai/sessions/:id', async () => {
    m.put.mockReturnValue(res({ id: 's1', title: 'My chat' }));

    await aiApi.updateSession('s1', { title: 'My chat' });

    expect(m.put).toHaveBeenCalledWith('/api/ai/sessions/s1', { title: 'My chat' });
  });

  it('deleteSession: DELETEs /api/ai/sessions/:id', async () => {
    m.delete.mockReturnValue(res(null));

    await aiApi.deleteSession('s1');

    expect(m.delete).toHaveBeenCalledWith('/api/ai/sessions/s1');
  });

  it('getMessages: GETs /api/ai/sessions/:id/messages', async () => {
    m.get.mockReturnValue(res({ items: [], total: 0 }));

    await aiApi.getMessages('s1', { limit: 100 });

    expect(m.get).toHaveBeenCalledWith('/api/ai/sessions/s1/messages', { params: { limit: 100 } });
  });

  it('updateAction: PATCHes the action URL', async () => {
    m.patch.mockReturnValue(res({ id: 'm1', content: 'hi', actions: [] }));

    await aiApi.updateAction('s1', 'm1', 'a1', { status: 'applied' });

    expect(m.patch).toHaveBeenCalledWith(
      '/api/ai/sessions/s1/messages/m1/actions/a1',
      { status: 'applied' },
    );
  });

  it('cancelGeneration: POSTs to /api/ai/sessions/:id/cancel', async () => {
    m.post.mockReturnValue(res(null));

    await aiApi.cancelGeneration('s1');

    expect(m.post).toHaveBeenCalledWith('/api/ai/sessions/s1/cancel');
  });

  it('dismissBulk: POSTs to dismiss endpoint', async () => {
    m.post.mockReturnValue(res({ id: 'm1', content: '', actions: null }));

    await aiApi.dismissBulk('s1', 'c1');

    expect(m.post).toHaveBeenCalledWith('/api/ai/sessions/s1/dismiss/c1');
  });
});

// ── SSE helpers ───────────────────────────────────────────────────────────────

function makeSseResponse(chunks: string[], ok = true) {
  const encoder = new TextEncoder();
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) {
        controller.enqueue(encoder.encode(chunk));
      }
      controller.close();
    },
  });
  return new Response(stream, {
    status: ok ? 200 : 400,
    headers: { 'content-type': ok ? 'text/event-stream' : 'application/json' },
  });
}

async function collectFrames<T>(gen: AsyncGenerator<T>) {
  const frames: T[] = [];
  for await (const f of gen) frames.push(f);
  return frames;
}

describe('sendMessage – SSE parsing', () => {
  afterEach(() => { vi.unstubAllGlobals(); });

  it('yields text_delta frames', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(
      makeSseResponse([
        'event: ai:text_delta\ndata: {"delta":"Hello"}\n\n',
        'event: ai:text_delta\ndata: {"delta":" world"}\n\n',
      ]),
    ));

    const frames = await collectFrames(sendMessage('s1', { content: 'hi' }));

    expect(frames).toHaveLength(2);
    expect(frames[0]).toEqual({ event: 'ai:text_delta', data: { delta: 'Hello' } });
    expect(frames[1]).toEqual({ event: 'ai:text_delta', data: { delta: ' world' } });
  });

  it('yields a proposal frame', async () => {
    const proposal = {
      type: 'proposal', id: 'p1', proposal_type: 'create_note',
      status: 'pending', data: { title: 'New note' }, summary: 'Create a note', note_id: null,
    };
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(
      makeSseResponse([`event: ai:proposal\ndata: ${JSON.stringify(proposal)}\n\n`]),
    ));

    const frames = await collectFrames(sendMessage('s1', { content: 'make a note' }));

    expect(frames[0].event).toBe('ai:proposal');
    expect(frames[0].data).toEqual(proposal);
  });

  it('yields ai:done with the final message', async () => {
    const message = { id: 'm1', session_id: 's1', role: 'assistant', content: 'Done!' };
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(
      makeSseResponse([`event: ai:done\ndata: ${JSON.stringify({ message })}\n\n`]),
    ));

    const frames = await collectFrames(sendMessage('s1', { content: 'go' }));

    expect(frames[0].event).toBe('ai:done');
    expect((frames[0].data as { message: unknown }).message).toEqual(message);
  });

  it('silently skips malformed JSON frames', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(
      makeSseResponse([
        'event: ai:text_delta\ndata: {INVALID JSON}\n\n',
        'event: ai:text_delta\ndata: {"delta":"ok"}\n\n',
      ]),
    ));

    const frames = await collectFrames(sendMessage('s1', { content: 'hi' }));

    expect(frames).toHaveLength(1);
    expect(frames[0].data).toEqual({ delta: 'ok' });
  });

  it('handles chunks split across multiple reads', async () => {
    const fullEvent = 'event: ai:text_delta\ndata: {"delta":"split"}\n\n';
    const mid = Math.floor(fullEvent.length / 2);
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(
      makeSseResponse([fullEvent.slice(0, mid), fullEvent.slice(mid)]),
    ));

    const frames = await collectFrames(sendMessage('s1', { content: 'hi' }));

    expect(frames).toHaveLength(1);
    expect(frames[0].data).toEqual({ delta: 'split' });
  });

  it('throws when the server returns a non-ok status', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: 'Not found' }), {
        status: 404,
        headers: { 'content-type': 'application/json' },
      }),
    ));

    await expect(collectFrames(sendMessage('s1', { content: 'hi' }))).rejects.toMatchObject({
      status: 404,
    });
  });

  it('throws when the response is not text/event-stream', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: 'unexpected' }), {
        status: 200,
        headers: { 'content-type': 'application/json' },
      }),
    ));

    await expect(collectFrames(sendMessage('s1', { content: 'hi' }))).rejects.toMatchObject({
      status: 200,
    });
  });

  it('attaches Authorization header when token is present', async () => {
    useAuthStore.setState({ accessToken: 'user-token' });
    const mockFetch = vi.fn().mockResolvedValue(makeSseResponse([]));
    vi.stubGlobal('fetch', mockFetch);

    await collectFrames(sendMessage('s1', { content: 'hi' }));

    expect(mockFetch).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: 'Bearer user-token' }),
      }),
    );
  });

  it('passes the abort signal through to fetch', async () => {
    const controller = new AbortController();
    const mockFetch = vi.fn().mockResolvedValue(makeSseResponse([]));
    vi.stubGlobal('fetch', mockFetch);

    await collectFrames(sendMessage('s1', { content: 'hi' }, controller.signal));

    expect(mockFetch).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({ signal: controller.signal }),
    );
  });
});

describe('confirmBulkStream', () => {
  afterEach(() => { vi.unstubAllGlobals(); });

  it('POSTs to the confirm endpoint and yields SSE frames', async () => {
    const mockFetch = vi.fn().mockResolvedValue(
      makeSseResponse(['event: ai:done\ndata: {"message":{}}\n\n']),
    );
    vi.stubGlobal('fetch', mockFetch);

    const frames = await collectFrames(confirmBulkStream('s1', 'c1'));

    expect(mockFetch).toHaveBeenCalledWith(
      '/api/ai/sessions/s1/confirm/c1',
      expect.objectContaining({ method: 'POST' }),
    );
    expect(frames).toHaveLength(1);
    expect(frames[0].event).toBe('ai:done');
  });
});
