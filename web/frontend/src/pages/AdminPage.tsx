import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { classColor } from '@/lib/utils';
import { ExternalLink, AlertTriangle, Loader2, Trash2, UserPlus, Settings, Users, BarChart3, ClipboardList } from 'lucide-react';
import type { Character, Permission, GuildConfig } from '@/types';

type Tab = 'overview' | 'permissions' | 'config' | 'reglog';

export function AdminPage() {
  const [tab, setTab] = useState<Tab>('overview');

  return (
    <div className="p-4 lg:p-8 max-w-5xl mx-auto space-y-6">
      <h1 className="text-2xl font-extrabold">Admin Tools</h1>

      <div className="flex gap-1 p-1 glass rounded-xl w-fit flex-wrap">
        {([
          { id: 'overview' as Tab,     label: 'Overview',      icon: BarChart3 },
          { id: 'permissions' as Tab,  label: 'Permissions',   icon: Users },
          { id: 'config' as Tab,       label: 'Config',        icon: Settings },
          { id: 'reglog' as Tab,       label: 'Reg Log',       icon: ClipboardList },
        ] as const).map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => setTab(id)}
            className={`px-4 py-2 rounded-lg text-sm font-semibold transition-all flex items-center gap-2 ${
              tab === id ? 'bg-indigo-600 text-white' : 'text-gray-400 hover:text-white'
            }`}
          >
            <Icon size={14} />{label}
          </button>
        ))}
      </div>

      {tab === 'overview'    && <OverviewTab />}
      {tab === 'permissions' && <PermissionsTab />}
      {tab === 'config'      && <ConfigTab />}
      {tab === 'reglog'      && <RegistrationLogTab />}
    </div>
  );
}

// ── Overview ──────────────────────────────────────────────────────────────────

function OverviewTab() {
  const { data: stats } = useQuery({
    queryKey: ['admin-stats'],
    queryFn: () => api.get('/api/admin/stats').then((r) => r.data),
  });

  const { data: lowAttendance } = useQuery({
    queryKey: ['low-attendance', {}],
    queryFn: () => api.get('/api/attendance/report').then((r) => r.data),
  });

  const { data: characters = [] } = useQuery<Character[]>({
    queryKey: ['admin-characters'],
    queryFn: () => api.get('/api/admin/characters').then((r) => r.data),
  });

  const { data: status } = useQuery({
    queryKey: ['admin-status'],
    queryFn: () => api.get('/api/admin/status').then((r) => r.data),
  });

  return (
    <div className="space-y-6">
      {/* Stat cards */}
      {stats && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          <StatCard label="Members"      value={stats.total_members} />
          <StatCard label="Characters"   value={stats.total_characters} />
          <StatCard label="Active Events" value={stats.active_events} />
          <StatCard label="Upcoming"     value={stats.upcoming_events} />
        </div>
      )}

      {/* Status strip */}
      {status && (
        <div className="glass rounded-xl p-4 grid sm:grid-cols-3 gap-3 text-sm">
          <div>
            <p className="text-xs text-gray-500 mb-1">Timezone</p>
            <p className="font-semibold">{status.settings?.timezone ?? '—'}</p>
          </div>
          <div>
            <p className="text-xs text-gray-500 mb-1">Attendance Threshold</p>
            <p className="font-semibold">{status.settings?.attendance_threshold ?? '—'}%</p>
          </div>
          <div>
            <p className="text-xs text-gray-500 mb-1">Templates / Recurring</p>
            <p className="font-semibold">{status.template_count} / {status.recurring_count}</p>
          </div>
        </div>
      )}

      {/* Low attendance alerts */}
      {(lowAttendance?.members?.length ?? 0) > 0 && (
        <div>
          <h2 className="font-bold text-base mb-3 flex items-center gap-2 text-orange-400">
            <AlertTriangle size={16} />
            Low Attendance — {lowAttendance.members.length} below {lowAttendance.threshold}%
          </h2>
          <div className="glass rounded-xl divide-y divide-gray-700/50">
            {lowAttendance.members.map((m: any) => (
              <div key={m.discord_id} className="flex items-center gap-3 p-3">
                <p className="text-sm font-mono text-gray-400 truncate flex-1">{m.discord_id}</p>
                <div className="flex items-center gap-3 shrink-0 text-xs text-gray-400">
                  <span className="text-red-400 font-bold text-base">{m.percentage}%</span>
                  <span>{m.present + m.late}/{m.total - m.excused} attended</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Characters list */}
      <div>
        <h2 className="font-bold text-base mb-3">All Characters ({characters.length})</h2>
        <div className="glass rounded-xl divide-y divide-gray-700/50 max-h-[500px] overflow-y-auto">
          {characters.map((c) => {
            const color = classColor(c.char_class);
            return (
              <div key={`${c.discord_id}-${c.char_name}`} className="flex items-center gap-3 p-3">
                {c.avatar_url ? (
                  <img src={c.avatar_url} alt="" className="w-8 h-8 rounded-lg object-cover shrink-0" />
                ) : (
                  <div className="w-8 h-8 rounded-lg flex items-center justify-center text-xs font-bold shrink-0" style={{ background: `${color}22` }}>
                    {c.char_name[0]}
                  </div>
                )}
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-semibold truncate" style={{ color }}>{c.char_name}</p>
                  <p className="text-xs text-gray-500">{c.char_class} · {c.main_spec}{c.ilvl ? ` · ${c.ilvl}` : ''}</p>
                </div>
                {c.raiderio_url && (
                  <a href={c.raiderio_url} target="_blank" rel="noopener noreferrer"
                    className="text-gray-500 hover:text-blue-400 shrink-0 transition-colors">
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

// ── Permissions ───────────────────────────────────────────────────────────────

function PermissionsTab() {
  const qc = useQueryClient();
  const [form, setForm] = useState({ discord_id: '', username: '', role: 'raid_leader' as 'raid_leader' | 'officer' });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const { data: permissions = [] } = useQuery<Permission[]>({
    queryKey: ['admin-permissions'],
    queryFn: () => api.get('/api/admin/permissions').then((r) => r.data),
  });

  async function grant(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError('');
    try {
      await api.post('/api/admin/permissions', form);
      qc.invalidateQueries({ queryKey: ['admin-permissions'] });
      setForm({ discord_id: '', username: '', role: 'raid_leader' });
    } catch (err: any) {
      setError(err.response?.data?.detail ?? 'Failed to grant permission');
    } finally {
      setSaving(false);
    }
  }

  async function revoke(discordId: string) {
    if (!confirm('Revoke this member\'s bot role?')) return;
    await api.delete(`/api/admin/permissions/${discordId}`);
    qc.invalidateQueries({ queryKey: ['admin-permissions'] });
  }

  const officers     = permissions.filter((p) => p.role === 'officer');
  const raidLeaders  = permissions.filter((p) => p.role === 'raid_leader');

  return (
    <div className="space-y-6">
      {/* Grant form */}
      <div className="glass rounded-xl p-5">
        <h2 className="font-bold text-base mb-4 flex items-center gap-2">
          <UserPlus size={16} /> Grant Bot Role
        </h2>
        <form onSubmit={grant} className="space-y-3">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div>
              <label className="text-xs text-gray-400 mb-1 block">Discord ID *</label>
              <input
                className="input"
                placeholder="123456789012345678"
                value={form.discord_id}
                onChange={(e) => setForm({ ...form, discord_id: e.target.value })}
                required
              />
            </div>
            <div>
              <label className="text-xs text-gray-400 mb-1 block">Username (for reference)</label>
              <input
                className="input"
                placeholder="Rantark"
                value={form.username}
                onChange={(e) => setForm({ ...form, username: e.target.value })}
              />
            </div>
            <div>
              <label className="text-xs text-gray-400 mb-1 block">Role *</label>
              <select
                className="input"
                value={form.role}
                onChange={(e) => setForm({ ...form, role: e.target.value as 'raid_leader' | 'officer' })}
              >
                <option value="raid_leader">Raid Leader</option>
                <option value="officer">Officer</option>
              </select>
            </div>
          </div>
          {error && <p className="text-red-400 text-xs">{error}</p>}
          <button type="submit" disabled={saving} className="btn-primary text-sm flex items-center gap-2">
            {saving && <Loader2 size={13} className="animate-spin" />}
            Grant Role
          </button>
        </form>
      </div>

      {/* Current roles */}
      {[
        { label: 'Officers', items: officers, color: 'text-purple-400' },
        { label: 'Raid Leaders', items: raidLeaders, color: 'text-blue-400' },
      ].map(({ label, items, color }) =>
        items.length > 0 && (
          <div key={label}>
            <h2 className={`font-bold text-base mb-3 ${color}`}>{label} ({items.length})</h2>
            <div className="glass rounded-xl divide-y divide-gray-700/50">
              {items.map((p) => (
                <div key={p.discord_id} className="flex items-center gap-3 p-3">
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-mono text-gray-300">{p.discord_id}</p>
                    <p className="text-xs text-gray-500 capitalize">{p.role.replace('_', ' ')}</p>
                  </div>
                  <button
                    onClick={() => revoke(p.discord_id)}
                    className="btn-danger text-xs py-1.5 flex items-center gap-1"
                  >
                    <Trash2 size={12} /> Revoke
                  </button>
                </div>
              ))}
            </div>
          </div>
        )
      )}

      {permissions.length === 0 && (
        <div className="glass rounded-xl p-8 text-center text-gray-500 text-sm">
          No bot roles granted yet
        </div>
      )}
    </div>
  );
}

// ── Config ────────────────────────────────────────────────────────────────────

function ConfigTab() {
  const qc = useQueryClient();
  const [saving, setSaving] = useState(false);
  const [success, setSuccess] = useState('');
  const [error, setError] = useState('');

  const { data: config, isLoading } = useQuery<GuildConfig>({
    queryKey: ['admin-config'],
    queryFn: () => api.get('/api/admin/config').then((r) => r.data),
  });

  const [form, setForm] = useState<{
    default_max_tanks: string;
    default_max_healers: string;
    default_max_dps: string;
    attendance_threshold: string;
    timezone: string;
  } | null>(null);

  // Initialize form once config loads
  if (config && form === null) {
    setForm({
      default_max_tanks: String(config.default_max_tanks),
      default_max_healers: String(config.default_max_healers),
      default_max_dps: String(config.default_max_dps),
      attendance_threshold: String(config.attendance_threshold),
      timezone: config.timezone,
    });
  }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    if (!form) return;
    setSaving(true);
    setError('');
    setSuccess('');
    try {
      await api.put('/api/admin/config', {
        default_max_tanks: parseInt(form.default_max_tanks),
        default_max_healers: parseInt(form.default_max_healers),
        default_max_dps: parseInt(form.default_max_dps),
        attendance_threshold: parseInt(form.attendance_threshold),
        timezone: form.timezone,
      });
      qc.invalidateQueries({ queryKey: ['admin-config'] });
      qc.invalidateQueries({ queryKey: ['admin-status'] });
      setSuccess('Config saved!');
      setTimeout(() => setSuccess(''), 3000);
    } catch (err: any) {
      setError(err.response?.data?.detail ?? 'Failed to save config');
    } finally {
      setSaving(false);
    }
  }

  if (isLoading) return <div className="text-gray-500 text-sm py-8 text-center">Loading config…</div>;
  if (!config || !form) return (
    <div className="glass rounded-xl p-8 text-center text-gray-500 text-sm">
      No guild config found — make sure the Discord bot has been run at least once.
    </div>
  );

  return (
    <form onSubmit={handleSave} className="glass rounded-xl p-5 space-y-4 max-w-lg">
      <h2 className="font-bold text-base flex items-center gap-2">
        <Settings size={16} /> Guild Settings
      </h2>

      <div>
        <label className="text-xs text-gray-400 mb-1 block">Timezone</label>
        <input
          className="input"
          value={form.timezone}
          onChange={(e) => setForm({ ...form, timezone: e.target.value })}
          placeholder="America/New_York"
        />
        <p className="text-xs text-gray-600 mt-1">IANA timezone name, e.g. America/Chicago, Europe/London</p>
      </div>

      <div>
        <label className="text-xs text-gray-400 mb-1 block">Attendance Threshold (%)</label>
        <input
          type="number" min="0" max="100"
          className="input"
          value={form.attendance_threshold}
          onChange={(e) => setForm({ ...form, attendance_threshold: e.target.value })}
        />
        <p className="text-xs text-gray-600 mt-1">Members below this % appear in low-attendance reports</p>
      </div>

      <div>
        <label className="text-xs text-gray-400 mb-2 block">Default Roster Slots</label>
        <div className="grid grid-cols-3 gap-3">
          <div>
            <label className="text-xs text-gray-500 mb-1 block">Tanks</label>
            <input type="number" min="0" max="40" className="input" value={form.default_max_tanks}
              onChange={(e) => setForm({ ...form, default_max_tanks: e.target.value })} />
          </div>
          <div>
            <label className="text-xs text-gray-500 mb-1 block">Healers</label>
            <input type="number" min="0" max="40" className="input" value={form.default_max_healers}
              onChange={(e) => setForm({ ...form, default_max_healers: e.target.value })} />
          </div>
          <div>
            <label className="text-xs text-gray-500 mb-1 block">DPS</label>
            <input type="number" min="0" max="40" className="input" value={form.default_max_dps}
              onChange={(e) => setForm({ ...form, default_max_dps: e.target.value })} />
          </div>
        </div>
      </div>

      {error   && <p className="text-red-400 text-xs">{error}</p>}
      {success && <p className="text-green-400 text-xs">{success}</p>}

      <button type="submit" disabled={saving} className="btn-primary text-sm flex items-center gap-2">
        {saving && <Loader2 size={13} className="animate-spin" />}
        Save Config
      </button>
    </form>
  );
}

// ── Registration Log ──────────────────────────────────────────────────────────

interface RegLogEntry {
  log_id: number;
  discord_id: number;
  username: string;
  char_name: string;
  char_class: string;
  action: string;
  source: string;
  created_at: string;
}

const ACTION_BADGE: Record<string, string> = {
  register: 'bg-green-900/40 text-green-300',
  delete:   'bg-red-900/40 text-red-300',
  update:   'bg-yellow-900/40 text-yellow-300',
};

const SOURCE_LABEL: Record<string, string> = {
  web:          'Web',
  discord:      'Discord',
  'officer-web': 'Officer (Web)',
};

function RegistrationLogTab() {
  const { data: entries = [], isLoading, error } = useQuery<RegLogEntry[]>({
    queryKey: ['char-reg-log'],
    queryFn: async () => (await api.get('/api/characters/log')).data,
  });

  if (isLoading) return <div className="text-gray-400 text-sm">Loading…</div>;
  if (error)    return <div className="text-red-400 text-sm">Failed to load registration log.</div>;

  return (
    <div className="glass rounded-2xl overflow-hidden">
      <div className="px-5 py-4 border-b border-white/10 flex items-center gap-2">
        <ClipboardList size={16} className="text-indigo-400" />
        <h2 className="font-bold">Character Registration Log</h2>
        <span className="ml-auto text-xs text-gray-500">{entries.length} entries</span>
      </div>

      {entries.length === 0 ? (
        <p className="p-5 text-sm text-gray-400">No registrations recorded yet.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-xs text-gray-400 border-b border-white/10">
                <th className="text-left px-4 py-2">Time (UTC)</th>
                <th className="text-left px-4 py-2">User</th>
                <th className="text-left px-4 py-2">Character</th>
                <th className="text-left px-4 py-2">Class</th>
                <th className="text-left px-4 py-2">Action</th>
                <th className="text-left px-4 py-2">Source</th>
              </tr>
            </thead>
            <tbody>
              {entries.map((e) => (
                <tr key={e.log_id} className="border-b border-white/5 hover:bg-white/5">
                  <td className="px-4 py-2 text-gray-400 whitespace-nowrap">
                    {new Date(e.created_at + 'Z').toLocaleString()}
                  </td>
                  <td className="px-4 py-2">
                    <span className="font-medium">{e.username || `<@${e.discord_id}>`}</span>
                  </td>
                  <td className="px-4 py-2 font-semibold">{e.char_name}</td>
                  <td className="px-4 py-2 text-gray-300">{e.char_class}</td>
                  <td className="px-4 py-2">
                    <span className={`px-2 py-0.5 rounded text-xs font-semibold ${ACTION_BADGE[e.action] ?? 'bg-gray-700 text-gray-300'}`}>
                      {e.action}
                    </span>
                  </td>
                  <td className="px-4 py-2 text-gray-400 text-xs">{SOURCE_LABEL[e.source] ?? e.source}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ── Shared ────────────────────────────────────────────────────────────────────

function StatCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="glass rounded-xl p-4">
      <p className="text-2xl font-extrabold">{value ?? '—'}</p>
      <p className="text-xs text-gray-400 mt-1">{label}</p>
    </div>
  );
}
