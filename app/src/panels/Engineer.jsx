import { useRef, useEffect } from 'preact/hooks';
import { useSignal } from '@preact/signals';
import { messages, isStreaming, activeTools, sendMessage } from '../state/engineer.js';
import { formatTimestamp } from '../lib/format.js';

function ToolIndicator({ tools }) {
  if (!tools || tools.length === 0) return null;
  return (
    <div class="eng-tools">
      {tools.map((t, i) => (
        <span
          key={i}
          class={`eng-tool eng-tool--${t.status}`}
          title={t.name}
        >
          {t.status === 'running' && <span class="eng-tool-spinner" />}
          {t.status === 'done' && <span class="eng-tool-check">✓</span>}
          {t.status === 'error' && <span class="eng-tool-err">✗</span>}
          {t.label}
        </span>
      ))}
    </div>
  );
}

export function Engineer() {
  const inputText = useSignal('');
  const scrollRef = useRef(null);

  // Auto-scroll to bottom on new messages or streaming updates
  useEffect(() => {
    const el = scrollRef.current;
    if (el) {
      el.scrollTop = el.scrollHeight;
    }
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

  const msgList = messages.value;

  return (
    <div class="panel panel-engineer">
      <div class="panel-header">
        PIT WALL RADIO
        {isStreaming.value && <span class="eng-streaming-dot" />}
        {activeTools.value.length > 0 && (
          <span class="eng-active-tool">{activeTools.value[activeTools.value.length - 1]}</span>
        )}
      </div>
      <div class="eng-messages" ref={scrollRef}>
        {msgList.length === 0 ? (
          <div class="eng-empty">
            <div class="eng-empty-label">RADIO SILENT</div>
            <div class="eng-empty-hint">Transmit to your race engineer below</div>
          </div>
        ) : (
          msgList.map((msg, i) => (
            <div
              key={i}
              class={`eng-msg eng-msg--${msg.role.toLowerCase()}${msg.proactive ? ' eng-msg--proactive' : ''}`}
            >
              <div class="eng-msg-header">
                <span class="eng-msg-role">
                  {msg.role}
                  {msg.proactive && <span class="eng-proactive-badge">AUTO</span>}
                </span>
                <span class="eng-msg-ts">{formatTimestamp(msg.ts)}</span>
              </div>
              {msg.tools && msg.tools.length > 0 && (
                <ToolIndicator tools={msg.tools} />
              )}
              <div class="eng-msg-text">
                {msg.text}
                {msg.streaming && <span class="eng-cursor" />}
              </div>
            </div>
          ))
        )}
      </div>
      <form class="eng-input-row" onSubmit={handleSubmit}>
        <input
          type="text"
          class="eng-input"
          placeholder="Talk to your engineer..."
          value={inputText}
          onInput={(e) => { inputText.value = e.target.value; }}
          onKeyDown={handleKeyDown}
          disabled={isStreaming.value}
        />
        <button
          type="submit"
          class="eng-tx-btn"
          disabled={isStreaming.value}
          title="Transmit"
        >
          TX
        </button>
      </form>
    </div>
  );
}
