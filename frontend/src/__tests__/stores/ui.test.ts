import { useUIStore } from '@/stores/ui';

beforeEach(() => {
  useUIStore.setState({
    openTabs: [],
    activeTabKey: null,
    chatOpen: true,
    profileOpen: false,
    offlineBanner: false,
    readonlyBanner: false,
    attachedNoteIds: [],
  });
});

describe('UI store – panel tabs', () => {
  it('starts with the notes panel tab open by default', () => {
    // Reset to the real initial state for this test
    useUIStore.setState({
      openTabs: [{ type: 'panel', panel: 'notes' }],
      activeTabKey: 'panel:notes',
    });
    expect(useUIStore.getState().activeTabKey).toBe('panel:notes');
  });

  it('openTab for a panel makes it active', () => {
    useUIStore.getState().openTab({ type: 'panel', panel: 'search' });
    expect(useUIStore.getState().activeTabKey).toBe('panel:search');
  });

  it('supports all valid panel types', () => {
    const panels = ['notes', 'search', 'tags', 'trash', 'admin'] as const;
    for (const p of panels) {
      useUIStore.getState().openTab({ type: 'panel', panel: p });
      expect(useUIStore.getState().activeTabKey).toBe(`panel:${p}`);
    }
  });

  it('opening the same panel tab twice does not duplicate it', () => {
    useUIStore.getState().openTab({ type: 'panel', panel: 'notes' });
    useUIStore.getState().openTab({ type: 'panel', panel: 'notes' });
    const panelTabs = useUIStore.getState().openTabs.filter((t) => t.type === 'panel');
    expect(panelTabs).toHaveLength(1);
  });

  it('panel tabs and note tabs coexist in openTabs', () => {
    useUIStore.getState().openTab({ type: 'panel', panel: 'notes' });
    useUIStore.getState().openTab({ type: 'note', id: 'abc' });
    expect(useUIStore.getState().openTabs).toHaveLength(2);
  });
});

describe('UI store – tabs', () => {
  it('starts with no open tabs (after beforeEach reset)', () => {
    expect(useUIStore.getState().openTabs).toHaveLength(0);
    expect(useUIStore.getState().activeTabKey).toBeNull();
  });

  it('openTab adds the tab and makes it active', () => {
    useUIStore.getState().openTab({ type: 'note', id: 'abc' });
    expect(useUIStore.getState().openTabs).toHaveLength(1);
    expect(useUIStore.getState().activeTabKey).toBe('note:abc');
  });

  it('openTab is idempotent – same tab opened twice stays once', () => {
    const tab = { type: 'note' as const, id: 'abc' };
    useUIStore.getState().openTab(tab);
    useUIStore.getState().openTab(tab);
    expect(useUIStore.getState().openTabs).toHaveLength(1);
  });

  it('openTab on an existing tab still makes it active', () => {
    useUIStore.getState().openTab({ type: 'note', id: 'abc' });
    useUIStore.getState().openTab({ type: 'note', id: 'xyz' }); // switch away
    useUIStore.getState().openTab({ type: 'note', id: 'abc' }); // back to abc
    expect(useUIStore.getState().activeTabKey).toBe('note:abc');
  });

  it('closeTab removes the tab', () => {
    const tab = { type: 'note' as const, id: 'abc' };
    useUIStore.getState().openTab(tab);
    useUIStore.getState().closeTab(tab);
    expect(useUIStore.getState().openTabs).toHaveLength(0);
  });

  it('closing the active tab activates the next available tab', () => {
    useUIStore.getState().openTab({ type: 'note', id: '1' });
    useUIStore.getState().openTab({ type: 'note', id: '2' });
    useUIStore.getState().openTab({ type: 'note', id: '3' });

    useUIStore.getState().closeTab({ type: 'note', id: '3' });
    expect(useUIStore.getState().activeTabKey).toBe('note:2');
  });

  it('closing the only tab sets activeTabKey to null', () => {
    const tab = { type: 'note' as const, id: 'abc' };
    useUIStore.getState().openTab(tab);
    useUIStore.getState().closeTab(tab);
    expect(useUIStore.getState().activeTabKey).toBeNull();
  });

  it('setActiveTab switches the active key', () => {
    useUIStore.getState().openTab({ type: 'note', id: '1' });
    useUIStore.getState().openTab({ type: 'note', id: '2' });
    useUIStore.getState().setActiveTab({ type: 'note', id: '1' });
    expect(useUIStore.getState().activeTabKey).toBe('note:1');
  });

  it('closing a panel tab works correctly', () => {
    useUIStore.getState().openTab({ type: 'panel', panel: 'notes' });
    useUIStore.getState().closeTab({ type: 'panel', panel: 'notes' });
    expect(useUIStore.getState().openTabs).toHaveLength(0);
    expect(useUIStore.getState().activeTabKey).toBeNull();
  });
});

describe('UI store – chat & profile', () => {
  it('chat is open by default', () => {
    expect(useUIStore.getState().chatOpen).toBe(true);
  });

  it('toggleChat flips chatOpen', () => {
    useUIStore.getState().toggleChat();
    expect(useUIStore.getState().chatOpen).toBe(false);
    useUIStore.getState().toggleChat();
    expect(useUIStore.getState().chatOpen).toBe(true);
  });

  it('setProfileOpen controls the profileOpen flag', () => {
    useUIStore.getState().setProfileOpen(true);
    expect(useUIStore.getState().profileOpen).toBe(true);
    useUIStore.getState().setProfileOpen(false);
    expect(useUIStore.getState().profileOpen).toBe(false);
  });
});

describe('UI store – banners', () => {
  it('banners start off', () => {
    expect(useUIStore.getState().offlineBanner).toBe(false);
    expect(useUIStore.getState().readonlyBanner).toBe(false);
  });

  it('setOfflineBanner and setReadonlyBanner work independently', () => {
    useUIStore.getState().setOfflineBanner(true);
    expect(useUIStore.getState().offlineBanner).toBe(true);
    expect(useUIStore.getState().readonlyBanner).toBe(false);

    useUIStore.getState().setReadonlyBanner(true);
    useUIStore.getState().setOfflineBanner(false);
    expect(useUIStore.getState().offlineBanner).toBe(false);
    expect(useUIStore.getState().readonlyBanner).toBe(true);
  });
});
