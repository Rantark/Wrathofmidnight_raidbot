import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Plus, Pencil, Trash2, Search, UserPlus, RefreshCw } from 'lucide-react';
import { api } from '@/lib/api';
import { CharacterCard } from '@/components/Characters/CharacterCard';
import { CharacterForm } from '@/components/Characters/CharacterForm';
import { Modal } from '@/components/common/Modal';
import { classColor } from '@/lib/utils';
import { useAuth } from '@/contexts/AuthContext';
import type { Character } from '@/types';

type Tab = 'mine' | 'roster';

export function CharactersPage() {
  const { isOfficer, isRaidLeader } = useAuth();
  const canViewRoster = isOfficer || isRaidLeader;
  const qc = useQueryClient();
  const [tab, setTab] = useState<Tab>('mine');
  const [showForm, setShowForm] = useState(false);
  const [editingChar, setEditingChar] = useState<Character | null>(null);

  // My characters
  const { data: myChars = [], isLoading: myLoading } = useQuery<Character[]>({
    queryKey: ['characters'],
    queryFn: () => api.get('/api/characters').then((r) => r.data),
  });

  // Guild roster (officers + raid leaders)
  const { data: rosterChars = [], isLoading: rosterLoading, isError: rosterError, error: rosterErrorObj } = useQuery<Character[]>({
    queryKey: ['characters-roster'],
    queryFn: () => api.get('/api/characters/roster').then((r) => r.data),
    enabled: canViewRoster,
    retry: 1,
  });

  async function handleSetMain(charName: string) {
    await api.post(`/api/characters/${encodeURIComponent(charName)}/main`);
    qc.invalidateQueries({ queryKey: ['characters'] });
  }

  async function handleDelete(charName: string) {
    if (!confirm(`Delete ${charName}? This cannot be undone.`)) return;
    await api.delete(`/api/characters/${encodeURIComponent(charName)}`);
    qc.invalidateQueries({ queryKey: ['characters'] });
  }

  return (
    <div className="p-4 lg:p-8 max-w-4xl mx-auto space-y-6">
      {/* Header + tabs */}
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-extrabold flex-1">Characters</h1>
        {tab === 'mine' && (
          <button
            onClick={() => setShowForm(!showForm)}
            className="btn-primary flex items-center gap-2 text-sm"
          >
            <Plus size={16} /> Add Character
          </button>
        )}
      </div>

      {/* Tab switcher (show only for officers/raid leaders) */}
      {canViewRoster && (
        <div className="flex gap-1 p-1 glass rounded-xl w-fit">
          {(['mine', 'roster'] as Tab[]).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`px-4 py-2 rounded-lg text-sm font-semibold transition-all ${
                tab === t ? 'bg-indigo-600 text-white' : 'text-gray-400 hover:text-white'
              }`}
            >
              {t === 'mine' ? 'My Characters' : 'Guild Roster'}
            </button>
          ))}
        </div>
      )}

      {/* Add form */}
      {tab === 'mine' && showForm && (
        <CharacterForm
          onSuccess={() => {
            setShowForm(false);
            qc.invalidateQueries({ queryKey: ['characters'] });
          }}
          onCancel={() => setShowForm(false)}
        />
      )}

      {/* My Characters tab */}
      {tab === 'mine' && (
        myLoading ? (
          <div className="text-center text-gray-500 py-12">Loading…</div>
        ) : myChars.length === 0 ? (
          <div className="glass rounded-xl p-12 text-center">
            <p className="text-gray-400 mb-4">No characters yet</p>
            <button onClick={() => setShowForm(true)} className="btn-primary text-sm">
              Add your first character
            </button>
          </div>
        ) : (
          <div className="grid lg:grid-cols-2 gap-4">
            {myChars.map((c) => (
              <div key={c.char_name} className="relative group">
                <CharacterCard
                  character={c}
                  onSetMain={() => handleSetMain(c.char_name)}
                  onDelete={() => handleDelete(c.char_name)}
                />
                <button
                  onClick={() => setEditingChar(c)}
                  className="absolute top-3 right-3 w-7 h-7 flex items-center justify-center rounded-lg
                             text-gray-500 hover:text-white hover:bg-white/10 transition-all
                             opacity-0 group-hover:opacity-100"
                  title="Edit character"
                >
                  <Pencil size={13} />
                </button>
              </div>
            ))}
          </div>
        )
      )}

      {/* Guild Roster tab */}
      {tab === 'roster' && canViewRoster && (
        rosterError ? (
          <div className="glass rounded-xl p-6 text-center space-y-2">
            <p className="text-red-400 font-semibold">Failed to load roster</p>
            <p className="text-gray-400 text-sm">
              {(rosterErrorObj as any)?.response?.data?.detail
                ?? (rosterErrorObj as any)?.message
                ?? 'Unknown error — check the browser console for details'}
            </p>
            <button
              onClick={() => qc.invalidateQueries({ queryKey: ['characters-roster'] })}
              className="btn-secondary text-sm mt-2"
            >
              Retry
            </button>
          </div>
        ) : (
          <RosterTab
            characters={rosterChars}
            isLoading={rosterLoading}
            onEdit={(c) => setEditingChar(c)}
            onDeleted={() => qc.invalidateQueries({ queryKey: ['characters-roster'] })}
          />
        )
      )}

      {/* Edit modal */}
      {editingChar && (
        <Modal
          title={`Edit ${editingChar.char_name}`}
          onClose={() => setEditingChar(null)}
        >
          <EditCharacterForm
            character={editingChar}
            officerMode={tab === 'roster'}
            onSuccess={() => {
              setEditingChar(null);
              if (tab === 'roster') {
                qc.invalidateQueries({ queryKey: ['characters-roster'] });
              } else {
                qc.invalidateQueries({ queryKey: ['characters'] });
              }
            }}
            onCancel={() => setEditingChar(null)}
          />
        </Modal>
      )}
    </div>
  );
}

// ── Edit form ─────────────────────────────────────────────────────────────────

function EditCharacterForm({
  character,
  onSuccess,
  onCancel,
  officerMode = false,
}: {
  character: Character;
  onSuccess: () => void;
  onCancel: () => void;
  officerMode?: boolean;
}) {
  const [form, setForm] = useState({
    main_spec: character.main_spec ?? '',
    off_spec: character.off_spec ?? '',
    ilvl: character.ilvl ? String(character.ilvl) : '',
    professions: character.professions ?? '',
    progression: character.progression ?? '',
    raiderio_url: character.raiderio_url ?? '',
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError('');
    try {
      const body = {
        main_spec: form.main_spec || undefined,
        off_spec: form.off_spec || undefined,
        ilvl: form.ilvl ? parseInt(form.ilvl) : undefined,
        professions: form.professions || undefined,
        progression: form.progression || undefined,
        raiderio_url: form.raiderio_url || undefined,
      };
      if (officerMode) {
        await api.patch(
          `/api/characters/officer/${character.discord_id}/${encodeURIComponent(character.char_name)}`,
          body,
        );
      } else {
        await api.patch(`/api/characters/${encodeURIComponent(character.char_name)}`, body);
      }
      onSuccess();
    } catch (err: any) {
      setError(err.response?.data?.detail ?? 'Update failed');
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="text-xs text-gray-400 mb-1 block">Main Spec</label>
          <input className="input" value={form.main_spec} onChange={(e) => setForm({ ...form, main_spec: e.target.value })} />
        </div>
        <div>
          <label className="text-xs text-gray-400 mb-1 block">Off Spec</label>
          <input className="input" value={form.off_spec} onChange={(e) => setForm({ ...form, off_spec: e.target.value })} placeholder="Optional" />
        </div>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="text-xs text-gray-400 mb-1 block">Item Level</label>
          <input type="number" min="1" max="700" className="input" value={form.ilvl} onChange={(e) => setForm({ ...form, ilvl: e.target.value })} />
        </div>
        <div>
          <label className="text-xs text-gray-400 mb-1 block">Progression</label>
          <input className="input" value={form.progression} onChange={(e) => setForm({ ...form, progression: e.target.value })} placeholder="8/8 M" />
        </div>
      </div>
      <div>
        <label className="text-xs text-gray-400 mb-1 block">Professions</label>
        <input className="input" value={form.professions} onChange={(e) => setForm({ ...form, professions: e.target.value })} placeholder="Blacksmithing, Mining" />
      </div>
      <div>
        <label className="text-xs text-gray-400 mb-1 block">Raider.IO URL</label>
        <input className="input" value={form.raiderio_url} onChange={(e) => setForm({ ...form, raiderio_url: e.target.value })} placeholder="https://raider.io/characters/…" />
      </div>

      {error && <p className="text-red-400 text-xs">{error}</p>}

      <div className="flex gap-2 pt-1">
        <button type="submit" disabled={saving} className="btn-primary flex-1 flex items-center justify-center gap-2">
          {saving && <span className="w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin" />}
          Save Changes
        </button>
        <button type="button" onClick={onCancel} className="btn-secondary">Cancel</button>
      </div>
    </form>
  );
}

// ── Guild Roster tab ──────────────────────────────────────────────────────────

function RosterTab({
  characters,
  isLoading,
  onEdit,
  onDeleted,
}: {
  characters: Character[];
  isLoading: boolean;
  onEdit: (c: Character) => void;
  onDeleted: () => void;
}) {
  const [search, setSearch] = useState('');
  const [classFilter, setClassFilter] = useState('');
  const [showAddForm, setShowAddForm] = useState(false);
  const [addDiscordId, setAddDiscordId] = useState('');
  const [syncing, setSyncing] = useState<string | null>(null); // key = `${discord_id}-${char_name}`
  const [syncingAll, setSyncingAll] = useState(false);
  const [syncAllResult, setSyncAllResult] = useState<{ synced: string[]; skipped: { char_name: string; reason: string }[] } | null>(null);

  async function handleOfficerDelete(c: Character) {
    if (!confirm(`Delete ${c.char_name}? This cannot be undone.`)) return;
    try {
      await api.delete(`/api/characters/officer/${c.discord_id}/${encodeURIComponent(c.char_name)}`);
      onDeleted();
    } catch (err: any) {
      alert(err.response?.data?.detail ?? 'Delete failed');
    }
  }

  async function handleSyncRio(c: Character) {
    const key = `${c.discord_id}-${c.char_name}`;
    setSyncing(key);
    try {
      const res = await api.post(`/api/characters/sync-rio/${c.discord_id}/${encodeURIComponent(c.char_name)}`);
      const u = res.data.updates ?? {};
      const parts = [];
      if (u.ilvl)       parts.push(`ilvl → ${u.ilvl}`);
      if (u.main_spec)  parts.push(`spec → ${u.main_spec}`);
      if (u.avatar_url) parts.push('portrait updated');
      alert(parts.length ? `Synced ${c.char_name}: ${parts.join(', ')}` : `${c.char_name} is already up to date`);
      onDeleted(); // reuse to invalidate/refresh roster
    } catch (err: any) {
      alert(err.response?.data?.detail ?? 'Sync failed');
    } finally {
      setSyncing(null);
    }
  }

  async function handleSyncAll() {
    setSyncingAll(true);
    setSyncAllResult(null);
    try {
      const res = await api.post('/api/characters/sync-rio-all');
      setSyncAllResult({ synced: res.data.synced ?? [], skipped: res.data.skipped ?? [] });
      onDeleted(); // refresh roster
    } catch (err: any) {
      alert(err.response?.data?.detail ?? 'Sync All failed');
    } finally {
      setSyncingAll(false);
    }
  }

  const filtered = characters.filter((c) => {
    const matchSearch = !search || c.char_name.toLowerCase().includes(search.toLowerCase());
    const matchClass  = !classFilter || c.char_class === classFilter;
    return matchSearch && matchClass;
  });

  const grouped = filtered.reduce<Record<string, Character[]>>((acc, c) => {
    (acc[c.char_class] ??= []).push(c);
    return acc;
  }, {});
  const classes = Object.keys(grouped).sort();

  return (
    <div className="space-y-5">
      {/* Toolbar: Add + Sync All */}
      <div className="flex flex-wrap gap-2">
        <button
          onClick={() => setShowAddForm(!showAddForm)}
          className="btn-secondary flex items-center gap-2 text-sm"
        >
          <UserPlus size={14} /> Add Character for Member
        </button>
        <button
          onClick={handleSyncAll}
          disabled={syncingAll}
          className="btn-secondary flex items-center gap-2 text-sm disabled:opacity-50"
        >
          <RefreshCw size={14} className={syncingAll ? 'animate-spin' : ''} />
          {syncingAll ? 'Syncing…' : 'Sync All with Raider.IO'}
        </button>
      </div>

      {/* Sync All results */}
      {syncAllResult && (
        <div className="glass rounded-xl p-4 text-sm space-y-2">
          <p className="font-semibold text-green-400">
            Sync complete — {syncAllResult.synced.length} synced, {syncAllResult.skipped.length} skipped
          </p>
          {syncAllResult.skipped.length > 0 && (
            <details className="text-xs text-gray-400">
              <summary className="cursor-pointer hover:text-white">Show skipped ({syncAllResult.skipped.length})</summary>
              <ul className="mt-2 space-y-1 pl-3">
                {syncAllResult.skipped.map((s) => (
                  <li key={s.char_name}><span className="text-gray-200">{s.char_name}</span> — {s.reason}</li>
                ))}
              </ul>
            </details>
          )}
        </div>
      )}

      {/* Add character for member (form) */}
      <div>
        {showAddForm && (
          <div className="mt-3 glass rounded-xl p-4 space-y-3">
            <p className="text-xs text-gray-400">Enter the member's Discord ID, then fill out their character details.</p>
            <div>
              <label className="text-xs text-gray-400 mb-1 block">Discord ID *</label>
              <input
                className="input"
                placeholder="e.g. 123456789012345678"
                value={addDiscordId}
                onChange={(e) => setAddDiscordId(e.target.value)}
              />
            </div>
            {addDiscordId && /^\d{17,20}$/.test(addDiscordId) && (
              <CharacterForm
                officerTargetDiscordId={parseInt(addDiscordId)}
                onSuccess={() => { setShowAddForm(false); setAddDiscordId(''); onDeleted(); }}
                onCancel={() => { setShowAddForm(false); setAddDiscordId(''); }}
              />
            )}
          </div>
        )}
      </div>

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" />
          <input
            className="input pl-9"
            placeholder="Search character…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <select
          className="input sm:max-w-[180px]"
          value={classFilter}
          onChange={(e) => setClassFilter(e.target.value)}
        >
          <option value="">All Classes</option>
          {[...new Set(characters.map((c) => c.char_class))].sort().map((cl) => (
            <option key={cl}>{cl}</option>
          ))}
        </select>
      </div>

      {isLoading ? (
        <div className="text-center text-gray-500 py-8">Loading roster…</div>
      ) : filtered.length === 0 ? (
        <div className="glass rounded-xl p-8 text-center text-gray-500">No characters found</div>
      ) : (
        <div className="space-y-5">
          {classes.map((cls) => {
            const color = classColor(cls);
            return (
              <div key={cls}>
                <h3 className="text-xs font-bold uppercase tracking-wider mb-2 px-1" style={{ color }}>
                  {cls} ({grouped[cls].length})
                </h3>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
                  {grouped[cls].map((c) => (
                    <div key={`${c.discord_id}-${c.char_name}`} className="relative group glass rounded-xl p-3 flex items-center gap-3">
                      {c.avatar_url ? (
                        <img src={c.avatar_url} alt="" className="w-9 h-9 rounded-lg object-cover shrink-0" />
                      ) : (
                        <div
                          className="w-9 h-9 rounded-lg flex items-center justify-center text-xs font-bold shrink-0"
                          style={{ background: `${color}22`, border: `1px solid ${color}44` }}
                        >
                          {c.char_name[0]}
                        </div>
                      )}
                      <div className="min-w-0 flex-1">
                        <p className="text-sm font-bold truncate" style={{ color }}>{c.char_name}</p>
                        <p className="text-xs text-gray-400 truncate">
                          {c.main_spec}{c.off_spec ? ` / ${c.off_spec}` : ''}{c.ilvl ? ` · ${c.ilvl}` : ''}
                        </p>
                        {c.progression && <p className="text-xs text-indigo-400 truncate">{c.progression}</p>}
                        <p className="text-xs text-gray-600 truncate font-mono">{c.discord_id}</p>
                      </div>
                      {/* Officer action buttons on hover */}
                      <div className="absolute top-2 right-2 flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                        <button
                          onClick={() => handleSyncRio(c)}
                          disabled={syncing === `${c.discord_id}-${c.char_name}`}
                          className="w-6 h-6 flex items-center justify-center rounded bg-white/10 hover:bg-green-700 transition-colors disabled:opacity-50"
                          title="Sync with Raider.IO"
                        >
                          <RefreshCw size={11} className={syncing === `${c.discord_id}-${c.char_name}` ? 'animate-spin' : ''} />
                        </button>
                        <button
                          onClick={() => onEdit(c)}
                          className="w-6 h-6 flex items-center justify-center rounded bg-white/10 hover:bg-indigo-600 transition-colors"
                          title="Edit character"
                        >
                          <Pencil size={11} />
                        </button>
                        <button
                          onClick={() => handleOfficerDelete(c)}
                          className="w-6 h-6 flex items-center justify-center rounded bg-white/10 hover:bg-red-600 transition-colors"
                          title="Delete character"
                        >
                          <Trash2 size={11} />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      )}
      <p className="text-center text-xs text-gray-600">{characters.length} total characters</p>
    </div>
  );
}
