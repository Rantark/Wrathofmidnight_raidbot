import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { AttendanceStatsCard } from '@/components/Attendance/AttendanceStats';
import { formatRelativeDate } from '@/lib/utils';
import type { AttendanceHistory } from '@/types';

const STATUS_STYLES: Record<string, string> = {
  present: 'bg-green-500/20 text-green-400',
  late:    'bg-yellow-500/20 text-yellow-400',
  excused: 'bg-blue-500/20 text-blue-400',
  absent:  'bg-red-500/20 text-red-400',
};

export function AttendancePage() {
  const { data: stats } = useQuery({
    queryKey: ['attendance-me'],
    queryFn: () => api.get('/api/attendance/me').then((r) => r.data),
  });

  const { data: history = [] } = useQuery<AttendanceHistory[]>({
    queryKey: ['attendance-history'],
    queryFn: () => api.get('/api/attendance/me/history').then((r) => r.data),
  });

  return (
    <div className="p-4 lg:p-8 max-w-3xl mx-auto space-y-6">
      <h1 className="text-2xl font-extrabold">My Attendance</h1>

      {stats && <AttendanceStatsCard stats={stats} />}

      {/* History */}
      <div>
        <h2 className="font-bold text-lg mb-3">Recent Events</h2>
        {history.length === 0 ? (
          <div className="glass rounded-xl p-8 text-center text-gray-500 text-sm">
            No attendance records yet
          </div>
        ) : (
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
        )}
      </div>
    </div>
  );
}
