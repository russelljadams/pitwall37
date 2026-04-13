/**
 * SessionBrowser — browse all sessions, filter by track, sort columns.
 */
import { useEffect } from 'preact/hooks';
import {
  sessions, sessionsLoading, sessionsError, trackFilter,
  sortField, sortDir, getTracks, getFilteredSessions, toggleSort, loadSessions,
} from '../state/sessions.js';
import {
  selectedSessionId, selectSession, compareSessionId, setCompareSession,
} from '../state/selection.js';
import { PanelShell } from '../components/PanelShell.jsx';
import { formatLapTime, formatDate } from '../lib/format.js';

const COLUMNS = [
  { key: 'session_date', label: 'Date', w: '70px' },
  { key: 'track', label: 'Track', w: '1fr' },
  { key: 'best_lap_time', label: 'Best', w: '75px' },
  { key: 'timed_laps', label: 'Laps', w: '40px' },
  { key: 'air_temp', label: 'Temp', w: '40px' },
];

function SortArrow({ field }) {
  if (sortField.value !== field) return null;
  return <span class="sb-sort-arrow">{sortDir.value === 'asc' ? '\u25B2' : '\u25BC'}</span>;
}

export function SessionBrowser() {
  useEffect(() => { loadSessions(); }, []);

  const tracks = getTracks();
  const filtered = getFilteredSessions();
  const selId = selectedSessionId.value;
  const cmpId = compareSessionId.value;

  function handleRowClick(e, session) {
    if (e.shiftKey) {
      setCompareSession(session.id);
    } else {
      selectSession(session.id);
    }
  }

  return (
    <PanelShell
      title="SESSIONS"
      badge={sessionsLoading.value ? '...' : sessions.value.length}
    >
      {/* Track filter pills */}
      {tracks.length > 1 && (
        <div class="sb-filters">
          <button
            class={`sb-filter-pill ${!trackFilter.value ? 'active' : ''}`}
            onClick={() => { trackFilter.value = null; }}
          >
            ALL
          </button>
          {tracks.map(t => (
            <button
              key={t}
              class={`sb-filter-pill ${trackFilter.value === t ? 'active' : ''}`}
              onClick={() => { trackFilter.value = trackFilter.value === t ? null : t; }}
            >
              {t}
            </button>
          ))}
        </div>
      )}

      {sessionsError.value && (
        <div class="sb-error">{sessionsError.value}</div>
      )}

      {sessionsLoading.value && !sessions.value.length ? (
        <div class="sb-loading">LOADING SESSIONS...</div>
      ) : (
        <table class="sb-table">
          <thead>
            <tr>
              {COLUMNS.map(col => (
                <th
                  key={col.key}
                  class={sortField.value === col.key ? 'sb-sorted' : ''}
                  onClick={() => toggleSort(col.key)}
                >
                  {col.label}
                  <SortArrow field={col.key} />
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filtered.map(s => {
              const isSel = s.id === selId;
              const isCmp = s.id === cmpId;
              return (
                <tr
                  key={s.id}
                  class={`${isSel ? 'sb-selected' : ''} ${isCmp ? 'sb-compare' : ''}`}
                  onClick={(e) => handleRowClick(e, s)}
                >
                  <td class="sb-date">{formatDate(s.session_date)}</td>
                  <td class="sb-track" title={s.track_config || s.track}>{s.track}</td>
                  <td class="sb-best">{formatLapTime(s.best_lap_time)}</td>
                  <td class="sb-laps-count">{s.timed_laps || s.total_laps || '-'}</td>
                  <td class="sb-temp">
                    {s.air_temp != null ? `${Math.round(s.air_temp)}\u00B0` : '-'}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </PanelShell>
  );
}
