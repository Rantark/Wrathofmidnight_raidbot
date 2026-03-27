import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { ExternalLink, Search } from 'lucide-react';
import { api } from '@/lib/api';
import { classColor } from '@/lib/utils';
import type { Character } from '@/types';

export function RosterView() {
  const [search, setSearch] = useState('');
  const [classFilter, setClassFilter] = useState('');

  const { data: characters = [], isLoading } = useQuery<Character[]>({
    queryKey: ['admin-characters'],
    queryFn: () => api.get('/api/admin/characters').then((r) => r.data),
  });

  const filtered = characters.filter((c) => {
    const matchSearch = !search || c.char_name.toLowerCase().includes(search.toLowerCase());
    const matchClass  = !classFilter || c.char_class === classFilter;
    return matchSearch && matchClass;
  });

  // Group by class
  const grouped = filtered.reduce<Record<string, Character[]>>((acc, c) => {
    (acc[c.char_class] ??= []).push(c);
    return acc;
  }, {});

  const classes = Object.keys(grouped).sort();

  return (
    <div className="p-4 lg:p-8 max-w-6xl mx-auto space-y-6">
      <h1 className="text-2xl font-extrabold">Guild Roster</h1>

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" />
          <input
            className="input pl-9"
            placeholder="Search character name…"
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
        <div className="text-center text-gray-500 py-12">Loading roster…</div>
      ) : filtered.length === 0 ? (
        <div className="glass rounded-xl p-12 text-center text-gray-500">No characters found</div>
      ) : (
        <div className="space-y-6">
          {classes.map((cls) => (
            <div key={cls}>
              <h2 className="font-bold text-sm mb-3 px-1" style={{ color: classColor(cls) }}>
                {cls} ({grouped[cls].length})
              </h2>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                {grouped[cls].map((c) => (
                  <RosterRow key={`${c.discord_id}-${c.char_name}`} character={c} />
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      <p className="text-center text-xs text-gray-600">{characters.length} total characters</p>
    </div>
  );
}

function RosterRow({ character: c }: { character: Character }) {
  const color = classColor(c.char_class);
  return (
    <div className="glass rounded-xl p-3 flex items-center gap-3">
      {c.avatar_url ? (
        <img src={c.avatar_url} alt="" className="w-10 h-10 rounded-xl object-cover shrink-0" />
      ) : (
        <div
          className="w-10 h-10 rounded-xl flex items-center justify-center text-sm font-bold shrink-0"
          style={{ background: `${color}22`, border: `1px solid ${color}44` }}
        >
          {c.char_name[0]}
        </div>
      )}
      <div className="min-w-0 flex-1">
        <p className="text-sm font-bold truncate" style={{ color }}>{c.char_name}</p>
        <p className="text-xs text-gray-400 truncate">
          {c.main_spec}{c.off_spec ? ` / ${c.off_spec}` : ''} {c.ilvl ? `· ${c.ilvl}` : ''}
        </p>
        {c.progression && <p className="text-xs text-indigo-400 truncate">{c.progression}</p>}
      </div>
      {c.raiderio_url && (
        <a
          href={c.raiderio_url}
          target="_blank"
          rel="noopener noreferrer"
          className="text-gray-500 hover:text-blue-400 shrink-0 transition-colors"
        >
          <ExternalLink size={14} />
        </a>
      )}
    </div>
  );
}
