import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useParams, Link } from 'react-router-dom';
import { ArrowLeft, Users, Lock, Calendar } from 'lucide-react';
import { api } from '@/lib/api';
import { EventCard } from '@/components/Events/EventCard';
import { EventFilters } from '@/components/Events/EventFilters';
import { AttendanceMarker } from '@/components/Attendance/AttendanceMarker';
import { classColor, formatEventDate } from '@/lib/utils';
import { useAuth } from '@/contexts/AuthContext';
import type { RaidEvent, Signup } from '@/types';
import { ROLE_ICONS } from '@/types';

// ── List view ──────────────────────────────────────────────────────────────

export function EventsList() {
  const [typeFilter, setTypeFilter] = useState('');

  const { data: events = [], isLoading } = useQuery<RaidEvent[]>({
    queryKey: ['events'],
    queryFn: () => api.get('/api/events?limit=50').then((r) => r.data),
  });

  const filtered = typeFilter
    ? events.filter((e) => e.event_type === typeFilter)
    : events;

  return (
    <div className="p-4 lg:p-8 max-w-5xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-extrabold">Raid Events</h1>
        <EventFilters typeFilter={typeFilter} onTypeChange={setTypeFilter} />
      </div>

      {isLoading ? (
        <div className="text-center text-gray-500 py-12">Loading…</div>
      ) : filtered.length === 0 ? (
        <div className="glass rounded-xl p-12 text-center text-gray-500">
          No upcoming events
        </div>
      ) : (
        <div className="grid gap-3 lg:gap-4">
          {filtered.map((e) => <EventCard key={e.event_id} event={e} />)}
        </div>
      )}
    </div>
  );
}

// ── Detail view ────────────────────────────────────────────────────────────

export function EventDetail() {
  const { id } = useParams<{ id: string }>();
  const { isRaidLeader } = useAuth();
  const [markMode, setMarkMode] = useState(false);

  const { data: event, isLoading } = useQuery({
    queryKey: ['event', id],
    queryFn: () => api.get(`/api/events/${id}`).then((r) => r.data),
    enabled: !!id,
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

  return (
    <div className="p-4 lg:p-8 max-w-4xl mx-auto space-y-6">
      <div className="flex items-center gap-3">
        <Link to="/events" className="text-gray-400 hover:text-white transition-colors">
          <ArrowLeft size={20} />
        </Link>
        <div className="min-w-0">
          <h1 className="text-xl lg:text-2xl font-extrabold truncate">{event.event_name}</h1>
          <p className="text-gray-400 text-sm mt-0.5">
            {formatEventDate(event.event_date, event.event_time)}
          </p>
        </div>
        {event.locked === 1 && (
          <span className="badge bg-yellow-500/20 text-yellow-400 border border-yellow-500/30 shrink-0">
            <Lock size={12} /> Locked
          </span>
        )}
      </div>

      {event.description && (
        <div className="glass rounded-xl p-4 text-sm text-gray-300">{event.description}</div>
      )}

      {/* Slot summary */}
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
          className="btn-primary shrink-0 flex items-center gap-2 text-sm"
          style={{ background: '#5865F2' }}
        >
          Sign Up in Discord
        </a>
      </div>

      {/* Attendance marking (raid leaders) */}
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
                onSaved={() => setMarkMode(false)}
              />
            </div>
          )}
        </div>
      )}

      {/* Roster sections */}
      <RosterSection title="Tanks" icon="🛡️" signups={tanks} color="#3b82f6" />
      <RosterSection title="Healers" icon="💚" signups={healers} color="#22c55e" />
      <RosterSection title="DPS" icon="⚔️" signups={dps} color="#ef4444" />
      {bench.length > 0 && <RosterSection title="Bench" icon="💺" signups={bench} color="#6b7280" />}
      {tent.length > 0  && <RosterSection title="Tentative" icon="❓" signups={tent} color="#f59e0b" />}
      {declined.length > 0 && <RosterSection title="Declined" icon="❌" signups={declined} color="#6b7280" />}
    </div>
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
