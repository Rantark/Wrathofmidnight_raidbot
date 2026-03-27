import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useParams, Link } from 'react-router-dom';
import {
  ArrowLeft, Users, Lock, Calendar, Plus, Pencil, Trash2,
  XCircle, BookTemplate, Save, PlayCircle, Loader2, MessageSquareWarning,
} from 'lucide-react';
import { api } from '@/lib/api';
import { EventCard } from '@/components/Events/EventCard';
import { EventFilters } from '@/components/Events/EventFilters';
import { AttendanceMarker } from '@/components/Attendance/AttendanceMarker';
import { Modal } from '@/components/common/Modal';
import { classColor, formatEventDate } from '@/lib/utils';
import { useAuth } from '@/contexts/AuthContext';
import type { RaidEvent, Signup, Template } from '@/types';
import { EVENT_TYPES } from '@/types';

// ─────────────────────────────────────────────────────────────────────────────
// Event List
// ─────────────────────────────────────────────────────────────────────────────

export function EventsList() {
  const [typeFilter, setTypeFilter] = useState('');
  const [showCreate, setShowCreate] = useState(false);
  const [showTemplates, setShowTemplates] = useState(false);
  const { isRaidLeader } = useAuth();
  const qc = useQueryClient();

  const { data: events = [], isLoading } = useQuery<RaidEvent[]>({
    queryKey: ['events'],
    queryFn: () => api.get('/api/events?limit=50').then((r) => r.data),
  });

  const filtered = typeFilter ? events.filter((e) => e.event_type === typeFilter) : events;

  return (
    <div className="p-4 lg:p-8 max-w-5xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-extrabold flex-1">Raid Events</h1>
        {isRaidLeader && (
          <>
            <button
              onClick={() => setShowTemplates(!showTemplates)}
              className="btn-secondary flex items-center gap-2 text-sm"
            >
              <BookTemplate size={14} /> Templates
            </button>
            <button
              onClick={() => setShowCreate(true)}
              className="btn-primary flex items-center gap-2 text-sm"
            >
              <Plus size={14} /> Create Raid
            </button>
          </>
        )}
        <EventFilters typeFilter={typeFilter} onTypeChange={setTypeFilter} />
      </div>

      {/* Templates panel */}
      {showTemplates && isRaidLeader && (
        <TemplatesPanel onEventCreated={() => qc.invalidateQueries({ queryKey: ['events'] })} />
      )}

      {/* Event list */}
      {isLoading ? (
        <div className="text-center text-gray-500 py-12">Loading…</div>
      ) : filtered.length === 0 ? (
        <div className="glass rounded-xl p-12 text-center text-gray-500">No upcoming events</div>
      ) : (
        <div className="grid gap-3 lg:gap-4">
          {filtered.map((e) => <EventCard key={e.event_id} event={e} />)}
        </div>
      )}

      {/* Create modal */}
      {showCreate && (
        <Modal title="Create Raid Event" onClose={() => setShowCreate(false)}>
          <EventForm
            onSuccess={() => {
              setShowCreate(false);
              qc.invalidateQueries({ queryKey: ['events'] });
            }}
            onCancel={() => setShowCreate(false)}
          />
        </Modal>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Event Detail
// ─────────────────────────────────────────────────────────────────────────────

export function EventDetail() {
  const { id } = useParams<{ id: string }>();
  const { isRaidLeader, isOfficer } = useAuth();
  const qc = useQueryClient();

  const [markMode, setMarkMode] = useState(false);
  const [showEdit, setShowEdit] = useState(false);
  const [showAbsenceForm, setShowAbsenceForm] = useState(false);
  const [cancelReason, setCancelReason] = useState('');
  const [showCancelConfirm, setShowCancelConfirm] = useState(false);
  const [savingAs, setSavingAs] = useState('');
  const [actionLoading, setActionLoading] = useState('');

  const { data: event, isLoading, refetch } = useQuery({
    queryKey: ['event', id],
    queryFn: () => api.get(`/api/events/${id}`).then((r) => r.data),
    enabled: !!id,
  });

  const { data: eventAbsences = [] } = useQuery({
    queryKey: ['event-absences', id],
    queryFn: () => api.get(`/api/absences/event/${id}`).then((r) => r.data),
    enabled: !!id && isRaidLeader,
  });

  const { data: eventAttendance = [] } = useQuery({
    queryKey: ['event-attendance', id],
    queryFn: () => api.get(`/api/attendance/event/${id}`).then((r) => r.data),
    enabled: !!id && isRaidLeader,
  });

  if (isLoading) return <div className="p-8 text-center text-gray-500">Loading…</div>;
  if (!event) return <div className="p-8 text-center text-gray-400">Event not found</div>;

  const signups: Signup[] = event.signups ?? [];
  const tanks    = signups.filter((s) => s.role === 'tank'   && s.signup_status === 'confirmed');
  const healers  = signups.filter((s) => s.role === 'healer' && s.signup_status === 'confirmed');
  const dps      = signups.filter((s) => s.role === 'dps'    && s.signup_status === 'confirmed');
  const bench    = signups.filter((s) => s.signup_status === 'bench');
  const tent     = signups.filter((s) => s.signup_status === 'tentative');
  const declined = signups.filter((s) => s.signup_status === 'declined');
  const confirmedCount = tanks.length + healers.length + dps.length;
  const isActive = event.status === 'active';

  async function doAction(action: string, fn: () => Promise<void>) {
    setActionLoading(action);
    try { await fn(); await refetch(); qc.invalidateQueries({ queryKey: ['events'] }); }
    catch (e: any) { alert(e.response?.data?.detail ?? 'Action failed'); }
    finally { setActionLoading(''); }
  }

  async function handleLock() {
    await doAction('lock', () => api.post(`/api/events/${id}/lock`));
  }

  async function handleCancel() {
    await doAction('cancel', () =>
      api.post(`/api/events/${id}/cancel`, { reason: cancelReason })
    );
    setShowCancelConfirm(false);
  }

  async function handleDelete() {
    if (!confirm('Permanently delete this event and all its data? This cannot be undone.')) return;
    await doAction('delete', () => api.delete(`/api/events/${id}`));
    window.location.href = '/events';
  }

  async function handleSaveTemplate() {
    const name = savingAs.trim();
    if (!name) return;
    await doAction('save-template', () =>
      api.post('/api/templates', { template_name: name, event_id: event.event_id })
    );
    setSavingAs('');
    alert(`Template "${name}" saved!`);
  }

  return (
    <div className="p-4 lg:p-8 max-w-4xl mx-auto space-y-5">
      {/* Title row */}
      <div className="flex items-start gap-3">
        <Link to="/events" className="text-gray-400 hover:text-white transition-colors mt-1">
          <ArrowLeft size={20} />
        </Link>
        <div className="min-w-0 flex-1">
          <h1 className="text-xl lg:text-2xl font-extrabold truncate">{event.event_name}</h1>
          <p className="text-gray-400 text-sm mt-0.5">
            {formatEventDate(event.event_date, event.event_time)}
            {event.status !== 'active' && (
              <span className="ml-2 text-red-400 font-semibold uppercase text-xs">
                [{event.status}]
              </span>
            )}
          </p>
        </div>
        {event.locked === 1 && (
          <span className="badge bg-yellow-500/20 text-yellow-400 border border-yellow-500/30 shrink-0 mt-1">
            <Lock size={12} /> Locked
          </span>
        )}
      </div>

      {/* Officer action bar */}
      {isRaidLeader && isActive && (
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => setShowEdit(true)}
            className="btn-secondary flex items-center gap-1.5 text-xs"
          >
            <Pencil size={12} /> Edit
          </button>
          <button
            onClick={handleLock}
            disabled={actionLoading === 'lock'}
            className="btn-secondary flex items-center gap-1.5 text-xs"
          >
            {actionLoading === 'lock'
              ? <Loader2 size={12} className="animate-spin" />
              : <Lock size={12} />}
            {event.locked ? 'Unlock' : 'Lock'}
          </button>
          <button
            onClick={() => setShowCancelConfirm(true)}
            className="btn-secondary text-orange-400 hover:bg-orange-500/10 flex items-center gap-1.5 text-xs"
          >
            <XCircle size={12} /> Cancel Event
          </button>
          <button
            onClick={handleDelete}
            className="btn-danger flex items-center gap-1.5 text-xs"
          >
            <Trash2 size={12} /> Delete
          </button>
          {/* Save as template */}
          <div className="flex items-center gap-1.5 ml-auto">
            <input
              className="input py-1.5 text-xs w-36"
              placeholder="Template name…"
              value={savingAs}
              onChange={(e) => setSavingAs(e.target.value)}
            />
            <button
              onClick={handleSaveTemplate}
              disabled={!savingAs.trim() || actionLoading === 'save-template'}
              className="btn-secondary flex items-center gap-1.5 text-xs"
            >
              <Save size={12} /> Save as Template
            </button>
          </div>
        </div>
      )}

      {event.description && (
        <div className="glass rounded-xl p-4 text-sm text-gray-300">{event.description}</div>
      )}

      {/* Slot bars */}
      <div className="grid grid-cols-3 gap-3">
        <SlotBar label="Tanks"   filled={tanks.length}   max={event.max_tanks}   color="#3b82f6" />
        <SlotBar label="Healers" filled={healers.length} max={event.max_healers} color="#22c55e" />
        <SlotBar label="DPS"     filled={dps.length}     max={event.max_dps}     color="#ef4444" />
      </div>

      {/* Discord signup CTA */}
      <div className="glass rounded-xl p-4 flex items-center justify-between gap-4">
        <div>
          <p className="font-semibold text-sm">{confirmedCount} signed up</p>
          <p className="text-gray-400 text-xs">Signups are managed in Discord</p>
        </div>
        <a
          href="https://discord.com"
          target="_blank"
          rel="noopener noreferrer"
          className="btn-primary shrink-0 text-sm"
          style={{ background: '#5865F2' }}
        >
          Sign Up in Discord
        </a>
      </div>

      {/* Submit absence (all members, active events) */}
      {isActive && (
        <div>
          <button
            onClick={() => setShowAbsenceForm(!showAbsenceForm)}
            className="btn-secondary flex items-center gap-2 text-sm"
          >
            <MessageSquareWarning size={14} /> {showAbsenceForm ? 'Hide Absence Form' : 'Submit Absence'}
          </button>
          {showAbsenceForm && (
            <AbsenceForm
              eventId={event.event_id}
              onSuccess={() => setShowAbsenceForm(false)}
            />
          )}
        </div>
      )}

      {/* Raid leader: mark attendance */}
      {isRaidLeader && (
        <div>
          <button
            onClick={() => setMarkMode(!markMode)}
            className="btn-secondary flex items-center gap-2 text-sm"
          >
            <Calendar size={14} /> {markMode ? 'Hide Attendance Panel' : 'Mark Attendance'}
          </button>
          {markMode && (
            <div className="mt-4">
              <AttendanceMarker
                eventId={event.event_id}
                signups={signups.filter((s) => s.signup_status !== 'declined')}
                onSaved={() => { setMarkMode(false); qc.invalidateQueries({ queryKey: ['event-attendance', id] }); }}
              />
            </div>
          )}
        </div>
      )}

      {/* Raid leader: absences and attendance breakdown */}
      {isRaidLeader && (
        <div className="space-y-3">
          {eventAbsences.length > 0 && (
            <div className="glass rounded-xl p-4">
              <h3 className="font-bold text-sm mb-3 text-blue-400">📋 Absence Requests ({eventAbsences.length})</h3>
              <div className="space-y-2">
                {eventAbsences.map((a: any) => (
                  <div key={a.absence_id} className="flex items-start gap-2 text-sm">
                    <span className="font-mono text-xs text-gray-500 shrink-0 mt-0.5">{a.discord_id}</span>
                    <span className="text-gray-300 flex-1 min-w-0">{a.reason}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {eventAttendance.length > 0 && (
            <div className="glass rounded-xl p-4">
              <h3 className="font-bold text-sm mb-3 text-indigo-400">📊 Attendance ({eventAttendance.length})</h3>
              <div className="grid grid-cols-2 lg:grid-cols-3 gap-2">
                {eventAttendance.map((a: any) => (
                  <div key={a.attendance_id} className="flex items-center gap-2 bg-gray-800/60 rounded-lg px-2.5 py-2">
                    <span className={`w-2 h-2 rounded-full shrink-0 ${
                      a.status === 'present' ? 'bg-green-400' :
                      a.status === 'late' ? 'bg-yellow-400' :
                      a.status === 'excused' ? 'bg-blue-400' : 'bg-red-400'
                    }`} />
                    <span className="text-xs text-gray-300 truncate flex-1">{a.char_name || a.discord_id}</span>
                    <span className="text-xs text-gray-500 capitalize shrink-0">{a.status}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Roster sections */}
      <RosterSection title="Tanks"     icon="🛡️" signups={tanks}    color="#3b82f6" />
      <RosterSection title="Healers"   icon="💚" signups={healers}  color="#22c55e" />
      <RosterSection title="DPS"       icon="⚔️" signups={dps}      color="#ef4444" />
      {bench.length > 0    && <RosterSection title="Bench"     icon="💺" signups={bench}    color="#6b7280" />}
      {tent.length > 0     && <RosterSection title="Tentative" icon="❓" signups={tent}     color="#f59e0b" />}
      {declined.length > 0 && <RosterSection title="Declined"  icon="❌" signups={declined} color="#6b7280" />}

      {/* Edit modal */}
      {showEdit && (
        <Modal title="Edit Event" onClose={() => setShowEdit(false)}>
          <EventForm
            initialValues={event}
            onSuccess={() => { setShowEdit(false); refetch(); qc.invalidateQueries({ queryKey: ['events'] }); }}
            onCancel={() => setShowEdit(false)}
            eventId={event.event_id}
          />
        </Modal>
      )}

      {/* Cancel confirm modal */}
      {showCancelConfirm && (
        <Modal title="Cancel Event" onClose={() => setShowCancelConfirm(false)} maxWidth="max-w-sm">
          <p className="text-sm text-gray-400 mb-4">
            This will mark the event as cancelled. Members will still see it but it won't be listed as active.
          </p>
          <input
            className="input mb-4"
            placeholder="Reason (optional)"
            value={cancelReason}
            onChange={(e) => setCancelReason(e.target.value)}
          />
          <div className="flex gap-2">
            <button
              onClick={handleCancel}
              disabled={actionLoading === 'cancel'}
              className="btn-danger flex-1 flex items-center justify-center gap-2"
            >
              {actionLoading === 'cancel' && <Loader2 size={14} className="animate-spin" />}
              Cancel Event
            </button>
            <button onClick={() => setShowCancelConfirm(false)} className="btn-secondary">
              Keep
            </button>
          </div>
        </Modal>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Sub-components
// ─────────────────────────────────────────────────────────────────────────────

function EventForm({
  initialValues,
  onSuccess,
  onCancel,
  eventId,
}: {
  initialValues?: Partial<RaidEvent>;
  onSuccess: () => void;
  onCancel: () => void;
  eventId?: number;
}) {
  const isEdit = !!eventId;
  const [form, setForm] = useState({
    event_name: initialValues?.event_name ?? '',
    event_date: initialValues?.event_date ?? '',
    event_time: (initialValues?.event_time ?? '').slice(0, 5),
    event_type: initialValues?.event_type ?? 'Heroic Raid',
    description: initialValues?.description ?? '',
    max_tanks: String(initialValues?.max_tanks ?? ''),
    max_healers: String(initialValues?.max_healers ?? ''),
    max_dps: String(initialValues?.max_dps ?? ''),
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError('');
    const payload = {
      event_name: form.event_name,
      event_date: form.event_date,
      event_time: form.event_time,
      event_type: form.event_type,
      description: form.description || undefined,
      max_tanks: form.max_tanks ? parseInt(form.max_tanks) : undefined,
      max_healers: form.max_healers ? parseInt(form.max_healers) : undefined,
      max_dps: form.max_dps ? parseInt(form.max_dps) : undefined,
    };
    try {
      if (isEdit) {
        await api.put(`/api/events/${eventId}`, payload);
      } else {
        await api.post('/api/events', payload);
      }
      onSuccess();
    } catch (err: any) {
      setError(err.response?.data?.detail ?? 'Failed to save event');
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <div>
        <label className="text-xs text-gray-400 mb-1 block">Event Name *</label>
        <input
          className="input"
          placeholder="Heroic Amirdrassil"
          value={form.event_name}
          onChange={(e) => setForm({ ...form, event_name: e.target.value })}
          required
        />
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="text-xs text-gray-400 mb-1 block">Date *</label>
          <input
            type="date"
            className="input"
            value={form.event_date}
            onChange={(e) => setForm({ ...form, event_date: e.target.value })}
            required
          />
        </div>
        <div>
          <label className="text-xs text-gray-400 mb-1 block">Time *</label>
          <input
            type="time"
            className="input"
            value={form.event_time}
            onChange={(e) => setForm({ ...form, event_time: e.target.value })}
            required
          />
        </div>
      </div>

      <div>
        <label className="text-xs text-gray-400 mb-1 block">Type *</label>
        <select
          className="input"
          value={form.event_type}
          onChange={(e) => setForm({ ...form, event_type: e.target.value })}
          required
        >
          {EVENT_TYPES.map((t) => <option key={t}>{t}</option>)}
        </select>
      </div>

      <div>
        <label className="text-xs text-gray-400 mb-1 block">Description</label>
        <textarea
          className="input resize-none"
          rows={2}
          placeholder="Optional event notes…"
          value={form.description}
          onChange={(e) => setForm({ ...form, description: e.target.value })}
        />
      </div>

      <div className="grid grid-cols-3 gap-3">
        <div>
          <label className="text-xs text-gray-400 mb-1 block">Tanks</label>
          <input
            type="number" min="0" max="40"
            className="input"
            placeholder="Default"
            value={form.max_tanks}
            onChange={(e) => setForm({ ...form, max_tanks: e.target.value })}
          />
        </div>
        <div>
          <label className="text-xs text-gray-400 mb-1 block">Healers</label>
          <input
            type="number" min="0" max="40"
            className="input"
            placeholder="Default"
            value={form.max_healers}
            onChange={(e) => setForm({ ...form, max_healers: e.target.value })}
          />
        </div>
        <div>
          <label className="text-xs text-gray-400 mb-1 block">DPS</label>
          <input
            type="number" min="0" max="40"
            className="input"
            placeholder="Default"
            value={form.max_dps}
            onChange={(e) => setForm({ ...form, max_dps: e.target.value })}
          />
        </div>
      </div>

      {error && <p className="text-red-400 text-xs">{error}</p>}

      <div className="flex gap-2 pt-1">
        <button type="submit" disabled={saving} className="btn-primary flex-1 flex items-center justify-center gap-2">
          {saving && <Loader2 size={14} className="animate-spin" />}
          {isEdit ? 'Save Changes' : 'Create Event'}
        </button>
        <button type="button" onClick={onCancel} className="btn-secondary">Cancel</button>
      </div>
    </form>
  );
}

function TemplatesPanel({ onEventCreated }: { onEventCreated: () => void }) {
  const qc = useQueryClient();
  const [loadDate, setLoadDate] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState('');

  const { data: templates = [] } = useQuery<Template[]>({
    queryKey: ['templates'],
    queryFn: () => api.get('/api/templates').then((r) => r.data),
  });

  async function handleLoad(name: string) {
    const date = loadDate[name];
    if (!date) { alert('Pick a date first'); return; }
    setLoading(name);
    try {
      await api.post(`/api/templates/${encodeURIComponent(name)}/load`, { date });
      qc.invalidateQueries({ queryKey: ['events'] });
      onEventCreated();
      alert(`Event created from template "${name}"!`);
    } catch (e: any) {
      alert(e.response?.data?.detail ?? 'Failed to load template');
    } finally {
      setLoading('');
    }
  }

  async function handleDelete(name: string) {
    if (!confirm(`Delete template "${name}"?`)) return;
    await api.delete(`/api/templates/${encodeURIComponent(name)}`);
    qc.invalidateQueries({ queryKey: ['templates'] });
  }

  if (templates.length === 0) {
    return (
      <div className="glass rounded-xl p-4 text-center text-gray-500 text-sm">
        No saved templates yet. Save an event as a template from its detail page.
      </div>
    );
  }

  return (
    <div className="glass rounded-xl p-4 space-y-3">
      <h2 className="font-bold text-sm text-gray-300">Saved Templates</h2>
      {templates.map((t) => (
        <div key={t.template_id} className="flex flex-wrap items-center gap-2 p-3 bg-gray-800/60 rounded-xl">
          <div className="min-w-0 flex-1">
            <p className="font-semibold text-sm truncate">{t.template_name}</p>
            <p className="text-xs text-gray-400">
              {t.event_name} · {t.event_type} · {t.event_time}
              {` · ${t.max_tanks}T / ${t.max_healers}H / ${t.max_dps}D`}
            </p>
          </div>
          <input
            type="date"
            className="input py-1.5 text-xs w-36 shrink-0"
            value={loadDate[t.template_name] ?? ''}
            onChange={(e) => setLoadDate((p) => ({ ...p, [t.template_name]: e.target.value }))}
          />
          <button
            onClick={() => handleLoad(t.template_name)}
            disabled={loading === t.template_name}
            className="btn-primary text-xs py-1.5 flex items-center gap-1"
          >
            {loading === t.template_name
              ? <Loader2 size={12} className="animate-spin" />
              : <PlayCircle size={12} />}
            Load
          </button>
          <button
            onClick={() => handleDelete(t.template_name)}
            className="btn-danger text-xs py-1.5"
          >
            <Trash2 size={12} />
          </button>
        </div>
      ))}
    </div>
  );
}

function AbsenceForm({ eventId, onSuccess }: { eventId: number; onSuccess: () => void }) {
  const [reason, setReason] = useState('');
  const [saving, setSaving] = useState(false);
  const [done, setDone] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      await api.post('/api/absences', { event_id: eventId, reason });
      setDone(true);
      setTimeout(onSuccess, 1500);
    } catch (err: any) {
      alert(err.response?.data?.detail ?? 'Failed to submit absence');
    } finally {
      setSaving(false);
    }
  }

  if (done) return (
    <div className="mt-3 glass rounded-xl p-3 text-green-400 text-sm text-center">
      ✓ Absence submitted
    </div>
  );

  return (
    <form onSubmit={submit} className="mt-3 glass rounded-xl p-4 space-y-3">
      <label className="text-xs text-gray-400 block">Reason for absence *</label>
      <input
        className="input"
        placeholder="Travelling, family commitment…"
        value={reason}
        onChange={(e) => setReason(e.target.value)}
        required
      />
      <div className="flex gap-2">
        <button type="submit" disabled={saving || !reason.trim()} className="btn-primary text-sm flex items-center gap-2">
          {saving && <Loader2 size={12} className="animate-spin" />}
          Submit Absence
        </button>
        <button type="button" onClick={onSuccess} className="btn-secondary text-sm">Cancel</button>
      </div>
    </form>
  );
}

function SlotBar({ label, filled, max, color }: { label: string; filled: number; max: number; color: string }) {
  const pct = max > 0 ? Math.min(100, (filled / max) * 100) : 0;
  return (
    <div className="glass rounded-xl p-3">
      <div className="flex justify-between text-xs mb-1.5">
        <span className="text-gray-400">{label}</span>
        <span className="font-semibold" style={{ color }}>{filled}/{max}</span>
      </div>
      <div className="h-1.5 bg-gray-700 rounded-full overflow-hidden">
        <div className="h-full rounded-full transition-all" style={{ width: `${pct}%`, background: color }} />
      </div>
    </div>
  );
}

function RosterSection({ title, icon, signups, color }: {
  title: string; icon: string; signups: Signup[]; color: string;
}) {
  if (signups.length === 0) return null;
  return (
    <div className="glass rounded-xl p-4">
      <h3 className="font-bold text-sm mb-3 flex items-center gap-2" style={{ color }}>
        {icon} {title} ({signups.length})
      </h3>
      <div className="grid grid-cols-2 lg:grid-cols-3 gap-2">
        {signups.map((s) => (
          <div key={s.signup_id} className="flex items-center gap-2 bg-gray-800/50 rounded-lg px-2.5 py-2">
            <span className="text-sm font-semibold truncate" style={{ color: classColor(s.char_class) }}>
              {s.char_name}
            </span>
            <span className="text-xs text-gray-500 shrink-0">{s.main_spec}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
