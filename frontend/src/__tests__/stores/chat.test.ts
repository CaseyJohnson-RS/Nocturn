import { useChatStore } from '@/stores/chat';
import type { AIMessageResponse, Proposal } from '@/types/api';

function makeMsg(overrides: Partial<AIMessageResponse> = {}): AIMessageResponse {
  return {
    id: 'msg-1',
    session_id: 'sess-1',
    role: 'user',
    content: 'Hello',
    actions: null,
    attached_note_ids: null,
    created_at: '2024-01-01T00:00:00Z',
    ...overrides,
  };
}

beforeEach(() => {
  useChatStore.setState({
    activeSessionId: null,
    messages: [],
    isGenerating: false,
    streamingContent: '',
    streamingActions: [],
    abortController: null,
  });
});

describe('Chat store – session', () => {
  it('starts with no active session', () => {
    expect(useChatStore.getState().activeSessionId).toBeNull();
  });

  it('setActiveSession stores the id', () => {
    useChatStore.getState().setActiveSession('sess-99');
    expect(useChatStore.getState().activeSessionId).toBe('sess-99');
  });

  it('setActiveSession clears messages and streaming state', () => {
    useChatStore.setState({
      messages: [makeMsg()],
      streamingContent: 'partial…',
      streamingActions: [],
    });
    useChatStore.getState().setActiveSession('new-sess');
    expect(useChatStore.getState().messages).toHaveLength(0);
    expect(useChatStore.getState().streamingContent).toBe('');
  });
});

describe('Chat store – messages', () => {
  it('setMessages replaces the list', () => {
    const msgs = [makeMsg({ id: 'a' }), makeMsg({ id: 'b' })];
    useChatStore.getState().setMessages(msgs);
    expect(useChatStore.getState().messages).toHaveLength(2);
  });

  it('addMessage appends to the list', () => {
    useChatStore.getState().addMessage(makeMsg({ id: 'a' }));
    useChatStore.getState().addMessage(makeMsg({ id: 'b' }));
    expect(useChatStore.getState().messages).toHaveLength(2);
    expect(useChatStore.getState().messages[1].id).toBe('b');
  });

  it('replaceMessage swaps the matching message in place', () => {
    useChatStore.setState({ messages: [makeMsg({ id: 'x', content: 'old' })] });
    useChatStore.getState().replaceMessage(makeMsg({ id: 'x', content: 'new' }));
    expect(useChatStore.getState().messages[0].content).toBe('new');
  });

  it('replaceMessage leaves other messages untouched', () => {
    useChatStore.setState({
      messages: [makeMsg({ id: 'a' }), makeMsg({ id: 'b', content: 'keep' })],
    });
    useChatStore.getState().replaceMessage(makeMsg({ id: 'a', content: 'changed' }));
    expect(useChatStore.getState().messages[1].content).toBe('keep');
  });

  it('replaceMessage on unknown id leaves list unchanged', () => {
    useChatStore.setState({ messages: [makeMsg({ id: 'a' })] });
    useChatStore.getState().replaceMessage(makeMsg({ id: 'does-not-exist' }));
    expect(useChatStore.getState().messages).toHaveLength(1);
  });
});

describe('Chat store – streaming', () => {
  it('appendDelta accumulates content', () => {
    useChatStore.getState().appendDelta('Hello');
    useChatStore.getState().appendDelta(' world');
    expect(useChatStore.getState().streamingContent).toBe('Hello world');
  });

  it('pushStreamingAction appends to the action list', () => {
    const action: Proposal = {
      type: 'proposal',
      id: 'p1',
      proposal_type: 'create_note',
      status: 'pending',
      data: {},
      summary: 'Create a new note',
      note_id: null,
    };
    useChatStore.getState().pushStreamingAction(action);
    expect(useChatStore.getState().streamingActions).toHaveLength(1);
  });

  it('clearStreaming resets content, actions, and controller', () => {
    const ctrl = new AbortController();
    useChatStore.setState({
      streamingContent: 'partial',
      streamingActions: [{ type: 'proposal' } as Proposal],
      abortController: ctrl,
    });
    useChatStore.getState().clearStreaming();
    const s = useChatStore.getState();
    expect(s.streamingContent).toBe('');
    expect(s.streamingActions).toHaveLength(0);
    expect(s.abortController).toBeNull();
  });
});

describe('Chat store – generating / cancel', () => {
  it('setGenerating(true) sets the flag and stores the controller', () => {
    const ctrl = new AbortController();
    useChatStore.getState().setGenerating(true, ctrl);
    expect(useChatStore.getState().isGenerating).toBe(true);
    expect(useChatStore.getState().abortController).toBe(ctrl);
  });

  it('setGenerating(false) without a controller clears the flag', () => {
    useChatStore.setState({ isGenerating: true });
    useChatStore.getState().setGenerating(false);
    expect(useChatStore.getState().isGenerating).toBe(false);
    expect(useChatStore.getState().abortController).toBeNull();
  });

  it('cancel calls abort() on the controller', () => {
    const ctrl = new AbortController();
    const spy = vi.spyOn(ctrl, 'abort');
    useChatStore.setState({ abortController: ctrl });
    useChatStore.getState().cancel();
    expect(spy).toHaveBeenCalledOnce();
  });

  it('cancel is a no-op when there is no controller', () => {
    expect(() => useChatStore.getState().cancel()).not.toThrow();
  });
});
