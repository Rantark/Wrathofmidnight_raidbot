import changelogData from '@/changelog.json';
import { Tag, Sparkles, Wrench, Trash2, TrendingUp } from 'lucide-react';

interface ChangeEntry {
  type: 'new' | 'improved' | 'fix' | 'removed';
  text: string;
}

interface VersionEntry {
  version: string;
  date: string;
  title: string;
  changes: ChangeEntry[];
}

interface Changelog {
  current: string;
  entries: VersionEntry[];
}

const TYPE_META = {
  new:      { label: 'New',      icon: Sparkles,   bg: 'bg-indigo-500/20', text: 'text-indigo-300', border: 'border-indigo-500/30' },
  improved: { label: 'Improved', icon: TrendingUp, bg: 'bg-blue-500/20',   text: 'text-blue-300',   border: 'border-blue-500/30'   },
  fix:      { label: 'Fix',      icon: Wrench,     bg: 'bg-green-500/20',  text: 'text-green-300',  border: 'border-green-500/30'  },
  removed:  { label: 'Removed',  icon: Trash2,     bg: 'bg-red-500/20',    text: 'text-red-300',    border: 'border-red-500/30'    },
} as const;

const data = changelogData as Changelog;

export function ChangelogPage() {
  return (
    <div className="p-4 lg:p-8 max-w-3xl mx-auto space-y-6">
      <div className="flex items-center gap-3">
        <Tag size={22} className="text-indigo-400" />
        <div>
          <h1 className="text-2xl font-extrabold">Changelog</h1>
          {data.current && (
            <p className="text-sm text-gray-400">
              Current version:{' '}
              <span className="text-indigo-300 font-mono font-semibold">v{data.current}</span>
            </p>
          )}
        </div>
      </div>

      {data.entries.map((entry, i) => (
        <div key={entry.version} className="glass rounded-2xl overflow-hidden">
          {/* Version header */}
          <div className="flex flex-wrap items-center gap-3 px-5 py-4 border-b border-gray-700/50">
            <span className={`px-2.5 py-0.5 rounded-full text-xs font-bold font-mono border ${
              i === 0
                ? 'bg-indigo-600/30 text-indigo-200 border-indigo-500/50'
                : 'bg-gray-700/50 text-gray-300 border-gray-600/50'
            }`}>
              v{entry.version}
            </span>
            <span className="font-semibold text-white">{entry.title}</span>
            <span className="ml-auto text-xs text-gray-500">{entry.date}</span>
          </div>

          {/* Change list */}
          <ul className="divide-y divide-gray-700/30">
            {entry.changes.map((c, j) => {
              const meta = TYPE_META[c.type] ?? TYPE_META.improved;
              const Icon = meta.icon;
              return (
                <li key={j} className="flex items-start gap-3 px-5 py-3">
                  <span className={`flex items-center gap-1.5 shrink-0 mt-0.5 px-2 py-0.5 rounded-md text-xs font-semibold border ${meta.bg} ${meta.text} ${meta.border}`}>
                    <Icon size={11} />
                    {meta.label}
                  </span>
                  <span className="text-sm text-gray-300 leading-snug">{c.text}</span>
                </li>
              );
            })}
          </ul>
        </div>
      ))}
    </div>
  );
}
