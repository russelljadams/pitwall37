/**
 * AgentChat — MGS codec-style chat with animated alien face.
 * Context-aware: shows what the agent can see from the current selection.
 */
import { useRef, useEffect } from 'preact/hooks';
import { useSignal } from '@preact/signals';
import {
  messages, isStreaming, activeTools, isConnected, sendMessage,
} from '../state/engineer.js';
import { contextSummary } from '../state/selection.js';
import { AlienFace } from '../components/AlienFace.jsx';
import { formatTimestamp } from '../lib/format.js';

function ToolPills({ tools }) {
  if (!tools || tools.length === 0) return null;
  return (
    <div class="ac-tools">
      {tools.map((t, i) => (
        <span key={i} class={`ac-tool ac-tool--${t.status}`}>
          {t.status === 'running' && <span class="ac-tool-spinner" />}
          {t.status === 'done' && '\u2713'}
          {t.status === 'error' && '\u2717'}
          {' '}{t.label}
        </span>
      ))}
    </div>
  );
}

/** Simple markdown-ish rendering for agent messages */
function renderText(text) {
  if (!text) return '';

  // Handle code blocks
  const parts = text.split(/(```[\s\S]*?```)/g);
  return parts.map((part, i) => {
    if (part.startsWith('```')) {
      const code = part.replace(/^```\w*\n?/, '').replace(/\n?```$/, '');
      return <pre key={i}><code>{code}</code></pre>;
    }
    // Handle inline code
    const inlined = part.split(/(`[^`]+`)/g).map((seg, j) => {
      if (seg.startsWith('`') && seg.endsWith('`')) {
        return <code key={j}>{seg.slice(1, -1)}</code>;
      }
      // Handle bold
      const bolded = seg.split(/(\*\*[^*]+\*\*)/g).map((bs, k) => {
        if (bs.startsWith('**') && bs.endsWith('**')) {
          return <strong key={k}>{bs.slice(2, -2)}</strong>;
        }
        return bs;
      });
      return bolded;
    });
    return <span key={i}>{inlined}</span>;
  });
}

export function AgentChat() {
  const inputText = useSignal('');
  const scrollRef = useRef(null);

  const msgList = messages.value;
  const streaming = isStreaming.value;
  const connected = isConnected.value;
  const tools = activeTools.value;
  const ctxStr = contextSummary.value;

  // Auto-scroll
  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  });

  function handleSubmit(e) {
    e.preventDefault();
    const text = inputText.value.trim();
    if (!text) return;
    sendMessage(text);
    inputText.value = '';
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  }

  const isSpeaking = streaming && msgList.length > 0 && msgList[msgList.length - 1].streaming;
  const isTooling = tools.length > 0;

  return (
    <div class="panel ac-container">
      <div class="panel-header">
        <span class="panel-title" style={{ color: 'var(--pw-cyan)' }}>A1I3N-37</span>
        {streaming && <span class="ac-streaming-dot" style={{
          width: '6px', height: '6px', borderRadius: '50%',
          background: 'var(--pw-cyan)', animation: 'ac-pulse 1s ease-in-out infinite',
          boxShadow: '0 0 6px var(--pw-cyan-glow)',
        }} />}
        <span class="panel-header-spacer" />
        <span class="panel-badge" style={{
          color: connected ? 'var(--pw-green)' : 'var(--pw-text-muted)',
        }}>
          {connected ? 'LINKED' : 'OFFLINE'}
        </span>
      </div>

      <div class="ac-codec">
        {/* Alien face frame */}
        <div class="ac-face-frame">
          <div class="ac-face-label">A1I3N-37</div>
          <AlienFace speaking={isSpeaking} toolActive={isTooling} />
          <div class={`ac-face-status ${streaming ? 'ac-streaming' : 'ac-online'}`}>
            {streaming ? 'TRANSMITTING' : 'STANDBY'}
          </div>
          <div class="ac-scanlines" />
        </div>

        {/* Chat messages */}
        <div class="ac-chat">
          <div class="ac-messages" ref={scrollRef}>
            {msgList.length === 0 ? (
              <div class="ac-empty">
                <div class="ac-empty-label">CHANNEL OPEN</div>
                <div class="ac-empty-hint">Ask your race engineer anything</div>
              </div>
            ) : (
              msgList.map((msg, i) => (
                <div
                  key={i}
                  class={`ac-msg ac-msg--${msg.role}`}
                >
                  <div class="ac-msg-role">
                    {msg.role === 'driver' ? 'DRIVER' : 'A1I3N'}
                    {msg.ts && (
                      <span style={{
                        marginLeft: '8px',
                        fontSize: '9px',
                        fontWeight: 400,
                        color: 'var(--pw-text-muted)',
                      }}>
                        {formatTimestamp(msg.ts)}
                      </span>
                    )}
                  </div>
                  {msg.tools && <ToolPills tools={msg.tools} />}
                  <div class="ac-msg-text">
                    {renderText(msg.text)}
                    {msg.streaming && <span class="ac-cursor" />}
                  </div>
                </div>
              ))
            )}
          </div>

          {/* Context indicator */}
          {ctxStr && (
            <div class="ac-context">
              <span class="ac-context-label">CTX</span>
              <span class="ac-context-text">{ctxStr}</span>
            </div>
          )}

          {/* Input */}
          <form class="ac-input-row" onSubmit={handleSubmit}>
            <input
              type="text"
              class="ac-input"
              placeholder="Talk to your engineer..."
              value={inputText}
              onInput={(e) => { inputText.value = e.target.value; }}
              onKeyDown={handleKeyDown}
              disabled={streaming}
            />
            <button
              type="submit"
              class="ac-send-btn"
              disabled={streaming}
            >
              TX
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
