import { useState } from 'react';
import { Loader2 } from 'lucide-react';
import { Signup } from '@/types';
import { classColor } from '@/lib/utils';
import { api } from '@/lib/api';

type Status = 'present' | 'absent' | 'late' | 'excused';

const STATUS_STYLES: Record<Status, string> = {
  present: 'bg-green-500/20 border-green-500/50 text-green-400',
  late:    'bg-yellow-500/20 border-yellow-500/50 text-yellow-400',
  excused: 'bg-blue-500/20 border-blue-500/50 text-blue-400',
  absent:  'bg-red-500/20 border-red-500/50 text-red-400',
};

interface Props {
  eventId: number;
  signups: Signup[];
  onSaved: () => void;
}

export function AttendanceMarker({ eventId, signups, onSaved }: Props) {
  const [records, setRecords] = useState<Record<string, Status>>(() =>
    Object.fromEntries(signups.map((s) => [s.discord_id, 'present']))
  );
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  function setStatus(id: string, status: Status) {
    setRecords((prev) => ({ ...prev, [id]: status }));
  }

  async function save() {
    setSaving(true);
    setError('');
    try {
      await api.post('/api/attendance/mark', {
        event_id: eventId,
        records: Object.entries(records).map(([discord_id, status]) => ({ discord_id, status })),
      });
      onSaved();
    } catch (err: any) {
      setError(err.response?.data?.detail ?? 'Failed to save attendance');
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-3">
      {signups.map((s) => {
        const status = records[s.discord_id] ?? 'absent';
        const color = classColor(s.char_class);
        return (
          <div key={s.signup_id} className="glass rounded-xl p-3 flex items-center gap-3">
            <div className="min-w-0 flex-1">
              <p className="text-sm font-semibold" style={{ color }}>{s.char_name}</p>
              <p className="text-xs text-gray-400">{s.char_class} · {s.main_spec}</p>
            </div>
            <div className="flex gap-1 shrink-0">
              {(['present','late','excused','absent'] as Status[]).map((st) => (
                <button
                  key={st}
                  onClick={() => setStatus(s.discord_id, st)}
                  className={`px-2.5 py-1.5 rounded-lg text-xs font-semibold border transition-all ${
                    status === st ? STATUS_STYLES[st] : 'border-gray-600 text-gray-500 hover:border-gray-400'
                  }`}
                >
                  {st.charAt(0).toUpperCase() + st.slice(1)}
                </button>
              ))}
            </div>
          </div>
        );
      })}

      {error && <p className="text-red-400 text-sm">{error}</p>}

      <button
        onClick={save}
        disabled={saving}
        className="btn-primary w-full flex items-center justify-center gap-2 mt-4"
      >
        {saving && <Loader2 size={14} className="animate-spin" />}
        {saving ? 'Saving…' : 'Save Attendance'}
      </button>
    </div>
  );
}
