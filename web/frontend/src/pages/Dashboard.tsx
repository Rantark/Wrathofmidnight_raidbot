import { useQuery } from '@tanstack/react-query';
import { Users, Calendar, TrendingUp, Shield, ExternalLink, PlusCircle, AlertCircle } from 'lucide-react';
import { api } from '@/lib/api';
import { useAuth } from '@/contexts/AuthContext';
import { EventCard } from '@/components/Events/EventCard';
import { AttendanceStatsCard } from '@/components/Attendance/AttendanceStats';
import { classColor } from '@/lib/utils';
import type { RaidEvent, AttendanceHistory, Character } from '@/types';

export function Dashboard() {
  const { user, isOfficer, isRaidLeader } = useAuth();

  const { data: events = [] } = useQuery<RaidEvent[]>({
    queryKey: ['events'],
    queryFn: () => api.get('/api/events?limit=3').then((r) => r.data),
  });

  const { data: myStats } = useQuery({
    queryKey: ['attendance-me'],
    queryFn: () => api.get('/api/attendance/me').then((r) => r.data),
  });

  const { data: history = [] } = useQuery<AttendanceHistory[]>({
    queryKey: ['attendance-history'],
    queryFn: () => api.get('/api/attendance/me/history').then((r) => r.data),
  });

  const { data: adminStats } = useQuery({
    queryKey: ['admin-stats'],
    queryFn: () => api.get('/api/admin/stats').then((r) => r.data),
    enabled: isOfficer,
  });

  const { data: myChars = [] } = useQuery<Character[]>({
    queryKey: ['characters'],
    queryFn: () => api.get('/api/characters').then((r) => r.data),
  });

  return (
    <div className="p-4 lg:p-8 space-y-6 max-w-7xl mx-auto">
      {/* Welcome */}
      <div>
        <h1 className="text-2xl lg:text-3xl font-extrabold">
          Welcome back, {user?.username?.split('#')[0] ?? 'Adventurer'} 👋
        </h1>
        <p className="text-gray-400 text-sm mt-1">Here's what's happening in the guild</p>
      </div>

      {/* Admin stat cards (officers only) */}
      {isOfficer && adminStats && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 lg:gap-4">
          <StatCard icon={Users}    label="Active Members"  value={adminStats.total_members}    gradient="gradient-blue" />
          <StatCard icon={Shield}   label="Characters"      value={adminStats.total_characters}  gradient="gradient-teal" />
          <StatCard icon={Calendar} label="Active Events"   value={adminStats.active_events}     gradient="gradient-orange" />
          <StatCard icon={TrendingUp} label="Upcoming"      value={adminStats.upcoming_events}   gradient="gradient-green" />
        </div>
      )}

      <div className="grid lg:grid-cols-5 gap-6">
        {/* Left: events + history */}
        <div className="lg:col-span-3 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="font-bold text-lg">Upcoming Raids</h2>
            <a href="/events" className="text-indigo-400 text-sm hover:text-indigo-300 flex items-center gap-1">
              View all <ExternalLink size={12} />
            </a>
          </div>

          {events.length === 0 ? (
            <div className="glass rounded-xl p-6 text-center text-gray-500 text-sm">
              No upcoming events
            </div>
          ) : (
            <div className="space-y-3">
              {events.map((e) => <EventCard key={e.event_id} event={e} />)}
            </div>
          )}

          {/* Recent attendance history */}
          {history.length > 0 && (
            <div>
              <h2 className="font-bold text-lg mb-3">Recent Events</h2>
              <div className="glass rounded-xl divide-y divide-gray-700/50">
                {history.slice(0, 5).map((h) => (
                  <div key={`${h.event_id}-${h.timestamp}`} className="flex items-center gap-3 p-3">
                    <StatusDot status={h.status} />
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium truncate">{h.event_name}</p>
                      <p className="text-xs text-gray-500">{h.event_date}</p>
                    </div>
                    <span className={`badge text-xs ${statusBadge(h.status)}`}>
                      {h.status}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Right: attendance stats + characters + quick actions */}
        <div className="lg:col-span-2 space-y-4">
          <h2 className="font-bold text-lg">My Attendance</h2>
          {myStats ? (
            <AttendanceStatsCard stats={myStats} />
          ) : (
            <div className="glass rounded-xl p-6 text-center text-gray-500 text-sm">
              No attendance data yet
            </div>
          )}

          {/* Characters summary */}
          <div className="glass rounded-xl p-4">
            <div className="flex items-center justify-between mb-3">
              <p className="text-sm font-semibold text-gray-300">My Characters</p>
              <a href="/characters" className="text-xs text-indigo-400 hover:text-indigo-300">
                Manage →
              </a>
            </div>
            {myChars.length === 0 ? (
              <div className="text-center py-3">
                <p className="text-xs text-gray-500 mb-2">No characters registered</p>
                <a href="/characters" className="text-xs text-indigo-400 hover:text-indigo-300">
                  Add your first character →
                </a>
              </div>
            ) : (
              <div className="space-y-2">
                {myChars.slice(0, 4).map((c) => {
                  const color = classColor(c.char_class);
                  return (
                    <div key={c.char_name} className="flex items-center gap-2">
                      {c.avatar_url ? (
                        <img src={c.avatar_url} alt="" className="w-7 h-7 rounded-md object-cover shrink-0" />
                      ) : (
                        <div
                          className="w-7 h-7 rounded-md flex items-center justify-center text-xs font-bold shrink-0"
                          style={{ background: `${color}22` }}
                        >
                          {c.char_name[0]}
                        </div>
                      )}
                      <div className="min-w-0 flex-1">
                        <p className="text-xs font-semibold truncate" style={{ color }}>{c.char_name}</p>
                        <p className="text-xs text-gray-500 truncate">{c.char_class} · {c.main_spec}</p>
                      </div>
                      {c.is_main === 1 && (
                        <span className="text-xs px-1.5 py-0.5 rounded bg-indigo-500/20 text-indigo-400 shrink-0">Main</span>
                      )}
                    </div>
                  );
                })}
                {myChars.length > 4 && (
                  <p className="text-xs text-gray-500 text-center pt-1">+{myChars.length - 4} more</p>
                )}
              </div>
            )}
          </div>

          {/* Quick actions */}
          <div className="glass rounded-xl p-4 space-y-1">
            <p className="text-sm font-semibold text-gray-300 mb-3">Quick Actions</p>
            {isRaidLeader && (
              <a href="/events" className="flex items-center gap-2 text-sm text-gray-400 hover:text-white p-2 rounded-lg hover:bg-white/5 transition-colors">
                <PlusCircle size={14} /> Create Raid Event
              </a>
            )}
            <a href="/attendance" className="flex items-center gap-2 text-sm text-gray-400 hover:text-white p-2 rounded-lg hover:bg-white/5 transition-colors">
              <AlertCircle size={14} /> Submit Absence
            </a>
            <a href="/characters" className="flex items-center gap-2 text-sm text-gray-400 hover:text-white p-2 rounded-lg hover:bg-white/5 transition-colors">
              <Shield size={14} /> Manage Characters
            </a>
            <a href="/events" className="flex items-center gap-2 text-sm text-gray-400 hover:text-white p-2 rounded-lg hover:bg-white/5 transition-colors">
              <Calendar size={14} /> View All Events
            </a>
            {isOfficer && (
              <a href="/admin" className="flex items-center gap-2 text-sm text-gray-400 hover:text-white p-2 rounded-lg hover:bg-white/5 transition-colors">
                <Users size={14} /> Admin Tools
              </a>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function StatCard({ icon: Icon, label, value, gradient }: {
  icon: React.ElementType; label: string; value: number; gradient: string;
}) {
  return (
    <div className={`rounded-2xl p-4 text-white ${gradient} shadow-lg`}>
      <Icon size={20} className="mb-2 opacity-80" />
      <p className="text-2xl font-extrabold">{value}</p>
      <p className="text-sm opacity-80 mt-0.5">{label}</p>
    </div>
  );
}

function StatusDot({ status }: { status: string }) {
  const colors: Record<string, string> = {
    present: 'bg-green-400', late: 'bg-yellow-400',
    excused: 'bg-blue-400', absent: 'bg-red-400',
  };
  return <span className={`w-2.5 h-2.5 rounded-full shrink-0 ${colors[status] ?? 'bg-gray-500'}`} />;
}

function statusBadge(status: string): string {
  const map: Record<string, string> = {
    present: 'bg-green-500/20 text-green-400',
    late:    'bg-yellow-500/20 text-yellow-400',
    excused: 'bg-blue-500/20 text-blue-400',
    absent:  'bg-red-500/20 text-red-400',
  };
  return map[status] ?? 'bg-gray-500/20 text-gray-400';
}
