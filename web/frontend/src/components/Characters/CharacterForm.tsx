import { useState } from 'react';
import { Loader2, X } from 'lucide-react';
import { api } from '@/lib/api';

const WOW_CLASSES = [
  'Death Knight','Demon Hunter','Druid','Evoker','Hunter',
  'Mage','Monk','Paladin','Priest','Rogue','Shaman','Warlock','Warrior',
];

interface Props {
  onSuccess: () => void;
  onCancel: () => void;
}

export function CharacterForm({ onSuccess, onCancel }: Props) {
  const [form, setForm] = useState({
    char_name: '',
    char_class: '',
    main_spec: '',
    off_spec: '',
    ilvl: '',
    realm: '',
    region: 'us',
    progression: '',
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError('');
    try {
      await api.post('/api/characters', {
        ...form,
        ilvl: form.ilvl ? parseInt(form.ilvl) : undefined,
        off_spec: form.off_spec || undefined,
        realm: form.realm || undefined,
        progression: form.progression || undefined,
      });
      onSuccess();
    } catch (err: any) {
      setError(err.response?.data?.detail ?? 'Failed to create character');
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="glass rounded-2xl p-5 animate-fade-in">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-bold">Add Character</h3>
        <button onClick={onCancel} className="text-gray-400 hover:text-white">
          <X size={18} />
        </button>
      </div>

      <form onSubmit={handleSubmit} className="space-y-3">
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-xs text-gray-400 mb-1 block">Name *</label>
            <input
              className="input"
              placeholder="Arthax"
              value={form.char_name}
              onChange={(e) => setForm({ ...form, char_name: e.target.value })}
              required
            />
          </div>
          <div>
            <label className="text-xs text-gray-400 mb-1 block">Realm</label>
            <input
              className="input"
              placeholder="stormrage"
              value={form.realm}
              onChange={(e) => setForm({ ...form, realm: e.target.value })}
            />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-xs text-gray-400 mb-1 block">Class *</label>
            <select
              className="input"
              value={form.char_class}
              onChange={(e) => setForm({ ...form, char_class: e.target.value })}
              required
            >
              <option value="">Select class</option>
              {WOW_CLASSES.map((c) => <option key={c}>{c}</option>)}
            </select>
          </div>
          <div>
            <label className="text-xs text-gray-400 mb-1 block">Region</label>
            <select
              className="input"
              value={form.region}
              onChange={(e) => setForm({ ...form, region: e.target.value })}
            >
              <option value="us">US</option>
              <option value="eu">EU</option>
              <option value="kr">KR</option>
              <option value="tw">TW</option>
            </select>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-xs text-gray-400 mb-1 block">Main Spec *</label>
            <input
              className="input"
              placeholder="Protection"
              value={form.main_spec}
              onChange={(e) => setForm({ ...form, main_spec: e.target.value })}
              required
            />
          </div>
          <div>
            <label className="text-xs text-gray-400 mb-1 block">Off Spec</label>
            <input
              className="input"
              placeholder="Arms"
              value={form.off_spec}
              onChange={(e) => setForm({ ...form, off_spec: e.target.value })}
            />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-xs text-gray-400 mb-1 block">Item Level</label>
            <input
              className="input"
              type="number"
              min="1"
              max="700"
              placeholder="480"
              value={form.ilvl}
              onChange={(e) => setForm({ ...form, ilvl: e.target.value })}
            />
          </div>
          <div>
            <label className="text-xs text-gray-400 mb-1 block">Progression</label>
            <input
              className="input"
              placeholder="8/8 M"
              value={form.progression}
              onChange={(e) => setForm({ ...form, progression: e.target.value })}
            />
          </div>
        </div>

        {error && <p className="text-red-400 text-xs">{error}</p>}

        <div className="flex gap-2 pt-1">
          <button type="submit" disabled={saving} className="btn-primary flex-1 flex items-center justify-center gap-2">
            {saving && <Loader2 size={14} className="animate-spin" />}
            {saving ? 'Saving…' : 'Add Character'}
          </button>
          <button type="button" onClick={onCancel} className="btn-secondary">
            Cancel
          </button>
        </div>
      </form>
    </div>
  );
}
