import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Plus } from 'lucide-react';
import { api } from '@/lib/api';
import { CharacterCard } from '@/components/Characters/CharacterCard';
import { CharacterForm } from '@/components/Characters/CharacterForm';
import type { Character } from '@/types';

export function CharactersPage() {
  const [showForm, setShowForm] = useState(false);
  const qc = useQueryClient();

  const { data: characters = [], isLoading } = useQuery<Character[]>({
    queryKey: ['characters'],
    queryFn: () => api.get('/api/characters').then((r) => r.data),
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
    <div className="p-4 lg:p-8 max-w-3xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-extrabold">My Characters</h1>
        <button onClick={() => setShowForm(!showForm)} className="btn-primary flex items-center gap-2 text-sm">
          <Plus size={16} /> Add Character
        </button>
      </div>

      {showForm && (
        <CharacterForm
          onSuccess={() => {
            setShowForm(false);
            qc.invalidateQueries({ queryKey: ['characters'] });
          }}
          onCancel={() => setShowForm(false)}
        />
      )}

      {isLoading ? (
        <div className="text-center text-gray-500 py-12">Loading…</div>
      ) : characters.length === 0 ? (
        <div className="glass rounded-xl p-12 text-center">
          <p className="text-gray-400 mb-4">No characters yet</p>
          <button onClick={() => setShowForm(true)} className="btn-primary text-sm">
            Add your first character
          </button>
        </div>
      ) : (
        <div className="grid lg:grid-cols-2 gap-4">
          {characters.map((c) => (
            <CharacterCard
              key={c.char_name}
              character={c}
              onSetMain={() => handleSetMain(c.char_name)}
              onDelete={() => handleDelete(c.char_name)}
            />
          ))}
        </div>
      )}
    </div>
  );
}
