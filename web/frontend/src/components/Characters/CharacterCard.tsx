import { Star, ExternalLink, Trash2 } from 'lucide-react';
import { Character } from '@/types';
import { classColor } from '@/lib/utils';

interface Props {
  character: Character;
  onSetMain?: () => void;
  onDelete?: () => void;
}

export function CharacterCard({ character, onSetMain, onDelete }: Props) {
  const color = classColor(character.char_class);

  return (
    <div className="glass rounded-xl p-4 animate-fade-in">
      <div className="flex items-start gap-3">
        {/* Avatar */}
        {character.avatar_url ? (
          <img
            src={character.avatar_url}
            alt={character.char_name}
            className="w-12 h-12 rounded-xl object-cover border-2"
            style={{ borderColor: `${color}66` }}
          />
        ) : (
          <div
            className="w-12 h-12 rounded-xl flex items-center justify-center text-xl font-bold border-2"
            style={{ borderColor: `${color}66`, background: `${color}22` }}
          >
            {character.char_name[0]}
          </div>
        )}

        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <h3 className="font-bold text-sm" style={{ color }}>
              {character.char_name}
            </h3>
            {character.is_main === 1 && (
              <span className="badge bg-yellow-500/20 text-yellow-400 border border-yellow-500/30 text-xs">
                <Star size={10} fill="currentColor" /> Main
              </span>
            )}
          </div>
          <p className="text-xs text-gray-400 mt-0.5">
            {character.char_class} · {character.main_spec}
            {character.off_spec && ` / ${character.off_spec}`}
          </p>
          {character.ilvl && (
            <p className="text-xs text-gray-500 mt-0.5">
              {character.ilvl} ilvl
              {character.realm && ` · ${character.realm}`}
            </p>
          )}
          {character.progression && (
            <p className="text-xs text-indigo-400 mt-1">{character.progression}</p>
          )}
        </div>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-2 mt-3 pt-3 border-t border-gray-700/50">
        {character.raiderio_url && (
          <a
            href={character.raiderio_url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1.5 text-xs text-blue-400 hover:text-blue-300 transition-colors"
          >
            <ExternalLink size={12} /> Raider.IO
          </a>
        )}
        <div className="ml-auto flex items-center gap-2">
          {onSetMain && character.is_main !== 1 && (
            <button onClick={onSetMain} className="btn-secondary text-xs py-1.5 px-3">
              Set Main
            </button>
          )}
          {onDelete && (
            <button onClick={onDelete} className="btn-danger text-xs py-1.5 px-3">
              <Trash2 size={12} />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
