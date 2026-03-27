import { AttendanceStats as Stats } from '@/types';
import { attendanceBadge } from '@/lib/utils';

interface Props {
  stats: Stats;
}

export function AttendanceStatsCard({ stats }: Props) {
  const badge = attendanceBadge(stats.percentage);

  return (
    <div className="glass rounded-2xl p-4 lg:p-6 space-y-4">
      {/* Overall % */}
      <div className="flex items-center justify-between">
        <div>
          <p className="text-gray-400 text-sm">Overall Attendance</p>
          <p className={`text-3xl font-bold ${badge.color}`}>{stats.percentage}%</p>
        </div>
        <div className={`badge text-sm px-3 py-1.5 ${badge.color} bg-current/10`}>
          {badge.label}
        </div>
      </div>

      {/* Progress bar */}
      <div className="h-2 bg-gray-700 rounded-full overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{
            width: `${stats.percentage}%`,
            background: stats.percentage >= 75
              ? 'linear-gradient(90deg, #11998e, #38ef7d)'
              : 'linear-gradient(90deg, #fc466b, #f5576c)',
          }}
        />
      </div>

      {/* Breakdown */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <StatPill label="Present" value={stats.present} color="text-green-400" />
        <StatPill label="Late" value={stats.late} color="text-yellow-400" />
        <StatPill label="Excused" value={stats.excused} color="text-blue-400" />
        <StatPill label="Absent" value={stats.absent} color="text-red-400" />
      </div>
    </div>
  );
}

function StatPill({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className="bg-gray-800/60 rounded-xl p-3 text-center">
      <p className={`text-xl font-bold ${color}`}>{value}</p>
      <p className="text-xs text-gray-400">{label}</p>
    </div>
  );
}
