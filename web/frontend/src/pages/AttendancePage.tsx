import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { useAuth } from '@/contexts/AuthContext';
import { AttendanceStatsCard } from '@/components/Attendance/AttendanceStats';
import type { AttendanceHistory, Absence, RaidEvent } from '@/types';

type Tab = 'mine' | 'absences' | 'report' | 'event';

const STATUS_STYLES: Record<string, string> = {
  present: 'bg-green-500/20 text-green-400',
  late:    'bg-yellow-500/20 text-yellow-400',
  excused: 'bg-blue-500/20 text-blue-400',
  absent:  'bg-red-500/20 text-red-400',
};

export function AttendancePage() {
  const { isRaidLeader, isOfficer } = useAuth();
  const [tab, setTab] = useState<Tab>('mine');

  const tabs = [
    { id: 'mine' as Tab, label: 'My Stats' },
    { id: 'absences' as Tab, label: 'Absences' },
    ...(isRaidLeader ? [{ id: 'event' as Tab, label: 'By Event' }] : []),
    ...(isOfficer    ? [{ id: 'report' as Tab, label: 'Low Attendance' }] : []),
  ];

  return (
    <div className="p-4 lg:p-8 max-w-4xl mx-auto space-y-6">
      <h1 className="text-2xl font-extrabold">Attendance</h1>

      {/* Tab bar */}
      <div className="flex gap-1 p-1 glass rounded-xl w-fit flex-wrap">
        {tabs.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`px-4 py-2 rounded-lg text-sm font-semibold transition-all ${
              tab === t.id ? 'bg-indigo-600 text-white' : 'text-gray-400 hover:text-white'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === 'mine'     && <MyStatsTab />}
      {tab === 'absences' && <AbsencesTab />}
      {tab === 'event'    && isRaidLeader && <EventAttendanceTab />}
      {tab === 'report'   && isOfficer && <LowAttendanceTab />}
    </div>
  );
}

// ── My Stats ──────────────────────────────────────────────────────────────────

function MyStatsTab() {
  const { data: stats } = useQuery({
    queryKey: ['attendance-me'],
    queryFn: () => api.get('/api/attendance/me').then((r) => r.data),
  });

  const { data: history = [] } = useQuery<AttendanceHistory[]>({
    queryKey: ['attendance-history'],
    queryFn: () => api.get('/api/attendance/me/history').then((r) => r.data),
  });

  return (
    <div className="space-y-6">
      {stats
        ? <AttendanceStatsCard stats={stats} />
        : <div className="glass rounded-xl p-8 text-center text-gray-500 text-sm">No attendance data yet</div>
      }

      <div>
        <h2 className="font-bold text-lg mb-3">Recent Events</h2>
        {history.length === 0
          ? <div className="glass rounded-xl p-8 text-center text-gray-500 text-sm">No history yet</div>
          : (
            <div className="glass rounded-xl divide-y divide-gray-700/50">
              {history.map((h) => (
                <div
                  key={`${h.event_id}-${h.timestamp}`}
                  className="flex items-center gap-3 p-3 hover:bg-white/[0.02] transition-colors"
                >
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium truncate">{h.event_name}</p>
                    <div className="flex items-center gap-2 mt-0.5">
                      <span className="text-xs text-gray-500">{h.event_date}</span>
                      <span className="text-xs text-gray-600">·</span>
                      <span className="text-xs text-gray-500">{h.event_type}</span>
                    </div>
                  </div>
                  <span className={`badge text-xs shrink-0 ${STATUS_STYLES[h.status] ?? 'bg-gray-500/20 text-gray-400'}`}>
                    {h.status}
                  </span>
                </div>
              ))}
            </div>
          )
        }
      </div>
    </div>
  );
}

// ── Absences ──────────────────────────────────────────────────────────────────

function AbsencesTab() {
  const { data: events = [] } = useQuery<RaidEvent[]>({
    queryKey: ['events'],
    queryFn: () => api.get('/api/events?limit=20').then((r) => r.data),
  });

  const { data: myAbsences = [], refetch } = useQuery<Absence[]>({
    queryKey: ['absences-me'],
    queryFn: () => api.get('/api/absences/me').then((r) => r.data),
  });

  const [selectedEvent, setSelectedEvent] = useState('');
  const [reason, setReason] = useState('');
  const [saving, setSaving] = useState(false);
  const [success, setSuccess] = useState('');

  async function submitAbsence(e: React.FormEvent) {
    e.preventDefault();
    if (!selectedEvent || !reason.trim()) return;
    setSaving(true);
    setSuccess('');
    try {
      await api.post('/api/absences', { event_id: parseInt(selectedEvent), reason });
      setReason('');
      setSelectedEvent('');
      setSuccess('Absence submitted!');
      refetch();
      setTimeout(() => setSuccess(''), 3000);
    } catch (err: any) {
      alert(err.response?.data?.detail ?? 'Failed to submit');
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-6">
      {/* Submit form */}
      <div className="glass rounded-xl p-5">
        <h2 className="font-bold text-base mb-4">Submit Absence Request</h2>
        <form onSubmit={submitAbsence} className="space-y-3">
          <div>
            <label className="text-xs text-gray-400 mb-1 block">Upcoming Event *</label>
            <select
              className="input"
              value={selectedEvent}
              onChange={(e) => setSelectedEvent(e.target.value)}
              required
            >
              <option value="">Select event…</option>
              {events.map((ev) => (
                <option key={ev.event_id} value={ev.event_id}>
                  {ev.event_name} — {ev.event_date}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-xs text-gray-400 mb-1 block">Reason *</label>
            <input
              className="input"
              placeholder="Travelling, family commitment, work…"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              required
            />
          </div>
          {success && <p className="text-green-400 text-xs">{success}</p>}
          <button type="submit" disabled={saving || !selectedEvent} className="btn-primary text-sm flex items-center gap-2">
            {saving && <span className="w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin" />}
            Submit Absence
          </button>
        </form>
      </div>

      {/* My submitted absences */}
      <div>
        <h2 className="font-bold text-base mb-3">My Submitted Absences</h2>
        {myAbsences.length === 0
          ? <div className="glass rounded-xl p-8 text-center text-gray-500 text-sm">No absences submitted</div>
          : (
            <div className="glass rounded-xl divide-y divide-gray-700/50">
              {myAbsences.map((a) => (
                <div key={a.absence_id} className="p-3 flex items-start gap-3">
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium truncate">{a.event_name ?? `Event #${a.event_id}`}</p>
                    <p className="text-xs text-gray-400 mt-0.5">{a.event_date}</p>
                    <p className="text-xs text-gray-300 mt-1 italic">"{a.reason}"</p>
                  </div>
                  <p className="text-xs text-gray-600 shrink-0">
                    {new Date(a.submitted_at).toLocaleDateString()}
                  </p>
                </div>
              ))}
            </div>
          )
        }
      </div>
    </div>
  );
}

// ── Per-Event Attendance (Raid Leaders) ───────────────────────────────────────

function EventAttendanceTab() {
  const [selectedEvent, setSelectedEvent] = useState('');

  const { data: events = [] } = useQuery<RaidEvent[]>({
    queryKey: ['events'],
    queryFn: () => api.get('/api/events?limit=50').then((r) => r.data),
  });

  const { data: records = [], isFetching } = useQuery({
    queryKey: ['event-attendance', selectedEvent],
    queryFn: () => api.get(`/api/attendance/event/${selectedEvent}`).then((r) => r.data),
    enabled: !!selectedEvent,
  });

  const { data: absences = [] } = useQuery({
    queryKey: ['event-absences-tab', selectedEvent],
    queryFn: () => api.get(`/api/absences/event/${selectedEvent}`).then((r) => r.data),
    enabled: !!selectedEvent,
  });

  const grouped = (records as any[]).reduce<Record<string, any[]>>((acc, r) => {
    (acc[r.status] ??= []).push(r);
    return acc;
  }, {});

  return (
    <div className="space-y-5">
      <div>
        <label className="text-xs text-gray-400 mb-1 block">Select Event</label>
        <select className="input max-w-sm" value={selectedEvent} onChange={(e) => setSelectedEvent(e.target.value)}>
          <option value="">Choose event…</option>
          {events.map((ev) => (
            <option key={ev.event_id} value={ev.event_id}>
              {ev.event_name} — {ev.event_date}
            </option>
          ))}
        </select>
      </div>

      {isFetching && <p className="text-gray-500 text-sm">Loading…</p>}

      {selectedEvent && !isFetching && records.length === 0 && (
        <div className="glass rounded-xl p-6 text-center text-gray-500 text-sm">
          No attendance recorded for this event yet
        </div>
      )}

      {records.length > 0 && (
        <div className="glass rounded-xl p-4 space-y-4">
          {(['present','late','excused','absent'] as const).map((status) => {
            const items = grouped[status] ?? [];
            if (items.length === 0) return null;
            return (
              <div key={status}>
                <h3 className={`text-xs font-bold uppercase tracking-wider mb-2 ${
                  status === 'present' ? 'text-green-400' :
                  status === 'late' ? 'text-yellow-400' :
                  status === 'excused' ? 'text-blue-400' : 'text-red-400'
                }`}>
                  {status} ({items.length})
                </h3>
                <div className="flex flex-wrap gap-2">
                  {items.map((r: any) => (
                    <span key={r.attendance_id} className="text-sm glass rounded-lg px-2.5 py-1">
                      {r.char_name || r.discord_id}
                    </span>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {absences.length > 0 && (
        <div className="glass rounded-xl p-4">
          <h3 className="text-xs font-bold uppercase tracking-wider mb-3 text-blue-400">
            Absence Requests ({absences.length})
          </h3>
          <div className="space-y-2">
            {(absences as any[]).map((a) => (
              <div key={a.absence_id} className="flex items-start gap-2 text-sm">
                <span className="font-mono text-xs text-gray-500 shrink-0">{a.discord_id}</span>
                <span className="text-gray-300">{a.reason}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Low Attendance Report (Officers) ─────────────────────────────────────────

function LowAttendanceTab() {
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [queryDates, setQueryDates] = useState<{ start: string; end: string }>({ start: '', end: '' });

  const { data, isFetching, refetch } = useQuery({
    queryKey: ['attendance-report', queryDates],
    queryFn: () => {
      const params = new URLSearchParams();
      if (queryDates.start) params.append('start_date', queryDates.start);
      if (queryDates.end)   params.append('end_date', queryDates.end);
      return api.get(`/api/attendance/report?${params}`).then((r) => r.data);
    },
  });

  function applyFilter() {
    setQueryDates({ start: startDate, end: endDate });
  }

  const members = data?.members ?? [];
  const threshold = data?.threshold ?? 75;

  return (
    <div className="space-y-5">
      {/* Filters */}
      <div className="glass rounded-xl p-4 flex flex-wrap items-end gap-3">
        <div>
          <label className="text-xs text-gray-400 mb-1 block">From</label>
          <input type="date" className="input py-1.5 text-sm" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
        </div>
        <div>
          <label className="text-xs text-gray-400 mb-1 block">To</label>
          <input type="date" className="input py-1.5 text-sm" value={endDate} onChange={(e) => setEndDate(e.target.value)} />
        </div>
        <button onClick={applyFilter} className="btn-primary text-sm">Apply Filter</button>
        {(startDate || endDate) && (
          <button
            onClick={() => { setStartDate(''); setEndDate(''); setQueryDates({ start: '', end: '' }); }}
            className="btn-secondary text-sm"
          >
            Clear
          </button>
        )}
      </div>

      {isFetching && <p className="text-gray-500 text-sm">Loading report…</p>}

      {!isFetching && members.length === 0 && (
        <div className="glass rounded-xl p-8 text-center text-gray-500 text-sm">
          No members below the {threshold}% threshold 🎉
        </div>
      )}

      {members.length > 0 && (
        <div>
          <h2 className="font-bold text-base mb-3 text-orange-400">
            ⚠️ {members.length} member{members.length !== 1 ? 's' : ''} below {threshold}%
          </h2>
          <div className="glass rounded-xl divide-y divide-gray-700/50">
            {members.map((m: any) => (
              <div key={m.discord_id} className="flex items-center gap-3 p-3">
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-mono text-gray-300 truncate">{m.discord_id}</p>
                  <div className="flex items-center gap-2 mt-0.5">
                    <span className="text-xs text-gray-500">
                      {m.present + m.late} / {m.total - m.excused} attended
                    </span>
                    {m.excused > 0 && (
                      <span className="text-xs text-blue-400">({m.excused} excused)</span>
                    )}
                  </div>
                </div>
                <div className="shrink-0 text-right">
                  <p className="text-lg font-extrabold text-red-400">{m.percentage}%</p>
                  <p className="text-xs text-gray-500">{m.total} events</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
