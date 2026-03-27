import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { classColor } from '@/lib/utils';
import { ExternalLink, AlertTriangle } from 'lucide-react';
import type { Character } from '@/types';

export function AdminPage() {
  const { data: stats } = useQuery({
    queryKey: ['admin-stats'],
    queryFn: () => api.get('/api/admin/stats').then((r) => r.data),
  });

  const { data: lowAttendance } = useQuery({
    queryKey: ['low-attendance'],
    queryFn: () => api.get('/api/attendance/report').then((r) => r.data),
  });

  const { data: characters = [] } = useQuery<Character[]>({
    queryKey: ['admin-characters'],
    queryFn: () => api.get('/api/admin/characters').then((r) => r.data),
  });

  return (
    <div className="p-4 lg:p-8 max-w-5xl mx-auto space-y-6">
      <h1 className="text-2xl font-extrabold">Admin Tools</h1>

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          <StatCard label="Members"    value={stats.total_members} />
          <StatCard label="Characters" value={stats.total_characters} />
          <StatCard label="Active Events" value={stats.active_events} />
          <StatCard label="Upcoming"   value={stats.upcoming_events} />
        </div>
      )}

      {/* Low attendance alerts */}
      {lowAttendance?.members?.length > 0 && (
        <div>
          <h2 className="font-bold text-lg mb-3 flex items-center gap-2 text-orange-400">
            <AlertTriangle size={18} /> Low Attendance ({lowAttendance.members.length} members below {lowAttendance.threshold}%)
          </h2>
          <div className="glass rounded-xl divide-y divide-gray-700/50">
            {lowAttendance.members.map((m: any) => (
              <div key={m.discord_id} className="flex items-center gap-3 p-3">
                <p className="text-sm font-mono text-gray-400 truncate flex-1">{m.discord_id}</p>
                <div className="flex items-center gap-3 shrink-0 text-xs text-gray-400">
                  <span className="text-red-400 font-bold">{m.percentage}%</span>
                  <span>{m.present + m.late}/{m.total - m.excused} attended</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Character list */}
      <div>
        <h2 className="font-bold text-lg mb-3">All Characters ({characters.length})</h2>
        <div className="glass rounded-xl divide-y divide-gray-700/50 max-h-[500px] overflow-y-auto">
          {characters.map((c) => {
            const color = classColor(c.char_class);
            return (
              <div key={`${c.discord_id}-${c.char_name}`} className="flex items-center gap-3 p-3">
                {c.avatar_url ? (
                  <img src={c.avatar_url} alt="" className="w-8 h-8 rounded-lg object-cover shrink-0" />
                ) : (
                  <div
                    className="w-8 h-8 rounded-lg flex items-center justify-center text-xs font-bold shrink-0"
                    style={{ background: `${color}22` }}
                  >
                    {c.char_name[0]}
                  </div>
                )}
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-semibold truncate" style={{ color }}>{c.char_name}</p>
                  <p className="text-xs text-gray-500">
                    {c.char_class} · {c.main_spec} {c.ilvl ? `· ${c.ilvl}` : ''}
                  </p>
                </div>
                {c.raiderio_url && (
                  <a
                    href={c.raiderio_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-gray-500 hover:text-blue-400 shrink-0 transition-colors"
                  >
                    <ExternalLink size={13} />
                  </a>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="glass rounded-xl p-4">
      <p className="text-2xl font-extrabold">{value ?? '—'}</p>
      <p className="text-xs text-gray-400 mt-1">{label}</p>
    </div>
  );
}
