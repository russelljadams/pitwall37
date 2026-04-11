import { useRef, useEffect } from 'preact/hooks';
import { useSignal } from '@preact/signals';
import { messages, isStreaming, sendMessage } from '../state/engineer.js';
import { formatTimestamp } from '../lib/format.js';

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
      </div>
      <div class="eng-messages" ref={scrollRef}>
        {msgList.length === 0 ? (
          <div class="eng-empty">
            <div class="eng-empty-label">RADIO SILENT</div>
            <div class="eng-empty-hint">Transmit to your race engineer below</div>
          </div>
        ) : (
          msgList.map((msg, i) => (
            <div key={i} class={`eng-msg eng-msg--${msg.role.toLowerCase()}`}>
              <div class="eng-msg-header">
                <span class="eng-msg-role">{msg.role}</span>
                <span class="eng-msg-ts">{formatTimestamp(msg.ts)}</span>
              </div>
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
