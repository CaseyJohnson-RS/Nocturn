import { create } from 'zustand';
import type { AIMessageResponse, Action } from '@/types/api';

interface ChatState {
  activeSessionId: string | null;
  messages: AIMessageResponse[];
  isGenerating: boolean;
  streamingContent: string;
  streamingActions: Action[];
  abortController: AbortController | null;

  setActiveSession: (id: string | null) => void;
  setMessages: (msgs: AIMessageResponse[]) => void;
  addMessage: (msg: AIMessageResponse) => void;
  replaceMessage: (msg: AIMessageResponse) => void;
  setGenerating: (v: boolean, controller?: AbortController) => void;
  appendDelta: (delta: string) => void;
  pushStreamingAction: (action: Action) => void;
  clearStreaming: () => void;
  cancel: () => void;
}

export const useChatStore = create<ChatState>((set, get) => ({
  activeSessionId: null,
  messages: [],
  isGenerating: false,
  streamingContent: '',
  streamingActions: [],
  abortController: null,

  setActiveSession: (id) =>
    set({ activeSessionId: id, messages: [], streamingContent: '', streamingActions: [] }),

  setMessages: (msgs) => set({ messages: msgs }),

  addMessage: (msg) =>
    set((s) => ({ messages: [...s.messages, msg] })),

  replaceMessage: (msg) =>
    set((s) => ({
      messages: s.messages.map((m) => (m.id === msg.id ? msg : m)),
    })),

  setGenerating: (isGenerating, controller) =>
    set({ isGenerating, abortController: controller ?? null }),

  appendDelta: (delta) =>
    set((s) => ({ streamingContent: s.streamingContent + delta })),

  pushStreamingAction: (action) =>
    set((s) => ({ streamingActions: [...s.streamingActions, action] })),

  clearStreaming: () =>
    set({ streamingContent: '', streamingActions: [], abortController: null }),

  cancel: () => {
    const { abortController } = get();
    abortController?.abort();
  },
}));
